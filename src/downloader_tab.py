from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QDialog, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QScrollArea, QWidget, QGraphicsDropShadowEffect,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QRect
from PyQt6.QtGui import QPixmap, QColor, QPalette, QFont, QLinearGradient, QPainter, QBrush, QPen
import os
import threading
import yt_dlp
import requests
import json
from PIL import Image
from io import BytesIO


# ══════════════════════════════════════════════════════════════════
#  DESIGN TOKENS  — dynamic, theme-aware
# ══════════════════════════════════════════════════════════════════
class T:
    """All colour tokens. Call T.set_dark() / T.set_light() to switch themes."""

    # Accents & status — same in both themes
    ACCENT              = "#4f8ef7"
    ACCENT_BRIGHT       = "#6ba3ff"
    ACCENT_DIM          = "rgba(79,142,247,0.10)"
    INPUT_BORDER_FOCUS  = "#4f8ef7"
    GREEN               = "#3ecf8e"
    RED                 = "#f56565"
    AMBER               = "#f5a623"
    R_SM  = "4px"
    R_MD  = "8px"
    R_LG  = "12px"

    # Dark-mode defaults
    BG_BASE        = "#0a0c14"
    BG_CARD        = "#10131e"
    BG_ELEVATED    = "#161925"
    BG_INPUT       = "#1c2030"
    BG_HOVER       = "#1e2235"
    TXT_PRIMARY    = "#dde1f5"
    TXT_SECONDARY  = "#6b7394"
    TXT_MUTED      = "#3e4462"
    INPUT_BORDER   = "#262d45"
    BORDER         = "#1e2438"
    BORDER_LIGHT   = "#2a3050"

    @classmethod
    def set_dark(cls):
        cls.BG_BASE       = "#0a0c14"
        cls.BG_CARD       = "#10131e"
        cls.BG_ELEVATED   = "#161925"
        cls.BG_INPUT      = "#1c2030"
        cls.BG_HOVER      = "#1e2235"
        cls.TXT_PRIMARY   = "#dde1f5"
        cls.TXT_SECONDARY = "#6b7394"
        cls.TXT_MUTED     = "#3e4462"
        cls.INPUT_BORDER  = "#262d45"
        cls.BORDER        = "#1e2438"
        cls.BORDER_LIGHT  = "#2a3050"

    @classmethod
    def set_light(cls):
        cls.BG_BASE       = "#f0f2f8"
        cls.BG_CARD       = "#ffffff"
        cls.BG_ELEVATED   = "#e8ebf4"
        cls.BG_INPUT      = "#ffffff"
        cls.BG_HOVER      = "#eef0f8"
        cls.TXT_PRIMARY   = "#1a1d2e"
        cls.TXT_SECONDARY = "#5a6080"
        cls.TXT_MUTED     = "#9ba3c0"
        cls.INPUT_BORDER  = "#d0d4e8"
        cls.BORDER        = "#dde0ee"
        cls.BORDER_LIGHT  = "#c8ccde"


# ══════════════════════════════════════════════════════════════════
#  DOWNLOAD THREAD
# ══════════════════════════════════════════════════════════════════
class DownloadThread(QThread):
    progress_signal = pyqtSignal(dict)
    status_signal   = pyqtSignal(str)
    finished        = pyqtSignal()

    def __init__(self, url, format_id, output_path, convert_to_mp3=False):
        super().__init__()
        self.url            = url
        self.format_id      = format_id
        self.output_path    = output_path
        self.convert_to_mp3 = convert_to_mp3
        self.paused         = False
        self._stop          = False

    def run(self):
        try:
            output_template = os.path.join(self.output_path, '%(title)s.%(ext)s')
            ydl_opts = {
                'outtmpl': output_template,
                'progress_hooks': [self._progress_hook],
                'retries': 10,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'nocheckcertificate': True
            }
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

            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
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
            total      = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            speed      = d.get('speed', 0)
            percent    = (downloaded / total * 100) if total > 0 else 0
            self.progress_signal.emit({
                'status': 'Downloading',
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': speed,
                'eta': d.get('eta', 0),
                'percent': percent
            })
        elif d['status'] == 'finished':
            msg = 'Download completed, converting to MP3…' if self.convert_to_mp3 else 'Processing file…'
            self.status_signal.emit(msg)

    def pause(self):  self.paused = True
    def resume(self): self.paused = False
    def stop(self):
        self._stop = True
        self.resume()


# ══════════════════════════════════════════════════════════════════
#  STYLED WIDGETS
# ══════════════════════════════════════════════════════════════════
class GlowButton(QPushButton):
    """Buttons — border: none except inputs. Cards & buttons use bg only."""
    def __init__(self, text="", variant="primary", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._apply_style()

    def _apply_style(self):
        if self.variant == "primary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {T.ACCENT}, stop:1 #6b5cf6);
                    color: #ffffff;
                    border: none;
                    border-radius: {T.R_MD};
                    padding: 11px 28px;
                    font-size: 13px;
                    font-weight: 700;
                    letter-spacing: 0.4px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {T.ACCENT_BRIGHT}, stop:1 #7c6cf7);
                }}
                QPushButton:pressed {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 #3a7be0, stop:1 #5a4de0);
                }}
                QPushButton:disabled {{
                    background: {T.BG_ELEVATED};
                    color: {T.TXT_MUTED};
                    border: none;
                }}
            """)
        elif self.variant == "secondary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {T.BG_ELEVATED};
                    color: {T.TXT_SECONDARY};
                    border: 1px solid {T.INPUT_BORDER};
                    border-radius: {T.R_MD};
                    padding: 10px 22px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {T.BG_HOVER};
                    color: {T.TXT_PRIMARY};
                    border-color: #303759;
                }}
                QPushButton:pressed {{ background: {T.BG_INPUT}; }}
                QPushButton:disabled {{
                    background: {T.BG_CARD};
                    color: {T.TXT_MUTED};
                    border-color: {T.INPUT_BORDER};
                }}
            """)
        elif self.variant == "ghost":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {T.TXT_SECONDARY};
                    border: 1px solid {T.INPUT_BORDER};
                    border-radius: {T.R_MD};
                    padding: 9px 18px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {T.BG_ELEVATED};
                    color: {T.TXT_PRIMARY};
                    border-color: #303759;
                }}
                QPushButton:pressed {{ background: {T.BG_INPUT}; }}
                QPushButton:disabled {{ color: {T.TXT_MUTED}; border-color: {T.INPUT_BORDER}; }}
            """)
        elif self.variant == "danger":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(245,101,101,0.10);
                    color: {T.RED};
                    border: none;
                    border-radius: {T.R_MD};
                    padding: 10px 22px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: rgba(245,101,101,0.18); }}
                QPushButton:disabled {{ opacity: 0.35; }}
            """)


class SectionCard(QFrame):
    """Card: no border — depth via background tone alone."""
    def __init__(self, owner=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {T.BG_CARD};
                border: none;
                border-radius: {T.R_LG};
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 18)
        self._layout.setSpacing(10)
        if owner is not None:
            owner._cards.append(self)

    def layout(self):
        return self._layout


class PillLabel(QLabel):
    """Small pill/badge label."""
    def __init__(self, text, color=T.ACCENT, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: rgba(79,142,247,0.12);
                border: 1px solid rgba(79,142,247,0.3);
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
        """)


class StyledInput(QLineEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T.BG_INPUT};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                padding: 10px 14px;
                font-size: 13px;
                selection-background-color: {T.ACCENT};
            }}
            QLineEdit:focus {{
                border: 1px solid {T.INPUT_BORDER_FOCUS};
                background-color: {T.BG_ELEVATED};
            }}
            QLineEdit:hover:!focus {{
                border-color: #303759;
            }}
        """)


class StyledCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {T.BG_INPUT};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                padding: 9px 14px;
                font-size: 12px;
                min-width: 200px;
            }}
            QComboBox:hover {{ border-color: #303759; }}
            QComboBox:focus {{ border-color: {T.INPUT_BORDER_FOCUS}; }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {T.TXT_SECONDARY};
                margin-right: 8px;
            }}
            QComboBox:disabled {{
                color: {T.TXT_MUTED};
                border-color: {T.INPUT_BORDER};
                background: {T.BG_CARD};
            }}
            QComboBox QAbstractItemView {{
                background-color: {T.BG_ELEVATED};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                selection-background-color: rgba(79,142,247,0.12);
                selection-color: {T.ACCENT_BRIGHT};
                padding: 4px;
            }}
        """)


class AnimatedProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {T.BG_INPUT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACCENT}, stop:1 {T.GREEN});
                border-radius: 3px;
            }}
        """)


class InfoRow(QWidget):
    """Key-value info row with dot separator."""
    def __init__(self, key, value="-", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._dot = QLabel("·")
        self._dot.setStyleSheet(f"color: {T.TXT_MUTED}; font-size: 16px; background: transparent;")
        self._dot.setFixedWidth(10)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFixedWidth(80)
        self._key_lbl.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; font-weight: 500; background: transparent;")

        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color: {T.TXT_PRIMARY}; font-size: 12px; background: transparent;")
        self.val_lbl.setWordWrap(True)

        lay.addWidget(self._dot)
        lay.addWidget(self._key_lbl)
        lay.addWidget(self.val_lbl, 1)

    def set_value(self, v):
        self.val_lbl.setText(v)


class SectionTitle(QWidget):
    """Section header with title + optional pill badge."""
    def __init__(self, title, badge=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(10)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"""
            color: {T.TXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.3px;
            background: transparent;
        """)
        lay.addWidget(lbl)

        if badge:
            lay.addWidget(PillLabel(badge))

        lay.addStretch()


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("background-color: rgba(255,255,255,0.04); border: none;")


# ══════════════════════════════════════════════════════════════════
#  MAIN DOWNLOADER TAB
# ══════════════════════════════════════════════════════════════════
class DownloaderTab:
    def __init__(self, parent):
        self.parent = parent
        self.setup_ui()

    # ── Public interface ───────────────────────────────────────────
    def apply_professional_theme(self, is_dark_mode=False):
        """Called by settings_tab when theme changes. Re-applies all styles."""
        if is_dark_mode:
            T.set_dark()
        else:
            T.set_light()
        self._restyle_all()

    def _restyle_all(self):
        """Re-apply every stylesheet after token update."""
        p = self.parent

        # Root background
        p.downloader_tab.setStyleSheet(f"background-color: {T.BG_BASE};")
        self._scroll_content.setStyleSheet(f"background-color: {T.BG_BASE};")

        # Scroll area
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {T.BG_BASE}; }}
            QScrollBar:vertical {{
                background: {T.BG_CARD}; width: 5px;
                border-radius: 3px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {T.BORDER_LIGHT}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {T.ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        # Cards
        card_style = f"""
            QFrame {{
                background-color: {T.BG_CARD};
                border: none;
                border-radius: {T.R_LG};
            }}
        """
        for card in self._cards:
            card.setStyleSheet(card_style)

        # Header labels
        self._header_title.setStyleSheet(
            f"color: {T.TXT_PRIMARY}; font-size: 18px; font-weight: 800; background: transparent;")
        self._header_sub.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; background: transparent;")

        # Hint label
        self._url_hint.setStyleSheet(
            f"color: {T.TXT_MUTED}; font-size: 11px; background: transparent; margin-top: 2px;")

        # Section titles
        for lbl in self._section_title_labels:
            lbl.setStyleSheet(
                f"color: {T.TXT_PRIMARY}; font-size: 13px; font-weight: 700; "
                f"letter-spacing: 0.3px; background: transparent;")

        # Dividers
        for d in self._dividers:
            d.setStyleSheet("background-color: rgba(128,128,128,0.08); border: none;")

        # Info rows
        for key_lbl, val_lbl, dot in self._info_rows:
            dot.setStyleSheet(f"color: {T.TXT_MUTED}; font-size: 16px; background: transparent;")
            key_lbl.setStyleSheet(
                f"color: {T.TXT_SECONDARY}; font-size: 12px; font-weight: 500; background: transparent;")
            val_lbl.setStyleSheet(f"color: {T.TXT_PRIMARY}; font-size: 12px; background: transparent;")

        # Inputs
        input_style = f"""
            QLineEdit {{
                background-color: {T.BG_INPUT};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                padding: 10px 14px;
                font-size: 13px;
                selection-background-color: {T.ACCENT};
            }}
            QLineEdit:focus {{
                border: 1px solid {T.INPUT_BORDER_FOCUS};
                background-color: {T.BG_ELEVATED};
            }}
            QLineEdit:hover:!focus {{ border-color: {T.BORDER_LIGHT}; }}
        """
        for inp in (p.url_input, p.output_path):
            inp.setStyleSheet(input_style)

        # Combo
        combo_style = f"""
            QComboBox {{
                background-color: {T.BG_INPUT};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                padding: 9px 14px;
                font-size: 12px;
                min-width: 200px;
            }}
            QComboBox:hover {{ border-color: {T.BORDER_LIGHT}; }}
            QComboBox:focus {{ border-color: {T.INPUT_BORDER_FOCUS}; }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {T.TXT_SECONDARY};
                margin-right: 8px;
            }}
            QComboBox:disabled {{
                color: {T.TXT_MUTED};
                border-color: {T.INPUT_BORDER};
                background: {T.BG_CARD};
            }}
            QComboBox QAbstractItemView {{
                background-color: {T.BG_ELEVATED};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.INPUT_BORDER};
                border-radius: {T.R_MD};
                selection-background-color: {T.ACCENT_DIM};
                selection-color: {T.ACCENT_BRIGHT};
                padding: 4px;
            }}
        """
        p.format_combo.setStyleSheet(combo_style)

        # Checkbox
        p.mp3_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {T.TXT_SECONDARY};
                font-size: 12px;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox:hover {{ color: {T.TXT_PRIMARY}; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 1px solid {T.INPUT_BORDER};
                border-radius: 4px;
                background: {T.BG_INPUT};
            }}
            QCheckBox::indicator:hover {{ border-color: {T.ACCENT}; }}
            QCheckBox::indicator:checked {{
                background: {T.ACCENT};
                border-color: {T.ACCENT};
            }}
            QCheckBox:disabled {{ color: {T.TXT_MUTED}; }}
        """)

        # Quality label
        self._quality_lbl.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; font-weight: 500; background: transparent;")

        # Thumbnail placeholder
        p.thumbnail_label.setStyleSheet(f"""
            QLabel {{
                background-color: {T.BG_INPUT};
                border: none;
                border-radius: {T.R_MD};
                color: {T.TXT_MUTED};
                font-size: 11px;
            }}
        """)

        # Status label
        p.status_label.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; background: transparent; padding: 2px 0;")

        # Progress bar
        p.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {T.BG_INPUT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACCENT}, stop:1 {T.GREEN});
                border-radius: 3px;
            }}
        """)

        # Buttons — re-apply
        for btn in self._all_buttons:
            btn._apply_style()


    @property
    def formats_list(self):
        return getattr(self.parent, 'formats_list', [])

    # ── UI Construction ────────────────────────────────────────────
    def setup_ui(self):
        # Root layout (no margins – scroll area fills everything)
        main_layout = QVBoxLayout(self.parent.downloader_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Init tracking lists
        self._cards               = []
        self._section_title_labels= []
        self._dividers            = []
        self._info_rows           = []   # list of (key_lbl, val_lbl, dot)
        self._all_buttons         = []

        # Full-tab background
        self.parent.downloader_tab.setStyleSheet(f"background-color: {T.BG_BASE};")

        # Scroll area
        self._scroll = QScrollArea()
        scroll = self._scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {T.BG_BASE}; }}
            QScrollBar:vertical {{
                background: {T.BG_CARD}; width: 5px;
                border-radius: 3px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {T.BORDER_LIGHT}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {T.ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._scroll_content = QWidget()
        content = self._scroll_content
        content.setStyleSheet(f"background-color: {T.BG_BASE};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        # ── Page header
        layout.addWidget(self._build_page_header())

        # ── URL card
        layout.addWidget(self._build_url_card())

        # ── Info + thumbnail side-by-side
        info_row = QHBoxLayout()
        info_row.setSpacing(14)
        info_row.addWidget(self._build_info_card(), 3)
        info_row.addWidget(self._build_thumbnail_card(), 2)
        layout.addLayout(info_row)

        # ── Options row
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        opt_row.addWidget(self._build_quality_card(), 3)
        opt_row.addWidget(self._build_output_card(), 2)
        layout.addLayout(opt_row)

        # ── Download card
        layout.addWidget(self._build_download_card())

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Wire URL change
        self.parent.url_input.textChanged.connect(self.on_url_change)

    # ── Section builders ───────────────────────────────────────────
    def _build_page_header(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._header_title = QLabel("Video Downloader")
        self._header_title.setStyleSheet(
            f"color: {T.TXT_PRIMARY}; font-size: 18px; font-weight: 800; background: transparent;")
        self._header_sub = QLabel("Download from YouTube, Vimeo, Dailymotion and more")
        self._header_sub.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; background: transparent;")
        title_col.addWidget(self._header_title)
        title_col.addWidget(self._header_sub)

        lay.addLayout(title_col)
        lay.addStretch()
        return w

    def _make_section_title(self, title, badge=None):
        """Helper: build SectionTitle and track the label for restyle."""
        w = SectionTitle(title, badge)
        # Find the QLabel inside and track it
        for child in w.findChildren(QLabel):
            if child.text() == title:
                self._section_title_labels.append(child)
                break
        return w

    def _make_divider(self):
        d = Divider()
        self._dividers.append(d)
        return d

    def _build_url_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Video URL", "REQUIRED"))
        card.layout().addWidget(self._make_divider())

        row = QHBoxLayout()
        row.setSpacing(8)

        self.parent.url_input = StyledInput("Paste a video URL from any supported platform…")
        self.parent.url_input.setMinimumHeight(42)

        paste_btn = GlowButton("Paste", "ghost")
        paste_btn.setFixedHeight(42)
        paste_btn.setFixedWidth(80)
        paste_btn.clicked.connect(self.paste_url)
        self._all_buttons.append(paste_btn)

        row.addWidget(self.parent.url_input, 1)
        row.addWidget(paste_btn)
        card.layout().addLayout(row)

        self._url_hint = QLabel("Supports YouTube · Vimeo · Dailymotion · Twitter · TikTok · and 1000+ more")
        self._url_hint.setStyleSheet(
            f"color: {T.TXT_MUTED}; font-size: 11px; background: transparent; margin-top: 2px;")
        card.layout().addWidget(self._url_hint)
        return card

    def _build_info_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Video Information"))
        card.layout().addWidget(self._make_divider())

        self._row_title    = InfoRow("Title")
        self._row_duration = InfoRow("Duration")
        self._row_channel  = InfoRow("Channel")
        self._row_views    = InfoRow("Views")

        self.parent.title_label    = self._row_title.val_lbl
        self.parent.duration_label = self._row_duration.val_lbl
        self.parent.channel_label  = self._row_channel.val_lbl
        self.parent.views_label    = self._row_views.val_lbl

        for row in (self._row_title, self._row_duration, self._row_channel, self._row_views):
            card.layout().addWidget(row)
            self._info_rows.append((row._key_lbl, row.val_lbl, row._dot))

        card.layout().addStretch()
        return card

    def _build_thumbnail_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Preview"))
        card.layout().addWidget(self._make_divider())

        self.parent.thumbnail_label = QLabel()
        self.parent.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parent.thumbnail_label.setMinimumHeight(130)
        self.parent.thumbnail_label.setStyleSheet(f"""
            QLabel {{
                background-color: {T.BG_INPUT};
                border: none;
                border-radius: {T.R_MD};
                color: {T.TXT_MUTED};
                font-size: 11px;
            }}
        """)
        self.parent.thumbnail_label.setText("No preview")
        card.layout().addWidget(self.parent.thumbnail_label, 1)
        return card

    def _build_quality_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Quality & Format"))
        card.layout().addWidget(self._make_divider())

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)

        self._quality_lbl = QLabel("Quality")
        self._quality_lbl.setFixedWidth(62)
        self._quality_lbl.setStyleSheet(
            f"color: {T.TXT_SECONDARY}; font-size: 12px; font-weight: 500; background: transparent;")

        self.parent.format_combo = StyledCombo()
        self.parent.format_combo.setMinimumHeight(38)
        self.parent.format_combo.setEnabled(False)

        self.show_formats_button = GlowButton("Advanced", "ghost")
        self.show_formats_button.setMinimumHeight(38)
        self.show_formats_button.setFixedWidth(100)
        self.show_formats_button.clicked.connect(self.show_formats_dialog)
        self.show_formats_button.setEnabled(False)
        self._all_buttons.append(self.show_formats_button)

        fmt_row.addWidget(self._quality_lbl)
        fmt_row.addWidget(self.parent.format_combo, 1)
        fmt_row.addWidget(self.show_formats_button)
        card.layout().addLayout(fmt_row)

        self.parent.mp3_checkbox = QCheckBox("  Extract audio only  (MP3 · 192kbps)")
        self.parent.mp3_checkbox.setEnabled(False)
        self.parent.mp3_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {T.TXT_SECONDARY};
                font-size: 12px;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox:hover {{ color: {T.TXT_PRIMARY}; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 1px solid {T.INPUT_BORDER};
                border-radius: 4px;
                background: {T.BG_INPUT};
            }}
            QCheckBox::indicator:hover {{ border-color: {T.ACCENT}; }}
            QCheckBox::indicator:checked {{
                background: {T.ACCENT};
                border-color: {T.ACCENT};
                image: none;
            }}
            QCheckBox:disabled {{ color: {T.TXT_MUTED}; }}
        """)
        card.layout().addWidget(self.parent.mp3_checkbox)
        card.layout().addStretch()
        return card

    def _build_output_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Save Location"))
        card.layout().addWidget(self._make_divider())

        self.parent.output_path = StyledInput()
        self.parent.output_path.setText(os.path.join(os.path.expanduser("~"), "Videos", "Downloads"))
        self.parent.output_path.setMinimumHeight(38)

        browse_btn = GlowButton("Browse", "secondary")
        browse_btn.setMinimumHeight(38)
        browse_btn.clicked.connect(self.browse_output)
        browse_btn.setMinimumWidth(90)
        self._all_buttons.append(browse_btn)

        card.layout().addWidget(self.parent.output_path)
        card.layout().addWidget(browse_btn)
        card.layout().addStretch()
        return card

    def _build_download_card(self):
        card = SectionCard(owner=self)
        card.layout().addWidget(self._make_section_title("Download", "READY"))
        card.layout().addWidget(self._make_divider())

        self.parent.progress_bar = AnimatedProgressBar()
        self.parent.progress_bar.hide()
        card.layout().addWidget(self.parent.progress_bar)

        self.parent.status_label = QLabel("")
        self.parent.status_label.setStyleSheet(f"""
            QLabel {{
                color: {T.TXT_SECONDARY};
                font-size: 12px;
                background: transparent;
                padding: 2px 0;
            }}
        """)
        card.layout().addWidget(self.parent.status_label)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.parent.download_button = GlowButton("Start Download", "primary")
        self.parent.download_button.setMinimumHeight(44)
        self.parent.download_button.setMinimumWidth(160)
        self.parent.download_button.clicked.connect(self.start_download)
        self._all_buttons.append(self.parent.download_button)

        self.parent.pause_button = GlowButton("Pause", "secondary")
        self.parent.pause_button.setMinimumHeight(44)
        self.parent.pause_button.setMinimumWidth(100)
        self.parent.pause_button.clicked.connect(self.toggle_pause)
        self.parent.pause_button.setEnabled(False)
        self._all_buttons.append(self.parent.pause_button)

        btn_row.addWidget(self.parent.download_button)
        btn_row.addWidget(self.parent.pause_button)
        btn_row.addStretch()
        card.layout().addLayout(btn_row)
        return card

    # ── Business Logic ─────────────────────────────────────────────
    def paste_url(self):
        self.parent.url_input.setText(QApplication.clipboard().text())

    def browse_output(self):
        d = QFileDialog.getExistingDirectory(
            self.parent, "Select Output Directory",
            self.parent.output_path.text(), QFileDialog.Option.ShowDirsOnly)
        if d:
            self.parent.output_path.setText(d)

    def on_url_change(self):
        self.parent.progress_bar.setValue(0)
        self.parent.progress_bar.hide()
        self.parent.download_button.setEnabled(False)
        self.parent.format_combo.clear()

        url = self.parent.url_input.text().strip()
        if url:
            self.parent.status_label.setText("Fetching video info…")
            self.parent.status_label.setStyleSheet(
                f"color: {T.ACCENT}; font-size: 12px; background: transparent;")
            threading.Thread(target=self.fetch_video_info, daemon=True).start()
        else:
            self.parent.status_label.setText("")
            for lbl in (self.parent.title_label, self.parent.duration_label,
                        self.parent.channel_label, self.parent.views_label):
                lbl.setText("—")
            self.parent.thumbnail_label.setText("No preview")
            self.parent.thumbnail_label.setPixmap(QPixmap())

    def fetch_video_info(self):
        url = self.parent.url_input.text().strip()
        try:
            ydl_opts = {'quiet': True}
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    cookies_path = config.get('youtube_cookies_path')
                    if cookies_path and os.path.exists(cookies_path):
                        ydl_opts['cookiefile'] = cookies_path
                except Exception:
                    pass

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # Update info rows
            self.parent.title_label.setText(info.get('title', '—'))
            duration = info.get('duration', 0)
            self.parent.duration_label.setText(
                f"{duration // 60}:{duration % 60:02d}" if duration else "—")
            self.parent.channel_label.setText(info.get('uploader', '—'))
            views = info.get('view_count', 0)
            self.parent.views_label.setText(f"{views:,}" if views else "—")

            self.parent.formats_list = info.get('formats', [])
            self.update_format_combo()
            self.update_formats_button()

            # Thumbnail
            if 'thumbnail' in info:
                try:
                    resp = requests.get(info['thumbnail'], timeout=8)
                    img  = Image.open(BytesIO(resp.content))
                    img  = img.resize((280, 158), Image.Resampling.LANCZOS)
                    buf  = BytesIO()
                    img.save(buf, format='PNG')
                    pix  = QPixmap()
                    pix.loadFromData(buf.getvalue())
                    self.parent.thumbnail_label.setPixmap(
                        pix.scaled(self.parent.thumbnail_label.size(),
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))
                    self.parent.thumbnail_label.setText("")
                except Exception:
                    pass

            self.parent.status_label.setText("Ready to download")
            self.parent.status_label.setStyleSheet(
                f"color: {T.GREEN}; font-size: 12px; background: transparent;")

        except Exception as e:
            msg = str(e)
            if "Sign in to confirm" in msg:
                msg = "Anti-bot protection triggered — set up browser cookies in Settings."
            elif "Unsupported URL" in msg:
                msg = "Unsupported URL. Please check the link and try again."
            else:
                msg = f"Error: {msg}"
            self.parent.status_label.setText(msg)
            self.parent.status_label.setStyleSheet(
                f"color: {T.RED}; font-size: 12px; background: transparent;")
            self.parent.download_button.setEnabled(False)

    def update_format_combo(self):
        self.parent.format_combo.clear()
        has_audio = False
        for f in self.formats_list:
            ext  = f.get('ext', '')
            res  = f.get('resolution', 'N/A')
            note = f.get('format_note', '')
            if f.get('acodec', 'none') != 'none':
                has_audio = True
            desc = f"{res} ({note})" if note else res
            if ext:
                desc = f"{desc} · {ext}"
            self.parent.format_combo.addItem(desc, f.get('format_id', ''))

        self.parent.format_combo.setEnabled(self.parent.format_combo.count() > 0)
        self.parent.download_button.setEnabled(self.parent.format_combo.count() > 0)
        self.parent.mp3_checkbox.setEnabled(has_audio)

    def update_formats_button(self):
        has = bool(self.formats_list)
        self.show_formats_button.setEnabled(has)

    def start_download(self):
        url = self.parent.url_input.text().strip()
        if not url:
            QMessageBox.warning(self.parent, "Error", "Please enter a video URL")
            return
        format_id = self.parent.format_combo.currentText().split(" · ")[0]
        if not format_id:
            QMessageBox.warning(self.parent, "Error", "Please select a format")
            return
        output_path = self.parent.output_path.text()
        if not output_path:
            QMessageBox.warning(self.parent, "Error", "Please select an output directory")
            return

        self.parent.download_thread = DownloadThread(
            url, format_id, output_path, self.parent.mp3_checkbox.isChecked())
        self.parent.download_thread.progress_signal.connect(self.parent.update_progress)
        self.parent.download_thread.status_signal.connect(self.parent.update_status)
        self.parent.download_thread.finished.connect(self.parent.on_download_complete)

        self.parent.progress_bar.setValue(0)
        self.parent.progress_bar.show()
        self.parent.download_button.setEnabled(False)
        self.parent.pause_button.setEnabled(True)
        self.parent.pause_button.setText("Pause")
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

    # ── Advanced formats dialog ────────────────────────────────────
    def show_formats_dialog(self):
        if not self.formats_list:
            QMessageBox.warning(self.parent, "Error",
                                "No formats available. Enter a valid video URL first.")
            return

        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Format Selection")
        dialog.setMinimumWidth(820)
        dialog.setMinimumHeight(580)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {T.BG_BASE};
                color: {T.TXT_PRIMARY};
            }}
            QLabel {{
                color: {T.TXT_PRIMARY};
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        hdr = QLabel("Advanced Format Selection")
        hdr.setStyleSheet(f"color: {T.TXT_PRIMARY}; font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Mode:")
        mode_lbl.setFixedWidth(50)
        mode_lbl.setStyleSheet(f"color: {T.TXT_SECONDARY}; font-size: 12px;")
        self.mode_combo = StyledCombo()
        self.mode_combo.addItems(["Single Format", "Separate Video + Audio"])
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        tree_style = f"""
            QTreeWidget {{
                background-color: {T.BG_CARD};
                color: {T.TXT_PRIMARY};
                border: 1px solid {T.BORDER};
                border-radius: {T.R_MD};
                font-size: 12px;
                gridline-color: transparent;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 7px 10px;
                border-bottom: 1px solid {T.BORDER};
            }}
            QTreeWidget::item:selected {{
                background-color: {T.ACCENT_DIM};
                color: {T.ACCENT_BRIGHT};
                border-left: 2px solid {T.ACCENT};
            }}
            QTreeWidget::item:hover {{
                background-color: {T.BG_HOVER};
            }}
            QHeaderView::section {{
                background-color: {T.BG_ELEVATED};
                color: {T.TXT_SECONDARY};
                font-weight: 700;
                font-size: 11px;
                padding: 9px 10px;
                border: none;
                border-bottom: 1px solid {T.BORDER};
                letter-spacing: 0.5px;
            }}
        """

        self.video_tree = QTreeWidget()
        self.audio_tree = QTreeWidget()
        for tree in (self.video_tree, self.audio_tree):
            tree.setHeaderLabels(["ID", "Extension", "Resolution / Bitrate", "FPS", "Size", "Codec"])
            tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
            tree.setStyleSheet(tree_style)

        self.video_label = QLabel("Video Formats")
        self.audio_label = QLabel("Audio Formats")
        for lbl in (self.video_label, self.audio_label):
            lbl.setStyleSheet(f"color: {T.TXT_SECONDARY}; font-size: 12px; font-weight: 600; margin-top: 4px;")

        self.tree_stack = QVBoxLayout()
        self.tree_stack.addWidget(self.video_label)
        self.tree_stack.addWidget(self.video_tree)
        self.tree_stack.addWidget(self.audio_label)
        self.tree_stack.addWidget(self.audio_tree)
        layout.addLayout(self.tree_stack)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        ok_btn     = GlowButton("Apply Selection", "primary")
        cancel_btn = GlowButton("Cancel", "ghost")
        ok_btn.setMinimumHeight(40)
        cancel_btn.setMinimumHeight(40)
        ok_btn.clicked.connect(lambda: self._handle_format_selection(dialog))
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        # Populate
        video_items, audio_items = [], []
        for f in self.formats_list:
            size = f.get('filesize', 0)
            size_str = f"{size/1024/1024:.1f} MB" if size and size > 0 else "—"
            is_video = f.get('vcodec') != 'none'
            res = f.get('resolution', '—')
            if not is_video:
                res = f"{f.get('abr', '—')}kbps"
            fps = str(f.get('fps', '—')) if is_video else '—'
            item = QTreeWidgetItem([
                f.get('format_id', '—'), f.get('ext', '—'), res, fps, size_str,
                f.get('vcodec', '—') if is_video else f.get('acodec', '—')
            ])
            (video_items if is_video else audio_items).append(item)

        video_items.sort(key=lambda x: self._get_resolution_value(x.text(2)), reverse=True)
        audio_items.sort(key=lambda x: self._get_bitrate_value(x.text(2)),    reverse=True)
        self.video_tree.addTopLevelItems(video_items)
        self.audio_tree.addTopLevelItems(audio_items)

        self.mode_combo.currentTextChanged.connect(self._update_selection_mode)
        self._update_selection_mode(self.mode_combo.currentText())
        dialog.exec()

    def _handle_format_selection(self, dialog):
        if self.mode_combo.currentText() == "Single Format":
            items = self.video_tree.selectedItems()
            if not items:
                QMessageBox.warning(self.parent, "Selection Error", "Please select a format.")
                return
            fid = items[0].text(0)
        else:
            v_items = self.video_tree.selectedItems()
            a_items = self.audio_tree.selectedItems()
            if not v_items or not a_items:
                QMessageBox.warning(self.parent, "Selection Error",
                                    "Please select both a video and an audio format.")
                return
            fid = f"{v_items[0].text(0)}+{a_items[0].text(0)}"

        self.parent.format_combo.clear()
        self.parent.format_combo.addItem(fid, fid)
        self.parent.format_combo.setCurrentText(fid)
        dialog.accept()

    def _update_selection_mode(self, mode):
        if mode == "Single Format":
            self.video_tree.clear()
            all_items = []
            for f in self.formats_list:
                size = f.get('filesize', 0)
                size_str = f"{size/1024/1024:.1f} MB" if size and size > 0 else "—"
                is_video = f.get('vcodec') != 'none'
                res = f.get('resolution', '—')
                if not is_video:
                    res = f"{f.get('abr', '—')}kbps"
                fps = str(f.get('fps', '—')) if is_video else '—'
                all_items.append(QTreeWidgetItem([
                    f.get('format_id', '—'), f.get('ext', '—'), res, fps, size_str,
                    f.get('vcodec', '—') if is_video else f.get('acodec', '—')
                ]))
            all_items.sort(key=lambda x: (
                self._get_resolution_value(x.text(2)),
                self._get_bitrate_value(x.text(2))
            ), reverse=True)
            self.video_tree.addTopLevelItems(all_items)
            self.audio_tree.setVisible(False)
            self.audio_label.setVisible(False)
            self.video_label.setText("Available Formats")
        else:
            self.video_label.setText("Video Formats")
            self.audio_tree.setVisible(True)
            self.audio_label.setVisible(True)

    def _get_resolution_value(self, res):
        try:
            return int(res.split('p')[0])
        except Exception:
            return -1

    def _get_bitrate_value(self, br):
        try:
            return float(br.replace('kbps', ''))
        except Exception:
            return -1
