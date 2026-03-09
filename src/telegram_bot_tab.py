from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                             QCheckBox, QLineEdit, QPushButton, QApplication,
                             QWidget, QMessageBox, QGroupBox, QStyleFactory,
                             QProgressDialog, QScrollArea, QComboBox, QTextEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
                             QTabWidget, QGraphicsDropShadowEffect, QSizePolicy,
                             QStackedWidget, QToolButton, QSpacerItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PyQt6.QtGui import QPalette, QColor, QFont, QIcon, QPainter, QPainterPath, QLinearGradient, QPixmap, QBrush
import json
import os
import datetime
import logging
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS  (edit here to reskin the entire tab)
# ─────────────────────────────────────────────────────────────────────────────
class Palette:
    # Primary brand colours
    ACCENT        = "#5b8af0"        # electric blue
    ACCENT_HOVER  = "#7aa3f7"
    ACCENT_DIM    = "rgba(91,138,240,0.15)"
    ACCENT_BORDER = "rgba(91,138,240,0.45)"

    # Status colours
    SUCCESS       = "#4fd69c"
    SUCCESS_DIM   = "rgba(79,214,156,0.15)"
    WARNING       = "#fbbf24"
    WARNING_DIM   = "rgba(251,191,36,0.15)"
    DANGER        = "#f87171"
    DANGER_DIM    = "rgba(248,113,113,0.15)"

    # Surface colours  
    BG_DEEP       = "#0d0f18"        # outermost / window
    BG_CARD       = "#13162a"        # card / panel
    BG_INPUT      = "#1a1d31"        # inputs, tables
    BG_HOVER      = "#1f2338"        # hover state
    BORDER        = "#252840"        # subtle dividers
    BORDER_LIGHT  = "#2e3352"        # slightly lighter dividers

    # Text
    TEXT_PRIMARY  = "#e8ecff"
    TEXT_SECONDARY= "#8b93b8"
    TEXT_MUTED    = "#525a7a"
    TEXT_CODE     = "#a6d9ff"        # monospace / log text


# ─────────────────────────────────────────────────────────────────────────────
# SHARED STYLESHEET FRAGMENTS
# ─────────────────────────────────────────────────────────────────────────────
def _card_style(border_color: str = Palette.BORDER) -> str:
    return f"""
        border: 1px solid {border_color};
        border-radius: 12px;
        background-color: {Palette.BG_CARD};
    """

def _btn_style(bg: str, hover: str, fg: str = "#fff", border: str = "none") -> str:
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {fg};
            border: {border};
            border-radius: 8px;
            padding: 9px 22px;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.4px;
        }}
        QPushButton:hover   {{ background-color: {hover}; }}
        QPushButton:pressed {{ opacity: 0.85; }}
        QPushButton:disabled{{
            background-color: {Palette.BG_INPUT};
            color: {Palette.TEXT_MUTED};
            border: 1px solid {Palette.BORDER};
        }}
    """

def _label_style(size: int = 13, weight: str = "normal",
                 color: str = Palette.TEXT_PRIMARY) -> str:
    return f"color: {color}; font-size: {size}px; font-weight: {weight};"

def _input_style() -> str:
    return f"""
        QLineEdit {{
            background-color: {Palette.BG_INPUT};
            color: {Palette.TEXT_PRIMARY};
            border: 1px solid {Palette.BORDER_LIGHT};
            border-radius: 8px;
            padding: 9px 14px;
            font-size: 13px;
            selection-background-color: {Palette.ACCENT};
        }}
        QLineEdit:focus {{
            border: 1px solid {Palette.ACCENT};
            background-color: {Palette.BG_HOVER};
        }}
        QLineEdit:hover {{
            border: 1px solid {Palette.BORDER_LIGHT};
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# HELPER WIDGETS
# ─────────────────────────────────────────────────────────────────────────────
class _Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {Palette.BORDER}; border: none;")


class _SectionHeader(QLabel):
    """Bold section title with optional accent tag pill."""
    def __init__(self, text: str, tag: str = "", parent=None):
        super().__init__(parent)
        display = text
        if tag:
            display += (
                f"  <span style='font-size:10px; font-weight:600; "
                f"background:{Palette.ACCENT_DIM}; color:{Palette.ACCENT}; "
                f"border:1px solid {Palette.ACCENT_BORDER}; border-radius:4px; "
                f"padding:1px 7px;'>{tag}</span>"
            )
        self.setText(display)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 15px; "
            f"font-weight: 700; padding: 0; background: transparent;"
        )


class _StatCard(QFrame):
    """Mini stat card: icon + number + label."""
    def __init__(self, icon: str, value: str, label: str,
                 accent: str = Palette.ACCENT, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Palette.BG_CARD};
                border: 1px solid {Palette.BORDER_LIGHT};
                border-radius: 12px;
                min-width: 120px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        top = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size:22px; background:transparent; border:none;")
        top.addWidget(icon_lbl)
        top.addStretch()
        lay.addLayout(top)

        self._val_lbl = QLabel(value)
        self._val_lbl.setStyleSheet(
            f"color:{accent}; font-size:22px; font-weight:700; "
            f"background:transparent; border:none;"
        )
        lay.addWidget(self._val_lbl)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{Palette.TEXT_SECONDARY}; font-size:11px; "
            f"font-weight:600; background:transparent; border:none;"
        )
        lay.addWidget(lbl)

    def set_value(self, v: str):
        self._val_lbl.setText(v)


class _StatusBadge(QLabel):
    """Pill badge that shows Running / Stopped etc."""
    PRESETS = {
        "running":  (Palette.SUCCESS,  Palette.SUCCESS_DIM,  "● RUNNING"),
        "stopped":  (Palette.DANGER,   Palette.DANGER_DIM,   "○ STOPPED"),
        "stopping": (Palette.WARNING,  Palette.WARNING_DIM,  "◎ STOPPING…"),
        "starting": (Palette.ACCENT,   Palette.ACCENT_DIM,   "◎ STARTING…"),
    }

    def __init__(self, state: str = "stopped", parent=None):
        super().__init__(parent)
        self.set_state(state)

    def set_state(self, state: str):
        fg, bg, text = self.PRESETS.get(state, self.PRESETS["stopped"])
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 10px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TAB CLASS
# ─────────────────────────────────────────────────────────────────────────────
class TelegramBotTab:
    def __init__(self, parent=None):
        self.parent = parent
        self.bot_manager = None

        # Stat cards registry (populated in _build_stats_panel)
        self._stat_users:     Optional[_StatCard] = None
        self._stat_active:    Optional[_StatCard] = None
        self._stat_downloads: Optional[_StatCard] = None
        self._stat_uptime:    Optional[_StatCard] = None

        # Timers
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start(1000)

        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self.update_uptime_display)
        self.uptime_timer.start(1000)

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh_data)
        self.refresh_timer.start(10000)

        self._last_log_mtime: dict = {}
        self._last_user_refresh: float = 0.0

        self.setup_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # TOP-LEVEL SETUP
    # ─────────────────────────────────────────────────────────────────────────
    def setup_ui(self):
        # Root scroll wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea   {{ border: none; background: {Palette.BG_DEEP}; }}
            QScrollBar:vertical {{
                background: {Palette.BG_CARD}; width: 6px;
                border-radius: 3px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {Palette.BORDER_LIGHT}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {Palette.ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        root = QWidget()
        root.setStyleSheet(f"background-color: {Palette.BG_DEEP};")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(28, 24, 28, 28)
        root_lay.setSpacing(20)

        # ── Header bar ────────────────────────────────────────────────────────
        root_lay.addWidget(self._build_header())

        # ── Stats row ─────────────────────────────────────────────────────────
        root_lay.addWidget(self._build_stats_row())

        # ── Body: left + right columns ────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(20)

        left_col = QVBoxLayout()
        left_col.setSpacing(20)
        left_col.addWidget(self._build_status_panel())
        left_col.addWidget(self._build_config_panel())
        left_col.addWidget(self._build_users_panel())
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(20)
        right_col.addWidget(self._build_log_panel(), stretch=2)
        right_col.addWidget(self._build_instructions_panel())

        left_w  = QWidget(); left_w.setLayout(left_col)
        right_w = QWidget(); right_w.setLayout(right_col)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; width: 20px; }")

        body.addWidget(splitter)
        root_lay.addLayout(body)

        scroll.setWidget(root)
        outer = QVBoxLayout(self.parent.telegram_bot_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Load settings & initial data
        self.load_bot_settings()
        self.refresh_user_data()
        self.refresh_statistics()
        self.update_logs()

    # ─────────────────────────────────────────────────────────────────────────
    # PANEL BUILDERS
    # ─────────────────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Palette.BG_CARD}, stop:1 #0d1229);
                border: 1px solid {Palette.BORDER};
                border-radius: 14px;
            }}
        """)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(24, 18, 24, 18)

        icon = QLabel("🤖")
        icon.setStyleSheet("font-size:32px; background:transparent; border:none;")

        info = QVBoxLayout()
        info.setSpacing(2)
        title = QLabel("Telegram Bot")
        title.setStyleSheet(
            f"color:{Palette.TEXT_PRIMARY}; font-size:20px; font-weight:800; "
            f"background:transparent; border:none;"
        )
        sub = QLabel("Manage your Telegram downloader bot in real-time")
        sub.setStyleSheet(
            f"color:{Palette.TEXT_SECONDARY}; font-size:12px; "
            f"background:transparent; border:none;"
        )
        info.addWidget(title)
        info.addWidget(sub)

        self._header_badge = _StatusBadge("stopped")

        lay.addWidget(icon)
        lay.addSpacing(12)
        lay.addLayout(info)
        lay.addStretch()
        lay.addWidget(self._header_badge)
        return w

    def _build_stats_row(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._stat_users     = _StatCard("👥", "0",  "Total Users",   Palette.ACCENT)
        self._stat_active    = _StatCard("🟢", "0",  "Active Users",  Palette.SUCCESS)
        self._stat_downloads = _StatCard("📥", "0",  "Downloads",     Palette.WARNING)
        self._stat_uptime    = _StatCard("⏱",  "00:00:00", "Uptime", Palette.TEXT_SECONDARY)

        for card in (self._stat_users, self._stat_active,
                     self._stat_downloads, self._stat_uptime):
            lay.addWidget(card)
        return w

    # ── Status & Controls ────────────────────────────────────────────────────
    def _build_status_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style(Palette.ACCENT_BORDER))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # Header row
        hdr = QHBoxLayout()
        hdr.addWidget(_SectionHeader("Bot Control", "LIVE"))
        hdr.addStretch()
        lay.addLayout(hdr)
        lay.addWidget(_Divider())

        # Status row
        status_row = QHBoxLayout()
        status_lbl = QLabel("Status")
        status_lbl.setStyleSheet(_label_style(13, "600", Palette.TEXT_SECONDARY))
        self.bot_status_display = _StatusBadge("stopped")
        status_row.addWidget(status_lbl)
        status_row.addStretch()
        status_row.addWidget(self.bot_status_display)
        lay.addLayout(status_row)

        # Control buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_bot_btn = QPushButton("▶  Start Bot")
        self.start_bot_btn.setStyleSheet(_btn_style(Palette.SUCCESS, "#5fe0ac"))
        self.start_bot_btn.setMinimumHeight(40)
        self.start_bot_btn.clicked.connect(self.start_bot)

        self.stop_bot_btn = QPushButton("■  Stop Bot")
        self.stop_bot_btn.setStyleSheet(_btn_style(Palette.DANGER, "#fc8a8a"))
        self.stop_bot_btn.setMinimumHeight(40)
        self.stop_bot_btn.setEnabled(False)
        self.stop_bot_btn.clicked.connect(self.stop_bot)

        self.restart_bot_btn = QPushButton("↺  Restart")
        self.restart_bot_btn.setStyleSheet(
            _btn_style(Palette.BG_INPUT, Palette.BG_HOVER,
                       Palette.ACCENT, f"1px solid {Palette.ACCENT_BORDER}")
        )
        self.restart_bot_btn.setMinimumHeight(40)
        self.restart_bot_btn.setEnabled(False)
        self.restart_bot_btn.clicked.connect(self.restart_bot)

        btn_row.addWidget(self.start_bot_btn)
        btn_row.addWidget(self.stop_bot_btn)
        btn_row.addWidget(self.restart_bot_btn)
        lay.addLayout(btn_row)
        return frame

    # ── Configuration ────────────────────────────────────────────────────────
    def _build_config_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        lay.addWidget(_SectionHeader("Bot Configuration"))
        lay.addWidget(_Divider())

        # Token field
        token_lbl = QLabel("Bot Token")
        token_lbl.setStyleSheet(_label_style(12, "600", Palette.TEXT_SECONDARY))
        lay.addWidget(token_lbl)

        token_row = QHBoxLayout()
        token_row.setSpacing(8)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Paste your BotFather token…")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setMinimumHeight(38)
        self.token_input.setStyleSheet(_input_style())

        self.show_token_btn = QPushButton("👁")
        self.show_token_btn.setFixedSize(38, 38)
        self.show_token_btn.setStyleSheet(
            _btn_style(Palette.BG_INPUT, Palette.BG_HOVER,
                       Palette.TEXT_SECONDARY, f"1px solid {Palette.BORDER_LIGHT}")
        )
        self.show_token_btn.clicked.connect(self.toggle_token_visibility)

        token_row.addWidget(self.token_input)
        token_row.addWidget(self.show_token_btn)
        lay.addLayout(token_row)

        # Admin Usernames field
        admin_lbl = QLabel("Admin Usernames  <span style='font-size:11px; "
                           f"color:{Palette.TEXT_MUTED};'>(comma-separated, no @)</span>")
        admin_lbl.setTextFormat(Qt.TextFormat.RichText)
        admin_lbl.setStyleSheet(_label_style(12, "600", Palette.TEXT_SECONDARY))
        lay.addWidget(admin_lbl)

        self.admin_input = QLineEdit()
        self.admin_input.setPlaceholderText("adamreal, janedoe, …")
        self.admin_input.setMinimumHeight(38)
        self.admin_input.setStyleSheet(_input_style())
        lay.addWidget(self.admin_input)

        # Admin User IDs field (preferred — ID-based, more secure than username)
        admin_id_lbl = QLabel(
            "Admin User IDs  <span style='font-size:11px; "
            f"color:{Palette.TEXT_MUTED};'>(numeric IDs, comma-separated — "
            f"<a style='color:{Palette.ACCENT}; text-decoration:none;' "
            f"href='https://t.me/userinfobot'>get your ID →</a>)</span>"
        )
        admin_id_lbl.setTextFormat(Qt.TextFormat.RichText)
        admin_id_lbl.setOpenExternalLinks(True)
        admin_id_lbl.setStyleSheet(_label_style(12, "600", Palette.TEXT_SECONDARY))
        lay.addWidget(admin_id_lbl)

        self.admin_id_input = QLineEdit()
        self.admin_id_input.setPlaceholderText("123456789, 987654321, …")
        self.admin_id_input.setMinimumHeight(38)
        self.admin_id_input.setStyleSheet(_input_style())
        lay.addWidget(self.admin_id_input)

        # Info note about ID vs username
        id_note = QLabel(
            f"<span style='color:{Palette.SUCCESS}; font-size:11px;'>✓ User ID</span>"
            f"<span style='color:{Palette.TEXT_MUTED}; font-size:11px;'> lebih aman — tidak berubah meskipun username diganti</span>"
        )
        id_note.setTextFormat(Qt.TextFormat.RichText)
        id_note.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(id_note)

        # Save button
        save_btn = QPushButton("💾  Save Configuration")
        save_btn.setStyleSheet(_btn_style(Palette.ACCENT, Palette.ACCENT_HOVER))
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_bot_config)
        lay.addWidget(save_btn)

        # BotFather hint
        hint = QLabel(
            f"<a style='color:{Palette.ACCENT}; text-decoration:none;' "
            f"href='https://t.me/BotFather'>Get a token from @BotFather →</a>"
        )
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet(f"font-size:11px; background:transparent; border:none;")
        lay.addWidget(hint)
        return frame

    # ── User Management ──────────────────────────────────────────────────────
    def _build_users_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_SectionHeader("Users"))
        hdr_row.addStretch()
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setStyleSheet(
            _btn_style(Palette.BG_INPUT, Palette.BG_HOVER,
                       Palette.ACCENT, f"1px solid {Palette.BORDER_LIGHT}")
        )
        refresh_btn.clicked.connect(self.refresh_user_data)
        hdr_row.addWidget(refresh_btn)
        lay.addLayout(hdr_row)
        lay.addWidget(_Divider())

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(4)
        self.user_table.setHorizontalHeaderLabels(["Username", "User ID", "Status", "Downloads"])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.user_table.setMaximumHeight(190)
        self.user_table.setShowGrid(False)
        self.user_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 7px 10px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {Palette.ACCENT_DIM};
                color: {Palette.ACCENT};
            }}
            QTableWidget::item:alternate {{
                background-color: {Palette.BG_HOVER};
            }}
            QHeaderView::section {{
                background-color: {Palette.BG_CARD};
                color: {Palette.TEXT_SECONDARY};
                font-weight: 600;
                font-size: 11px;
                padding: 8px 10px;
                border: none;
                border-bottom: 1px solid {Palette.BORDER};
                letter-spacing: 0.5px;
            }}
        """)
        lay.addWidget(self.user_table)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.block_btn   = QPushButton("🚫  Block")
        self.unblock_btn = QPushButton("✅  Unblock")

        self.block_btn.setStyleSheet(
            _btn_style(Palette.DANGER_DIM, "rgba(248,113,113,0.25)",
                       Palette.DANGER, f"1px solid {Palette.DANGER}")
        )
        self.unblock_btn.setStyleSheet(
            _btn_style(Palette.SUCCESS_DIM, "rgba(79,214,156,0.25)",
                       Palette.SUCCESS, f"1px solid {Palette.SUCCESS}")
        )
        for b in (self.block_btn, self.unblock_btn):
            b.setMinimumHeight(34)

        self.block_btn.clicked.connect(self.block_user)
        self.unblock_btn.clicked.connect(self.unblock_user)

        action_row.addWidget(self.block_btn)
        action_row.addWidget(self.unblock_btn)
        action_row.addStretch()
        lay.addLayout(action_row)
        return frame

    # ── Log Panel ────────────────────────────────────────────────────────────
    def _build_log_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_SectionHeader("Live Log", "REALTIME"))
        hdr_row.addStretch()

        clear_btn = QPushButton("🗑  Clear")
        export_btn = QPushButton("↗  Export")
        for b in (clear_btn, export_btn):
            b.setMinimumHeight(30)
            b.setStyleSheet(
                _btn_style(Palette.BG_INPUT, Palette.BG_HOVER,
                           Palette.TEXT_SECONDARY, f"1px solid {Palette.BORDER_LIGHT}")
            )
        clear_btn.clicked.connect(self.clear_logs)
        export_btn.clicked.connect(self.export_logs)

        hdr_row.addWidget(clear_btn)
        hdr_row.addSpacing(6)
        hdr_row.addWidget(export_btn)
        lay.addLayout(hdr_row)
        lay.addWidget(_Divider())

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(280)
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Palette.BG_DEEP};
                color: {Palette.TEXT_CODE};
                border: 1px solid {Palette.BORDER};
                border-radius: 8px;
                padding: 12px;
                font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
                font-size: 11px;
                line-height: 1.5;
            }}
            QScrollBar:vertical {{
                background: {Palette.BG_CARD}; width: 4px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {Palette.BORDER_LIGHT}; border-radius: 2px;
            }}
        """)
        lay.addWidget(self.log_display)
        return frame

    # ── Instructions Panel ───────────────────────────────────────────────────
    def _build_instructions_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        lay.addWidget(_SectionHeader("Quick Reference"))
        lay.addWidget(_Divider())

        commands = [
            ("/start",    "Start the bot & see welcome"),
            ("/download", "<url>  — Download video"),
            ("/audio",    "<url>  — Extract MP3 audio"),
            ("/status",   "Show active downloads"),
            ("/menu",     "Interactive button menu ☰"),
            ("/stats",    "Admin: usage statistics"),
            ("/logs",     "Admin: download log file"),
        ]

        grid = QWidget()
        grid.setStyleSheet("background:transparent;")
        g_lay = QVBoxLayout(grid)
        g_lay.setContentsMargins(0, 0, 0, 0)
        g_lay.setSpacing(6)

        for cmd, desc in commands:
            row = QHBoxLayout()
            cmd_lbl = QLabel(cmd)
            cmd_lbl.setFixedWidth(100)
            cmd_lbl.setStyleSheet(
                f"color:{Palette.ACCENT}; font-family:'Consolas',monospace; "
                f"font-size:12px; font-weight:700; background:transparent; border:none;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                f"color:{Palette.TEXT_SECONDARY}; font-size:12px; "
                f"background:transparent; border:none;"
            )
            row.addWidget(cmd_lbl)
            row.addWidget(desc_lbl)
            row.addStretch()
            g_lay.addLayout(row)

        lay.addWidget(grid)

        open_btn = QPushButton("📖  Full Documentation")
        open_btn.setMinimumHeight(34)
        open_btn.setStyleSheet(
            _btn_style(Palette.BG_INPUT, Palette.BG_HOVER,
                       Palette.ACCENT, f"1px solid {Palette.ACCENT_BORDER}")
        )
        open_btn.clicked.connect(self.open_full_instructions)
        lay.addWidget(open_btn)
        return frame

    # ─────────────────────────────────────────────────────────────────────────
    # BUSINESS LOGIC  (identical contracts as before)
    # ─────────────────────────────────────────────────────────────────────────
    def load_bot_settings(self):
        try:
            config = self.parent.config
            self.token_input.setText(config.get("telegram_bot_token", ""))

            # Load admin usernames (legacy)
            admins = config.get("admin_users", [])
            self.admin_input.setText(", ".join(admins) if isinstance(admins, list) else str(admins))

            # Load admin user IDs (preferred)
            admin_ids = config.get("admin_user_ids", [])
            self.admin_id_input.setText(
                ", ".join(str(i) for i in admin_ids) if isinstance(admin_ids, list) else str(admin_ids)
            )
            self.update_bot_status()
        except Exception as e:
            print(f"Error loading bot settings: {e}")

    def save_bot_config(self):
        try:
            token = self.token_input.text().strip()

            # Admin usernames (legacy)
            admin_text = self.admin_input.text().strip()
            admins = [u.strip().lstrip("@") for u in admin_text.split(",") if u.strip()] if admin_text else []

            # Admin user IDs (preferred) — parse as integers, skip invalid
            admin_id_text = self.admin_id_input.text().strip()
            admin_ids = []
            invalid_ids = []
            for part in admin_id_text.split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    admin_ids.append(int(part))
                except ValueError:
                    invalid_ids.append(part)

            if invalid_ids:
                QMessageBox.warning(
                    self.parent, "Invalid User IDs",
                    "ID berikut bukan angka dan diabaikan:\n"
                    + ", ".join(invalid_ids)
                    + "\n\nUser ID harus berupa angka, contoh: 123456789"
                )

            self.parent.config["telegram_bot_token"] = token
            self.parent.config["admin_users"] = admins
            self.parent.config["admin_user_ids"] = admin_ids
            self.parent.save_config()
            self._toast("Configuration saved ✓", Palette.SUCCESS)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", f"Failed to save: {str(e)}")

    def save_bot_config_silent(self):
        try:
            token = self.token_input.text().strip()
            admin_text = self.admin_input.text().strip()
            admins = [u.strip().lstrip("@") for u in admin_text.split(",") if u.strip()] if admin_text else []
            admin_id_text = self.admin_id_input.text().strip()
            admin_ids = []
            for part in admin_id_text.split(","):
                part = part.strip()
                try:
                    if part:
                        admin_ids.append(int(part))
                except ValueError:
                    pass
            self.parent.config["telegram_bot_token"] = token
            self.parent.config["admin_users"] = admins
            self.parent.config["admin_user_ids"] = admin_ids
            self.parent.save_config()
        except Exception as e:
            print(f"Error saving bot config silently: {e}")

    def start_bot(self):
        try:
            token = self.token_input.text().strip()
            if not token:
                QMessageBox.warning(self.parent, "Token Required",
                                    "Please enter a bot token first.")
                return
            self.save_bot_config_silent()
            from src.telegram_bot_manager import TelegramBotManager
            if not self.bot_manager:
                self.bot_manager = TelegramBotManager(self.parent)
            if not self.bot_manager.is_bot_running():
                self._set_running_state("starting")
                QTimer.singleShot(400, self._do_start)
            else:
                self._toast("Bot is already running", Palette.WARNING)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", f"Start failed: {str(e)}")
            self.update_bot_status()

    def _do_start(self):
        try:
            success = self.bot_manager.start_bot()
            if success:
                self.update_bot_status()
                self._toast("Bot started successfully ✓", Palette.SUCCESS)
            else:
                QMessageBox.critical(self.parent, "Error",
                                     "Failed to start bot. Check your token and try again.")
                self.update_bot_status()
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))
            self.update_bot_status()

    def stop_bot(self):
        try:
            if not (self.bot_manager and self.bot_manager.is_bot_running()):
                self._toast("Bot is not running", Palette.WARNING)
                return
            self._set_running_state("stopping")
            import threading
            def _stop():
                try:
                    success = self.bot_manager.stop_bot()
                    QTimer.singleShot(100, self.update_bot_status)
                    msg = "Bot stopped ✓" if success else "Bot may already be stopped"
                    color = Palette.SUCCESS if success else Palette.WARNING
                    QTimer.singleShot(200, lambda: self._toast(msg, color))
                except Exception as ex:
                    print(f"Stop error: {ex}")
                    QTimer.singleShot(100, self.update_bot_status)
            threading.Thread(target=_stop, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))
            self.update_bot_status()

    def restart_bot(self):
        try:
            self._set_running_state("stopping")
            import threading, time
            def _restart():
                try:
                    if self.bot_manager and self.bot_manager.is_bot_running():
                        self.bot_manager.stop_bot()
                    time.sleep(2)
                    from PyQt6.QtCore import QMetaObject
                    QMetaObject.invokeMethod(self, "start_bot",
                                             Qt.ConnectionType.QueuedConnection)
                except Exception as ex:
                    print(f"Restart error: {ex}")
                    QTimer.singleShot(100, self.update_bot_status)
            threading.Thread(target=_restart, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))
            self.update_bot_status()

    def update_bot_status(self):
        try:
            is_running = bool(self.bot_manager and self.bot_manager.is_bot_running())
            state = "running" if is_running else "stopped"
            self.bot_status_display.set_state(state)
            self._header_badge.set_state(state)
            self.start_bot_btn.setEnabled(not is_running)
            self.stop_bot_btn.setEnabled(is_running)
            self.restart_bot_btn.setEnabled(is_running)
        except Exception as e:
            print(f"Error updating bot status: {e}")

    def _set_running_state(self, state: str):
        """Transitional state (starting / stopping)."""
        self.bot_status_display.set_state(state)
        self._header_badge.set_state(state)
        for b in (self.start_bot_btn, self.stop_bot_btn, self.restart_bot_btn):
            b.setEnabled(False)

    def toggle_token_visibility(self):
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_token_btn.setText("🙈")
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_token_btn.setText("👁")

    # ── User table ────────────────────────────────────────────────────────────
    def refresh_user_data(self):
        try:
            self.user_table.setRowCount(0)
            users = []
            if self.bot_manager and self.bot_manager.is_bot_running():
                try:
                    bi = self.bot_manager.bot_instance
                    if bi and hasattr(bi, "get_user_stats"):
                        users = bi.get_user_stats()
                except Exception:
                    pass
            if not users:
                users = self.load_user_data_from_file()

            if not users:
                self.user_table.setRowCount(1)
                empty_items = ["No users yet", "—", "Waiting for connections…", "0"]
                for col, txt in enumerate(empty_items):
                    item = QTableWidgetItem(txt)
                    item.setForeground(QColor(Palette.TEXT_MUTED))
                    self.user_table.setItem(0, col, item)
                return

            self.user_table.setRowCount(len(users))
            STATUS_COLORS = {
                "Aktif":    Palette.SUCCESS,
                "Diblokir": Palette.DANGER,
            }
            for row, u in enumerate(users):
                username  = u.get("username", f"user_{u.get('user_id','?')}")
                user_id   = str(u.get("user_id", "N/A"))
                status    = u.get("status", "Aktif")
                downloads = str(u.get("download_count", 0))

                color = STATUS_COLORS.get(status, Palette.TEXT_SECONDARY)

                for col, txt in enumerate([username, user_id, status, downloads]):
                    item = QTableWidgetItem(txt)
                    if col == 2:                         # status column gets colour
                        item.setForeground(QColor(color))
                    else:
                        item.setForeground(QColor(Palette.TEXT_PRIMARY))
                    self.user_table.setItem(row, col, item)
        except Exception as e:
            print(f"Error refreshing user data: {e}")

    def load_user_data_from_file(self):
        try:
            if os.path.exists("bot_users.json"):
                with open("bot_users.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading user data: {e}")
        return []

    def block_user(self):
        row = self.user_table.currentRow()
        if row < 0:
            self._toast("Select a user first", Palette.WARNING); return
        username = self.user_table.item(row, 0).text()
        user_id  = self.user_table.item(row, 1).text()
        if QMessageBox.question(
                self.parent, "Block User",
                f"Block <b>{username}</b>?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            if self.update_user_status(user_id, "Diblokir"):
                self.user_table.setItem(row, 2, QTableWidgetItem("Diblokir"))
                self.user_table.item(row, 2).setForeground(QColor(Palette.DANGER))
                self._toast(f"{username} blocked", Palette.DANGER)
            else:
                QMessageBox.critical(self.parent, "Error", f"Failed to block {username}")

    def unblock_user(self):
        row = self.user_table.currentRow()
        if row < 0:
            self._toast("Select a user first", Palette.WARNING); return
        username = self.user_table.item(row, 0).text()
        user_id  = self.user_table.item(row, 1).text()
        if QMessageBox.question(
                self.parent, "Unblock User",
                f"Unblock <b>{username}</b>?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            if self.update_user_status(user_id, "Aktif"):
                self.user_table.setItem(row, 2, QTableWidgetItem("Aktif"))
                self.user_table.item(row, 2).setForeground(QColor(Palette.SUCCESS))
                self._toast(f"{username} unblocked", Palette.SUCCESS)
            else:
                QMessageBox.critical(self.parent, "Error", f"Failed to unblock {username}")

    def update_user_status(self, user_id: str, new_status: str) -> bool:
        try:
            if (self.bot_manager and self.bot_manager.is_bot_running()
                    and self.bot_manager.bot_instance
                    and hasattr(self.bot_manager.bot_instance, "update_user_status")):
                return self.bot_manager.bot_instance.update_user_status(int(user_id), new_status)
            # file fallback
            data = self.load_user_data_from_file()
            for u in data:
                if str(u.get("user_id")) == user_id:
                    u["status"] = new_status
                    with open("bot_users.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    return True
            return False
        except Exception as e:
            print(f"Error updating user status: {e}"); return False

    # ── Log ───────────────────────────────────────────────────────────────────
    def update_logs(self):
        try:
            log_content = ""
            for log_file in ("bot_logs.log", "telegram_bot.log", "logs/bot.log"):
                if os.path.exists(log_file):
                    try:
                        mtime = os.path.getmtime(log_file)
                        if self._last_log_mtime.get(log_file) == mtime:
                            return          # unchanged
                        self._last_log_mtime[log_file] = mtime
                        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                            try:
                                with open(log_file, "r", encoding=enc) as f:
                                    lines = f.readlines()
                                    log_content = "".join(lines[-150:])
                                    break
                            except UnicodeDecodeError:
                                continue
                        if log_content:
                            break
                    except Exception:
                        continue

            if not log_content:
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self.bot_manager and self.bot_manager.is_bot_running():
                    log_content = (f"[{ts}]  ● Bot is running — activity will appear here in real-time\n"
                                   f"[{ts}]  ✉  Send a message to your bot to see logs\n")
                else:
                    log_content = (f"[{ts}]  ○ Bot is not running\n"
                                   f"[{ts}]  ▶  Click 'Start Bot' to begin\n")

            sb = self.log_display.verticalScrollBar()
            at_bottom = sb.value() >= sb.maximum() - 10
            self.log_display.setPlainText(log_content)
            if at_bottom:
                sb.setValue(sb.maximum())
        except Exception as e:
            print(f"Error updating logs: {e}")

    def clear_logs(self):
        if QMessageBox.question(
            self.parent, "Clear Logs", "Clear all log content?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.log_display.clear()
            if os.path.exists("bot_logs.log"):
                open("bot_logs.log", "w").close()
            self._toast("Logs cleared", Palette.SUCCESS)

    def export_logs(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Export Log",
                f"bot_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.log_display.toPlainText())
                self._toast(f"Exported → {os.path.basename(filename)}", Palette.SUCCESS)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))

    # ── Statistics ────────────────────────────────────────────────────────────
    def refresh_statistics(self):
        try:
            total_users = active_users = total_downloads = 0
            uptime = "00:00:00"

            if self.bot_manager and self.bot_manager.is_bot_running():
                if hasattr(self.bot_manager, "start_time"):
                    delta = datetime.datetime.now() - self.bot_manager.start_time
                    h, r = divmod(int(delta.total_seconds()), 3600)
                    m, s = divmod(r, 60)
                    uptime = f"{h:02d}:{m:02d}:{s:02d}"
                try:
                    bi = self.bot_manager.bot_instance
                    if bi and hasattr(bi, "get_statistics"):
                        st = bi.get_statistics()
                        total_users     = st.get("total_users", 0)
                        active_users    = st.get("active_users", 0)
                        total_downloads = st.get("total_downloads", 0)
                except Exception:
                    pass

            if total_users == 0:
                data = self.load_user_data_from_file()
                total_users = len(data)
                now = datetime.datetime.now()
                for u in data:
                    total_downloads += u.get("download_count", 0)
                    la = u.get("last_activity")
                    if la:
                        try:
                            if (now - datetime.datetime.fromisoformat(la)).days <= 30:
                                active_users += 1
                        except Exception:
                            pass

            if self._stat_users:
                self._stat_users.set_value(str(total_users))
                self._stat_active.set_value(str(active_users))
                self._stat_downloads.set_value(str(total_downloads))
                self._stat_uptime.set_value(uptime)
        except Exception as e:
            print(f"Error refreshing statistics: {e}")

    def update_uptime_display(self):
        try:
            if (self.bot_manager and self.bot_manager.is_bot_running()
                    and hasattr(self.bot_manager, "start_time")):
                delta = datetime.datetime.now() - self.bot_manager.start_time
                h, r = divmod(int(delta.total_seconds()), 3600)
                m, s = divmod(r, 60)
                if self._stat_uptime:
                    self._stat_uptime.set_value(f"{h:02d}:{m:02d}:{s:02d}")
            else:
                if self._stat_uptime:
                    self._stat_uptime.set_value("00:00:00")
        except Exception as e:
            print(f"Error updating uptime: {e}")

    def auto_refresh_data(self):
        try:
            import time
            self.refresh_statistics()
            now = time.time()
            if now - self._last_user_refresh > 30:
                self.refresh_user_data()
                self._last_user_refresh = now
            self.update_bot_status()
        except Exception as e:
            print(f"Error in auto refresh: {e}")

    # ── Misc ──────────────────────────────────────────────────────────────────
    def open_full_instructions(self):
        import subprocess, platform
        f = "TELEGRAM_BOT_INSTRUCTIONS_ID.md"
        if os.path.exists(f):
            try:
                if platform.system() == "Windows":    os.startfile(f)
                elif platform.system() == "Darwin":   subprocess.run(["open", f])
                else:                                  subprocess.run(["xdg-open", f])
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))
        else:
            QMessageBox.information(self.parent, "Not Found",
                                    "Documentation file not found. Visit GitHub for details.")

    def _toast(self, message: str, color: str = Palette.SUCCESS):
        """Show a temporary status message in the log area header."""
        # Simple approach: flash the header badge text
        self.bot_status_display.setText(message)
        self.bot_status_display.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: transparent;
                border: 1px solid {color};
                border-radius: 10px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        QTimer.singleShot(2500, self.update_bot_status)
