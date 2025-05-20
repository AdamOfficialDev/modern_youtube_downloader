from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit,
                             QPushButton, QProgressBar, QLabel, QFileDialog,
                             QHBoxLayout, QSpinBox, QComboBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QCheckBox, QFrame,
                             QSizePolicy, QScrollArea, QStyle, QStyleFactory,
                             QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QMutex, QSize, QWaitCondition
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon
import yt_dlp
import os
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import time
from typing import Dict, List, Optional
import threading
from datetime import datetime, timedelta

class DownloadStatus(Enum):
    PENDING = "Pending"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    FAILED = "Failed"
    RETRYING = "Retrying"
    PAUSED = "Paused"

@dataclass
class DownloadItem:
    url: str
    title: str = ""
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    error: str = ""
    retry_count: int = 0
    format_id: str = "best"
    file_path: str = ""
    size: str = "Unknown"
    speed: str = "0 KB/s"
    eta: str = "Unknown"

class DownloadWorker(QThread):
    progress_updated = pyqtSignal(str, float, str, str, str)  # url, progress, speed, eta, size
    status_updated = pyqtSignal(str, DownloadStatus, str)  # url, status, error
    title_updated = pyqtSignal(str, str)  # url, title

    def __init__(self, url, format_option="best", output_dir=""):
        super().__init__()
        self.url = url
        self.format_option = format_option
        self.output_dir = output_dir
        self._is_paused = False
        self._is_stopped = False
        self._pause_condition = QWaitCondition()
        self._pause_mutex = QMutex()

    def run(self):
        try:
            self.status_updated.emit(self.url, DownloadStatus.DOWNLOADING, "")

            # Base options
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [self._progress_hook],
            }

            # Add format-specific options
            if self.format_option == "mp3":
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                    'prefer_ffmpeg': True,
                })
            else:
                ydl_opts['format'] = self.format_option
                ydl_opts['outtmpl'] = os.path.join(self.output_dir, '%(title)s.%(ext)s')

            # Check for browser cookies
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)

                    # Add cookies if available
                    cookies_path = config.get('youtube_cookies_path')
                    if cookies_path and os.path.exists(cookies_path):
                        ydl_opts['cookiefile'] = cookies_path
                except Exception as e:
                    print(f"Warning: Could not load cookies: {str(e)}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Get video info first
                    info = ydl.extract_info(self.url, download=False)
                    title = info.get('title', self.url)
                    self.title_updated.emit(self.url, title)  # Emit title information

                    # Start download
                    ydl.download([self.url])

                    if not self._is_stopped:
                        self.status_updated.emit(self.url, DownloadStatus.COMPLETED, "")
                except Exception as e:
                    error_msg = str(e)
                    if "Sign in to confirm you're not a bot" in error_msg:
                        error_msg = "Anti-bot protection triggered. Please set up browser cookies in Settings tab."
                    elif "Unsupported URL" in error_msg:
                        error_msg = "Unsupported URL. Please check the URL and try again."
                    self.status_updated.emit(self.url, DownloadStatus.FAILED, error_msg)

        except Exception as e:
            self.status_updated.emit(self.url, DownloadStatus.FAILED, str(e))

    def _progress_hook(self, d):
        if self._is_stopped:
            raise Exception("Download stopped")

        if d['status'] == 'downloading':
            # Calculate progress
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)

            if total_bytes > 0:
                progress = (downloaded_bytes / total_bytes) * 100
            else:
                progress = 0

            # Get download speed
            speed = d.get('speed', 0)
            if speed:
                speed_str = f"{speed/1024/1024:.1f} MB/s"
            else:
                speed_str = "N/A"

            # Calculate ETA
            if speed and speed > 0 and total_bytes > 0:
                remaining_bytes = total_bytes - downloaded_bytes
                eta_seconds = remaining_bytes / speed
                eta_str = str(timedelta(seconds=int(eta_seconds)))
            else:
                eta_str = "N/A"

            # Get size
            if total_bytes > 0:
                size_str = f"{total_bytes/1024/1024:.1f} MB"
            else:
                size_str = "N/A"

            # Check if paused
            self._pause_mutex.lock()
            try:
                while self._is_paused and not self._is_stopped:
                    self.status_updated.emit(self.url, DownloadStatus.PAUSED, "")
                    self._pause_condition.wait(self._pause_mutex)
                if not self._is_stopped:
                    self.status_updated.emit(self.url, DownloadStatus.DOWNLOADING, "")
            finally:
                self._pause_mutex.unlock()

            # Emit progress
            self.progress_updated.emit(self.url, progress, speed_str, eta_str, size_str)

    def pause(self):
        self._pause_mutex.lock()
        self._is_paused = True
        self._pause_mutex.unlock()

    def resume(self):
        self._pause_mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    def stop(self):
        self._is_stopped = True
        self.resume()  # Wake up if paused

class BatchDownloadManager:
    def __init__(self):
        self.downloads = {}
        self.mutex = QMutex()
        self.max_concurrent = 3
        self.workers = {}
        self.format_id = "best"
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.output_dir = ""
        self.is_downloading = False
        self.max_retries = 3  # Maximum number of retry attempts

    def add_to_list(self, url: str) -> None:
        """Add a URL to the download list without starting the download"""
        self.mutex.lock()
        try:
            if url not in self.downloads:
                download = DownloadItem(url=url)
                self.downloads[url] = download
        finally:
            self.mutex.unlock()

    def retry_failed(self) -> None:
        """Retry all failed downloads that haven't exceeded max retry attempts"""
        self.mutex.lock()
        try:
            for url, download in self.downloads.items():
                if (download.status == DownloadStatus.FAILED and
                    download.retry_count < self.max_retries):
                    download.status = DownloadStatus.PENDING
                    download.retry_count += 1
                    download.error = ""
            if not self.is_downloading:
                self.start_downloads()
        finally:
            self.mutex.unlock()

    def remove_completed(self) -> None:
        """Remove all completed downloads from the list"""
        self.mutex.lock()
        try:
            urls_to_remove = [url for url, download in self.downloads.items()
                            if download.status == DownloadStatus.COMPLETED]
            for url in urls_to_remove:
                del self.downloads[url]
        finally:
            self.mutex.unlock()

    def remove_failed(self) -> None:
        """Remove all failed downloads from the list"""
        self.mutex.lock()
        try:
            urls_to_remove = [url for url, download in self.downloads.items()
                            if download.status == DownloadStatus.FAILED]
            for url in urls_to_remove:
                del self.downloads[url]
        finally:
            self.mutex.unlock()

    def get_total_progress(self) -> tuple[float, int, int]:
        """Get overall progress and counts
        Returns:
            tuple: (total_progress_percentage, completed_count, total_count)
        """
        self.mutex.lock()
        try:
            if not self.downloads:
                return 0.0, 0, 0

            total_progress = 0.0
            completed_count = 0
            total_count = len(self.downloads)

            for download in self.downloads.values():
                if download.status == DownloadStatus.COMPLETED:
                    total_progress += 100.0
                    completed_count += 1
                else:
                    total_progress += download.progress

            avg_progress = total_progress / total_count
            return avg_progress, completed_count, total_count
        finally:
            self.mutex.unlock()

    def start_downloads(self) -> None:
        """Start downloading all pending items in the list"""
        self.mutex.lock()
        try:
            self.is_downloading = True
            for url, download in self.downloads.items():
                if download.status == DownloadStatus.PENDING and url not in self.workers:
                    self.start_download(url)
        finally:
            self.mutex.unlock()

    def add_download(self, url: str) -> None:
        self.mutex.lock()
        try:
            if url not in self.downloads:
                download = DownloadItem(url=url)
                self.downloads[url] = download
                # Don't start download automatically
        finally:
            self.mutex.unlock()

    def start_download(self, url: str) -> None:
        if url in self.workers:
            return

        worker = DownloadWorker(url, self.format_id, self.output_dir)
        worker.progress_updated.connect(
            lambda u, p, s, e, sz: self._update_progress(u, p, s, e, sz))
        worker.status_updated.connect(
            lambda u, s, e: self._update_status(u, s, e))
        worker.title_updated.connect(
            lambda u, t: self._update_title(u, t))

        self.workers[url] = worker
        worker.start()

    def _update_progress(self, url: str, progress: float, speed: str, eta: str, size: str) -> None:
        self.mutex.lock()
        try:
            if url in self.downloads:
                download = self.downloads[url]
                download.progress = progress
                download.speed = speed
                download.eta = eta
                download.size = size
        finally:
            self.mutex.unlock()

    def _update_status(self, url: str, status: DownloadStatus, error: str = "") -> None:
        self.mutex.lock()
        try:
            if url in self.downloads:
                download = self.downloads[url]
                download.status = status
                download.error = error

                if status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]:
                    if url in self.workers:
                        worker = self.workers[url]
                        worker.quit()
                        worker.wait()
                        del self.workers[url]

                    # Check if all downloads are finished
                    if not self.workers:
                        self.is_downloading = False
        finally:
            self.mutex.unlock()

    def _update_title(self, url: str, title: str) -> None:
        self.mutex.lock()
        try:
            if url in self.downloads:
                download = self.downloads[url]
                download.title = title
        finally:
            self.mutex.unlock()

    def pause_all(self) -> None:
        self.mutex.lock()
        try:
            for worker in self.workers.values():
                worker.pause()
        finally:
            self.mutex.unlock()

    def resume_all(self) -> None:
        self.mutex.lock()
        try:
            for worker in self.workers.values():
                worker.resume()
        finally:
            self.mutex.unlock()

    def stop_all(self) -> None:
        self.mutex.lock()
        try:
            for worker in self.workers.values():
                worker.stop()
            self.workers.clear()
            self.is_downloading = False
        finally:
            self.mutex.unlock()

    def set_format(self, format_id: str) -> None:
        """Set the format ID for downloads"""
        self.format_id = format_id

class StyledButton(QPushButton):
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        if icon:
            self.setIcon(icon)
        self.setMinimumHeight(40)
        self.setFont(QFont("Segoe UI", 9))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

class ControlPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlPanel")

        # Apply dark palette
        dark_palette = parent.palette() if parent else QPalette()
        self.setPalette(dark_palette)

        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)

        # Concurrent downloads control
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("Max Concurrent:")
        concurrent_label.setFont(QFont("Segoe UI", 9))
        concurrent_label.setPalette(self.palette())  # Use parent's palette

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.setMinimumHeight(30)
        self.concurrent_spin.setPalette(self.palette())  # Use parent's palette

        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.concurrent_spin)

        # Format selection
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setFont(QFont("Segoe UI", 9))
        format_label.setPalette(self.palette())  # Use parent's palette

        self.format_combo = QComboBox()
        # self.format_combo.setMinimumHeight(30)
        self.format_combo.addItems([
            "Best Quality (Video + Audio)",
            "High Quality Video",
            "Medium Quality",
            "Audio Only (Best)",
            "Audio Only (MP3)"
        ])
        self.format_combo.setPalette(self.palette())  # Use parent's palette

        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)

        # Add layouts with proper spacing
        layout.addLayout(concurrent_layout)
        layout.addWidget(create_vertical_line())
        layout.addLayout(format_layout)
        layout.addStretch()

class DownloadTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Apply dark palette
        if parent:
            self.setPalette(parent.palette())
        self.setup_ui()

    def setup_ui(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Title", "Status", "Progress", "Speed", "ETA", "Size", "Error"
        ])

        # Style the table
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.verticalHeader().hide()
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Set column sizes
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Title
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Progress
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # Speed
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # ETA
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)    # Size
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Error

        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)

        # Set fixed column widths
        self.setColumnWidth(1, 100)  # Status
        self.setColumnWidth(2, 100)  # Progress
        self.setColumnWidth(3, 100)  # Speed
        self.setColumnWidth(4, 100)  # ETA
        self.setColumnWidth(5, 100)  # Size

def create_vertical_line():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line

class BatchDownloadWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.download_manager = BatchDownloadManager()
        self.is_dark_mode = True
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Title
        title_label = QLabel("Batch Download Manager")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setProperty("title", True)
        main_layout.addWidget(title_label)

        # Control Panel
        self.control_panel = ControlPanel(self)
        main_layout.addWidget(self.control_panel)

        # Save to directory selector
        save_layout = QHBoxLayout()
        save_label = QLabel("Save to:")
        save_label.setFont(QFont("Segoe UI", 9))
        self.save_path_input = QLineEdit()
        self.save_path_input.setReadOnly(True)
        self.save_path_input.setPlaceholderText("Select download directory...")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.select_save_directory)

        save_layout.addWidget(save_label)
        save_layout.addWidget(self.save_path_input)
        save_layout.addWidget(self.browse_btn)
        main_layout.addLayout(save_layout)

        # URL Input Section
        url_section = QFrame(self)
        url_layout = QVBoxLayout(url_section)
        url_layout.setContentsMargins(0, 0, 0, 0)

        url_label = QLabel("Enter video URLs from any platform (one per line):")
        url_label.setFont(QFont("Segoe UI", 9))

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=...\nhttps://vimeo.com/...\nhttps://dailymotion.com/video/...")
        self.url_input.setMinimumHeight(100)

        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addWidget(url_section)

        # Download Table
        self.download_table = DownloadTable(self)
        main_layout.addWidget(self.download_table)

        # Progress Bar
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress.setValue(0)
        self.total_progress.setFormat("Overall Progress: 0.0% (0/0)")
        main_layout.addWidget(self.total_progress)

        # Status Label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # Create styled buttons with icons
        self.start_btn = StyledButton("Start Downloads", self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.pause_btn = StyledButton("Pause All", self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.resume_btn = StyledButton("Resume All", self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.stop_btn = StyledButton("Stop All", self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))

        # Connect button signals
        self.start_btn.clicked.connect(self.start_downloads)
        self.pause_btn.clicked.connect(self.download_manager.pause_all)
        self.resume_btn.clicked.connect(self.download_manager.resume_all)
        self.stop_btn.clicked.connect(self.download_manager.stop_all)

        # Add buttons to layout
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.resume_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        # Start update timer
        self.update_timer = self.startTimer(500)

    def add_to_list(self):
        url = self.url_input.toPlainText().strip()
        if url:
            self.download_manager.add_to_list(url)
            self.update_download_table()
            self.url_input.clear()

    def update_download_table(self):
        downloads = self.download_manager.downloads
        self.download_table.setRowCount(len(downloads))

        for i, (url, download) in enumerate(downloads.items()):
            items = [
                QTableWidgetItem(download.title or url),
                QTableWidgetItem(download.status.value),
                QTableWidgetItem(f"{download.progress:.1f}%"),
                QTableWidgetItem(download.speed),
                QTableWidgetItem(download.eta),
                QTableWidgetItem(download.size),
                QTableWidgetItem(download.error)
            ]

            for col, item in enumerate(items):
                self.download_table.setItem(i, col, item)

            # Color schemes for dark and light modes
            if self.is_dark_mode:
                color_scheme = {
                    DownloadStatus.PENDING: (QColor("#2d2d2d"), QColor("#ffffff")),
                    DownloadStatus.DOWNLOADING: (QColor("#1a365d"), QColor("#93c5fd")),
                    DownloadStatus.COMPLETED: (QColor("#14532d"), QColor("#86efac")),
                    DownloadStatus.FAILED: (QColor("#7f1d1d"), QColor("#fca5a5")),
                    DownloadStatus.RETRYING: (QColor("#713f12"), QColor("#fde047")),
                    DownloadStatus.PAUSED: (QColor("#374151"), QColor("#e5e7eb"))
                }
            else:
                color_scheme = {
                    DownloadStatus.PENDING: (QColor("#FFFFFF"), QColor("#1a1a1a")),
                    DownloadStatus.DOWNLOADING: (QColor("#cfe2ff"), QColor("#084298")),
                    DownloadStatus.COMPLETED: (QColor("#d1e7dd"), QColor("#0f5132")),
                    DownloadStatus.FAILED: (QColor("#f8d7da"), QColor("#842029")),
                    DownloadStatus.RETRYING: (QColor("#fff3cd"), QColor("#664d03")),
                    DownloadStatus.PAUSED: (QColor("#e2e3e5"), QColor("#41464b"))
                }

            bg_color, text_color = color_scheme.get(download.status,
                (QColor("#2d2d2d" if self.is_dark_mode else "#FFFFFF"),
                 QColor("#ffffff" if self.is_dark_mode else "#1a1a1a")))

            for col in range(self.download_table.columnCount()):
                item = self.download_table.item(i, col)
                if item:
                    item.setBackground(bg_color)
                    item.setForeground(text_color)

    def timerEvent(self, event):
        self.update_download_table()

        # Update button and control states based on download status
        is_downloading = self.download_manager.is_downloading
        self.start_btn.setEnabled(not is_downloading)

        # Disable controls during download
        self.control_panel.concurrent_spin.setEnabled(not is_downloading)
        self.control_panel.format_combo.setEnabled(not is_downloading)
        self.save_path_input.setEnabled(not is_downloading)
        self.browse_btn.setEnabled(not is_downloading)
        self.url_input.setEnabled(not is_downloading)  # Disable URL input during downloads

        # Update overall progress and status
        progress, completed, total = self.download_manager.get_total_progress()
        self.total_progress.setMaximum(total)
        self.total_progress.setValue(completed)
        self.total_progress.setFormat(f"Overall Progress: {progress:.1f}% ({completed}/{total})")

        # Update status label
        if is_downloading:
            self.status_label.setText(f"Downloading: {completed}/{total} completed")
        elif total == 0:
            self.status_label.setText("Ready")
        else:
            self.status_label.setText(f"Paused: {completed}/{total} completed")

    def select_save_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.save_path_input.setText(directory)
            self.download_manager.output_dir = directory

    def start_downloads(self):
        # Check if save directory is selected
        if not self.save_path_input.text():
            QMessageBox.warning(
                self,
                "No Save Directory",
                "Please select a directory to save the downloads.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Get URLs from text input and validate them
        urls = []
        invalid_urls = []
        duplicate_urls = []

        for url in [url.strip() for url in self.url_input.toPlainText().split('\n') if url.strip()]:
            # Basic URL validation - must start with http:// or https://
            if not (url.startswith('http://') or url.startswith('https://')):
                invalid_urls.append(url)
                continue

            # Check for duplicates
            if url in urls or url in self.download_manager.downloads:
                duplicate_urls.append(url)
                continue

            urls.append(url)

        # Show warnings if there are invalid or duplicate URLs
        if invalid_urls or duplicate_urls:
            warning_msg = ""
            if invalid_urls:
                warning_msg += f"Invalid URLs (must start with http:// or https://):\n{chr(10).join(invalid_urls)}\n\n"
            if duplicate_urls:
                warning_msg += f"Duplicate URLs (will be skipped):\n{chr(10).join(duplicate_urls)}"

            QMessageBox.warning(
                self,
                "URL Validation Warning",
                warning_msg,
                QMessageBox.StandardButton.Ok
            )

            if not urls:  # If no valid URLs remain
                return

        if not urls:
            QMessageBox.warning(
                self,
                "No URLs",
                "Please enter at least one valid video URL to download.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Show feedback about number of videos to download
        response = QMessageBox.question(
            self,
            "Start Downloads",
            f"Start downloading {len(urls)} videos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if response != QMessageBox.StandardButton.Yes:
            return

        # Get format ID based on combo box selection
        format_map = {
            "Best Quality (Video + Audio)": "best",
            "High Quality Video": "bestvideo+bestaudio",
            "Medium Quality": "18",
            "Audio Only (Best)": "bestaudio",
            "Audio Only (MP3)": "mp3"
        }

        selected_format = self.control_panel.format_combo.currentText()
        self.download_manager.set_format(format_map[selected_format])

        # Add URLs to download manager
        for url in urls:
            self.download_manager.add_to_list(url)

        # Clear the URL input after adding to queue
        self.url_input.clear()

        # Start the downloads
        self.download_manager.start_downloads()

        # Disable start button while downloading
        self.start_btn.setEnabled(False)
