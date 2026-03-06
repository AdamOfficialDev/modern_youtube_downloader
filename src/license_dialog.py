"""
License Dialog — Modern Video Downloader
=========================================
Dialog aktivasi lisensi dengan UI profesional (dark theme).
Muncul otomatis saat startup jika aplikasi belum diaktivasi.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QApplication, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QBrush, QLinearGradient

from src.license_manager import LicenseManager, PLANS


# ── Palette ───────────────────────────────────────────────────────────────────
class _P:
    BG_DEEP      = "#0a0c14"
    BG_CARD      = "#10131e"
    BG_INPUT     = "#1a1d31"
    BG_HOVER     = "#1f2338"
    BORDER       = "#252840"
    BORDER_LIGHT = "#2e3352"
    ACCENT       = "#4f8ef7"
    ACCENT_DIM   = "rgba(79,142,247,0.12)"
    GREEN        = "#3ecf8e"
    RED          = "#f56565"
    AMBER        = "#f5a623"
    TXT_PRIMARY  = "#e8ecff"
    TXT_SEC      = "#8b93b8"
    TXT_MUTED    = "#525a7a"
    PLAN_COLORS  = {
        'T': "#f5a623", 'B': "#4a9eff",
        'P': "#9b59b6", 'E': "#2ecc71", 'L': "#e74c3c",
    }


# ── Auto-formatting code input ────────────────────────────────────────────────
class _CodeInput(QLineEdit):
    """QLineEdit yang otomatis memformat kode sebagai XXXXX-XXXXX-XXXXX-XXXXX-XXXXX."""

    complete = pyqtSignal()   # emited ketika 25 karakter sudah diisi

    _RAW_LEN = 25

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxLength(29)   # 25 alnum + 4 dashes
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_P.BG_INPUT};
                color: {_P.TXT_PRIMARY};
                border: 2px solid {_P.BORDER_LIGHT};
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 18px;
                font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
                font-weight: 700;
                letter-spacing: 2px;
                selection-background-color: {_P.ACCENT};
            }}
            QLineEdit:focus {{
                border: 2px solid {_P.ACCENT};
                background-color: {_P.BG_HOVER};
            }}
        """)
        self._updating = False
        self.textChanged.connect(self._auto_format)

    def _auto_format(self, text: str):
        if self._updating:
            return
        self._updating = True

        # Ambil hanya karakter alphanumeric, uppercase, maks 25
        clean = ''.join(c for c in text.upper() if c.isalnum())[:self._RAW_LEN]

        # Potong per 5 char, gabung dengan dash
        parts = [clean[i:i+5] for i in range(0, len(clean), 5)]
        formatted = '-'.join(parts)

        self.setText(formatted)
        self.setCursorPosition(len(formatted))
        self._updating = False

        if len(clean) == self._RAW_LEN:
            self.complete.emit()

    def raw_code(self) -> str:
        """Kembalikan kode tanpa dash."""
        return self.text().replace('-', '')

    def is_complete(self) -> bool:
        return len(self.raw_code()) == self._RAW_LEN

    def set_error_style(self):
        self.setStyleSheet(self.styleSheet().replace(
            f"border: 2px solid {_P.BORDER_LIGHT};",
            f"border: 2px solid {_P.RED};"
        ))
        QTimer.singleShot(1500, self.reset_style)

    def reset_style(self):
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_P.BG_INPUT};
                color: {_P.TXT_PRIMARY};
                border: 2px solid {_P.BORDER_LIGHT};
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 18px;
                font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
                font-weight: 700;
                letter-spacing: 2px;
                selection-background-color: {_P.ACCENT};
            }}
            QLineEdit:focus {{
                border: 2px solid {_P.ACCENT};
                background-color: {_P.BG_HOVER};
            }}
        """)


# ── Paket Badge ───────────────────────────────────────────────────────────────
class _PlanBadge(QLabel):
    def __init__(self, key: str, info: dict, parent=None):
        super().__init__(parent)
        color = _P.PLAN_COLORS.get(key, _P.ACCENT)
        self.setText(f"  {info['name']}  ")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: transparent;
                border: 1px solid {color};
                border-radius: 8px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)


# ── Main Dialog ───────────────────────────────────────────────────────────────
class LicenseDialog(QDialog):
    """
    Dialog aktivasi lisensi.

    Cara pakai::

        mgr = LicenseManager(BASE_PATH)
        if not mgr.is_activated():
            dlg = LicenseDialog(mgr)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                sys.exit(0)
    """

    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self._mgr = license_manager

        self.setWindowTitle("Aktivasi Lisensi — Modern Video Downloader")
        self.setFixedSize(580, 640)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(f"QDialog {{ background-color: {_P.BG_DEEP}; }}")

        self._build_ui()

    # ── UI Builder ────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top gradient header
        root.addWidget(self._build_header())

        # Main card
        card = QWidget()
        card.setStyleSheet(f"background-color: {_P.BG_DEEP};")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(40, 30, 40, 30)
        card_lay.setSpacing(20)

        # ── Code input section
        card_lay.addWidget(self._lbl("Masukkan Kode Lisensi Anda", size=14,
                                     weight="700", color=_P.TXT_SEC))

        self._code_input = _CodeInput()
        self._code_input.complete.connect(self._on_code_complete)
        card_lay.addWidget(self._code_input)

        # ── Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setMinimumHeight(36)
        self._status_lbl.setStyleSheet(
            f"color: {_P.TXT_MUTED}; font-size: 12px; background: transparent;"
        )
        card_lay.addWidget(self._status_lbl)

        # ── Activate button
        self._activate_btn = QPushButton("🔓  Aktifkan Sekarang")
        self._activate_btn.setMinimumHeight(52)
        self._activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._activate_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_P.ACCENT}, stop:1 #6b5cf6);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6ba3ff, stop:1 #7c6cf7);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3a7be0, stop:1 #5a4de0);
            }}
            QPushButton:disabled {{
                background: {_P.BG_INPUT};
                color: {_P.TXT_MUTED};
            }}
        """)
        self._activate_btn.clicked.connect(self._do_activate)
        card_lay.addWidget(self._activate_btn)

        # ── Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {_P.BORDER}; border: none;")
        card_lay.addWidget(div)

        # ── Paket info grid
        card_lay.addWidget(self._lbl("Paket Tersedia", size=13,
                                     weight="700", color=_P.TXT_SEC))
        card_lay.addWidget(self._build_plans_grid())

        # Spacer
        card_lay.addStretch()

        # ── Contact footer
        card_lay.addWidget(self._build_footer())

        root.addWidget(card)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(130)
        w.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d1229, stop:0.6 #131630, stop:1 #0a0c14);
                border-bottom: 1px solid {_P.BORDER};
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(4)

        # Icon + App name row
        top_row = QHBoxLayout()
        icon_lbl = QLabel("🎥")
        icon_lbl.setStyleSheet("font-size: 36px; background: transparent; border: none;")
        top_row.addWidget(icon_lbl)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        app_name = QLabel("Modern Video Downloader")
        app_name.setStyleSheet(
            f"color: {_P.TXT_PRIMARY}; font-size: 18px; font-weight: 800; "
            f"background: transparent; border: none;"
        )
        by_label = QLabel("by Adam Official Dev")
        by_label.setStyleSheet(
            f"color: {_P.TXT_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        name_col.addWidget(app_name)
        name_col.addWidget(by_label)
        top_row.addLayout(name_col)
        top_row.addStretch()
        lay.addLayout(top_row)

        # Sub-heading
        sub = QLabel("⚠️  Aktivasi diperlukan untuk menggunakan semua fitur")
        sub.setStyleSheet(
            f"color: {_P.AMBER}; font-size: 12px; font-weight: 600; "
            f"background: transparent; border: none;"
        )
        lay.addWidget(sub)
        return w

    def _build_plans_grid(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        grid = QHBoxLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        for key, info in PLANS.items():
            cell = QFrame()
            cell.setStyleSheet(f"""
                QFrame {{
                    background-color: {_P.BG_CARD};
                    border: 1px solid {_P.BORDER_LIGHT};
                    border-radius: 8px;
                }}
            """)
            cell_lay = QVBoxLayout(cell)
            cell_lay.setContentsMargins(10, 10, 10, 10)
            cell_lay.setSpacing(4)

            badge = _PlanBadge(key, info)
            cell_lay.addWidget(badge)

            dur = QLabel(info['label'])
            dur.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dur.setStyleSheet(
                f"color: {_P.TXT_SEC}; font-size: 10px; background: transparent; border: none;"
            )
            cell_lay.addWidget(dur)
            grid.addWidget(cell)

        return w

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        contact = QLabel(
            "📩  Butuh lisensi? Hubungi: "
            "<a style='color:#4f8ef7; text-decoration:none;' "
            "href='mailto:contact@adamofficial.dev'>contact@adamofficial.dev</a>"
            " &nbsp;|&nbsp; "
            "<a style='color:#4f8ef7; text-decoration:none;' "
            "href='https://github.com/AdamOfficialDev'>GitHub</a>"
        )
        contact.setOpenExternalLinks(True)
        contact.setTextFormat(Qt.TextFormat.RichText)
        contact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact.setStyleSheet(f"color: {_P.TXT_SEC}; font-size: 11px; background: transparent;")
        lay.addWidget(contact)
        return w

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lbl(self, text: str, size=12, weight="400", color=None) -> QLabel:
        lbl = QLabel(text)
        color = color or _P.TXT_PRIMARY
        lbl.setStyleSheet(
            f"color: {color}; font-size: {size}px; font-weight: {weight}; "
            f"background: transparent;"
        )
        return lbl

    def _set_status(self, msg: str, color: str):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: 600; background: transparent;"
        )

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _on_code_complete(self):
        """Kode sudah 25 char — validasi live (tanpa aktivasi)."""
        code = self._code_input.text()
        is_valid, plan_info, msg = self._mgr.validate_code(code)
        if is_valid:
            color = _P.PLAN_COLORS.get(code.replace('-','')[0], _P.GREEN)
            self._set_status(f"✅  {msg}", color)
        else:
            self._set_status(f"❌  {msg}", _P.RED)

    def _do_activate(self):
        """Tombol Aktifkan ditekan."""
        code = self._code_input.text().strip()
        if not code:
            self._set_status("⚠️  Masukkan kode lisensi terlebih dahulu", _P.AMBER)
            self._code_input.setFocus()
            return

        self._activate_btn.setEnabled(False)
        self._activate_btn.setText("⏳  Memvalidasi...")
        QApplication.processEvents()

        # Sedikit jeda agar UX terasa natural
        QTimer.singleShot(400, lambda: self._finish_activation(code))

    def _finish_activation(self, code: str):
        success, msg = self._mgr.activate(code)

        if success:
            self._set_status(msg, _P.GREEN)
            self._activate_btn.setText("✅  Aktivasi Berhasil!")
            self._activate_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_P.GREEN};
                    color: #fff;
                    border: none;
                    border-radius: 10px;
                    font-size: 15px;
                    font-weight: 800;
                }}
            """)
            # Tutup dialog setelah 1.5 detik
            QTimer.singleShot(1500, self.accept)
        else:
            self._set_status(f"❌  {msg}", _P.RED)
            self._code_input.set_error_style()
            self._activate_btn.setEnabled(True)
            self._activate_btn.setText("🔓  Aktifkan Sekarang")

    def closeEvent(self, event):
        """Tutup dialog = tolak (app akan exit)."""
        event.accept()
