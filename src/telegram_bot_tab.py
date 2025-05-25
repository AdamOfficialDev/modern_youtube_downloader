from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QCheckBox, QLineEdit, QPushButton, QApplication,
                             QWidget, QMessageBox, QGroupBox, QStyleFactory,
                             QProgressDialog, QScrollArea, QComboBox, QTextEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
                             QTabWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPalette, QColor, QFont
import json
import os
import datetime
import logging
from typing import Dict, List, Optional

class TelegramBotTab:
    def __init__(self, parent=None):
        self.parent = parent
        self.bot_manager = None
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start(1000)  # Update logs every 1 second for real-time

        # Timer for uptime updates
        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self.update_uptime_display)
        self.uptime_timer.start(1000)  # Update uptime every 1 second

        # Timer for refreshing statistics and user data
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh_data)
        self.refresh_timer.start(10000)  # Update every 10 seconds
        self.setup_ui()

    def setup_ui(self):
        # Create main widget and layout for scroll area
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(20)

        # Title Header
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("🤖 Telegram Bot Management")
        title_label.setStyleSheet("""
            QLabel {
                color: #7aa2f7;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addWidget(title_frame)

        # Instructions section
        instructions_group = QGroupBox("📋 Petunjuk Penggunaan")
        instructions_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        instructions_layout = QVBoxLayout(instructions_group)

        instructions_text = QLabel("""
        <div style='padding: 10px; font-size: 13px; line-height: 1.6;'>
            <b>Langkah-langkah:</b><br>
            1. Dapatkan token bot dari @BotFather di Telegram<br>
            2. Masukkan token dan admin users di konfigurasi<br>
            3. Klik "Simpan Konfigurasi" lalu "Mulai Bot"<br>
            4. Bot siap menerima perintah dari pengguna Telegram<br><br>

            <b>Perintah Bot:</b><br>
            • <code>/start</code> - Memulai bot<br>
            • <code>/download [URL]</code> - Download video<br>
            • <code>/audio [URL]</code> - Ekstrak audio<br>
            • <code>/menu</code> - Menu interaktif (☰)<br>
            • Kirim URL langsung untuk download
        </div>
        """)
        instructions_text.setWordWrap(True)
        instructions_text.setTextFormat(Qt.TextFormat.RichText)
        instructions_text.setStyleSheet("""
            QLabel {
                background-color: rgba(122, 162, 247, 0.05);
                border: 1px solid rgba(122, 162, 247, 0.3);
                border-radius: 4px;
                padding: 10px;
            }
        """)
        instructions_layout.addWidget(instructions_text)

        # Add link to full instructions
        full_instructions_btn = QPushButton("📖 Buka Panduan Lengkap")
        full_instructions_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
        """)
        full_instructions_btn.clicked.connect(self.open_full_instructions)
        instructions_layout.addWidget(full_instructions_btn)

        layout.addWidget(instructions_group)

        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Controls and Configuration
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)

        # Bot Status Group
        self.create_bot_status_group(left_layout)

        # Bot Configuration Group
        self.create_bot_config_group(left_layout)

        # User Management Group
        self.create_user_management_group(left_layout)

        left_layout.addStretch()

        # Right panel - Logs and Activity
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)

        # Logs and Activity Group
        self.create_logs_group(right_layout)

        # Statistics Group
        self.create_statistics_group(right_layout)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidget(main_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Set scroll area as main widget
        main_layout = QVBoxLayout(self.parent.telegram_bot_tab)
        main_layout.addWidget(scroll)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Initialize bot manager
        self.bot_manager = None

        # Load current settings
        self.load_bot_settings()

        # Initial data refresh
        self.refresh_user_data()
        self.refresh_statistics()
        self.update_logs()

    def create_bot_status_group(self, parent_layout):
        """Create bot status and control group"""
        status_group = QGroupBox("Status & Kontrol Bot")
        status_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(15)

        # Bot status display
        status_frame = QFrame()
        status_frame_layout = QHBoxLayout(status_frame)

        status_label = QLabel("Status Bot:")
        status_label.setStyleSheet("QLabel { font-weight: bold; font-size: 14px; }")

        self.bot_status_display = QLabel("❌ Tidak Berjalan")
        self.bot_status_display.setStyleSheet("""
            QLabel {
                padding: 8px 15px;
                background-color: rgba(255, 68, 68, 0.1);
                border: 1px solid #ff4444;
                border-radius: 4px;
                color: #ff4444;
                font-weight: bold;
            }
        """)

        status_frame_layout.addWidget(status_label)
        status_frame_layout.addWidget(self.bot_status_display)
        status_frame_layout.addStretch()
        status_layout.addWidget(status_frame)

        # Control buttons
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)

        self.start_bot_btn = QPushButton("▶️ Mulai Bot")
        self.stop_bot_btn = QPushButton("⏹️ Hentikan Bot")
        self.restart_bot_btn = QPushButton("🔄 Restart Bot")

        button_style = """
            QPushButton {
                padding: 10px 20px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
            QPushButton:pressed {
                background-color: #6992e7;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #666666;
            }
        """

        self.start_bot_btn.setStyleSheet(button_style)
        self.stop_bot_btn.setStyleSheet(button_style.replace("#7aa2f7", "#f7768e"))
        self.restart_bot_btn.setStyleSheet(button_style.replace("#7aa2f7", "#ff9e64"))

        self.start_bot_btn.clicked.connect(self.start_bot)
        self.stop_bot_btn.clicked.connect(self.stop_bot)
        self.restart_bot_btn.clicked.connect(self.restart_bot)

        buttons_layout.addWidget(self.start_bot_btn)
        buttons_layout.addWidget(self.stop_bot_btn)
        buttons_layout.addWidget(self.restart_bot_btn)
        buttons_layout.addStretch()
        status_layout.addWidget(buttons_frame)

        parent_layout.addWidget(status_group)

    def create_bot_config_group(self, parent_layout):
        """Create bot configuration group"""
        config_group = QGroupBox("Konfigurasi Bot")
        config_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(15)

        # Bot Token
        token_frame = QFrame()
        token_layout = QHBoxLayout(token_frame)

        token_label = QLabel("Token Bot:")
        token_label.setStyleSheet("QLabel { font-weight: bold; }")
        token_label.setMinimumWidth(120)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Masukkan token bot Telegram Anda")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setStyleSheet("""
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

        self.show_token_btn = QPushButton("👁️")
        self.show_token_btn.setMaximumWidth(40)
        self.show_token_btn.clicked.connect(self.toggle_token_visibility)

        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input)
        token_layout.addWidget(self.show_token_btn)
        config_layout.addWidget(token_frame)

        # Admin Users
        admin_frame = QFrame()
        admin_layout = QHBoxLayout(admin_frame)

        admin_label = QLabel("Admin Users:")
        admin_label.setStyleSheet("QLabel { font-weight: bold; }")
        admin_label.setMinimumWidth(120)

        self.admin_input = QLineEdit()
        self.admin_input.setPlaceholderText("Username admin (pisahkan dengan koma)")
        self.admin_input.setStyleSheet("""
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

        admin_layout.addWidget(admin_label)
        admin_layout.addWidget(self.admin_input)
        config_layout.addWidget(admin_frame)

        # Save button
        save_btn = QPushButton("💾 Simpan Konfigurasi")
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #9ece6a;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #a9d96a;
            }
        """)
        save_btn.clicked.connect(self.save_bot_config)
        config_layout.addWidget(save_btn)

        parent_layout.addWidget(config_group)

    def create_user_management_group(self, parent_layout):
        """Create user management group"""
        user_group = QGroupBox("Manajemen Pengguna")
        user_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        user_layout = QVBoxLayout(user_group)
        user_layout.setSpacing(15)

        # User table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(4)
        self.user_table.setHorizontalHeaderLabels(["Username", "User ID", "Status", "Total Downloads"])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.setMaximumHeight(200)

        self.user_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: 1px solid #7aa2f7;
                border-radius: 4px;
                gridline-color: #45475a;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #45475a;
            }
            QTableWidget::item:selected {
                background-color: #7aa2f7;
                color: white;
            }
            QHeaderView::section {
                background-color: #7aa2f7;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)

        user_layout.addWidget(self.user_table)

        # User management buttons
        user_buttons_frame = QFrame()
        user_buttons_layout = QHBoxLayout(user_buttons_frame)

        refresh_users_btn = QPushButton("🔄 Refresh Data")
        block_user_btn = QPushButton("🚫 Blokir User")
        unblock_user_btn = QPushButton("✅ Buka Blokir")

        button_style = """
            QPushButton {
                padding: 8px 16px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
        """

        refresh_users_btn.setStyleSheet(button_style)
        block_user_btn.setStyleSheet(button_style.replace("#7aa2f7", "#f7768e"))
        unblock_user_btn.setStyleSheet(button_style.replace("#7aa2f7", "#9ece6a"))

        refresh_users_btn.clicked.connect(self.refresh_user_data)
        block_user_btn.clicked.connect(self.block_user)
        unblock_user_btn.clicked.connect(self.unblock_user)

        user_buttons_layout.addWidget(refresh_users_btn)
        user_buttons_layout.addWidget(block_user_btn)
        user_buttons_layout.addWidget(unblock_user_btn)
        user_buttons_layout.addStretch()
        user_layout.addWidget(user_buttons_frame)

        parent_layout.addWidget(user_group)

    def create_logs_group(self, parent_layout):
        """Create logs and activity group"""
        logs_group = QGroupBox("Log & Aktivitas Bot")
        logs_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        logs_layout = QVBoxLayout(logs_group)
        logs_layout.setSpacing(15)

        # Log controls
        log_controls_frame = QFrame()
        log_controls_layout = QHBoxLayout(log_controls_frame)

        clear_logs_btn = QPushButton("🗑️ Hapus Log")
        export_logs_btn = QPushButton("📤 Export Log")

        button_style = """
            QPushButton {
                padding: 6px 12px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
        """

        clear_logs_btn.setStyleSheet(button_style.replace("#7aa2f7", "#f7768e"))
        export_logs_btn.setStyleSheet(button_style)

        clear_logs_btn.clicked.connect(self.clear_logs)
        export_logs_btn.clicked.connect(self.export_logs)

        log_controls_layout.addWidget(clear_logs_btn)
        log_controls_layout.addWidget(export_logs_btn)
        log_controls_layout.addStretch()
        logs_layout.addWidget(log_controls_frame)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(300)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #c0caf5;
                border: 1px solid #7aa2f7;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }
        """)
        logs_layout.addWidget(self.log_display)

        parent_layout.addWidget(logs_group)

    def create_statistics_group(self, parent_layout):
        """Create statistics group"""
        stats_group = QGroupBox("Statistik Bot")
        stats_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 1em;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #7aa2f7;
            }
        """)
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(15)

        # Statistics display
        stats_frame = QFrame()
        stats_grid_layout = QVBoxLayout(stats_frame)

        # Create statistics labels
        self.total_users_label = QLabel("👥 Total Pengguna: 0")
        self.active_users_label = QLabel("🟢 Pengguna Aktif: 0")
        self.total_downloads_label = QLabel("📥 Total Download: 0")
        self.uptime_label = QLabel("⏱️ Uptime: 00:00:00")

        stat_style = """
            QLabel {
                padding: 8px 12px;
                background-color: rgba(122, 162, 247, 0.1);
                border: 1px solid #7aa2f7;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
        """

        self.total_users_label.setStyleSheet(stat_style)
        self.active_users_label.setStyleSheet(stat_style)
        self.total_downloads_label.setStyleSheet(stat_style)
        self.uptime_label.setStyleSheet(stat_style)

        stats_grid_layout.addWidget(self.total_users_label)
        stats_grid_layout.addWidget(self.active_users_label)
        stats_grid_layout.addWidget(self.total_downloads_label)
        stats_grid_layout.addWidget(self.uptime_label)

        stats_layout.addWidget(stats_frame)

        # Refresh stats button
        refresh_stats_btn = QPushButton("🔄 Refresh Statistik")
        refresh_stats_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #7aa2f7;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #8ab2ff;
            }
        """)
        refresh_stats_btn.clicked.connect(self.refresh_statistics)
        stats_layout.addWidget(refresh_stats_btn)

        parent_layout.addWidget(stats_group)

    # Implementation methods
    def load_bot_settings(self):
        """Load bot settings from config"""
        try:
            config = self.parent.config

            # Load token
            token = config.get('telegram_bot_token', '')
            self.token_input.setText(token)

            # Load admin users
            admin_users = config.get('admin_users', [])
            if isinstance(admin_users, list):
                self.admin_input.setText(', '.join(admin_users))
            else:
                self.admin_input.setText(str(admin_users))

            # Update bot status
            self.update_bot_status()

        except Exception as e:
            print(f"Error loading bot settings: {e}")

    def save_bot_config(self):
        """Save bot configuration"""
        try:
            # Get values
            token = self.token_input.text().strip()
            admin_text = self.admin_input.text().strip()

            # Parse admin users
            admin_users = []
            if admin_text:
                admin_users = [user.strip() for user in admin_text.split(',')]
                # Remove @ symbol if present
                admin_users = [user[1:] if user.startswith('@') else user for user in admin_users]

            # Update config
            self.parent.config['telegram_bot_token'] = token
            self.parent.config['admin_users'] = admin_users

            # Save to file using parent's save method
            self.parent.save_config()

            QMessageBox.information(
                self.parent,
                "Sukses",
                "Konfigurasi bot berhasil disimpan!"
            )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Gagal menyimpan konfigurasi: {str(e)}"
            )

    def save_bot_config_silent(self):
        """Save bot configuration without showing notification"""
        try:
            # Get values
            token = self.token_input.text().strip()
            admin_text = self.admin_input.text().strip()

            # Parse admin users
            admin_users = []
            if admin_text:
                admin_users = [user.strip() for user in admin_text.split(',')]
                # Remove @ symbol if present
                admin_users = [user[1:] if user.startswith('@') else user for user in admin_users]

            # Update config
            self.parent.config['telegram_bot_token'] = token
            self.parent.config['admin_users'] = admin_users

            # Save to file using parent's save method
            self.parent.save_config()

        except Exception as e:
            print(f"Error saving bot config silently: {e}")

    def start_bot(self):
        """Start the Telegram bot"""
        try:
            # Check if token is configured
            token = self.token_input.text().strip()
            if not token:
                QMessageBox.warning(
                    self.parent,
                    "Peringatan",
                    "Silakan masukkan token bot terlebih dahulu!"
                )
                return

            # Save config first (silently)
            self.save_bot_config_silent()

            # Import and start bot manager
            from src.telegram_bot_manager import TelegramBotManager

            # Create bot manager if needed
            if not self.bot_manager:
                self.bot_manager = TelegramBotManager(self.parent)

            if not self.bot_manager.is_bot_running():
                success = self.bot_manager.start_bot()
                if success:
                    self.update_bot_status()
                    QMessageBox.information(
                        self.parent,
                        "Sukses",
                        "Bot Telegram berhasil dijalankan!"
                    )
                else:
                    QMessageBox.critical(
                        self.parent,
                        "Error",
                        "Gagal menjalankan bot. Periksa token dan coba lagi."
                    )
            else:
                QMessageBox.information(
                    self.parent,
                    "Info",
                    "Bot sudah berjalan!"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error menjalankan bot: {str(e)}"
            )

    def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            if self.bot_manager and self.bot_manager.is_bot_running():
                # Disable buttons during stop
                self.start_bot_btn.setEnabled(False)
                self.stop_bot_btn.setEnabled(False)
                self.restart_bot_btn.setEnabled(False)

                # Show stopping status
                self.bot_status_display.setText("⏹️ Stopping...")

                # Use threading to prevent UI freeze
                import threading
                def stop_process():
                    try:
                        success = self.bot_manager.stop_bot()

                        # Update UI in main thread
                        QTimer.singleShot(100, lambda: self.update_bot_status())

                        if success:
                            QTimer.singleShot(200, lambda: QMessageBox.information(
                                self.parent,
                                "Sukses",
                                "Bot Telegram berhasil dihentikan!"
                            ))
                        else:
                            QTimer.singleShot(200, lambda: QMessageBox.warning(
                                self.parent,
                                "Peringatan",
                                "Bot mungkin sudah berhenti atau ada masalah saat menghentikan."
                            ))
                    except Exception as e:
                        print(f"Error in stop process: {e}")
                        QTimer.singleShot(100, lambda: self.update_bot_status())
                        QTimer.singleShot(200, lambda: QMessageBox.critical(
                            self.parent,
                            "Error",
                            f"Error menghentikan bot: {str(e)}"
                        ))

                stop_thread = threading.Thread(target=stop_process, daemon=True)
                stop_thread.start()

            else:
                QMessageBox.information(
                    self.parent,
                    "Info",
                    "Bot tidak sedang berjalan!"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error menghentikan bot: {str(e)}"
            )
            # Re-enable buttons
            self.update_bot_status()

    def restart_bot(self):
        """Restart the Telegram bot"""
        try:
            # Disable buttons during restart
            self.start_bot_btn.setEnabled(False)
            self.stop_bot_btn.setEnabled(False)
            self.restart_bot_btn.setEnabled(False)

            # Show progress
            self.bot_status_display.setText("🔄 Restarting...")

            # Use threading to prevent UI freeze
            import threading
            def restart_process():
                try:
                    # Stop first
                    if self.bot_manager and self.bot_manager.is_bot_running():
                        self.bot_manager.stop_bot()

                    # Wait a moment for cleanup
                    import time
                    time.sleep(2)

                    # Signal main thread to start bot (avoid QTimer in background thread)
                    from PyQt6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(self, "start_bot", Qt.ConnectionType.QueuedConnection)

                except Exception as e:
                    print(f"Error in restart process: {e}")
                    # Signal main thread to update status (avoid QTimer in background thread)
                    from PyQt6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(self, "update_bot_status", Qt.ConnectionType.QueuedConnection)

            restart_thread = threading.Thread(target=restart_process, daemon=True)
            restart_thread.start()

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error restart bot: {str(e)}"
            )
            # Re-enable buttons
            self.update_bot_status()

    def update_bot_status(self):
        """Update bot status display"""
        try:
            is_running = False
            # Check if bot manager exists and is running
            if self.bot_manager:
                is_running = self.bot_manager.is_bot_running()

            if is_running:
                self.bot_status_display.setText("✅ Berjalan")
                self.bot_status_display.setStyleSheet("""
                    QLabel {
                        padding: 8px 15px;
                        background-color: rgba(158, 206, 106, 0.1);
                        border: 1px solid #9ece6a;
                        border-radius: 4px;
                        color: #9ece6a;
                        font-weight: bold;
                    }
                """)
                self.start_bot_btn.setEnabled(False)
                self.stop_bot_btn.setEnabled(True)
                self.restart_bot_btn.setEnabled(True)
            else:
                self.bot_status_display.setText("❌ Tidak Berjalan")
                self.bot_status_display.setStyleSheet("""
                    QLabel {
                        padding: 8px 15px;
                        background-color: rgba(255, 68, 68, 0.1);
                        border: 1px solid #ff4444;
                        border-radius: 4px;
                        color: #ff4444;
                        font-weight: bold;
                    }
                """)
                self.start_bot_btn.setEnabled(True)
                self.stop_bot_btn.setEnabled(False)
                self.restart_bot_btn.setEnabled(False)

        except Exception as e:
            print(f"Error updating bot status: {e}")

    def toggle_token_visibility(self):
        """Toggle token visibility"""
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_token_btn.setText("🙈")
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_token_btn.setText("👁️")

    def refresh_user_data(self):
        """Refresh user data table"""
        try:
            # Clear existing data
            self.user_table.setRowCount(0)

            # Try to get real user data from bot manager
            users_data = []
            # Check if bot manager exists and is running
            if self.bot_manager and self.bot_manager.is_bot_running():
                # Try to get user data from bot instance
                try:
                    bot_instance = self.bot_manager.bot_instance
                    print(f"Bot instance: {bot_instance}")
                    if bot_instance and hasattr(bot_instance, 'get_user_stats'):
                        users_data = bot_instance.get_user_stats()
                        print(f"Got user data from bot: {len(users_data)} users")
                    else:
                        print("Bot instance doesn't have get_user_stats method")
                except Exception as e:
                    print(f"Error getting user data from bot: {e}")

            # If no real data available, check if we have any stored user data
            if not users_data:
                users_data = self.load_user_data_from_file()

            # If still no data, show empty table with informative message
            if not users_data:
                self.user_table.setRowCount(1)
                self.user_table.setItem(0, 0, QTableWidgetItem("Belum ada pengguna"))
                self.user_table.setItem(0, 1, QTableWidgetItem("-"))
                self.user_table.setItem(0, 2, QTableWidgetItem("Mulai bot dan tunggu pengguna"))
                self.user_table.setItem(0, 3, QTableWidgetItem("0"))

                # Style the empty row differently
                for col in range(4):
                    item = self.user_table.item(0, col)
                    if item:
                        item.setForeground(QColor("#888888"))
                return

            self.user_table.setRowCount(len(users_data))

            for row, user_data in enumerate(users_data):
                username = user_data.get('username', f"user_{user_data.get('user_id', 'unknown')}")
                user_id = str(user_data.get('user_id', 'N/A'))
                status = user_data.get('status', 'Aktif')
                downloads = str(user_data.get('download_count', 0))

                self.user_table.setItem(row, 0, QTableWidgetItem(username))
                self.user_table.setItem(row, 1, QTableWidgetItem(user_id))
                self.user_table.setItem(row, 2, QTableWidgetItem(status))
                self.user_table.setItem(row, 3, QTableWidgetItem(downloads))

        except Exception as e:
            print(f"Error refreshing user data: {e}")
            # Show error in table
            self.user_table.setRowCount(1)
            self.user_table.setItem(0, 0, QTableWidgetItem("Error"))
            self.user_table.setItem(0, 1, QTableWidgetItem("-"))
            self.user_table.setItem(0, 2, QTableWidgetItem("Gagal memuat data"))
            self.user_table.setItem(0, 3, QTableWidgetItem("0"))

    def load_user_data_from_file(self):
        """Load user data from file if available"""
        try:
            user_data_file = "bot_users.json"
            if os.path.exists(user_data_file):
                with open(user_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading user data from file: {e}")
        return []

    def block_user(self):
        """Block selected user"""
        try:
            current_row = self.user_table.currentRow()
            if current_row >= 0:
                username = self.user_table.item(current_row, 0).text()
                reply = QMessageBox.question(
                    self.parent,
                    "Konfirmasi",
                    f"Apakah Anda yakin ingin memblokir user '{username}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    # Get user ID from table
                    user_id = self.user_table.item(current_row, 1).text()

                    # Update status in bot's user data
                    success = self.update_user_status(user_id, "Diblokir")

                    if success:
                        # Update status in table
                        self.user_table.setItem(current_row, 2, QTableWidgetItem("Diblokir"))
                        QMessageBox.information(
                            self.parent,
                            "Sukses",
                            f"User '{username}' berhasil diblokir!"
                        )
                    else:
                        QMessageBox.critical(
                            self.parent,
                            "Error",
                            f"Gagal memblokir user '{username}'"
                        )
            else:
                QMessageBox.warning(
                    self.parent,
                    "Peringatan",
                    "Silakan pilih user yang ingin diblokir!"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error memblokir user: {str(e)}"
            )

    def unblock_user(self):
        """Unblock selected user"""
        try:
            current_row = self.user_table.currentRow()
            if current_row >= 0:
                username = self.user_table.item(current_row, 0).text()
                reply = QMessageBox.question(
                    self.parent,
                    "Konfirmasi",
                    f"Apakah Anda yakin ingin membuka blokir user '{username}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    # Get user ID from table
                    user_id = self.user_table.item(current_row, 1).text()

                    # Update status in bot's user data
                    success = self.update_user_status(user_id, "Aktif")

                    if success:
                        # Update status in table
                        self.user_table.setItem(current_row, 2, QTableWidgetItem("Aktif"))
                        QMessageBox.information(
                            self.parent,
                            "Sukses",
                            f"User '{username}' berhasil dibuka blokirnya!"
                        )
                    else:
                        QMessageBox.critical(
                            self.parent,
                            "Error",
                            f"Gagal membuka blokir user '{username}'"
                        )
            else:
                QMessageBox.warning(
                    self.parent,
                    "Peringatan",
                    "Silakan pilih user yang ingin dibuka blokirnya!"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error membuka blokir user: {str(e)}"
            )

    def update_logs(self):
        """Update log display in real-time"""
        try:
            log_content = ""
            log_files_to_check = ["bot_logs.log", "telegram_bot.log", "logs/bot.log"]

            # Track file modification time for real-time updates
            if not hasattr(self, '_last_log_mtime'):
                self._last_log_mtime = {}

            file_updated = False

            # Check multiple possible log file locations
            for log_file in log_files_to_check:
                if os.path.exists(log_file):
                    try:
                        # Check if file was modified since last read
                        current_mtime = os.path.getmtime(log_file)
                        if log_file not in self._last_log_mtime or current_mtime > self._last_log_mtime[log_file]:
                            self._last_log_mtime[log_file] = current_mtime
                            file_updated = True

                        # Try multiple encodings to handle different file formats
                        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

                        for encoding in encodings_to_try:
                            try:
                                with open(log_file, 'r', encoding=encoding) as f:
                                    lines = f.readlines()
                                    # Show last 150 lines for better visibility
                                    recent_lines = lines[-150:] if len(lines) > 150 else lines
                                    log_content = ''.join(recent_lines)
                                    break
                            except UnicodeDecodeError:
                                continue

                        if log_content:
                            break
                    except Exception as e:
                        print(f"Error reading log file {log_file}: {e}")
                        continue

            # If no log files found, show status message
            if not log_content:
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if self.bot_manager and self.bot_manager.is_bot_running():
                    log_content = f"[{current_time}] 🤖 Bot sedang berjalan dan siap menerima perintah\n"
                    log_content += f"[{current_time}] 📝 Log aktivitas akan muncul di sini secara real-time\n"
                    log_content += f"[{current_time}] 💡 Kirim pesan ke bot untuk melihat log aktivitas\n"
                    log_content += f"[{current_time}] 🔄 Monitoring log setiap detik...\n"
                elif self.bot_manager:
                    log_content = f"[{current_time}] ⏹️ Bot tidak sedang berjalan\n"
                    log_content += f"[{current_time}] ▶️ Klik 'Mulai Bot' untuk memulai\n"
                else:
                    log_content = f"[{current_time}] ⚙️ Bot manager belum diinisialisasi\n"
                    log_content += f"[{current_time}] 🔧 Konfigurasi bot terlebih dahulu\n"
                file_updated = True  # Always update status messages

            # Only update display if content changed or file was updated
            current_content = self.log_display.toPlainText()
            if file_updated or current_content != log_content:
                # Store current scroll position
                scrollbar = self.log_display.verticalScrollBar()
                was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10

                self.log_display.setPlainText(log_content)

                # Auto-scroll to bottom if user was already at bottom
                if was_at_bottom:
                    cursor = self.log_display.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.log_display.setTextCursor(cursor)
                    scrollbar.setValue(scrollbar.maximum())

        except Exception as e:
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_msg = f"[{current_time}] ❌ ERROR: Gagal memperbarui log: {str(e)}\n"
            error_msg += f"[{current_time}] 🔧 Periksa konfigurasi bot dan coba lagi\n"
            self.log_display.setPlainText(error_msg)
            print(f"Error updating logs: {e}")

    def clear_logs(self):
        """Clear log display and file"""
        try:
            reply = QMessageBox.question(
                self.parent,
                "Konfirmasi",
                "Apakah Anda yakin ingin menghapus semua log?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Clear display
                self.log_display.clear()

                # Clear log file
                log_file = "bot_logs.log"
                if os.path.exists(log_file):
                    open(log_file, 'w').close()

                QMessageBox.information(
                    self.parent,
                    "Sukses",
                    "Log berhasil dihapus!"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error menghapus log: {str(e)}"
            )

    def export_logs(self):
        """Export logs to file"""
        try:
            from PyQt6.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self.parent,
                "Export Log",
                f"bot_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )

            if filename:
                log_content = self.log_display.toPlainText()
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                QMessageBox.information(
                    self.parent,
                    "Sukses",
                    f"Log berhasil diekspor ke: {filename}"
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Error mengekspor log: {str(e)}"
            )



    def refresh_statistics(self):
        """Refresh bot statistics"""
        try:
            # Initialize default values
            total_users = 0
            active_users = 0
            total_downloads = 0
            uptime = "00:00:00"

            # Try to get real statistics from bot manager
            if self.bot_manager and self.bot_manager.is_bot_running():
                # Calculate uptime
                if hasattr(self.bot_manager, 'start_time'):
                    start_time = self.bot_manager.start_time
                    current_time = datetime.datetime.now()
                    uptime_delta = current_time - start_time
                    hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                # Try to get user statistics from bot instance
                try:
                    bot_instance = self.bot_manager.bot_instance
                    if bot_instance and hasattr(bot_instance, 'get_statistics'):
                        stats = bot_instance.get_statistics()
                        total_users = stats.get('total_users', 0)
                        active_users = stats.get('active_users', 0)
                        total_downloads = stats.get('total_downloads', 0)
                except Exception as e:
                    print(f"Error getting bot statistics: {e}")

            # If no real data from bot, try to get from stored files
            if total_users == 0:
                user_data = self.load_user_data_from_file()
                total_users = len(user_data)

                # Count active users (users who have downloaded in last 30 days)
                active_users = 0
                total_downloads = 0
                current_time = datetime.datetime.now()

                for user in user_data:
                    downloads = user.get('download_count', 0)
                    total_downloads += downloads

                    # Check if user was active in last 30 days
                    last_activity = user.get('last_activity')
                    if last_activity:
                        try:
                            last_activity_date = datetime.datetime.fromisoformat(last_activity)
                            if (current_time - last_activity_date).days <= 30:
                                active_users += 1
                        except:
                            pass

            # Update labels with real or calculated data
            self.total_users_label.setText(f"👥 Total Pengguna: {total_users}")
            self.active_users_label.setText(f"🟢 Pengguna Aktif: {active_users}")
            self.total_downloads_label.setText(f"📥 Total Download: {total_downloads}")
            self.uptime_label.setText(f"⏱️ Uptime: {uptime}")

        except Exception as e:
            print(f"Error refreshing statistics: {e}")
            # Show error in statistics
            self.total_users_label.setText("👥 Total Pengguna: Error")
            self.active_users_label.setText("🟢 Pengguna Aktif: Error")
            self.total_downloads_label.setText("📥 Total Download: Error")
            self.uptime_label.setText("⏱️ Uptime: Error")

    def open_full_instructions(self):
        """Open full instructions file"""
        try:
            import subprocess
            import platform

            instructions_file = "TELEGRAM_BOT_INSTRUCTIONS_ID.md"

            if os.path.exists(instructions_file):
                if platform.system() == "Windows":
                    os.startfile(instructions_file)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", instructions_file])
                else:  # Linux
                    subprocess.run(["xdg-open", instructions_file])
            else:
                QMessageBox.information(
                    self.parent,
                    "Info",
                    "File panduan tidak ditemukan. Silakan baca dokumentasi di GitHub."
                )

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Gagal membuka panduan: {str(e)}"
            )

    def auto_refresh_data(self):
        """Auto refresh statistics and user data"""
        try:
            # Always refresh statistics for real-time updates
            self.refresh_statistics()

            # Refresh user data less frequently to avoid performance issues
            import time
            current_time = time.time()
            if not hasattr(self, '_last_user_refresh') or (current_time - self._last_user_refresh) > 30:
                self.refresh_user_data()
                self._last_user_refresh = current_time

            # Update bot status
            self.update_bot_status()
        except Exception as e:
            print(f"Error in auto refresh: {e}")

    def update_uptime_display(self):
        """Update uptime display in real-time"""
        try:
            if self.bot_manager and self.bot_manager.is_bot_running() and hasattr(self.bot_manager, 'start_time'):
                start_time = self.bot_manager.start_time
                current_time = datetime.datetime.now()
                uptime_delta = current_time - start_time
                hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                # Update uptime in statistics (use correct attribute name)
                if hasattr(self, 'uptime_label'):
                    self.uptime_label.setText(f"⏱️ Uptime: {uptime}")
            else:
                # Bot not running, show 00:00:00
                if hasattr(self, 'uptime_label'):
                    self.uptime_label.setText("⏱️ Uptime: 00:00:00")

        except Exception as e:
            print(f"Error updating uptime display: {e}")

    def update_user_status(self, user_id: str, new_status: str) -> bool:
        """Update user status in bot's user data"""
        try:
            # Try to update via bot instance first
            if self.bot_manager and self.bot_manager.is_bot_running() and self.bot_manager.bot_instance:
                if hasattr(self.bot_manager.bot_instance, 'update_user_status'):
                    return self.bot_manager.bot_instance.update_user_status(int(user_id), new_status)

            # Fallback: update file directly
            user_data = self.load_user_data_from_file()
            user_found = False

            for user in user_data:
                if str(user.get('user_id')) == user_id:
                    user['status'] = new_status
                    user_found = True
                    break

            if user_found:
                # Save updated data
                user_data_file = "bot_users.json"
                with open(user_data_file, 'w', encoding='utf-8') as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)
                print(f"User {user_id} status updated to {new_status}")
                return True
            else:
                print(f"User {user_id} not found")
                return False

        except Exception as e:
            print(f"Error updating user status: {e}")
            return False
