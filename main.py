import sys
import os

# ============================================================
# FIX: Dynamic base path untuk EXE maupun development
# ============================================================
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
os.chdir(BASE_PATH)  # Pastikan working directory benar
# ============================================================

import json
import threading
import yt_dlp
import time
import re
import subprocess
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Warning: Google API Client not installed. Search functionality will be limited.")
    build = None
    HttpError = Exception

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStyleFactory, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QFileDialog, QMessageBox, QFrame, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QDialog, QScrollArea, QTreeWidget, QTreeWidgetItem, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPalette, QColor, QImage
import requests
from PIL import Image
from io import BytesIO
from src.batch_downloader import BatchDownloadWidget
from src.downloader_tab import DownloaderTab
from src.history_tab import HistoryWidget
from src.settings_tab import SettingsTab
from src.search_tab import SearchTab
from src.telegram_bot_tab import TelegramBotTab
from src.license_manager import LicenseManager
from src.license_dialog import LicenseDialog

class ExportThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, history_data, file_path):
        super().__init__()
        self.history_data = history_data
        self.file_path = file_path

    def run(self):
        try:
            import csv
            columns = ['Title', 'Channel', 'Download Date', 'Format', 'Duration',
                      'Views', 'Output Directory', 'Status']
            with open(self.file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for item in self.history_data:
                    writer.writerow([
                        item.get('title', ''),
                        item.get('channel', ''),
                        item.get('date', ''),
                        item.get('format', ''),
                        item.get('duration', ''),
                        item.get('views', ''),
                        item.get('output_dir', ''),
                        item.get('status', 'Completed')
                    ])
            self.finished_signal.emit(True, "History exported successfully!")
        except Exception as e:
            self.finished_signal.emit(False, f"Failed to export history: {str(e)}")

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Modern Multi-Platform Video Downloader")
        self.setFixedSize(600, 400)

        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)

        title_label = QLabel("Modern Multi-Platform Video Downloader")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3; margin: 10px;")

        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 16px; color: #666;")

        dev_label = QLabel("Developed by Adam Official Dev")
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_label.setStyleSheet("font-size: 16px; margin: 10px;")

        desc_text = """
        Modern Video Downloader is a powerful and user-friendly application designed to download videos from YouTube and other platforms. Built with Python and PyQt6, it offers a modern and intuitive interface for all your video downloading needs.

        Key Features:
        • Beautiful and intuitive graphical user interface
        • Support for multiple video quality options
        • Batch download capability
        • Download history tracking
        • Video search functionality
        • Dark/Light mode support
        • Progress tracking with detailed status updates
        • FFmpeg integration for optimal video processing

        Technologies Used:
        • Python 3.8+
        • PyQt6 for the graphical interface
        • yt-dlp for video downloading
        • FFmpeg for video processing

        This software is open source and available on GitHub. Feel free to contribute or report issues!
        """

        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 14px; line-height: 1.5; margin: 20px;")

        # License status
        mgr = LicenseManager(BASE_PATH)
        license_status = mgr.get_status_text()
        license_label = QLabel(f"🔑 License: {license_status}")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("font-size: 13px; color: #4a9eff; margin: 5px; padding: 6px 12px; background: #1a2a3a; border-radius: 6px;")
        content_layout.addWidget(license_label)

        links_label = QLabel("""
        <a href="https://github.com/AdamOfficialDev/modern_youtube_downloader">GitHub Repository</a> |
        <a href="https://github.com/AdamOfficialDev">Developer Profile</a>
        """)
        links_label.setOpenExternalLinks(True)
        links_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links_label.setStyleSheet("margin: 20px;")

        content_layout.addWidget(title_label)
        content_layout.addWidget(version_label)
        content_layout.addWidget(dev_label)
        content_layout.addWidget(desc_label)
        content_layout.addWidget(links_label)
        content_layout.addStretch()

        layout.addWidget(scroll)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)

        layout.addWidget(close_button)
        self.setLayout(layout)

class LicenseWatcher(QThread):
    """
    Background thread — cek status lisensi ke server tiap 1 menit.
    Emit sinyal jika lisensi dicabut/expired ATAU dipulihkan kembali oleh admin.
    """
    license_invalid  = pyqtSignal(str, str)  # (reason: 'revoked'|'expired'|other, pesan)
    license_restored = pyqtSignal(str)        # plan_info

    def __init__(self, manager: LicenseManager, interval_seconds: int = 60):
        super().__init__()
        self._mgr            = manager
        self._interval       = interval_seconds
        self._running        = True
        self._was_locked     = False

    def stop(self):
        self._running = False

    def run(self):
        import time as _t

        try:
            cache = self._mgr.get_license_info()
            if cache and (cache.get("revoked") or cache.get("expired")):
                self._was_locked = True
        except Exception:
            pass

        # Tunggu 1 interval penuh — startup sudah cek di is_activated()
        for _ in range(self._interval):
            if not self._running:
                return
            _t.sleep(1)

        while self._running:
            try:
                is_valid = self._mgr.is_activated()

                if not is_valid and not self._was_locked:
                    self._was_locked = True
                    cache  = self._mgr.get_license_info() or {}
                    reason = cache.get("invalid_reason", "revoked")
                    if reason == "expired":
                        msg = "Lisensi kamu sudah kadaluarsa."
                    else:
                        msg = "Lisensi kamu telah dinonaktifkan oleh administrator."
                    self.license_invalid.emit(reason, msg)

                elif is_valid and self._was_locked:
                    self._was_locked = False
                    cache     = self._mgr.get_license_info() or {}
                    plan_info = f"{cache.get('plan', 'Unknown')} ({cache.get('label', '')})"
                    self.license_restored.emit(plan_info)

            except Exception as e:
                print(f"[LicenseWatcher] Error: {e}")

            for _ in range(self._interval):
                if not self._running:
                    return
                _t.sleep(1)



class ModernVideoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Adam | Modern Multi-Platform Video Downloader")
        self.setMinimumSize(1000, 700)

        self.config = self.load_config()
        self.setup_ffmpeg()

        self.download_history = self.load_history()
        self.is_downloading = False
        self.is_paused = False
        self.formats_list = []
        self.download_thread = None
        self.is_dark_mode = True

        self.youtube = None
        self.current_api_key = None
        self.api_key_valid = False
        self.api_status_label = None
        self._license_locked = False   # True saat lisensi dicabut

        self.setup_ui()

        # ── License Watcher — cek tiap 1 menit ────────────────────────────────
        self._license_mgr     = LicenseManager(BASE_PATH)
        self._license_watcher = LicenseWatcher(self._license_mgr, interval_seconds=60)
        self._license_watcher.license_invalid.connect(self._on_license_invalid)
        self._license_watcher.license_restored.connect(self._on_license_restored)
        self._license_watcher.start()
        # ───────────────────────────────────────────────────────────────────────

        help_menu = self.menuBar().addMenu("Help")
        self.about_action = help_menu.addAction("About")
        self.about_action.triggered.connect(self.show_about_dialog)
        help_menu.addSeparator()
        self.license_action = help_menu.addAction("🔑 Activate / License")
        self.license_action.triggered.connect(self.show_license_dialog)

        self.youtube = self.setup_youtube_api(show_error=False)
        if self.youtube:
            self.update_tab_states(True)
            self.tabs.setCurrentIndex(0)
        else:
            self.update_tab_states(False)
            self.tabs.setCurrentIndex(5)
            QTimer.singleShot(100, lambda: self._ensure_settings_tab_active())

        self.settings_widget.apply_style()

    def _ensure_settings_tab_active(self):
        try:
            current_index = self.tabs.currentIndex()
            current_tab_name = self.tabs.tabText(current_index)
            if current_tab_name != "Settings":
                self.tabs.setCurrentIndex(5)
                self.tabs.setCurrentWidget(self.settings_tab)
        except Exception as e:
            print(f"Error ensuring Settings tab active: {e}")

    def changeEvent(self, event):
        if event.type() == event.Type.PaletteChange:
            is_now_dark = self.palette().color(QPalette.ColorRole.Window).lightness() <= 128
            if is_now_dark != self.is_dark_mode:
                self.is_dark_mode = is_now_dark
                self.update_all_video_widgets()
        super().changeEvent(event)

    def update_all_video_widgets(self):
        for widget in self.search_tab_instance.video_widgets:
            if widget and not widget.isHidden():
                self.update_video_widget_style(widget)
                widget.update()

    def update_video_widget_style(self, frame):
        is_light_mode = not self.is_dark_mode
        if is_light_mode:
            style = """
                QFrame {
                    background-color: #f0f0f0;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 5px;
                    border: 1px solid #ddd;
                }
            """
            title_style = "QLabel { color: #000000; font-weight: bold; }"
            channel_style = "QLabel { color: #666666; }"
        else:
            style = """
                QFrame {
                    background-color: #2d2d2d;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 5px;
                    border: 1px solid #404040;
                }
            """
            title_style = "QLabel { color: white; font-weight: bold; }"
            channel_style = "QLabel { color: #aaa; }"

        frame.setStyleSheet(style)
        for child in frame.findChildren(QLabel):
            if child.property("type") == "title":
                child.setStyleSheet(title_style)
            elif child.property("type") == "channel":
                child.setStyleSheet(channel_style)
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        frame.update()

    def setup_downloader_tab(self):
        self.downloader_tab_instance = DownloaderTab(self)

    def setup_search_tab(self):
        self.search_tab_instance = SearchTab(self)
        layout = QVBoxLayout(self.search_tab)
        layout.addWidget(self.search_tab_instance)

    def setup_history_tab(self):
        self.history_widget = HistoryWidget(self)
        layout = QVBoxLayout(self.history_tab)
        layout.addWidget(self.history_widget)
        self.history_widget.set_download_history(self.download_history, update_display_only=True)

    def setup_telegram_bot_tab(self):
        self.telegram_bot_widget = TelegramBotTab(self)

    def setup_settings_tab(self):
        self.settings_widget = SettingsTab(self)

    def load_history(self):
        try:
            history_path = os.path.join(BASE_PATH, 'download_history.json')
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    history = json.load(f)
                    for item in history:
                        if 'date' not in item:
                            item['date'] = 'N/A'
                        if 'status' not in item:
                            item['status'] = 'Completed'
                    return history
        except Exception as e:
            print(f"Error loading history: {e}")
        return []

    def load_config(self):
        """Load configuration from config.json"""
        config_path = os.path.join(BASE_PATH, 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if "ffmpeg_path" not in config:
                        config["ffmpeg_path"] = None
                    if "youtube_api_key" not in config:
                        config["youtube_api_key"] = ""
                    if "telegram_bot_token" not in config:
                        config["telegram_bot_token"] = ""
                    if "admin_users" not in config:
                        config["admin_users"] = []
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
        return {"ffmpeg_path": None, "youtube_api_key": "", "telegram_bot_token": "", "admin_users": []}

    def save_config(self):
        """Save configuration to config.json"""
        config_path = os.path.join(BASE_PATH, 'config.json')

        if self.config.get('ffmpeg_path') is None:
            ffmpeg_dir = os.path.join(BASE_PATH, 'ffmpeg')
            if os.path.exists(ffmpeg_dir):
                try:
                    shutil.rmtree(ffmpeg_dir)
                    print("FFmpeg directory removed successfully")
                except Exception as e:
                    print(f"Error removing FFmpeg directory: {e}")

        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def set_ffmpeg_config(self, path=None):
        """Set ffmpeg configuration and handle directory cleanup"""
        self.config['ffmpeg_path'] = path
        self.save_config()

    def add_to_history(self):
        try:
            url = self.url_input.text().strip()
            history_entry = {
                'title': self.title_label.text().replace("Title: ", ""),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'format': self.format_combo.currentText(),
                'output_dir': self.output_path.text(),
                'status': 'Completed',
                'channel': self.channel_label.text().replace("Channel: ", ""),
                'duration': self.duration_label.text().replace("Duration: ", ""),
                'views': self.views_label.text().replace("Views: ", ""),
                'url': url
            }
            self.download_history.append(history_entry)
            self.save_history()
            if hasattr(self, 'history_widget'):
                self.history_widget.update_history_display()
        except Exception as e:
            print(f"Error adding to history: {str(e)}")

    def add_batch_download_to_history(self, title, format_id, output_dir, url="N/A"):
        try:
            history_entry = {
                'title': title,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'format': format_id,
                'output_dir': output_dir,
                'status': 'Completed',
                'channel': 'Batch Download',
                'duration': 'N/A',
                'views': 'N/A',
                'url': url
            }
            self.download_history.append(history_entry)
            self.save_history()
            if hasattr(self, 'history_widget'):
                self.history_widget.update_history_display()
        except Exception as e:
            print(f"Error adding batch download to history: {str(e)}")

    def update_status(self, status):
        try:
            self.status_label.setText(status)
        except Exception as e:
            print(f"Error updating status: {str(e)}")

    def update_progress(self, data):
        try:
            downloaded = data.get('downloaded_bytes', 0)
            total = data.get('total_bytes', 0)
            speed = data.get('speed', 0)
            percent = data.get('percent', 0)
            eta = data.get('eta', 0)

            self.progress_bar.setValue(int(percent))
            status = f"{data.get('status', '')} "

            if total > 0:
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                status += f"{downloaded_mb:.1f}MB of {total_mb:.1f}MB "
                status += f"({percent:.1f}%) "

            if speed > 0:
                speed_mb = speed / (1024 * 1024)
                status += f"at {speed_mb:.1f}MB/s "

            if eta and eta > 0:
                minutes = int(eta // 60)
                seconds = int(eta % 60)
                status += f"- {minutes}:{seconds:02d} remaining"

            self.status_label.setText(status.strip())
        except Exception as e:
            print(f"Error updating progress: {str(e)}")

    def on_download_complete(self):
        self.progress_bar.setValue(100)
        self.download_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.add_to_history()

    def save_history(self):
        try:
            history_path = os.path.join(BASE_PATH, 'download_history.json')
            with open(history_path, 'w') as f:
                json.dump(self.download_history, f, indent=4)

            if hasattr(self, 'history_widget'):
                self.history_widget.set_download_history(self.download_history, update_display_only=True)

            print(f"History saved successfully. Items: {len(self.download_history)}")
        except Exception as e:
            print(f"Error saving history: {e}")

    def perform_search(self):
        self.search_tab_instance.perform_search()

    def clear_search_results(self):
        self.search_tab_instance.clear_results()

    def add_video(self, video_item):
        self.search_tab_instance.add_video(video_item)

    def on_search_finished(self, success, message):
        self.search_tab_instance.on_search_finished(success, message)

    def sort_results(self):
        self.search_tab_instance.sort_results()

    def _debounce_search(self):
        self.search_tab_instance._debounce_search()

    def _execute_search(self):
        self.search_tab_instance._execute_search()

    def create_video_widget(self, video_item):
        return self.search_tab_instance.create_video_widget(video_item)

    def setup_youtube_api(self, show_error=False):
        try:
            config_path = os.path.join(BASE_PATH, 'config.json')
            if not os.path.exists(config_path):
                if show_error:
                    QMessageBox.warning(self, "Error", "Please set your YouTube API key in Settings", QMessageBox.StandardButton.Ok)
                if hasattr(self, 'api_status_label') and self.api_status_label:
                    self.update_api_status_label("Not Connected", is_error=True)
                return None

            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('youtube_api_key')

            if not api_key:
                if show_error:
                    QMessageBox.warning(self, "Error", "Please set your YouTube API key in Settings", QMessageBox.StandardButton.Ok)
                if hasattr(self, 'api_status_label') and self.api_status_label:
                    self.update_api_status_label("Not Connected", is_error=True)
                return None

            youtube = build('youtube', 'v3', developerKey=api_key)
            request = youtube.channels().list(part="snippet", id="UC_x5XG1OV2P6uZZ5FSM9Ttw")
            request.execute()

            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Connected", is_error=False)
            return youtube

        except HttpError as e:
            if show_error:
                QMessageBox.critical(self, "Error", "Invalid API key or API quota exceeded", QMessageBox.StandardButton.Ok)
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Invalid API Key", is_error=True)
            return None

        except (FileNotFoundError, KeyError):
            if show_error:
                QMessageBox.warning(self, "Error", "Please set your YouTube API key in Settings", QMessageBox.StandardButton.Ok)
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Not Connected", is_error=True)
            return None

        except Exception as e:
            if show_error:
                QMessageBox.critical(self, "Error", f"Failed to initialize YouTube API: {str(e)}", QMessageBox.StandardButton.Ok)
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Error", is_error=True)
            return None

    def update_tab_states(self, api_valid=False):
        # Jika lisensi sedang dikunci, jangan buka apapun
        if getattr(self, '_license_locked', False):
            return

        downloader_index = self.tabs.indexOf(self.downloader_tab)
        batch_index      = self.tabs.indexOf(self.batch_downloader)
        search_index     = self.tabs.indexOf(self.search_tab)

        self.tabs.setTabEnabled(downloader_index, api_valid)
        self.tabs.setTabEnabled(batch_index, api_valid)
        self.tabs.setTabEnabled(search_index, api_valid)

        tooltip = "⚠️ This tab requires a valid YouTube API key.\nPlease go to Settings tab and enter a valid API key." if not api_valid else ""
        self.tabs.setTabToolTip(downloader_index, tooltip)
        self.tabs.setTabToolTip(batch_index, tooltip)
        self.tabs.setTabToolTip(search_index, tooltip)

        if not api_valid and self.tabs.currentIndex() in [downloader_index, batch_index, search_index]:
            self.tabs.setCurrentIndex(5)

    def update_api_status_label(self, status, is_error=True):
        if not hasattr(self, 'api_status_label') or self.api_status_label is None:
            return
        if is_error:
            color = "#ff4444"
            self.update_tab_states(False)
        else:
            color = "#44aa44"
            self.update_tab_states(True)
        self.api_status_label.setText(f"API Status: {status}")
        self.api_status_label.setStyleSheet(f"QLabel {{ padding: 5px 10px; color: {color}; font-weight: bold; }}")

    def prepare_download(self, url):
        if not isinstance(url, str) or not url.strip():
            QMessageBox.warning(self, "Invalid URL", "Received an empty/invalid URL. Please try another result.", QMessageBox.StandardButton.Ok)
            return

        m = re.search(r"(?:v=|youtu\.be/|/shorts/)([0-9A-Za-z_-]{11})", url)
        if not m:
            QMessageBox.warning(self, "Invalid YouTube Link", f"Could not detect a valid YouTube video ID from:\n{url}", QMessageBox.StandardButton.Ok)
            return

        url = f"https://www.youtube.com/watch?v={m.group(1)}"
        self.downloader_tab_instance.parent.url_input.setText(url)
        self.tabs.setCurrentIndex(0)
        self.downloader_tab_instance.parent.status_label.setText("Fetching video information...")
        self.downloader_tab_instance.parent.status_label.setStyleSheet("QLabel { color: #1a73e8; }")
        self.downloader_tab_instance.parent.status_label.repaint()
        threading.Thread(target=self.downloader_tab_instance.fetch_video_info, daemon=True).start()

    def on_tab_changed(self, index):
        try:
            tab_name = self.tabs.tabText(index)
            if tab_name == "Search":
                if not hasattr(self, 'youtube') or self.youtube is None:
                    import threading
                    def init_api():
                        self.youtube = self.setup_youtube_api(show_error=False)
                    api_thread = threading.Thread(target=init_api, daemon=True)
                    api_thread.start()
            elif tab_name == "Settings":
                if hasattr(self, 'settings_widget') and self.settings_widget:
                    QTimer.singleShot(50, lambda: self.settings_widget.reload_api_key())
        except Exception as e:
            print(f"Error in on_tab_changed: {str(e)}")

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.downloader_tab = QWidget()
        self.search_tab = QWidget()
        self.history_tab = QWidget()
        self.telegram_bot_tab = QWidget()
        self.settings_tab = QWidget()
        self.batch_downloader = BatchDownloadWidget(self)

        self.setup_downloader_tab()
        self.setup_search_tab()
        self.setup_history_tab()
        self.setup_telegram_bot_tab()
        self.setup_settings_tab()

        self.tabs.addTab(self.downloader_tab, "Download")
        self.tabs.addTab(self.batch_downloader, "Batch")
        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.telegram_bot_tab, "Bot")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.tabs.setCurrentIndex(5)

        # ── Revoke Banner (tersembunyi sampai diperlukan) ──────────────────────
        self._revoke_banner = QFrame()
        self._revoke_banner.setFixedHeight(56)
        self._revoke_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7b0000, stop:1 #c0392b);
                border-bottom: 2px solid #e74c3c;
            }
        """)
        banner_layout = QHBoxLayout(self._revoke_banner)
        banner_layout.setContentsMargins(16, 0, 16, 0)

        banner_icon = QLabel("🔒")
        banner_icon.setStyleSheet("font-size: 22px; background: transparent;")

        self._revoke_banner_msg = QLabel("Lisensi kamu telah dinonaktifkan.")
        self._revoke_banner_msg.setStyleSheet("""
            color: #fff;
            font-size: 13px;
            font-weight: 600;
            background: transparent;
        """)

        self._revoke_reactivate_btn = QPushButton("🔑  Masukkan Kode Baru")
        self._revoke_reactivate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._revoke_reactivate_btn.clicked.connect(self._show_reactivate_dialog)
        self._revoke_reactivate_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.15);
                color: white;
                border: 1px solid rgba(255,255,255,0.4);
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.28);
            }
        """)

        banner_layout.addWidget(banner_icon)
        banner_layout.addWidget(self._revoke_banner_msg)
        banner_layout.addStretch()
        banner_layout.addWidget(self._revoke_reactivate_btn)
        self._revoke_banner.hide()
        # ───────────────────────────────────────────────────────────────────────

        # Wrapper layout: banner di atas, tabs di bawah
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._revoke_banner)
        central_layout.addWidget(self.tabs)

        self.setCentralWidget(central)

    def _on_license_invalid(self, reason: str, msg: str):
        """Dipanggil dari LicenseWatcher saat lisensi expired atau revoked."""
        self._license_locked = True

        if reason == "expired":
            banner_msg = f"⏰  {msg}  —  Perbarui lisensi untuk melanjutkan."
            btn_text   = "🔑  Perbarui Lisensi"
            dlg_title  = "⏰  Lisensi Kadaluarsa"
            dlg_detail = f"{msg}\n\nSemua fitur telah dikunci.\nBeli lisensi baru untuk melanjutkan."
        else:
            banner_msg = f"🚫  {msg}  —  Semua fitur dinonaktifkan."
            btn_text   = "🔑  Masukkan Kode Baru"
            dlg_title  = "🚫  Lisensi Dinonaktifkan"
            dlg_detail = f"{msg}\n\nSemua fitur telah dikunci.\nHubungi administrator untuk info lebih lanjut."

        self._revoke_banner_msg.setText(banner_msg)
        self._revoke_reactivate_btn.setText(btn_text)
        self._revoke_reactivate_btn.show()
        self._revoke_banner.show()

        # Kunci SEMUA tab kecuali Settings
        settings_index = self.tabs.count() - 1
        for i in range(self.tabs.count()):
            if i != settings_index:
                self.tabs.setTabEnabled(i, False)
                self.tabs.setTabToolTip(i, "🔒 Lisensi tidak aktif")
        self.tabs.setCurrentIndex(settings_index)

        QMessageBox.warning(self, dlg_title, dlg_detail, QMessageBox.StandardButton.Ok)


    def _unlock_all_tabs(self):
        """Buka kunci semua tab, re-check YouTube API di background, lalu terapkan state."""
        # Step 1: Enable semua tab + clear semua tooltip lisensi dulu
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, True)
            self.tabs.setTabToolTip(i, "")

        # Step 2: Re-check YouTube API key di background thread agar UI tidak freeze
        def _recheck_api():
            youtube = self.setup_youtube_api(show_error=False)
            # setup_youtube_api sudah panggil update_api_status_label
            # yang akan panggil update_tab_states secara otomatis
            # Jika API tidak valid, pastikan tetap disable 3 tab
            if not youtube:
                self.update_tab_states(False)

        import threading
        threading.Thread(target=_recheck_api, daemon=True).start()

    def _on_license_restored(self, plan_info: str):
        """Dipanggil dari LicenseWatcher saat admin restore lisensi — auto unlock."""
        self._license_locked = False
        self._revoke_banner.hide()
        self._unlock_all_tabs()

        QMessageBox.information(
            self,
            "✅  Lisensi Dipulihkan",
            f"Lisensi kamu telah diaktifkan kembali oleh administrator.\n\n"
            f"Paket: {plan_info}\n\n"
            "Semua fitur kini dapat digunakan kembali.",
            QMessageBox.StandardButton.Ok
        )

    def _show_reactivate_dialog(self):
        """Buka dialog aktivasi dari banner (untuk kode baru)."""
        mgr = LicenseManager(BASE_PATH)
        dlg = LicenseDialog(mgr, parent=self, reactivation_mode=True)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            self._license_locked = False
            self._revoke_banner.hide()
            self._unlock_all_tabs()

            # Restart watcher dengan state bersih
            self._license_watcher.stop()
            self._license_watcher.wait(2000)
            self._license_watcher = LicenseWatcher(mgr, interval_seconds=60)
            self._license_watcher.license_invalid.connect(self._on_license_invalid)
            self._license_watcher.license_restored.connect(self._on_license_restored)
            self._license_watcher.start()

    def on_palette_changed(self, palette):
        try:
            if hasattr(self, 'search_tab_instance') and self.search_tab_instance.video_widgets:
                for widget in self.search_tab_instance.video_widgets:
                    self.update_video_widget_style(widget)
        except Exception as e:
            print(f"Error updating widget styles: {str(e)}")

    def closeEvent(self, event):
        if self.is_downloading:
            msg = "A download is in progress. Are you sure you want to exit?"
        else:
            msg = "Are you sure you want to exit?"

        reply = QMessageBox.question(
            self, 'Confirm Exit', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.is_downloading and self.download_thread:
                self.download_thread.terminate()
                self.download_thread.wait()
            if hasattr(self.settings_widget, 'bot_manager') and self.settings_widget.bot_manager:
                if self.settings_widget.bot_manager.is_bot_running():
                    self.settings_widget.bot_manager.stop_bot()
            # Stop license watcher
            if hasattr(self, '_license_watcher'):
                self._license_watcher.stop()
                self._license_watcher.wait(2000)
            event.accept()
        else:
            event.ignore()

    def setup_ffmpeg(self):
        """Check if FFmpeg is installed and set it up if not."""
        if self.is_ffmpeg_installed():
            return True

        try:
            progress = QDialog(self)
            progress.setWindowTitle("FFmpeg Setup")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setFixedSize(400, 150)

            layout = QVBoxLayout()
            status_label = QLabel("Initializing FFmpeg...", progress)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(status_label)

            progress_bar = QProgressBar(progress)
            progress_bar.setTextVisible(False)
            layout.addWidget(progress_bar)

            detail_label = QLabel("", progress)
            detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

            progress.setLayout(layout)
            progress.show()

            status_label.setText("Checking FFmpeg bundle...")
            QApplication.processEvents()

            # ============================================================
            # FIX: Gunakan BASE_PATH untuk mencari bundled ffmpeg
            # ============================================================
            ffmpeg_bundle_path = os.path.join(BASE_PATH, 'bundled', 'ffmpeg.zip')
            ffmpeg_dir = os.path.join(BASE_PATH, 'ffmpeg')
            os.makedirs(ffmpeg_dir, exist_ok=True)

            if os.path.exists(ffmpeg_bundle_path):
                status_label.setText("Extracting FFmpeg...")
                detail_label.setText("This may take a few moments...")
                progress_bar.setRange(0, 0)
                QApplication.processEvents()

                with zipfile.ZipFile(ffmpeg_bundle_path, 'r') as zip_ref:
                    total_files = len(zip_ref.namelist())
                    progress_bar.setRange(0, total_files)
                    for i, member in enumerate(zip_ref.namelist(), 1):
                        zip_ref.extract(member, ffmpeg_dir)
                        progress_bar.setValue(i)
                        detail_label.setText(f"Extracting: {os.path.basename(member)}")
                        QApplication.processEvents()

                status_label.setText("Configuring FFmpeg...")
                detail_label.setText("Looking for FFmpeg executable...")
                QApplication.processEvents()

                expected_bin_dir = os.path.join(ffmpeg_dir, 'ffmpeg-master-latest-win64-gpl', 'bin')
                if os.path.exists(os.path.join(expected_bin_dir, 'ffmpeg.exe')):
                    ffmpeg_bin_dir = expected_bin_dir
                else:
                    ffmpeg_bin_dir = None
                    for root, dirs, files in os.walk(ffmpeg_dir):
                        if 'ffmpeg.exe' in files:
                            ffmpeg_bin_dir = root
                            break

                if ffmpeg_bin_dir:
                    current_path = os.environ.get('PATH', '')
                    if ffmpeg_bin_dir not in current_path:
                        os.environ['PATH'] = ffmpeg_bin_dir + os.pathsep + current_path

                    self.ffmpeg_path = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe')
                    self.set_ffmpeg_config(self.ffmpeg_path)
                    self.ydl_opts = {'ffmpeg_location': self.ffmpeg_path}

                    progress.close()
                    QMessageBox.information(self, "FFmpeg Setup Complete", "FFmpeg has been successfully set up and is ready to use!")
                    return True
                else:
                    progress.close()
                    QMessageBox.critical(self, "FFmpeg Setup Error", "Could not find ffmpeg.exe in the extracted files.")
                    return False
            else:
                progress.close()
                QMessageBox.critical(
                    self, "FFmpeg Setup Error",
                    "FFmpeg not found.\n\nPlease copy ffmpeg.exe and ffprobe.exe into the 'ffmpeg' folder next to this application."
                )
                return False

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "FFmpeg Setup Error", f"Error setting up FFmpeg: {str(e)}")
            return False

    def is_ffmpeg_installed(self):
        """Check if FFmpeg is available - with proper path resolution for EXE."""

        # ============================================================
        # FIX: Cek ffmpeg di folder yang sama dengan EXE (BASE_PATH)
        # ============================================================

        # 1. Cek ffmpeg langsung di folder BASE_PATH/ffmpeg/
        local_ffmpeg = os.path.join(BASE_PATH, 'ffmpeg', 'ffmpeg.exe')
        if os.path.exists(local_ffmpeg):
            try:
                result = subprocess.run([local_ffmpeg, '-version'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Update config dengan path yang benar
                    self.set_ffmpeg_config(local_ffmpeg)
                    os.environ['PATH'] = os.path.dirname(local_ffmpeg) + os.pathsep + os.environ.get('PATH', '')
                    print(f"[FFmpeg] Found at: {local_ffmpeg}")
                    return True
            except Exception as e:
                print(f"[FFmpeg] Error checking local ffmpeg: {e}")

        # 2. Cek path yang tersimpan di config (validasi ulang)
        if self.config.get('ffmpeg_path'):
            ffmpeg_path = self.config['ffmpeg_path']
            if os.path.exists(ffmpeg_path):
                try:
                    result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
                    if result.returncode == 0:
                        os.environ['PATH'] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get('PATH', '')
                        print(f"[FFmpeg] Found at config path: {ffmpeg_path}")
                        return True
                except:
                    pass
            else:
                # Path di config tidak valid (path dari komputer lain), reset
                print(f"[FFmpeg] Config path invalid (from another PC): {ffmpeg_path}")
                self.config['ffmpeg_path'] = None

        # 3. Cek subfolder di BASE_PATH/ffmpeg/ (hasil ekstrak zip)
        ffmpeg_dir = os.path.join(BASE_PATH, 'ffmpeg')
        if os.path.exists(ffmpeg_dir):
            for root, dirs, files in os.walk(ffmpeg_dir):
                if 'ffmpeg.exe' in files:
                    ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
                    try:
                        result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
                        if result.returncode == 0:
                            self.set_ffmpeg_config(ffmpeg_path)
                            os.environ['PATH'] = root + os.pathsep + os.environ.get('PATH', '')
                            print(f"[FFmpeg] Found in subdirectory: {ffmpeg_path}")
                            return True
                    except:
                        pass

        # 4. Cek sistem PATH
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("[FFmpeg] Found in system PATH")
                return True
        except FileNotFoundError:
            pass

        print("[FFmpeg] Not found anywhere")
        return False

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def show_license_dialog(self):
        mgr = LicenseManager(BASE_PATH)
        # Selalu reactivation_mode=True karena dipanggil setelah app berjalan
        # (artinya user sudah punya lisensi aktif)
        dlg = LicenseDialog(mgr, parent=self, reactivation_mode=True)
        dlg.exec()

def main():
    app = QApplication(sys.argv)

    # ── LICENSE GUARD ──────────────────────────────────────────────────────
    mgr      = LicenseManager(BASE_PATH)
    is_valid = mgr.is_activated()

    if not is_valid:
        cache  = mgr.get_license_info()
        reason = (cache.get("invalid_reason", "") if cache else "")

        # Tampilkan pesan spesifik sebelum dialog aktivasi
        if cache and reason:
            from PyQt6.QtWidgets import QMessageBox
            mb = QMessageBox()
            mb.setStandardButtons(QMessageBox.StandardButton.Ok)
            mb.setStyleSheet("QMessageBox { background-color: #0a0c14; color: #e8ecff; }")

            if reason == "expired":
                mb.setWindowTitle("⏰  Lisensi Kadaluarsa")
                mb.setIcon(QMessageBox.Icon.Warning)
                mb.setText(
                    "<b>Lisensi kamu sudah kadaluarsa.</b><br><br>"
                    "Masa berlaku lisensi telah habis.<br>"
                    "Masukkan kode lisensi baru untuk melanjutkan."
                )
            elif reason == "revoked":
                mb.setWindowTitle("🚫  Lisensi Dinonaktifkan")
                mb.setIcon(QMessageBox.Icon.Critical)
                mb.setText(
                    "<b>Lisensi kamu telah dinonaktifkan.</b><br><br>"
                    "Kode aktivasi dicabut oleh administrator.<br>"
                    "Masukkan kode lisensi baru untuk melanjutkan."
                )
            else:
                mb.setWindowTitle("⚠️  Lisensi Tidak Valid")
                mb.setIcon(QMessageBox.Icon.Warning)
                mb.setText(
                    "<b>Lisensi kamu tidak valid.</b><br><br>"
                    "Masukkan kode lisensi untuk melanjutkan."
                )
            mb.exec()

        dlg = LicenseDialog(mgr)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
    # ───────────────────────────────────────────────────────────────────────

    window = ModernVideoDownloader()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
