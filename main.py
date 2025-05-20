import sys
import os
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

class ExportThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, history_data, file_path):
        super().__init__()
        self.history_data = history_data
        self.file_path = file_path

    def run(self):
        try:
            import csv

            # Define columns
            columns = ['Title', 'Channel', 'Download Date', 'Format', 'Duration',
                      'Views', 'Output Directory', 'Status']

            # Write to CSV
            with open(self.file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)  # Write header

                # Write data rows
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

        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)

        # App Logo and Title
        title_label = QLabel("Modern Multi-Platform Video Downloader")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3; margin: 10px;")

        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 16px; color: #666;")

        # Developer Info
        dev_label = QLabel("Developed by Adam Official Dev")
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_label.setStyleSheet("font-size: 16px; margin: 10px;")

        # Description
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

        # Links
        links_label = QLabel("""
        <a href="https://github.com/AdamOfficialDev/modern_youtube_downloader">GitHub Repository</a> |
        <a href="https://github.com/AdamOfficialDev">Developer Profile</a>
        """)
        links_label.setOpenExternalLinks(True)
        links_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links_label.setStyleSheet("margin: 20px;")

        # Add widgets to layout
        content_layout.addWidget(title_label)
        content_layout.addWidget(version_label)
        content_layout.addWidget(dev_label)
        content_layout.addWidget(desc_label)
        content_layout.addWidget(links_label)
        content_layout.addStretch()

        # Add scroll area to main layout
        layout.addWidget(scroll)

        # Close button
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

class ModernVideoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Adam | Modern Multi-Platform Video Downloader")
        self.setMinimumSize(1000, 700)

        # Initialize config first
        self.config = self.load_config()

        # Check and setup FFmpeg
        self.setup_ffmpeg()

        # Initialize other variables
        self.download_history = self.load_history()
        self.is_downloading = False
        self.is_paused = False
        self.formats_list = []
        self.download_thread = None
        self.is_dark_mode = True  # Track current theme

        # Initialize YouTube API variables
        self.youtube = None  # Initialize youtube attribute
        self.current_api_key = None  # Track current API key
        self.api_key_valid = False  # Track API key validity
        self.api_status_label = None  # Initialize status label

        # Setup UI
        self.setup_ui()
        self.settings_widget.apply_style()

        # Add About action
        self.about_action = self.menuBar().addMenu("Help").addAction("About")
        self.about_action.triggered.connect(self.show_about_dialog)

        # Now that UI is setup, initialize API and set initial tab
        self.youtube = self.setup_youtube_api(show_error=False)
        if self.youtube:  # If API key is valid
            # Enable tabs and show downloader tab
            self.update_tab_states(True)
            self.tabs.setCurrentIndex(0)  # Show downloader tab
        else:
            # Disable tabs and show settings tab
            self.update_tab_states(False)
            settings_index = self.tabs.indexOf(self.settings_tab)
            self.tabs.setCurrentIndex(settings_index)

    def changeEvent(self, event):
        if event.type() == event.Type.PaletteChange:
            # Check if theme actually changed
            is_now_dark = self.palette().color(QPalette.ColorRole.Window).lightness() <= 128
            if is_now_dark != self.is_dark_mode:
                self.is_dark_mode = is_now_dark
                self.update_all_video_widgets()
        super().changeEvent(event)

    def update_all_video_widgets(self):
        for widget in self.search_tab_instance.video_widgets:
            if widget and not widget.isHidden():
                self.update_video_widget_style(widget)
                widget.update()  # Force widget to repaint

    def update_video_widget_style(self, frame):
        is_light_mode = not self.is_dark_mode

        if is_light_mode:
            # Light mode
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
            # Dark mode
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

        # Update label colors
        for child in frame.findChildren(QLabel):
            if child.property("type") == "title":
                child.setStyleSheet(title_style)
            elif child.property("type") == "channel":
                child.setStyleSheet(channel_style)

        # Force frame to update
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
        self.history_widget.set_download_history(self.download_history, update_display_only=True)  # Set initial history

    def setup_settings_tab(self):
        self.settings_widget = SettingsTab(self)

    def load_history(self):
        try:
            if os.path.exists('download_history.json'):
                with open('download_history.json', 'r') as f:
                    history = json.load(f)
                    # Ensure all items have required fields
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
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except:
                return {"ffmpeg_path": None}
        return {"ffmpeg_path": None}

    def save_config(self):
        """Save configuration to config.json"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'config.json')

        # If ffmpeg_path is being set to null, remove the ffmpeg directory
        if self.config.get('ffmpeg_path') is None:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
            if os.path.exists(ffmpeg_dir):
                try:
                    shutil.rmtree(ffmpeg_dir)
                    print("FFmpeg directory removed successfully")
                except Exception as e:
                    print(f"Error removing FFmpeg directory: {e}")

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def set_ffmpeg_config(self, path=None):
        """Set ffmpeg configuration and handle directory cleanup"""
        self.config['ffmpeg_path'] = path
        self.save_config()

    def add_to_history(self):
        try:
            history_entry = {
                'title': self.title_label.text().replace("Title: ", ""),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'format': self.format_combo.currentText(),
                'output_dir': self.output_path.text(),
                'status': 'Completed',
                'channel': self.channel_label.text().replace("Channel: ", ""),
                'duration': self.duration_label.text().replace("Duration: ", ""),
                'views': self.views_label.text().replace("Views: ", "")
            }
            self.download_history.append(history_entry)
            self.save_history()
            if hasattr(self, 'history_widget'):
                self.history_widget.update_history_display()
        except Exception as e:
            print(f"Error adding to history: {str(e)}")

    def update_status(self, status):
        try:
            self.status_label.setText(status)
        except Exception as e:
            print(f"Error updating status: {str(e)}")

    def update_progress(self, data):
        try:
            # Get values from data
            downloaded = data.get('downloaded_bytes', 0)
            total = data.get('total_bytes', 0)
            speed = data.get('speed', 0)
            percent = data.get('percent', 0)
            eta = data.get('eta', 0)

            # Update progress bar
            self.progress_bar.setValue(int(percent))

            # Format sizes and create status message
            status = f"{data.get('status', '')} "

            if total > 0:  # Only show sizes if we have valid total
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                status += f"{downloaded_mb:.1f}MB of {total_mb:.1f}MB "
                status += f"({percent:.1f}%) "

            if speed > 0:  # Only show speed if we have valid speed
                speed_mb = speed / (1024 * 1024)
                status += f"at {speed_mb:.1f}MB/s "

            if eta and eta > 0:  # Only show ETA if we have valid eta
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
            with open('download_history.json', 'w') as f:
                json.dump(self.download_history, f, indent=4)
            if hasattr(self, 'history_widget'):
                self.history_widget.set_download_history(self.download_history, update_display_only=True)
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
            # Load API key from config
            if not os.path.exists('config.json'):
                if show_error:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Please set your YouTube API key in Settings",
                        QMessageBox.StandardButton.Ok
                    )
                if hasattr(self, 'api_status_label') and self.api_status_label:
                    self.update_api_status_label("Not Connected", is_error=True)
                return None

            with open('config.json', 'r') as f:
                config = json.load(f)
                api_key = config.get('youtube_api_key')

            if not api_key:
                if show_error:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Please set your YouTube API key in Settings",
                        QMessageBox.StandardButton.Ok
                    )
                if hasattr(self, 'api_status_label') and self.api_status_label:
                    self.update_api_status_label("Not Connected", is_error=True)
                return None

            # Initialize the YouTube API
            youtube = build('youtube', 'v3', developerKey=api_key)

            # Test the API with a simple request
            request = youtube.channels().list(
                part="snippet",
                id="UC_x5XG1OV2P6uZZ5FSM9Ttw"  # Google Developers channel
            )
            request.execute()

            # If we get here, the API is working
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Connected", is_error=False)
            return youtube

        except HttpError as e:
            if show_error:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Invalid API key or API quota exceeded",
                    QMessageBox.StandardButton.Ok
                )
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Invalid API Key", is_error=True)
            return None

        except (FileNotFoundError, KeyError):
            if show_error:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Please set your YouTube API key in Settings",
                    QMessageBox.StandardButton.Ok
                )
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Not Connected", is_error=True)
            return None

        except Exception as e:
            if show_error:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to initialize YouTube API: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
            if hasattr(self, 'api_status_label') and self.api_status_label:
                self.update_api_status_label("Error", is_error=True)
            return None

    def update_tab_states(self, api_valid=False):
        # Get tab indices
        downloader_index = self.tabs.indexOf(self.downloader_tab)
        batch_index = self.tabs.indexOf(self.batch_downloader)
        search_index = self.tabs.indexOf(self.search_tab)

        # Enable/disable tabs based on API status
        self.tabs.setTabEnabled(downloader_index, api_valid)
        self.tabs.setTabEnabled(batch_index, api_valid)
        self.tabs.setTabEnabled(search_index, api_valid)

        # Update tooltips based on API status
        tooltip = "⚠️ This tab requires a valid YouTube API key.\nPlease go to Settings tab and enter a valid API key." if not api_valid else ""
        self.tabs.setTabToolTip(downloader_index, tooltip)
        self.tabs.setTabToolTip(batch_index, tooltip)
        self.tabs.setTabToolTip(search_index, tooltip)

        # If current tab is disabled, switch to settings tab
        if not api_valid and self.tabs.currentIndex() in [downloader_index, batch_index, search_index]:
            settings_index = self.tabs.indexOf(self.settings_tab)
            self.tabs.setCurrentIndex(settings_index)

    def update_api_status_label(self, status, is_error=True):
        # Only update if label exists
        if not hasattr(self, 'api_status_label') or self.api_status_label is None:
            return

        if is_error:
            color = "#ff4444"  # Red for error
            self.update_tab_states(False)  # Disable tabs on error
        else:
            color = "#44aa44"  # Green for success
            self.update_tab_states(True)  # Enable tabs on success

        self.api_status_label.setText(f"API Status: {status}")
        self.api_status_label.setStyleSheet(f"QLabel {{ padding: 5px 10px; color: {color}; font-weight: bold; }}")

    def prepare_download(self, url):
        # Set URL in input field
        self.downloader_tab_instance.parent.url_input.setText(url)
        # Switch to Downloader tab (index 0)
        self.tabs.setCurrentIndex(0)
        # Update status label
        self.downloader_tab_instance.parent.status_label.setText("Fetching video information...")
        self.downloader_tab_instance.parent.status_label.setStyleSheet("QLabel { color: #1a73e8; }")
        self.downloader_tab_instance.parent.status_label.repaint()
        # Fetch video info
        threading.Thread(target=self.downloader_tab_instance.fetch_video_info, daemon=True).start()

    def on_tab_changed(self, index):
        try:
            # Reinitialize YouTube API when switching to search tab
            if self.tabs.tabText(index) == "Search":
                if not hasattr(self, 'youtube') or self.youtube is None:
                    self.youtube = self.setup_youtube_api(show_error=False)
        except Exception as e:
            print(f"Error in on_tab_changed: {str(e)}")

    def setup_ui(self):
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)  # Connect tab change event

        # Create tabs
        self.downloader_tab = QWidget()
        self.search_tab = QWidget()
        self.history_tab = QWidget()
        self.settings_tab = QWidget()
        self.batch_downloader = BatchDownloadWidget()  # Initialize batch downloader

        # Setup individual tabs
        self.setup_downloader_tab()
        self.setup_search_tab()
        self.setup_history_tab()
        self.setup_settings_tab()

        # Add tabs to widget
        self.tabs.addTab(self.downloader_tab, "Single Download")
        self.tabs.addTab(self.batch_downloader, "Batch Download")
        self.tabs.addTab(self.search_tab, "Search")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.settings_tab, "Settings")

        # Set the central widget
        self.setCentralWidget(self.tabs)

    def on_palette_changed(self, palette):
        try:
            # Update all video widgets if they exist
            if hasattr(self, 'search_tab_instance') and self.search_tab_instance.video_widgets:
                for widget in self.search_tab_instance.video_widgets:
                    self.update_video_widget_style(widget)
        except Exception as e:
            print(f"Error updating widget styles: {str(e)}")

    def closeEvent(self, event):
        """Handle application close event"""
        # Check if download is in progress
        if self.is_downloading:
            msg = "A download is in progress. Are you sure you want to exit?"
        else:
            msg = "Are you sure you want to exit?"

        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Save any pending changes or cleanup if needed
            if self.is_downloading and self.download_thread:
                self.download_thread.terminate()
                self.download_thread.wait()
            event.accept()
        else:
            event.ignore()

    def setup_ffmpeg(self):
        """Check if FFmpeg is installed and set it up if not."""
        if self.is_ffmpeg_installed():
            return True

        try:
            # Create and show progress dialog
            progress = QDialog(self)
            progress.setWindowTitle("FFmpeg Setup")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setFixedSize(400, 150)

            layout = QVBoxLayout()

            # Add status label
            status_label = QLabel("Initializing FFmpeg...", progress)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(status_label)

            # Add progress bar
            progress_bar = QProgressBar(progress)
            progress_bar.setTextVisible(False)
            layout.addWidget(progress_bar)

            # Add detail label
            detail_label = QLabel("", progress)
            detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

            progress.setLayout(layout)
            progress.show()

            # Update status
            status_label.setText("Checking FFmpeg bundle...")
            QApplication.processEvents()

            # Get the application directory
            app_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_bundle_path = os.path.join(app_dir, 'bundled', 'ffmpeg.zip')

            # Create directory for FFmpeg if it doesn't exist
            ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
            os.makedirs(ffmpeg_dir, exist_ok=True)

            # Extract bundled FFmpeg
            if os.path.exists(ffmpeg_bundle_path):
                status_label.setText("Extracting FFmpeg...")
                detail_label.setText("This may take a few moments...")
                progress_bar.setRange(0, 0)  # Indeterminate progress
                QApplication.processEvents()

                with zipfile.ZipFile(ffmpeg_bundle_path, 'r') as zip_ref:
                    # Get total files for progress
                    total_files = len(zip_ref.namelist())
                    progress_bar.setRange(0, total_files)

                    # Extract with progress
                    for i, member in enumerate(zip_ref.namelist(), 1):
                        zip_ref.extract(member, ffmpeg_dir)
                        progress_bar.setValue(i)
                        detail_label.setText(f"Extracting: {os.path.basename(member)}")
                        QApplication.processEvents()

                # Find the bin directory (it might be nested in a subfolder)
                status_label.setText("Configuring FFmpeg...")
                detail_label.setText("Looking for FFmpeg executable...")
                QApplication.processEvents()

                # Look for ffmpeg.exe in the expected location first
                expected_bin_dir = os.path.join(ffmpeg_dir, 'ffmpeg-master-latest-win64-gpl', 'bin')
                if os.path.exists(os.path.join(expected_bin_dir, 'ffmpeg.exe')):
                    ffmpeg_bin_dir = expected_bin_dir
                else:
                    # Fallback to searching in all subdirectories
                    ffmpeg_bin_dir = None
                    for root, dirs, files in os.walk(ffmpeg_dir):
                        if 'ffmpeg.exe' in files:
                            ffmpeg_bin_dir = root
                            break

                if ffmpeg_bin_dir:
                    # Add to current session PATH only
                    current_path = os.environ.get('PATH', '')
                    if ffmpeg_bin_dir not in current_path:
                        os.environ['PATH'] = ffmpeg_bin_dir + os.pathsep + current_path

                    # Store FFmpeg path for direct use
                    self.ffmpeg_path = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe')

                    # Save the path to config using the new method
                    self.set_ffmpeg_config(self.ffmpeg_path)

                    # Configure yt-dlp to use our FFmpeg
                    self.ydl_opts = {
                        'ffmpeg_location': self.ffmpeg_path,
                    }

                    # Close progress dialog
                    progress.close()

                    # Show success message
                    QMessageBox.information(
                        self,
                        "FFmpeg Setup Complete",
                        "FFmpeg has been successfully set up and is ready to use!"
                    )

                    return True
                else:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "FFmpeg Setup Error",
                        "Could not find ffmpeg.exe in the extracted files."
                    )
                    return False
            else:
                progress.close()
                QMessageBox.critical(
                    self,
                    "FFmpeg Setup Error",
                    "FFmpeg bundle not found in the application directory. "
                    "Please make sure the application is properly installed."
                )
                return False

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(
                self,
                "FFmpeg Setup Error",
                f"Error setting up FFmpeg: {str(e)}"
            )
            return False

    def is_ffmpeg_installed(self):
        """Check if FFmpeg is available in the system or our bundled version."""
        # First check if we have a saved valid path
        if self.config.get('ffmpeg_path'):
            ffmpeg_path = self.config['ffmpeg_path']
            if os.path.exists(ffmpeg_path):
                try:
                    result = subprocess.run([ffmpeg_path, '-version'],
                                         capture_output=True, text=True)
                    if result.returncode == 0:
                        # Set the path in environment
                        os.environ['PATH'] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get('PATH', '')
                        return True
                except:
                    pass

        try:
            # Check system PATH
            result = subprocess.run(['ffmpeg', '-version'],
                                 capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            # Then check our bundled version
            app_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')

            # Check directly in the ffmpeg directory first (where download_ffmpeg.py places it)
            direct_bin = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
            if os.path.exists(direct_bin):
                # Found it, update config and return True
                self.set_ffmpeg_config(direct_bin)
                return True

            # Check in expected location next
            expected_bin = os.path.join(ffmpeg_dir, 'ffmpeg-master-latest-win64-gpl', 'bin', 'ffmpeg.exe')
            if os.path.exists(expected_bin):
                # Found it, update config and return True
                self.set_ffmpeg_config(expected_bin)
                return True

            # Fallback to searching all subdirectories
            for root, dirs, files in os.walk(ffmpeg_dir):
                if 'ffmpeg.exe' in files:
                    # Found it, update config and return True
                    ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
                    self.set_ffmpeg_config(ffmpeg_path)
                    return True
            return False

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

def main():
    app = QApplication(sys.argv)
    window = ModernVideoDownloader()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()