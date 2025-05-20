from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QCheckBox, QLineEdit, QPushButton, QApplication,
                             QWidget, QMessageBox, QGroupBox, QStyleFactory,
                             QProgressDialog, QScrollArea, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
import json
import os
import yt_dlp
import requests
import subprocess
import platform
import re

class SettingsTab:
    def __init__(self, parent=None):
        self.parent = parent
        self.current_version = self.get_ytdlp_version()
        self.setup_ui()

    def get_ytdlp_version(self):
        try:
            # Menggunakan subprocess untuk mendapatkan versi
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
            return result.stdout.strip()
        except Exception:
            return "Unknown"

    def setup_ui(self):
        # Buat main widget dan layout untuk scroll area
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Theme settings
        theme_group = QGroupBox("")
        theme_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 0.5em;
                padding-top: 5px;
            }
        """)
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setSpacing(15)

        # Custom header for theme settings
        theme_header_container = QFrame()
        theme_header_layout = QHBoxLayout(theme_header_container)
        theme_header_layout.setContentsMargins(0, 0, 0, 0)

        theme_header = QLabel("🎨 Theme Settings")
        theme_header.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        theme_header_layout.addWidget(theme_header)
        theme_header_layout.addStretch()
        theme_layout.addWidget(theme_header_container)

        # Theme controls frame
        theme_frame = QFrame()
        theme_box_layout = QHBoxLayout(theme_frame)
        theme_box_layout.setContentsMargins(15, 12, 15, 12)

        # Theme controls
        theme_label = QLabel("Dark Theme:")
        theme_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        theme_label.setMinimumWidth(100)
        self.parent.dark_mode_checkbox = QCheckBox()
        self.parent.dark_mode_checkbox.setChecked(True)
        self.parent.dark_mode_checkbox.stateChanged.connect(self.toggle_theme)
        self.parent.dark_mode_checkbox.stateChanged.connect(self.update_notice_colors)

        theme_box_layout.addWidget(theme_label)
        theme_box_layout.addWidget(self.parent.dark_mode_checkbox)
        theme_box_layout.addStretch()

        theme_layout.addWidget(theme_frame)
        layout.addWidget(theme_group)

        # API Key settings
        api_group = QGroupBox("")
        api_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 0.5em;
                padding-top: 5px;
            }
        """)
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(15)

        # Custom header for API settings
        api_header_container = QFrame()
        api_header_layout = QHBoxLayout(api_header_container)
        api_header_layout.setContentsMargins(0, 0, 0, 0)

        api_header = QLabel("🔑 YouTube API Settings")
        api_header.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        api_header_layout.addWidget(api_header)
        api_header_layout.addStretch()
        api_layout.addWidget(api_header_container)

        # Notice section
        self.notice_box = QGroupBox("Notice")  # Make it instance variable
        self.notice_label = QLabel()  # Make it instance variable
        self.update_notice_colors(self.parent.dark_mode_checkbox.isChecked())  # Initial color setup

        notice_layout = QVBoxLayout()
        notice_layout.addWidget(self.notice_label)
        self.notice_box.setLayout(notice_layout)
        api_layout.addWidget(self.notice_box)

        # Add some spacing between notice and API controls
        api_layout.addSpacing(10)

        # API controls section
        self.api_box = QGroupBox("API Configuration")  # Make it instance variable
        self.api_box.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        api_box_layout = QVBoxLayout()
        api_box_layout.setSpacing(15)  # Increase spacing between elements

        # API Status Label with icon
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(5, 5, 5, 5)
        self.parent.api_status_label = QLabel("API Status: Not Connected")
        self.parent.api_status_label.setStyleSheet("""
            QLabel {
                padding: 8px 15px;
                background-color: rgba(255, 68, 68, 0.1);
                border: 1px solid #ff4444;
                border-radius: 4px;
                color: #ff4444;
                font-weight: bold;
            }
        """)
        status_layout.addWidget(self.parent.api_status_label)
        status_layout.addStretch()
        api_box_layout.addLayout(status_layout)

        # Add link to Google Console with improved styling
        console_link_label = QLabel("""
            <div style='padding: 10px; border-radius: 4px; border: 1px solid #7aa2f7;'>
                🔗 Get your API key from <a style='color: #7aa2f7; text-decoration: none; font-weight: bold;'
                href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">Google Cloud Console</a>
            </div>
        """)
        console_link_label.setOpenExternalLinks(True)
        console_link_label.setTextFormat(Qt.TextFormat.RichText)
        api_box_layout.addWidget(console_link_label)

        # API Label and Input row with improved styling
        api_input_frame = QFrame()
        api_input_frame.setStyleSheet("""
            QFrame {
                border-radius: 4px;
                padding: 5px;
            }
        """)
        api_input_layout = QHBoxLayout(api_input_frame)
        api_input_layout.setContentsMargins(10, 10, 10, 10)

        api_label = QLabel("API Key:")
        api_label.setStyleSheet("QLabel { font-weight: bold; }")
        self.parent.api_key_input = QLineEdit()
        self.parent.api_key_input.setPlaceholderText("Enter your YouTube API Key")
        self.parent.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.parent.api_key_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #7aa2f7;
                border-radius: 4px;
                background: transparent;
                selection-background-color: #7aa2f7;
            }
            QLineEdit:focus {
                border: 2px solid #7aa2f7;
                background: rgba(122, 162, 247, 0.1);
            }
        """)

        api_input_layout.addWidget(api_label)
        api_input_layout.addWidget(self.parent.api_key_input)
        api_box_layout.addWidget(api_input_frame)

        # Show/Hide and Save buttons row with improved styling
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(5, 5, 5, 5)
        self.parent.show_api_button = QPushButton("🙈 Show")
        save_api_button = QPushButton("💾 Save API Key")

        button_style = """
            QPushButton {
                padding: 8px 20px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
            QPushButton:pressed {
                background-color: #6992e7;
                padding-top: 9px;
                padding-bottom: 7px;
            }
        """

        self.parent.show_api_button.setStyleSheet(button_style)
        save_api_button.setStyleSheet(button_style)

        buttons_layout.addWidget(self.parent.show_api_button)
        buttons_layout.addWidget(save_api_button)
        buttons_layout.addStretch()

        # Connect button signals
        self.parent.show_api_button.clicked.connect(self.toggle_api_visibility)
        save_api_button.clicked.connect(self._save_api_key)

        api_box_layout.addLayout(buttons_layout)

        # Load current API key
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.parent.api_key_input.setText(config.get('youtube_api_key', ''))
        except:
            pass

        self.api_box.setLayout(api_box_layout)
        api_layout.addWidget(self.api_box)

        # Add help text with improved styling
        help_text = QLabel("""
            <div style='padding: 10px; border-radius: 4px;'>
                ℹ️ <span style='color: #808080;'>To use the search feature, you need a YouTube Data API key.
                Get one from Google Cloud Console.</span>
            </div>
        """)
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        api_layout.addWidget(help_text)

        layout.addWidget(api_group)

        # FFmpeg settings
        ffmpeg_group = QGroupBox("")
        ffmpeg_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 0.5em;
                padding-top: 5px;
            }
        """)
        ffmpeg_layout = QVBoxLayout(ffmpeg_group)
        ffmpeg_layout.setSpacing(15)

        # Custom header for FFmpeg settings
        ffmpeg_header_container = QFrame()
        ffmpeg_header_layout = QHBoxLayout(ffmpeg_header_container)
        ffmpeg_header_layout.setContentsMargins(0, 0, 0, 0)

        ffmpeg_header = QLabel("🎥 FFmpeg Settings")
        ffmpeg_header.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        ffmpeg_header_layout.addWidget(ffmpeg_header)
        ffmpeg_header_layout.addStretch()
        ffmpeg_layout.addWidget(ffmpeg_header_container)

        # FFmpeg notice
        self.ffmpeg_notice = QLabel()
        self.ffmpeg_notice.setStyleSheet("""
            QLabel {
                background-color: rgba(122, 162, 247, 0.1);
                border: 1px solid #7aa2f7;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
                color: #7aa2f7;
            }
        """)
        self.ffmpeg_notice.setWordWrap(True)
        self.ffmpeg_notice.setTextFormat(Qt.TextFormat.RichText)
        self.update_ffmpeg_notice()
        ffmpeg_layout.addWidget(self.ffmpeg_notice)

        # FFmpeg controls frame
        ffmpeg_frame = QFrame()
        ffmpeg_box_layout = QVBoxLayout(ffmpeg_frame)
        ffmpeg_box_layout.setContentsMargins(15, 12, 15, 12)
        ffmpeg_box_layout.setSpacing(15)  # Add spacing between elements

        # FFmpeg status with better styling
        ffmpeg_status_layout = QHBoxLayout()
        ffmpeg_status_label = QLabel("Status")
        ffmpeg_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #c0caf5;
            }
        """)
        ffmpeg_status_label.setMinimumWidth(100)

        is_installed = bool(self.parent.config.get('ffmpeg_path'))
        status_text = "✅ Installed" if is_installed else "❌ Not Installed"
        status_color = "#9ece6a" if is_installed else "#f7768e"

        self.ffmpeg_status_value = QLabel(status_text)
        self.ffmpeg_status_value.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                color: {status_color};
                font-weight: bold;
            }}
        """)

        ffmpeg_status_layout.addWidget(ffmpeg_status_label)
        ffmpeg_status_layout.addWidget(self.ffmpeg_status_value)
        ffmpeg_status_layout.addStretch()

        # FFmpeg path with better styling
        ffmpeg_path_layout = QHBoxLayout()
        ffmpeg_path_label = QLabel("Location")
        ffmpeg_path_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #c0caf5;
            }
        """)
        ffmpeg_path_label.setMinimumWidth(100)

        path_text = self.parent.config.get('ffmpeg_path', '—')
        self.ffmpeg_path_value = QLabel(path_text)
        self.ffmpeg_path_value.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #a9b1d6;
            }
        """)
        self.ffmpeg_path_value.setWordWrap(True)

        ffmpeg_path_layout.addWidget(ffmpeg_path_label)
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_value)
        ffmpeg_path_layout.addStretch()

        # FFmpeg actions with better styling
        ffmpeg_actions_layout = QHBoxLayout()

        self.remove_ffmpeg_btn = QPushButton("🗑️ Remove FFmpeg")
        self.remove_ffmpeg_btn.setStyleSheet("""
            QPushButton {
                background-color: #f7768e;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #ff8b98;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #666666;
            }
        """)
        self.remove_ffmpeg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_ffmpeg_btn.clicked.connect(self.remove_ffmpeg)
        self.remove_ffmpeg_btn.setEnabled(bool(self.parent.config.get('ffmpeg_path')))

        ffmpeg_actions_layout.addWidget(self.remove_ffmpeg_btn)
        ffmpeg_actions_layout.addStretch()

        # Add all layouts to ffmpeg frame
        ffmpeg_box_layout.addLayout(ffmpeg_status_layout)
        ffmpeg_box_layout.addLayout(ffmpeg_path_layout)
        ffmpeg_box_layout.addLayout(ffmpeg_actions_layout)

        ffmpeg_layout.addWidget(ffmpeg_frame)
        layout.addWidget(ffmpeg_group)

        # YouTube Authentication Settings
        auth_group = QGroupBox("")
        auth_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 0.5em;
                padding-top: 5px;
            }
        """)
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(15)

        # Custom header for YouTube Authentication
        auth_header_container = QFrame()
        auth_header_layout = QHBoxLayout(auth_header_container)
        auth_header_layout.setContentsMargins(0, 0, 0, 0)

        auth_header = QLabel("🔐 YouTube Authentication")
        auth_header.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        auth_header_layout.addWidget(auth_header)
        auth_header_layout.addStretch()
        auth_layout.addWidget(auth_header_container)

        # Authentication notice
        auth_notice = QLabel("""
            <div style='margin: 5px;'>
                <span style='color: #f7768e;'>⚠️ YouTube requires authentication to download some videos</span><br><br>
                To bypass YouTube's anti-bot protection, this app can use cookies from your browser.
                This allows downloads without triggering the "Sign in to confirm you're not a robot" message.
                <br><br>
                <span style='color: #7aa2f7;'>ℹ️ Your browser cookies will be extracted and saved locally. No data is sent to any server.</span>
            </div>
        """)
        auth_notice.setStyleSheet("""
            QLabel {
                background-color: rgba(122, 162, 247, 0.1);
                border: 1px solid #7aa2f7;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
            }
        """)
        auth_notice.setWordWrap(True)
        auth_notice.setTextFormat(Qt.TextFormat.RichText)
        auth_layout.addWidget(auth_notice)

        # Browser selection frame
        browser_frame = QFrame()
        browser_layout = QVBoxLayout(browser_frame)
        browser_layout.setContentsMargins(15, 12, 15, 12)
        browser_layout.setSpacing(15)

        # Cookie status
        cookie_status_layout = QHBoxLayout()
        cookie_status_label = QLabel("Status")
        cookie_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #c0caf5;
            }
        """)
        cookie_status_label.setMinimumWidth(100)

        # Check if cookies are configured
        has_cookies = bool(self.parent.config.get('youtube_cookies_path'))
        status_text = "✅ Configured" if has_cookies else "❌ Not Configured"
        status_color = "#9ece6a" if has_cookies else "#f7768e"

        self.cookie_status_value = QLabel(status_text)
        self.cookie_status_value.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                color: {status_color};
                font-weight: bold;
            }}
        """)

        cookie_status_layout.addWidget(cookie_status_label)
        cookie_status_layout.addWidget(self.cookie_status_value)
        cookie_status_layout.addStretch()
        browser_layout.addLayout(cookie_status_layout)

        # Browser selection
        browser_selection_layout = QHBoxLayout()
        browser_label = QLabel("Browser:")
        browser_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #c0caf5;
            }
        """)
        browser_label.setMinimumWidth(100)

        self.browser_combo = QComboBox()

        # Get available browsers based on platform
        browsers = self.get_available_browsers()
        self.browser_combo.addItems(browsers)

        # Set current browser if configured
        current_browser = self.parent.config.get('youtube_cookies_browser')
        if current_browser and current_browser in browsers:
            self.browser_combo.setCurrentText(current_browser)

        self.browser_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #7aa2f7;
                border-radius: 4px;
                background: transparent;
                min-width: 200px;
            }
        """)

        browser_selection_layout.addWidget(browser_label)
        browser_selection_layout.addWidget(self.browser_combo)
        browser_selection_layout.addStretch()
        browser_layout.addLayout(browser_selection_layout)

        # Extract cookies button
        extract_button = QPushButton("🔄 Extract Cookies")
        extract_button.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
            QPushButton:pressed {
                background-color: #6992e7;
                padding-top: 9px;
                padding-bottom: 7px;
            }
        """)
        extract_button.clicked.connect(self.extract_cookies)

        browser_layout.addWidget(extract_button)
        auth_layout.addWidget(browser_frame)

        # Add help text
        help_text = QLabel("""
            <div style='padding: 10px; border-radius: 4px;'>
                ℹ️ <span style='color: #808080;'>Make sure you're logged into YouTube in your selected browser before extracting cookies.</span>
            </div>
        """)
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        auth_layout.addWidget(help_text)

        layout.addWidget(auth_group)

        # yt-dlp version settings
        ytdlp_group = QGroupBox("")
        ytdlp_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 0.5em;
                padding-top: 5px;
            }
        """)
        ytdlp_layout = QVBoxLayout(ytdlp_group)
        ytdlp_layout.setSpacing(15)

        # Custom header for yt-dlp version
        header_container = QFrame()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("⚡ yt-dlp Version")
        header_label.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
            }
        """)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        ytdlp_layout.addWidget(header_container)

        # Version info container
        version_container = QFrame()
        version_container.setStyleSheet("""
            QFrame {
                border: 1px solid #7aa2f7;
                border-radius: 4px;
            }
        """)
        version_layout = QHBoxLayout(version_container)
        version_layout.setContentsMargins(15, 12, 15, 12)

        # Version info with icon and larger text
        self.current_version_value = QLabel(f"""
            <div style='color: #7aa2f7; font-size: 14px;'>
                📦 <span style='font-weight: bold;'>Current Version:</span>
                <span style='
                    padding: 4px 10px;
                    border-radius: 4px;
                    border: 1px solid #7aa2f7;
                    color: #7aa2f7;
                    font-family: monospace;
                    font-weight: bold;
                '>{self.current_version}</span>
            </div>
        """)
        self.current_version_value.setTextFormat(Qt.TextFormat.RichText)

        # Check update button with improved style
        check_update_btn = QPushButton("🔄 Check for Updates")
        check_update_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
            QPushButton:pressed {
                background-color: #6992e7;
                padding-top: 9px;
                padding-bottom: 7px;
            }
        """)
        check_update_btn.clicked.connect(self.check_yt_dlp_version)

        version_layout.addWidget(self.current_version_value)
        version_layout.addWidget(check_update_btn)
        version_layout.addStretch()

        ytdlp_layout.addWidget(version_container)

        # Add help text with larger font
        help_text = QLabel("""
            <div style='padding: 10px; font-size: 13px;'>
                ℹ️ <span style='color: #808080;'>yt-dlp is the core downloader engine.
                Keep it updated for the best performance and compatibility.</span>
            </div>
        """)
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        ytdlp_layout.addWidget(help_text)

        ytdlp_group.setLayout(ytdlp_layout)
        layout.addWidget(ytdlp_group)

        # Add stretch to push everything to the top
        layout.addStretch()

        # Save button with improved style
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
            QPushButton:pressed {
                background-color: #6992e7;
                padding-top: 9px;
                padding-bottom: 7px;
            }
        """)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # Load saved settings
        self._load_settings()

        # Buat scroll area
        scroll = QScrollArea()
        scroll.setWidget(main_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Set scroll area sebagai widget utama
        main_layout = QVBoxLayout(self.parent.settings_tab)
        main_layout.addWidget(scroll)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def toggle_theme(self, state):
        if state:
            # Dark theme
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(31, 31, 46))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 63))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 63))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 63))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Link, QColor(122, 162, 247))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(122, 162, 247))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

            style = """
                QMainWindow, QDialog, QWidget {
                    background: #1e1e2e;
                    color: white;
                }
                QLabel {
                    color: white;
                    font-size: 13px;
                }
                QPushButton {
                    background-color: #444b6e;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background-color: #525d89;
                    padding: 7px 20px 9px 20px;
                }
                QPushButton:pressed {
                    background-color: #373e5c;
                    padding: 9px 20px 7px 20px;
                }
                QPushButton:disabled {
                    background-color: #45475a;
                    color: #888888;
                }
                QLineEdit {
                    padding: 8px 12px;
                    border: 2px solid #45475a;
                    border-radius: 6px;
                    background: #2a2a3f;
                    color: white;
                    font-size: 13px;
                    selection-background-color: #7aa2f7;
                }
                QLineEdit:focus {
                    border: 2px solid #7aa2f7;
                    background: #2d2d44;
                }
                QLineEdit:hover {
                    border: 2px solid #585b70;
                }
                QProgressBar {
                    border: none;
                    border-radius: 6px;
                    background-color: #2a2a3f;
                    text-align: center;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #7aa2f7;
                    border-radius: 6px;
                }
                QTabWidget::pane {
                    border: 2px solid #45475a;
                    border-radius: 8px;
                    top: -2px;
                }
                QTabBar::tab {
                    background: #2a2a3f;
                    color: #cdd6f4;
                    padding: 10px 25px;
                    border: 2px solid #45475a;
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    font-size: 13px;
                    margin-right: 4px;
                }
                QTabBar::tab:selected {
                    background: #7aa2f7;
                    color: white;
                    border-color: #7aa2f7;
                }
                QTabBar::tab:disabled {
                    background: #181825;
                    color: #6c7086;
                    border-color: #313244;
                }
                QTabBar::tab:hover:!selected {
                    background: #45475a;
                    border-color: #585b70;
                }
                QTreeWidget {
                    background: #2a2a3f;
                    color: white;
                    border: 2px solid #45475a;
                    border-radius: 8px;
                    padding: 5px;
                    font-size: 13px;
                }
                QTreeWidget::item {
                    padding: 5px;
                    border-radius: 4px;
                }
                QTreeWidget::item:selected {
                    background: #7aa2f7;
                    color: white;
                }
                QTreeWidget::item:hover {
                    background: #45475a;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #2a2a3f;
                    width: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background: #45475a;
                    border-radius: 6px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #585b70;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QCheckBox {
                    color: white;
                    spacing: 8px;
                    font-size: 13px;
                }
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                    border: 2px solid #45475a;
                    border-radius: 6px;
                    background: #2a2a3f;
                }
                QCheckBox::indicator:hover {
                    border-color: #585b70;
                }
                QCheckBox::indicator:checked {
                    background-color: #7aa2f7;
                    border-color: #7aa2f7;
                    image: url(check.png);
                }
                QComboBox {
                    background: #2a2a3f;
                    border: 2px solid #45475a;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: white;
                    font-size: 13px;
                    selection-background-color: #7aa2f7;
                }
                QComboBox:hover {
                    border-color: #585b70;
                }
                QComboBox:focus {
                    border-color: #7aa2f7;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox::down-arrow {
                    image: url(arrow-down.png);
                    width: 12px;
                    height: 12px;
                }
                QToolTip {
                    background-color: #2a2a3f;
                    color: white;
                    border: 2px solid #45475a;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                }
            """
        else:
            # Light theme
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Link, QColor(37, 99, 235))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(37, 99, 235))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

            style = """
                QMainWindow, QDialog, QWidget {
                    background: #f5f5f5;
                    color: #1e1e2e;
                }
                QLabel {
                    color: #1e1e2e;
                    font-size: 13px;
                }
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                    padding: 7px 20px 9px 20px;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                    padding: 9px 20px 7px 20px;
                }
                QPushButton:disabled {
                    background-color: #e5e7eb;
                    color: #9ca3af;
                }
                QLineEdit {
                    padding: 8px 12px;
                    border: 2px solid #e5e7eb;
                    border-radius: 6px;
                    background: white;
                    color: #1e1e2e;
                    font-size: 13px;
                    selection-background-color: #2563eb;
                }
                QLineEdit:focus {
                    border: 2px solid #2563eb;
                    background: #f8fafc;
                }
                QLineEdit:hover {
                    border: 2px solid #d1d5db;
                }
                QProgressBar {
                    border: none;
                    border-radius: 6px;
                    background-color: #e5e7eb;
                    text-align: center;
                    color: #1e1e2e;
                    font-size: 12px;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #2563eb;
                    border-radius: 6px;
                }
                QTabWidget::pane {
                    border: 2px solid #e5e7eb;
                    border-radius: 8px;
                    top: -2px;
                }
                QTabBar::tab {
                    background: #f8fafc;
                    color: #4b5563;
                    padding: 10px 25px;
                    border: 2px solid #e5e7eb;
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    font-size: 13px;
                    margin-right: 4px;
                }
                QTabBar::tab:selected {
                    background: #2563eb;
                    color: white;
                    border-color: #2563eb;
                }
                QTabBar::tab:disabled {
                    background: #f1f5f9;
                    color: #9ca3af;
                    border-color: #e5e7eb;
                }
                QTabBar::tab:hover:!selected {
                    background: #e5e7eb;
                    border-color: #d1d5db;
                }
                QTreeWidget {
                    background: white;
                    color: #1e1e2e;
                    border: 2px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 5px;
                    font-size: 13px;
                }
                QTreeWidget::item {
                    padding: 5px;
                    border-radius: 4px;
                }
                QTreeWidget::item:selected {
                    background: #2563eb;
                    color: white;
                }
                QTreeWidget::item:hover {
                    background: #e5e7eb;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #f1f5f9;
                    width: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background: #d1d5db;
                    border-radius: 6px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #9ca3af;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QCheckBox {
                    color: #1e1e2e;
                    spacing: 8px;
                    font-size: 13px;
                }
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                    border: 2px solid #e5e7eb;
                    border-radius: 6px;
                    background: white;
                }
                QCheckBox::indicator:hover {
                    border-color: #d1d5db;
                }
                QCheckBox::indicator:checked {
                    background-color: #2563eb;
                    border-color: #2563eb;
                    image: url(check.png);
                }
                QComboBox {
                    background: white;
                    border: 2px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: #1e1e2e;
                    font-size: 13px;
                    selection-background-color: #2563eb;
                }
                QComboBox:hover {
                    border-color: #d1d5db;
                }
                QComboBox:focus {
                    border-color: #2563eb;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox::down-arrow {
                    image: url(arrow-down.png);
                    width: 12px;
                    height: 12px;
                }
                QToolTip {
                    background-color: white;
                    color: #1e1e2e;
                    border: 2px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                }
            """

        # Apply the palette
        app = QApplication.instance()
        app.setPalette(palette)

        # Apply stylesheet to the main window and all child widgets
        self.parent.setStyleSheet(style)

        # Force update all widgets
        for widget in self.parent.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        # Update the tab widget separately
        for i in range(self.parent.tabs.count()):
            tab = self.parent.tabs.widget(i)
            tab.setStyleSheet(style)
            for child in tab.findChildren(QWidget):
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()

    def apply_style(self):
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))

        # Load saved theme setting
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    settings = json.load(f)
                    is_dark = settings.get('theme', {}).get('dark_mode', True)
            else:
                is_dark = True  # Default to dark mode if no settings file
        except Exception as e:
            print(f"Error loading theme settings: {e}")
            is_dark = True  # Default to dark mode if error

        # Set theme and checkbox state
        self.parent.dark_mode_checkbox.setChecked(is_dark)
        self.toggle_theme(is_dark)

        # Connect palette change event
        app.paletteChanged.connect(self.parent.on_palette_changed)

    def update_api_status_label(self, status, is_error=True):
        # Only update if label exists
        if not hasattr(self.parent, 'api_status_label') or self.parent.api_status_label is None:
            return

        if is_error:
            color = "#ff4444"  # Lebih terang untuk error
        else:
            color = "#44aa44"  # Lebih terang untuk success
        self.parent.api_status_label.setText(f"API Status: {status}")
        self.parent.api_status_label.setStyleSheet(f"QLabel {{ padding: 5px 10px; color: {color}; font-weight: bold; }}")

    def toggle_api_visibility(self):
        current_mode = self.parent.api_key_input.echoMode()
        if current_mode == QLineEdit.EchoMode.Password:
            self.parent.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.parent.show_api_button.setText("🙉 Hide")  # Showing, can hide
        else:
            self.parent.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.parent.show_api_button.setText("🙈 Show")  # Hidden, can show

    def _save_api_key(self):
        try:
            # Get new API key
            new_api_key = self.parent.api_key_input.text().strip()
            if not new_api_key:
                QMessageBox.warning(
                    self.parent,
                    "Error",
                    "Please enter an API key",
                    QMessageBox.StandardButton.Ok
                )
                return

            # Load existing config or create new one
            config = {}
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
            except:
                pass

            # Update API key
            config['youtube_api_key'] = new_api_key

            # Save config
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)

            # Try to initialize YouTube API with new key
            api = self.parent.setup_youtube_api(show_error=True)  # Show error when saving new key
            if api is not None:
                self.parent.youtube = api
                QMessageBox.information(
                    self.parent,
                    "Success",
                    "API key saved and validated successfully!",
                    QMessageBox.StandardButton.Ok
                )
            else:
                # setup_youtube_api already showed error message
                pass

        except Exception as e:
            QMessageBox.warning(
                self.parent,
                "Error",
                f"Failed to save API key: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _save_settings(self):
        settings = {
            'theme': {
                'dark_mode': self.parent.dark_mode_checkbox.isChecked()
            }
        }

        try:
            with open('settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            QMessageBox.information(
                self.parent,
                "Success",
                "Settings saved successfully!",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Failed to save settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def _load_settings(self):
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    settings = json.load(f)

                # Apply theme settings
                dark_mode = settings.get('theme', {}).get('dark_mode', True)
                self.parent.dark_mode_checkbox.setChecked(dark_mode)
                self.toggle_theme(dark_mode)  # Apply theme immediately
        except Exception as e:
            QMessageBox.warning(
                self.parent,
                "Warning",
                f"Failed to load settings: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def update_ytdlp(self):
        try:
            # Buat progress dialog
            self.progress_dialog = QProgressDialog("Updating yt-dlp...", None, 0, 0, self.parent)
            self.progress_dialog.setWindowTitle("Update Progress")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setAutoReset(False)
            self.progress_dialog.show()

            # Buat dan jalankan thread update
            self.update_thread = UpdateThread()
            self.update_thread.progress.connect(self.update_progress)
            self.update_thread.finished.connect(self.update_finished)
            self.update_thread.start()

        except Exception as e:
            QMessageBox.warning(
                self.parent,
                "Error",
                f"Failed to start update: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    def update_progress(self, message):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setLabelText(message)

    def update_finished(self, success, message):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if success:
            # Update berhasil, perbarui label versi
            self.current_version = self.get_ytdlp_version()
            self.current_version_value.setText(f"""
                <div style='color: #7aa2f7; font-size: 14px;'>
                    📦 <span style='font-weight: bold;'>Current Version:</span>
                    <span style='
                        padding: 4px 10px;
                        border-radius: 4px;
                        border: 1px solid #7aa2f7;
                        color: #7aa2f7;
                        font-family: monospace;
                        font-weight: bold;
                    '>{self.current_version}</span>
                </div>
            """)

            QMessageBox.information(
                self.parent,
                "Success",
                "yt-dlp has been successfully updated!",
                QMessageBox.StandardButton.Ok
            )
        else:
            QMessageBox.warning(
                self.parent,
                "Error",
                f"Failed to update yt-dlp: {message}",
                QMessageBox.StandardButton.Ok
            )

    def get_available_browsers(self):
        """Get a list of browsers that are likely to be installed on the system."""
        browsers = []

        # Common browsers across platforms
        common_browsers = ["chrome", "firefox", "edge", "safari", "opera"]

        # Platform-specific browsers
        if platform.system() == "Windows":
            browsers = ["chrome", "firefox", "edge", "opera", "brave"]
        elif platform.system() == "Darwin":  # macOS
            browsers = ["chrome", "firefox", "safari", "edge", "opera", "brave"]
        else:  # Linux and others
            browsers = ["chrome", "firefox", "chromium", "opera", "brave"]

        return browsers

    def extract_cookies(self):
        """Extract cookies from the selected browser."""
        browser = self.browser_combo.currentText()

        if not browser:
            QMessageBox.warning(
                self.parent,
                "Browser Selection",
                "Please select a browser to extract cookies from."
            )
            return

        # Create progress dialog
        progress = QProgressDialog(f"Extracting cookies from {browser}...", None, 0, 0, self.parent)
        progress.setWindowTitle("Cookie Extraction")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        # Create and start cookie extraction thread
        self.cookie_thread = CookieExtractThread(browser)
        self.cookie_thread.progress.connect(progress.setLabelText)
        self.cookie_thread.finished.connect(lambda success, msg, path: self.cookie_extraction_finished(success, msg, path, progress))
        self.cookie_thread.start()

    def cookie_extraction_finished(self, success, message, cookie_path, progress_dialog):
        """Handle the completion of cookie extraction."""
        progress_dialog.close()

        if success:
            # Update UI
            self.cookie_status_value.setText("✅ Configured")
            self.cookie_status_value.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #9ece6a;
                    font-weight: bold;
                }
            """)

            QMessageBox.information(
                self.parent,
                "Cookie Extraction Successful",
                f"{message}\n\nYou can now download videos that require authentication."
            )
        else:
            QMessageBox.warning(
                self.parent,
                "Cookie Extraction Failed",
                f"{message}\n\nPlease try another browser or make sure you're logged into YouTube."
            )

    def check_yt_dlp_version(self):
        try:
            response = requests.get('https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest')
            latest_version = response.json()['tag_name']

            if self.current_version != latest_version and self.current_version != "Unknown":
                msg = QMessageBox(self.parent)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"A new version of yt-dlp is available!\n\nCurrent version: {self.current_version}\nLatest version: {latest_version}")
                msg.setWindowTitle("Update Available")
                msg.setWindowModality(Qt.WindowModality.ApplicationModal)

                # Menambahkan tombol Update dan Cancel
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)
                msg.button(QMessageBox.StandardButton.Yes).setText("Update")
                msg.button(QMessageBox.StandardButton.No).setText("Cancel")

                # Tampilkan dialog dan tunggu respons
                response = msg.exec()

                # Jika user memilih Update
                if response == QMessageBox.StandardButton.Yes:
                    self.update_ytdlp()
            else:
                msg = QMessageBox(self.parent)
                msg.setWindowModality(Qt.WindowModality.ApplicationModal)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setWindowTitle("Up to Date")
                msg.setText("You are using the latest version of yt-dlp.")
                msg.exec()
        except Exception as e:
            msg = QMessageBox(self.parent)
            msg.setWindowModality(Qt.WindowModality.ApplicationModal)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Error")
            msg.setText(f"Failed to check yt-dlp version: {str(e)}")
            msg.exec()

    def update_notice_colors(self, is_dark_mode):
        # Update GroupBox style
        border_color = "#ff9800"
        if is_dark_mode:
            bg_color = "rgba(255, 152, 0, 0.1)"
            text_color = "#e0e0e0"
            title_color = "#ff9800"
        else:
            bg_color = "rgba(255, 152, 0, 0.15)"
            text_color = "#333333"
            title_color = "#d17600"

        self.notice_box.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {border_color};
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {title_color};
            }}
        """)

        # Update label content with dynamic colors
        self.notice_label.setText(f"""
            <div style='margin: 5px;'>
                ⚠️ <span style='font-weight: bold; color: {title_color};'>When API is not connected, the following tabs will be disabled:</span>
                <ul style='margin-top: 5px; margin-bottom: 5px; color: {text_color};'>
                    <li>Single Download</li>
                    <li>Batch Download</li>
                    <li>Search</li>
                </ul>
            </div>
        """)

        self.notice_label.setStyleSheet(f"""
            QLabel {{
                padding: 15px;
                background-color: {bg_color};
                border-radius: 6px;
            }}
        """)
        self.notice_label.setTextFormat(Qt.TextFormat.RichText)
        self.notice_label.setWordWrap(True)

    def update_ffmpeg_notice(self):
        is_installed = bool(self.parent.config.get('ffmpeg_path'))
        if is_installed:
            notice = """
                <span style='color: #9ece6a;'>✨ FFmpeg is installed and ready to use!</span><br><br>
                FFmpeg is a critical component required for:
                <ul>
                    <li>Downloading YouTube videos in the highest quality</li>
                    <li>Ensuring videos have audio (sound)</li>
                    <li>Processing videos during download</li>
                </ul>
                <span style='color: #7aa2f7;'>ℹ️ If you remove FFmpeg, the application will not work until you run run.bat again.</span>
            """
        else:
            notice = """
                <span style='color: #f7768e;'>⚠️ FFmpeg is not installed</span><br><br>
                The application requires FFmpeg to download videos. To install:
                <ul>
                    <li>Run the run.bat file</li>
                    <li>Wait for the installation to complete</li>
                    <li>The application will be ready to use</li>
                </ul>
                <span style='color: #f7768e;'>⚠️ The application cannot download videos without FFmpeg!</span>
            """
        self.ffmpeg_notice.setText(notice)

    def remove_ffmpeg(self):
        reply = QMessageBox.question(
            None,
            "Remove FFmpeg",
            "<h3>Remove FFmpeg Installation?</h3>"
            "<p>Are you sure you want to remove FFmpeg? This will:</p>"
            "<ul>"
            "<li>Delete the FFmpeg files from your system</li>"
            "<li>Free up disk space</li>"
            "<li>Require reinstallation for future video downloads</li>"
            "</ul>"
            "<p><b>Note:</b> FFmpeg will be automatically reinstalled when needed.</p>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Set ffmpeg path to null, which will trigger the cleanup
            self.parent.set_ffmpeg_config(None)

            # Update UI
            self.ffmpeg_status_value.setText("❌ Not Installed")
            self.ffmpeg_status_value.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #f7768e;
                    font-weight: bold;
                }
            """)
            self.ffmpeg_path_value.setText("—")
            self.remove_ffmpeg_btn.setEnabled(False)
            self.update_ffmpeg_notice()

            QMessageBox.information(
                None,
                "FFmpeg Removed",
                "<h3>FFmpeg Successfully Removed</h3>"
                "<p>FFmpeg has been removed from your system. It will be automatically reinstalled when needed.</p>"
                "<p style='color: #7aa2f7;'>ℹ️ You can continue using the application normally!</p>"
            )

class UpdateThread(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Updating yt-dlp...")
            result = subprocess.run(['pip', 'install', '--upgrade', 'yt-dlp'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                self.finished.emit(True, "Update successful")
            else:
                self.finished.emit(False, f"Update failed: {result.stderr}")
        except Exception as e:
            self.finished.emit(False, str(e))

class CookieExtractThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, message, cookie_path

    def __init__(self, browser_name):
        super().__init__()
        self.browser_name = browser_name

    def run(self):
        try:
            self.progress.emit(f"Extracting cookies from {self.browser_name}...")

            # Create cookies directory if it doesn't exist
            cookies_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cookies')
            os.makedirs(cookies_dir, exist_ok=True)

            # Generate cookie file path
            cookie_file = os.path.join(cookies_dir, f'youtube_cookies_{self.browser_name.lower()}.txt')

            # Use yt-dlp to extract cookies
            cmd = [
                'yt-dlp',
                "--cookies-from-browser", self.browser_name,
                "youtube.com",
                "--cookies", cookie_file,
                "--skip-download",
                "-o", os.devnull,
                "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # First YouTube video ever
            ]

            self.progress.emit(f"Running cookie extraction command...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(cookie_file):
                self.progress.emit("Cookies extracted successfully!")

                # Update config with cookie path
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
                config = {}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                    except:
                        pass

                config['youtube_cookies_path'] = cookie_file
                config['youtube_cookies_browser'] = self.browser_name

                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)

                self.finished.emit(True, f"Successfully extracted cookies from {self.browser_name}.", cookie_file)
            else:
                error_msg = result.stderr if result.stderr else "No error details available."
                if "not supported" in error_msg:
                    error_msg = f"Browser {self.browser_name} is not supported or not installed on your system."
                elif "failed to extract cookies" in error_msg:
                    error_msg = f"Failed to extract cookies from {self.browser_name}. Make sure you're logged into YouTube in this browser."

                self.progress.emit(f"Cookie extraction failed: {error_msg}")
                self.finished.emit(False, f"Failed to extract cookies: {error_msg}", "")

        except Exception as e:
            self.progress.emit(f"Cookie extraction failed: {str(e)}")
            self.finished.emit(False, f"Error extracting cookies: {str(e)}", "")
