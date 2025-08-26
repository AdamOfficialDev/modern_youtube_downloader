from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QDialog, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QScrollArea, QWidget
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
        
    def apply_professional_theme(self, is_dark_mode=False):
        """Apply professional theme styling to all sections"""
        if is_dark_mode:
            # Dark theme styling
            section_style = """
                QFrame[class="primary"] {
                    border: 2px solid #4a9eff;
                    border-radius: 8px;
                    background-color: rgba(74, 158, 255, 0.05);
                }
                QFrame[class="action"] {
                    border: 1px solid #40d472;
                    border-radius: 8px;
                    background-color: rgba(64, 212, 114, 0.05);
                }
                QFrame[class="normal"] {
                    border: 1px solid #555555;
                    border-radius: 8px;
                    background-color: rgba(64, 64, 64, 0.3);
                }
                QLabel[class="section_header"] {
                    color: #e9ecef;
                    font-weight: 600;
                }
                QLabel[class="primary_header"] {
                    color: #4a9eff;
                }
                QLabel[class="action_header"] {
                    color: #40d472;
                }
            """
        else:
            # Light theme styling  
            section_style = """
                QFrame[class="primary"] {
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    background-color: rgba(0, 123, 255, 0.02);
                }
                QFrame[class="action"] {
                    border: 1px solid #28a745;
                    border-radius: 8px;
                    background-color: rgba(40, 167, 69, 0.02);
                }
                QFrame[class="normal"] {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    background-color: rgba(248, 249, 250, 0.5);
                }
                QLabel[class="section_header"] {
                    color: #495057;
                    font-weight: 600;
                }
                QLabel[class="primary_header"] {
                    color: #007bff;
                }
                QLabel[class="action_header"] {
                    color: #28a745;
                }
            """
        
        # Apply styles to downloader tab
        self.parent.downloader_tab.setStyleSheet(section_style)

    @property
    def formats_list(self):
        return getattr(self.parent, 'formats_list', [])

    def setup_ui(self):
        # Create main layout for the tab
        main_layout = QVBoxLayout(self.parent.downloader_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins for scroll area
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create content widget that will be scrollable
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(16)  # Optimized spacing between sections
        layout.setContentsMargins(20, 20, 20, 20)  # Reduced margins for better space usage

        # URL Input Section - Professional styling
        url_section = self.create_section("Video URL", is_primary=True)
        url_content = QVBoxLayout()
        
        # URL input with professional styling
        url_input_container = QHBoxLayout()
        self.parent.url_input = QLineEdit()
        self.parent.url_input.setPlaceholderText("Enter video URL from any platform...")
        self.parent.url_input.setMinimumHeight(40)  # Professional height
        
        paste_button = QPushButton("Paste")
        paste_button.setMinimumHeight(40)
        paste_button.setMinimumWidth(80)
        paste_button.clicked.connect(self.paste_url)
        
        url_input_container.addWidget(self.parent.url_input)
        url_input_container.addWidget(paste_button)
        
        # Add subtle help text
        help_text = QLabel("Supports YouTube, Vimeo, Dailymotion, and other platforms")
        help_text.setStyleSheet("color: #666; font-size: 12px;")
        
        url_content.addLayout(url_input_container)
        url_content.addWidget(help_text)
        url_section.layout().addLayout(url_content)
        layout.addWidget(url_section)

        # Video Information Section - Clean professional layout
        info_section = self.create_section("Video Information")
        info_content = QHBoxLayout()
        info_content.setSpacing(30)
        
        # Left side - Video details with professional typography
        info_details = QVBoxLayout()
        info_details.setSpacing(12)
        
        self.parent.title_label = QLabel("Title: -")
        self.parent.duration_label = QLabel("Duration: -")
        self.parent.channel_label = QLabel("Channel: -")
        self.parent.views_label = QLabel("Views: -")

        # Apply professional styling to info labels
        for label in [self.parent.title_label, self.parent.duration_label,
                     self.parent.channel_label, self.parent.views_label]:
            label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: 500;
                    padding: 4px 0px;
                }
            """)
            info_details.addWidget(label)
        
        info_details.addStretch()
        
        # Right side - Thumbnail with professional frame
        thumbnail_container = QVBoxLayout()
        self.parent.thumbnail_label = QLabel()
        self.parent.thumbnail_label.setFixedSize(280, 158)  # 16:9 aspect ratio
        self.parent.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parent.thumbnail_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
        """)
        thumbnail_container.addWidget(self.parent.thumbnail_label)
        thumbnail_container.addStretch()
        
        info_content.addLayout(info_details, 2)  # 2/3 of space
        info_content.addLayout(thumbnail_container, 1)  # 1/3 of space
        info_section.layout().addLayout(info_content)
        layout.addWidget(info_section)

        # Download Options Section - Professional controls
        options_section = self.create_section("Download Options")
        options_content = QVBoxLayout()
        options_content.setSpacing(16)
        
        # Format selection row
        format_row = QHBoxLayout()
        format_label = QLabel("Quality:")
        format_label.setMinimumWidth(80)
        format_label.setStyleSheet("font-weight: 500;")
        
        self.parent.format_combo = QComboBox()
        self.parent.format_combo.setMinimumWidth(200)
        self.parent.format_combo.setMinimumHeight(36)
        self.parent.format_combo.setEnabled(False)
        
        self.show_formats_button = QPushButton("Advanced")
        self.show_formats_button.setMinimumHeight(36)
        self.show_formats_button.setMinimumWidth(100)
        self.show_formats_button.clicked.connect(self.show_formats_dialog)
        self.show_formats_button.setEnabled(False)
        
        format_row.addWidget(format_label)
        format_row.addWidget(self.parent.format_combo)
        format_row.addWidget(self.show_formats_button)
        format_row.addStretch()
        
        # MP3 option row
        audio_row = QHBoxLayout()
        audio_spacer = QLabel("")  # Alignment spacer
        audio_spacer.setMinimumWidth(80)
        
        self.parent.mp3_checkbox = QCheckBox("Extract audio only (MP3)")
        self.parent.mp3_checkbox.setEnabled(False)
        self.parent.mp3_checkbox.setStyleSheet("font-weight: 500;")
        
        audio_row.addWidget(audio_spacer)
        audio_row.addWidget(self.parent.mp3_checkbox)
        audio_row.addStretch()
        
        options_content.addLayout(format_row)
        options_content.addLayout(audio_row)
        options_section.layout().addLayout(options_content)
        layout.addWidget(options_section)

        # Output Location Section - Clean file selection
        output_section = self.create_section("Output Location")
        output_content = QHBoxLayout()
        
        output_label = QLabel("Folder:")
        output_label.setMinimumWidth(80)
        output_label.setStyleSheet("font-weight: 500;")
        
        self.parent.output_path = QLineEdit()
        self.parent.output_path.setText(os.path.join(os.path.expanduser("~"), "Videos", "Downloads"))
        self.parent.output_path.setMinimumHeight(36)
        
        browse_button = QPushButton("Browse")
        browse_button.setMinimumHeight(36)
        browse_button.setMinimumWidth(100)
        browse_button.clicked.connect(self.browse_output)
        
        output_content.addWidget(output_label)
        output_content.addWidget(self.parent.output_path)
        output_content.addWidget(browse_button)
        
        output_section.layout().addLayout(output_content)
        layout.addWidget(output_section)

        # Download Controls Section - Professional action area
        controls_section = self.create_section("Download", is_action=True)
        controls_content = QVBoxLayout()
        controls_content.setSpacing(12)
        
        # Progress bar - initially hidden
        self.parent.progress_bar = QProgressBar()
        self.parent.progress_bar.setMinimumHeight(8)
        self.parent.progress_bar.hide()
        
        # Status label with professional styling
        self.parent.status_label = QLabel("")
        self.parent.status_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: #666;
                padding: 4px 0px;
            }
        """)
        
        # Control buttons - professional layout
        button_row = QHBoxLayout()
        self.parent.download_button = QPushButton("Start Download")
        self.parent.download_button.setMinimumHeight(44)
        self.parent.download_button.setMinimumWidth(140)
        self.parent.download_button.clicked.connect(self.start_download)
        self.parent.download_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: 600;
            }
        """)
        
        self.parent.pause_button = QPushButton("Pause")
        self.parent.pause_button.setMinimumHeight(44)
        self.parent.pause_button.setMinimumWidth(100)
        self.parent.pause_button.clicked.connect(self.toggle_pause)
        self.parent.pause_button.setEnabled(False)
        
        button_row.addWidget(self.parent.download_button)
        button_row.addWidget(self.parent.pause_button)
        button_row.addStretch()
        
        controls_content.addWidget(self.parent.progress_bar)
        controls_content.addWidget(self.parent.status_label)
        controls_content.addLayout(button_row)
        
        controls_section.layout().addLayout(controls_content)
        layout.addWidget(controls_section)
        
        # Set the content widget to the scroll area
        scroll_area.setWidget(content_widget)
        
        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)

        # Connect URL input to video info fetcher
        self.parent.url_input.textChanged.connect(self.on_url_change)
    
    def create_section(self, title, is_primary=False, is_action=False):
        """Create a professional section container with optimized spacing"""
        section = QFrame()
        section.setFrameStyle(QFrame.Shape.StyledPanel)
        
        # Set class property for theming
        if is_primary:
            section.setProperty("class", "primary")
        elif is_action:
            section.setProperty("class", "action")
        else:
            section.setProperty("class", "normal")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 12, 16, 12)  # Reduced padding for compact layout
        layout.setSpacing(8)  # Tighter spacing within sections
        
        # Section header with professional typography
        header = QLabel(title)
        header.setProperty("class", "section_header")
        if is_primary:
            header.setProperty("class", "primary_header")
        elif is_action:
            header.setProperty("class", "action_header")
        
        # Base styling that works for both themes - more compact
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 4px;
            }
        """)
        
        layout.addWidget(header)
        return section

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
