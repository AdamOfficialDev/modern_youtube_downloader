from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QDialog, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
import os
import threading
import yt_dlp
import requests
import json
from PIL import Image
from io import BytesIO

class DownloadThread(QThread):
    progress_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, url, format_id, output_path, convert_to_mp3=False):
        super().__init__()
        self.url = url
        self.format_id = format_id
        self.output_path = output_path
        self.convert_to_mp3 = convert_to_mp3
        self.paused = False
        self._stop = False

    def run(self):
        try:
            output_template = os.path.join(self.output_path, '%(title)s.%(ext)s')

            # Base options for both formats
            ydl_opts = {
                'outtmpl': output_template,
                'progress_hooks': [self._progress_hook],
                'retries': 10,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'nocheckcertificate': True
            }

            # Add format-specific options
            if self.convert_to_mp3:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                })
            else:
                ydl_opts['format'] = self.format_id

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
                        self.status_signal.emit("Using browser cookies for authentication")
                except Exception as e:
                    self.status_signal.emit(f"Warning: Could not load cookies: {str(e)}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            self.status_signal.emit("Download completed!")
            self.finished.emit()

        except Exception as e:
            self.status_signal.emit(f"Error: {str(e)}")

    def _progress_hook(self, d):
        if self._stop:
            raise Exception("Download stopped")

        while self.paused:
            if self._stop:
                raise Exception("Download stopped")
            QThread.msleep(100)

        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            speed = d.get('speed', 0)

            if total > 0:  # Only calculate percent if we have a valid total
                percent = (downloaded / total) * 100
            else:
                percent = 0

            progress_data = {
                'status': 'Downloading',
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': speed,
                'eta': d.get('eta', 0),
                'percent': percent
            }
            self.progress_signal.emit(progress_data)

        elif d['status'] == 'finished':
            if self.convert_to_mp3:
                self.status_signal.emit('Download completed, converting to MP3...')
            else:
                self.status_signal.emit('Download completed, processing file...')

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self._stop = True
        self.resume()  # Resume if paused to allow the stop to process

class DownloaderTab:
    def __init__(self, parent):
        self.parent = parent
        self.setup_ui()

    @property
    def formats_list(self):
        return getattr(self.parent, 'formats_list', [])

    def setup_ui(self):
        layout = QVBoxLayout(self.parent.downloader_tab)

        # URL Input Section
        url_frame = QFrame()
        url_layout = QHBoxLayout(url_frame)

        url_label = QLabel("Video URL (supports YouTube, Vimeo, Dailymotion, etc.):")
        self.parent.url_input = QLineEdit()
        self.parent.url_input.setPlaceholderText("Enter video URL from any platform...")
        paste_button = QPushButton("Paste")
        paste_button.clicked.connect(self.paste_url)

        url_layout.addWidget(url_label)
        url_layout.addWidget(self.parent.url_input)
        url_layout.addWidget(paste_button)

        layout.addWidget(url_frame)

        # Video Info Section
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        info_layout = QHBoxLayout(info_frame)

        # Left side - Info labels
        info_labels = QVBoxLayout()
        self.parent.title_label = QLabel("Title: -")
        self.parent.duration_label = QLabel("Duration: -")
        self.parent.channel_label = QLabel("Channel: -")
        self.parent.views_label = QLabel("Views: -")

        for label in [self.parent.title_label, self.parent.duration_label,
                     self.parent.channel_label, self.parent.views_label]:
            info_labels.addWidget(label)

        # Right side - Thumbnail
        self.parent.thumbnail_label = QLabel()
        self.parent.thumbnail_label.setFixedSize(320, 180)
        self.parent.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_layout.addLayout(info_labels)
        info_layout.addWidget(self.parent.thumbnail_label)

        layout.addWidget(info_frame)

        # Format Selection
        format_frame = QFrame()
        format_layout = QHBoxLayout(format_frame)

        format_label = QLabel("Format:")
        self.parent.format_combo = QComboBox()
        self.parent.format_combo.setMinimumWidth(200)
        self.parent.format_combo.setEnabled(False)
        self.show_formats_button = QPushButton("Show All Formats")
        self.show_formats_button.clicked.connect(self.show_formats_dialog)
        self.show_formats_button.setEnabled(False)  # Initially disabled

        # MP3 Conversion Option
        self.parent.mp3_checkbox = QCheckBox("Convert to MP3")
        self.parent.mp3_checkbox.setEnabled(False)

        format_layout.addWidget(format_label)
        format_layout.addWidget(self.parent.format_combo)
        format_layout.addWidget(self.show_formats_button)
        format_layout.addWidget(self.parent.mp3_checkbox)
        format_layout.addStretch()

        layout.addWidget(format_frame)

        # Output Directory
        output_frame = QFrame()
        output_layout = QHBoxLayout(output_frame)

        output_label = QLabel("Save to:")
        self.parent.output_path = QLineEdit()
        self.parent.output_path.setText(os.path.join(os.path.expanduser("~"), "Videos\\Captures"))
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_output)

        output_layout.addWidget(output_label)
        output_layout.addWidget(self.parent.output_path)
        output_layout.addWidget(browse_button)

        layout.addWidget(output_frame)

        # Progress Section
        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)

        self.parent.progress_bar = QProgressBar()
        self.parent.progress_bar.hide()  # Sembunyikan progress bar

        self.parent.status_label = QLabel("")

        control_layout = QHBoxLayout()
        self.parent.download_button = QPushButton("Download")
        self.parent.download_button.clicked.connect(self.start_download)
        self.parent.pause_button = QPushButton("Pause")
        self.parent.pause_button.clicked.connect(self.toggle_pause)
        self.parent.pause_button.setEnabled(False)

        control_layout.addWidget(self.parent.download_button)
        control_layout.addWidget(self.parent.pause_button)
        control_layout.addStretch()

        progress_layout.addWidget(self.parent.progress_bar)
        progress_layout.addWidget(self.parent.status_label)
        progress_layout.addLayout(control_layout)

        layout.addWidget(progress_frame)
        layout.addStretch()

        # Connect URL input to video info fetcher
        self.parent.url_input.textChanged.connect(self.on_url_change)

    def paste_url(self):
        clipboard = QApplication.clipboard()
        self.parent.url_input.setText(clipboard.text())

    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(
            self.parent,
            "Select Output Directory",
            self.parent.output_path.text(),
            QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self.parent.output_path.setText(dir_path)

    def on_url_change(self):
        # Reset progress dan status ketika URL berubah
        self.parent.progress_bar.setValue(0)
        self.parent.progress_bar.hide()  # Sembunyikan progress bar
        self.parent.download_button.setEnabled(False)
        self.parent.format_combo.clear()

        url = self.parent.url_input.text().strip()
        if url:
            self.parent.status_label.setText("Fetching video info...")
            threading.Thread(target=self.fetch_video_info, daemon=True).start()
        else:
            self.parent.status_label.setText("")
            self.parent.title_label.setText("Title: -")
            self.parent.duration_label.setText("Duration: -")
            self.parent.channel_label.setText("Channel: -")
            self.parent.views_label.setText("Views: -")

    def fetch_video_info(self):
        url = self.parent.url_input.text().strip()
        try:
            # Base options
            ydl_opts = {'quiet': True}

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
                        self.parent.status_label.setText("Using browser cookies for authentication...")
                except Exception as e:
                    print(f"Warning: Could not load cookies: {str(e)}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Update info labels
                self.parent.title_label.setText(f"Title: {info.get('title', '-')}")
                duration = info.get('duration', 0)
                self.parent.duration_label.setText(
                    f"Duration: {duration//60}:{duration%60:02d}")
                self.parent.channel_label.setText(
                    f"Channel: {info.get('uploader', '-')}")
                self.parent.views_label.setText(
                    f"Views: {info.get('view_count', 0):,}")

                # Update formats
                self.parent.formats_list = info.get('formats', [])
                self.update_format_combo()

                # Update show formats button
                self.update_formats_button()

                # Update thumbnail
                if 'thumbnail' in info:
                    response = requests.get(info['thumbnail'])
                    img = Image.open(BytesIO(response.content))
                    img = img.resize((320, 180))
                    img_bytes = BytesIO()
                    img.save(img_bytes, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_bytes.getvalue())
                    self.parent.thumbnail_label.setPixmap(pixmap)

            self.parent.status_label.setText("Ready to download")  # Update status setelah fetch berhasil

        except Exception as e:
            error_msg = str(e)
            if "Sign in to confirm you're not a bot" in error_msg:
                self.parent.status_label.setText("Error: Anti-bot protection triggered. Please set up browser cookies in Settings tab.")
            elif "Unsupported URL" in error_msg:
                self.parent.status_label.setText("Error: Unsupported URL. Please check the URL and try again.")
            else:
                self.parent.status_label.setText(f"Error: {error_msg}")
            self.parent.download_button.setEnabled(False)

    def update_format_combo(self):
        self.parent.format_combo.clear()

        # Add formats to combo box
        has_audio = False
        for f in self.formats_list:
            format_id = f.get('format_id', '')
            ext = f.get('ext', '')
            res = f.get('resolution', 'N/A')
            format_note = f.get('format_note', '')

            # Check if format contains audio
            if f.get('acodec', 'none') != 'none':
                has_audio = True

            # Create format description
            desc = f"{res} ({format_note})" if format_note else res
            if ext:
                desc = f"{desc} - {ext}"

            self.parent.format_combo.addItem(desc, format_id)

        # Enable download button if formats are available
        self.parent.download_button.setEnabled(self.parent.format_combo.count() > 0)

        # Enable MP3 checkbox only if audio formats are available
        self.parent.mp3_checkbox.setEnabled(has_audio)

    def start_download(self):
        url = self.parent.url_input.text().strip()

        if not url:
            QMessageBox.warning(
                self.parent,
                "Error",
                "Please enter a video URL",
                QMessageBox.StandardButton.Ok
            )
            return

        format_id = self.parent.format_combo.currentText().split(" - ")[0]
        if not format_id:
            QMessageBox.warning(
                self.parent,
                "Error",
                "Please select a format",
                QMessageBox.StandardButton.Ok
            )
            return

        output_path = self.parent.output_path.text()
        if not output_path:
            QMessageBox.warning(
                self.parent,
                "Error",
                "Please select an output directory",
                QMessageBox.StandardButton.Ok
            )
            return

        # Create download thread
        self.parent.download_thread = DownloadThread(
            url, format_id, output_path,
            self.parent.mp3_checkbox.isChecked()
        )

        # Connect signals
        self.parent.download_thread.progress_signal.connect(self.parent.update_progress)
        self.parent.download_thread.status_signal.connect(self.parent.update_status)
        self.parent.download_thread.finished.connect(self.parent.on_download_complete)

        # Update UI
        self.parent.progress_bar.setValue(0)
        self.parent.progress_bar.show()
        self.parent.download_button.setEnabled(False)
        self.parent.pause_button.setEnabled(True)
        self.parent.pause_button.setText("Pause")

        # Start download
        self.parent.download_thread.start()

    def toggle_pause(self):
        if not hasattr(self.parent, 'download_thread'):
            return

        if self.parent.download_thread.isRunning():
            if self.parent.download_thread.paused:
                self.parent.download_thread.resume()
                self.parent.pause_button.setText("Pause")
            else:
                self.parent.download_thread.pause()
                self.parent.pause_button.setText("Resume")

    def show_formats_dialog(self):
        if not self.formats_list:
            QMessageBox.warning(
                self.parent,
                "Error",
                "No formats available. Please enter a valid video URL first.",
                QMessageBox.StandardButton.Ok
            )
            return

        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Available Formats")
        dialog.setMinimumWidth(800)

        layout = QVBoxLayout(dialog)

        # Add selection mode options
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Selection Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single Format", "Separate Video + Audio"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Create trees for video and audio formats
        self.video_tree = QTreeWidget()
        self.audio_tree = QTreeWidget()

        for tree in [self.video_tree, self.audio_tree]:
            tree.setHeaderLabels([
                "Format ID", "Extension", "Resolution/Bitrate",
                "FPS", "File Size", "Codec"
            ])
            tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        # Populate trees
        video_formats = []
        audio_formats = []

        for f in self.formats_list:
            filesize = f.get('filesize', 0)
            if filesize is not None and filesize > 0:
                filesize = f"{filesize/1024/1024:.1f} MB"
            else:
                filesize = "N/A"

            is_video = f.get('vcodec') != 'none'
            resolution = f.get('resolution', 'N/A')

            if not is_video:
                resolution = f"{f.get('abr', 'N/A')}kbps"

            fps = f.get('fps', 'N/A')
            if fps == 'N/A' and not is_video:
                fps = '-'

            item = QTreeWidgetItem([
                f.get('format_id', 'N/A'),
                f.get('ext', 'N/A'),
                resolution,
                str(fps),
                filesize,
                f.get('vcodec', 'N/A') if is_video else f.get('acodec', 'N/A')
            ])

            if is_video:
                video_formats.append(item)
            else:
                audio_formats.append(item)

        # Sort formats by quality
        video_formats.sort(key=lambda x: self._get_resolution_value(x.text(2)), reverse=True)
        audio_formats.sort(key=lambda x: self._get_bitrate_value(x.text(2)), reverse=True)

        self.video_tree.addTopLevelItems(video_formats)
        self.audio_tree.addTopLevelItems(audio_formats)

        # Stack the trees
        self.tree_stack = QVBoxLayout()

        self.video_label = QLabel("Video Formats:")
        self.audio_label = QLabel("Audio Formats:")

        self.tree_stack.addWidget(self.video_label)
        self.tree_stack.addWidget(self.video_tree)
        self.tree_stack.addWidget(self.audio_label)
        self.tree_stack.addWidget(self.audio_tree)

        layout.addLayout(self.tree_stack)

        # Add buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")

        ok_button.clicked.connect(lambda: self._handle_format_selection(dialog))
        cancel_button.clicked.connect(dialog.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Connect mode change
        self.mode_combo.currentTextChanged.connect(self._update_selection_mode)
        self._update_selection_mode(self.mode_combo.currentText())

        dialog.exec()

    def _handle_format_selection(self, dialog):
        mode = self.mode_combo.currentText()

        if mode == "Single Format":
            selected_items = self.video_tree.selectedItems()
            if not selected_items:
                QMessageBox.warning(
                    self.parent,
                    "Selection Error",
                    "Please select a format",
                    QMessageBox.StandardButton.Ok
                )
                return
            format_id = selected_items[0].text(0)
            self.parent.format_combo.clear()
            self.parent.format_combo.addItem(format_id, format_id)
            self.parent.format_combo.setCurrentText(format_id)

        else:
            video_items = self.video_tree.selectedItems()
            audio_items = self.audio_tree.selectedItems()

            if not video_items or not audio_items:
                QMessageBox.warning(
                    self.parent,
                    "Selection Error",
                    "Please select both video and audio formats",
                    QMessageBox.StandardButton.Ok
                )
                return

            video_id = video_items[0].text(0)
            audio_id = audio_items[0].text(0)
            combined_format = f"{video_id}+{audio_id}"
            self.parent.format_combo.clear()
            self.parent.format_combo.addItem(combined_format, combined_format)
            self.parent.format_combo.setCurrentText(combined_format)

        dialog.accept()

    def _update_selection_mode(self, mode):
        if mode == "Single Format":
            self.video_tree.clear()
            all_formats = []
            for f in self.formats_list:
                filesize = f.get('filesize', 0)
                if filesize is not None and filesize > 0:
                    filesize = f"{filesize/1024/1024:.1f} MB"
                else:
                    filesize = "N/A"

                is_video = f.get('vcodec') != 'none'
                resolution = f.get('resolution', 'N/A')

                if not is_video:
                    resolution = f"{f.get('abr', 'N/A')}kbps"

                fps = f.get('fps', 'N/A')
                if fps == 'N/A' and not is_video:
                    fps = '-'

                item = QTreeWidgetItem([
                    f.get('format_id', 'N/A'),
                    f.get('ext', 'N/A'),
                    resolution,
                    str(fps),
                    filesize,
                    f.get('vcodec', 'N/A') if is_video else f.get('acodec', 'N/A')
                ])
                all_formats.append(item)

            # Sort formats
            all_formats.sort(key=lambda x: (
                self._get_resolution_value(x.text(2)),
                self._get_bitrate_value(x.text(2))
            ), reverse=True)

            self.video_tree.addTopLevelItems(all_formats)
            self.audio_tree.setVisible(False)
            self.audio_label.setVisible(False)
            self.video_label.setText("Available Formats:")
        else:
            self.video_label.setText("Video Formats:")
            self.audio_tree.setVisible(True)
            self.audio_label.setVisible(True)

    def _get_resolution_value(self, resolution):
        if resolution == 'N/A':
            return -1
        try:
            return int(resolution.split('p')[0])
        except:
            return -1

    def _get_bitrate_value(self, bitrate):
        if bitrate == 'N/A':
            return -1
        try:
            return float(bitrate.replace('kbps', ''))
        except:
            return -1

    def update_formats_button(self):
        has_formats = hasattr(self.parent, 'formats_list') and len(self.parent.formats_list) > 0
        self.show_formats_button.setEnabled(has_formats)
