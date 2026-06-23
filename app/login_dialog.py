# =============================================================
# GC Toxic Shield — Login Dialog (PySide6)
# =============================================================
# Modal login dialog yang muncul:
# - Saat aplikasi pertama dibuka
# - Saat dashboard dipanggil dari System Tray
# - Saat user ingin Exit dari tray
#
# Non-blocking: menggunakan QDialog dengan exec_()
# =============================================================

import logging
from typing import Callable, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QHBoxLayout, QApplication
)
from PySide6.QtCore import Qt, QTimer

logger = logging.getLogger("GCToxicShield.Login")


class LoginDialog(QDialog):
    """
    Modal login dialog menggunakan PySide6.
    """

    def __init__(
        self,
        auth_service,
        on_success: Callable,
        on_cancel: Optional[Callable] = None,
        exit_mode: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self._auth = auth_service
        self._on_success = on_success
        self._on_cancel = on_cancel
        self._exit_mode = exit_mode
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)
        self._remaining_seconds = 0

        # Window Setup
        self.setWindowTitle("🔒 Login — GC Toxic Shield")
        self.setFixedSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) # Remove ? button
        
        # Center Window
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - 400) // 2, (screen.height() - 300) // 2)

        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #E8EAED; font-family: "Segoe UI"; }
            QLineEdit { background-color: #161B22; color: white; border: 1px solid #21262D; border-radius: 6px; padding: 8px; font-size: 14px; }
            QPushButton { border-radius: 6px; font-weight: bold; font-family: "Segoe UI"; padding: 8px; font-size: 13px; }
            QPushButton#BtnLogin { background-color: #1565C0; color: white; }
            QPushButton#BtnLogin:hover { background-color: #0D47A1; }
            QPushButton#BtnCancel { background-color: #424242; color: white; }
            QPushButton#BtnCancel:hover { background-color: #616161; }
        """)

        self._build_ui()
        self._check_lockout_on_open()
        logger.info("Login dialog opened (exit_mode=%s)", exit_mode)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #1a1a2e;")
        h_lyt = QVBoxLayout(header)
        h_lbl = QLabel("🔒 Authentication Required")
        h_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        h_lbl.setAlignment(Qt.AlignCenter)
        h_lyt.addWidget(h_lbl)
        main_layout.addWidget(header)

        # Content
        content = QFrame()
        c_lyt = QVBoxLayout(content)
        c_lyt.setContentsMargins(30, 20, 30, 20)
        c_lyt.setSpacing(12)

        info_text = "Masukkan password untuk keluar dari aplikasi" if self._exit_mode else "Masukkan password administrator"
        lbl_info = QLabel(info_text)
        lbl_info.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        lbl_info.setAlignment(Qt.AlignCenter)
        c_lyt.addWidget(lbl_info)

        self._password_entry = QLineEdit()
        self._password_entry.setPlaceholderText("Password...")
        self._password_entry.setEchoMode(QLineEdit.Password)
        self._password_entry.returnPressed.connect(self._attempt_login)
        c_lyt.addWidget(self._password_entry)

        self._login_btn = QPushButton("🔓 Login")
        self._login_btn.setObjectName("BtnLogin")
        self._login_btn.setFixedHeight(38)
        self._login_btn.clicked.connect(self._attempt_login)
        c_lyt.addWidget(self._login_btn)

        btn_cancel = QPushButton("Batal")
        btn_cancel.setObjectName("BtnCancel")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self._cancel)
        c_lyt.addWidget(btn_cancel)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #FF5252; font-size: 12px;")
        self._status_label.setAlignment(Qt.AlignCenter)
        c_lyt.addWidget(self._status_label)

        c_lyt.addStretch()
        main_layout.addWidget(content)
        
        # Focus password field
        QTimer.singleShot(100, self._password_entry.setFocus)

    def _check_lockout_on_open(self):
        locked, remaining = self._auth.is_locked_out()
        if locked:
             self._start_lockout_countdown(remaining)

    def _attempt_login(self):
        password = self._password_entry.text().strip()
        if not password:
            self._status_label.setText("⚠ Password tidak boleh kosong!")
            self._status_label.setStyleSheet("color: #FFA726;")
            return

        success, message = self._auth.login(password)
        if success:
            self._status_label.setText("✅ " + message)
            self._status_label.setStyleSheet("color: #66BB6A;")
            logger.info("✓ Login successful via dialog")
            if self._on_success: self._on_success()
            self.accept() # Close dialog with accepted state
        else:
            self._status_label.setText("❌ " + message)
            self._status_label.setStyleSheet("color: #FF5252;")
            self._password_entry.clear()
            self._password_entry.setFocus()

            locked, remaining = self._auth.is_locked_out()
            if locked:
                self._start_lockout_countdown(remaining)

    def _start_lockout_countdown(self, seconds: int):
        self._password_entry.setEnabled(False)
        self._login_btn.setEnabled(False)
        self._remaining_seconds = seconds
        self._countdown_timer.start(1000)
        self._update_countdown() # Immediate update

    def _update_countdown(self):
        if self._remaining_seconds <= 0:
            self._countdown_timer.stop()
            self._password_entry.setEnabled(True)
            self._login_btn.setEnabled(True)
            self._status_label.setText("🔓 Silakan coba lagi")
            self._status_label.setStyleSheet("color: #66BB6A;")
            self._password_entry.setFocus()
            return

        self._status_label.setText(f"🔒 Terkunci! Tunggu {self._remaining_seconds} detik...")
        self._status_label.setStyleSheet("color: #FF5252;")
        self._remaining_seconds -= 1

    def closeEvent(self, event):
        self._cancel()
        event.accept()

    def _cancel(self):
        logger.info("Login dialog cancelled")
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
        if self._on_cancel:
            self._on_cancel()
        self.reject()

def show_login_dialog(auth_service, on_success: Callable, exit_mode: bool = False, on_cancel: Optional[Callable] = None, parent=None):
    """Factory helper untuk menampilkan dialog."""
    dlg = LoginDialog(auth_service, on_success, on_cancel, exit_mode, parent)
    dlg.exec()
