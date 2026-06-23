# =============================================================
# GC Toxic Shield — Tiered Warning & Lockdown Overlay (PySide6)
# =============================================================
# Sistem penindakan:
#   Level 1-2 (mod 3): WarningBox (pesan + tombol delayed)
#   Level 3   (mod 3): LockdownOverlay (fullscreen + kutipan)
#   Siklus berulang setiap kelipatan 3.
#
# Features:
#   - IsPenaltyActive: block new violations during active penalty
#   - Admin Override: hidden password input + Enter key unlock
#   - Anti-Brute Force on lockdown override
#   - Penalty Reset timer (60m default)
#
# Referensi: ConfigManager.cs & StaticData.cs
# =============================================================

import time
import logging
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from app import static_data

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.Overlay")


# ================================================================
# WARNING BOX (Level 1-2 dalam siklus 3)
# ================================================================

class WarningBox(QDialog):
    """
    Jendela peringatan yang muncul di tengah layar.
    Tombol 'Saya Mengerti' di-disable selama WarningDelaySeconds.
    """

    def __init__(
        self,
        level: int,
        matched_words: list,
        auth_service=None,
        warning_delay: int = 5,
        message: str = None,
        on_dismiss: Callable = None,
        parent=None,
    ):
        super().__init__(parent)
        self._auth = auth_service
        self._delay = warning_delay
        self._custom_message = message
        self._on_dismiss = on_dismiss
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._timer_tick)
        self._remaining = 0

        # Window Setup
        self.setWindowTitle("⚠️ Peringatan — GC Toxic Shield")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(560, 480)

        # Center on screen
        if parent: 
            self.move(parent.geometry().center() - self.rect().center())
        else:
            # Fallback centering
            screen_geom = QApplication.primaryScreen().geometry()
            x = (screen_geom.width() - self.width()) // 2
            y = (screen_geom.height() - self.height()) // 2
            self.move(x, y)

        self._build_ui(level, matched_words)
        
        self._start_delay_countdown(self._delay)
        logger.info("WarningBox shown (level %d, delay %ds)", level, warning_delay)
        
        self.setWindowModality(Qt.ApplicationModal)
        self.show()

        # Focus enforcement timer (200ms)
        self._focus_timer = QTimer(self)
        self._focus_timer.timeout.connect(self._enforce_focus)
        self._focus_timer.start(200)

    def _build_ui(self, level: int, matched_words: list):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        card = QFrame()
        card.setFixedSize(560, 480)
        card.setStyleSheet("background-color: #121212; color: white; border-radius: 12px; border: 2px solid #333333;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("background-color: #FFC107; border-top-left-radius: 10px; border-top-right-radius: 10px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px; border: none;")
        h_lyt = QVBoxLayout(header)
        h_lyt.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"⚠️ PERINGATAN PELANGGARAN LEVEL {level}")
        title.setStyleSheet("font-size: 22px; font-weight: 900; color: #000000; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignCenter)
        h_lyt.addWidget(title)
        layout.addWidget(header)

        # Content
        content = QFrame()
        content.setStyleSheet("border: none;")
        c_lyt = QVBoxLayout(content)
        c_lyt.setContentsMargins(40, 30, 40, 30)
        c_lyt.setSpacing(20)

        # "Apa yang terjadi?"
        info_lbl = QLabel("Tindakan Anda melanggar aturan komunikasi.")
        info_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #E0E0E0;")
        info_lbl.setAlignment(Qt.AlignCenter)
        c_lyt.addWidget(info_lbl)

        # Message
        msg_text = self._custom_message if self._custom_message else static_data.get_message(level)
        msg_lbl = QLabel(msg_text)
        msg_lbl.setStyleSheet("font-size: 18px; color: #FFFFFF;")
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        c_lyt.addWidget(msg_lbl)

        # Words Highlight Box
        if matched_words:
            w_frame = QFrame()
            w_frame.setStyleSheet("background-color: rgba(255, 82, 82, 0.15); border: 2px solid #FF5252; border-radius: 8px;")
            wf_lyt = QVBoxLayout(w_frame)
            wf_lyt.setContentsMargins(15, 15, 15, 15)
            
            w_lbl = QLabel(f"KATA TERDETEKSI:\n{', '.join(matched_words).upper()}")
            w_lbl.setStyleSheet("font-size: 16px; font-weight: 900; color: #FF5252; border: none;")
            w_lbl.setAlignment(Qt.AlignCenter)
            w_lbl.setWordWrap(True)
            wf_lyt.addWidget(w_lbl)
            c_lyt.addWidget(w_frame)
            
        c_lyt.addStretch()

        self._ack_btn = QPushButton(f"SAYA MENGERTI ({self._delay}s)")
        self._ack_btn.setFixedHeight(55)
        self._ack_btn.setEnabled(False)
        self._ack_btn.setCursor(Qt.PointingHandCursor)
        self._ack_btn.setStyleSheet("""
            QPushButton { background-color: #424242; color: #9E9E9E; border-radius: 8px; font-size: 17px; font-weight: 900; border: none; }
            QPushButton:enabled { background-color: #FFC107; color: #000000; }
            QPushButton:enabled:hover { background-color: #FFB300; }
        """)
        self._ack_btn.clicked.connect(self._dismiss)
        c_lyt.addWidget(self._ack_btn)

        layout.addWidget(content)
        main_layout.addWidget(card)

    def _start_delay_countdown(self, remaining: int):
        self._remaining = remaining
        if remaining > 0:
            self._ack_btn.setText(f"SAYA MENGERTI ({self._remaining}s)")
            self._countdown_timer.start(1000)
        else:
            self._timer_tick()

    def _timer_tick(self):
        # Selalu paksa fokus meskipun waktu hitung mundur habis agar tidak di-bypass
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
        if self._remaining > 0:
            self._remaining -= 1
            if self._remaining <= 0:
                self._ack_btn.setEnabled(True)
                self._ack_btn.setText("SAYA MENGERTI ✓")
            else:
                self._ack_btn.setText(f"SAYA MENGERTI ({self._remaining}s)")

    def closeEvent(self, event):
        """Intercept X button — require password."""
        if self._auth:
            event.ignore()
            self._show_password_prompt()
        else:
            self._dismiss()

    def _show_password_prompt(self):
        from app.login_dialog import show_login_dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show() # Refresh flags
        
        def _on_cancel():
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()

        show_login_dialog(
            auth_service=self._auth,
            on_success=self._force_dismiss,
            on_cancel=_on_cancel,
            exit_mode=True,
            parent=self
        )

    def _force_dismiss(self):
        logger.info("WarningBox force-dismissed via password")
        self._dismiss()

    def _enforce_focus(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _dismiss(self):
        if hasattr(self, "_focus_timer"):
            self._focus_timer.stop()
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
        logger.info("WarningBox dismissed")
        if self._on_dismiss:
            try: self._on_dismiss()
            except Exception: pass
        self.accept()


# ================================================================
# SIMPLE WARNING BOX (Surgical Downloads Guard)
# ================================================================

class SimpleWarningBox(QDialog):
    _instance = None
    
    def __init__(self, custom_text=None, parent=None):
        if SimpleWarningBox._instance is not None:
            return
            
        SimpleWarningBox._instance = self
        super().__init__(parent)
        
        self.setWindowTitle("⚠️ Peringatan Sistem")
        self.setFixedSize(450, 220)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #0D1117; color: white; border-radius: 10px; border: 2px solid #D32F2F;")
        
        if parent: self.move(parent.geometry().center() - self.rect().center())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        h = QLabel("🚨 DILARANG 🚨")
        h.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF5252;")
        h.setAlignment(Qt.AlignCenter)
        layout.addWidget(h)
        
        txt = custom_text if custom_text else "Dilarang mengunduh dan mengeksekusi installer di folder Downloads."
        m = QLabel(txt)
        m.setStyleSheet("font-size: 14px;")
        m.setAlignment(Qt.AlignCenter)
        m.setWordWrap(True)
        layout.addWidget(m)
        
        btn = QPushButton("OK, Saya Mengerti")
        btn.setFixedHeight(35)
        btn.setFixedWidth(200)
        btn.setStyleSheet("background-color: #161B22; color: white; border: 1px solid #21262D; border-radius: 6px; font-weight: bold;")
        btn.clicked.connect(self._dismiss)
        
        # Center the button
        h_lyt = QVBoxLayout()
        h_lyt.setAlignment(Qt.AlignCenter)
        h_lyt.addWidget(btn)
        layout.addLayout(h_lyt)
        
        self.setWindowModality(Qt.ApplicationModal)
        self.show()
        
        # Focus enforcement timer
        self._focus_timer = QTimer(self)
        self._focus_timer.timeout.connect(self._enforce_focus)
        self._focus_timer.start(500)
        
    def _enforce_focus(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _dismiss(self):
        if hasattr(self, "_focus_timer"):
            self._focus_timer.stop()
        SimpleWarningBox._instance = None
        self.accept()


# ================================================================
# LOCKDOWN OVERLAY (Level 3 dalam siklus 3)
# ================================================================

class LockdownOverlay:
    """
    Fullscreen overlay yang muncul saat lockdown aktif (kelipatan 3).
    """

    MAX_OVERRIDE_ATTEMPTS = 3
    OVERRIDE_LOCKOUT_SEC = 30

    def __init__(self, parent=None, auth_service=None):
        self._parent = parent
        self._auth = auth_service
        self._overlay_window = None
        self._is_active = False
        self._remaining_seconds = 0
        self._on_dismiss = None
        self._on_unlock = None

        self._override_attempt_count = 0
        self._override_lockout_until = 0.0

        self._hook_installed = False
        self._hook_handle = None
        self._hook_callback = None

    @property
    def is_active(self) -> bool:
        return self._is_active

    def show(self, level: int, matched_words: list = None, duration: int = 60,
             on_dismiss: Callable = None, on_unlock: Callable = None):
        if self._is_active: return

        self._on_dismiss = on_dismiss
        self._on_unlock = on_unlock

        lockdown_title = "AREA TERKUNCI"
        lockdown_message = "Anda melanggar aturan berbahasa di GC Net."
        if self._auth:
            lockdown_title = self._auth.get_config("LockdownTitle", lockdown_title)
            lockdown_message = self._auth.get_config("LockdownMessage", lockdown_message)

        logger.warning(f"🔒 LOCKDOWN ACTIVATED | Level {level} | Duration: {duration}s")
        self._is_active = True
        self._remaining_seconds = duration
        self._override_attempt_count = 0
        self._override_lockout_until = 0.0

        quote = static_data.get_random_quote(level)
        self._create_overlay(level, lockdown_title, lockdown_message, duration, matched_words or [], quote)
        self._install_keyboard_hook()

    def dismiss(self):
        self._is_active = False
        if self._overlay_window:
            if self._overlay_window._countdown_timer.isActive():
                self._overlay_window._countdown_timer.stop()
            self._overlay_window.close()
            self._overlay_window = None

        self._remove_keyboard_hook()
        logger.info("🔓 LOCKDOWN DISMISSED")
        if self._on_dismiss:
            try: self._on_dismiss()
            except Exception: pass

    def _create_overlay(self, level, title, message, duration, matched_words, quote):
        self._overlay_window = LockdownWindow(self, level, title, message, duration, matched_words, quote)
        self._overlay_window.showFullScreen()

    # ================================================================
    # INPUT BLOCKING
    # ================================================================

    def _install_keyboard_hook(self):
        if self._hook_installed: return
        try:
            import ctypes
            import ctypes.wintypes

            WH_KEYBOARD_LL = 13
            WM_KEYDOWN = 0x0100
            WM_SYSKEYDOWN = 0x0104
            VK_TAB = 0x09
            VK_LWIN = 0x5B
            VK_RWIN = 0x5C
            VK_ESCAPE = 0x1B
            VK_F4 = 0x73

            HOOKPROC = ctypes.CFUNCTYPE(ctypes.wintypes.LPARAM, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            def keyboard_hook_proc(nCode, wParam, lParam):
                if nCode >= 0 and self._is_active:
                    vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value
                    # Block Alt+Tab
                    if wParam == WM_SYSKEYDOWN and vk_code == VK_TAB: return 1
                    # Block Win keys
                    if vk_code in (VK_LWIN, VK_RWIN): return 1
                    # Block Ctrl+Esc (Task Manager shortcut)
                    if vk_code == VK_ESCAPE:
                        if user32.GetAsyncKeyState(0x11) & 0x8000: return 1
                    # Block Alt+F4
                    if wParam == WM_SYSKEYDOWN and vk_code == VK_F4: return 1
                    # Block Alt+Esc
                    if wParam == WM_SYSKEYDOWN and vk_code == VK_ESCAPE: return 1
                    # Block Ctrl+Shift+Esc (Task Manager)
                    if vk_code == VK_ESCAPE:
                        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
                        shift = user32.GetAsyncKeyState(0x10) & 0x8000
                        if ctrl and shift: return 1
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            self._hook_callback = HOOKPROC(keyboard_hook_proc)
            self._hook_handle = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._hook_callback, kernel32.GetModuleHandleW(None), 0
            )

            if self._hook_handle:
                self._hook_installed = True
            else:
                logger.warning("Hook unavailable. Run as Admin. Continuing.")
        except Exception as e:
            logger.warning("Hook error: %s — continuing without hook", e)

    def _remove_keyboard_hook(self):
        if not self._hook_installed or not self._hook_handle: return
        try:
            import ctypes
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_installed = False
            self._hook_handle = None
        except Exception: pass


class LockdownWindow(QDialog):
    """Actual fullscreen QDialog for Lockdown."""
    def __init__(self, manager: LockdownOverlay, level, title, message, duration, matched_words, quote):
        super().__init__()
        self._manager = manager
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2b0000, stop:1 #0a0000);
                font-family: 'Segoe UI';
            }
        """)
        self.setAttribute(Qt.WA_TranslucentBackground, False) # True breaks click-through sometimes, making it 95% opacity works

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(25)
        
        icon = QLabel("🔒")
        icon.setStyleSheet("font-size: 120px; color: #FF3333;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        t = QLabel(title.upper())
        t.setStyleSheet("font-size: 48px; font-weight: 900; color: #FF1744; letter-spacing: 2px;")
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)

        m = QLabel(f"KENAPA SAYA DIBLOKIR?\n{message}")
        m.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        m.setAlignment(Qt.AlignCenter)
        m.setWordWrap(True)
        layout.addWidget(m)

        l = QLabel(f"⚠ PELANGGARAN KE-{level}")
        l.setStyleSheet("font-size: 18px; font-weight: 900; color: #FF6D00; background-color: rgba(255,109,0,0.15); padding: 5px 15px; border-radius: 8px;")
        l.setAlignment(Qt.AlignCenter)
        
        l_lyt = QHBoxLayout()
        l_lyt.setAlignment(Qt.AlignCenter)
        l_lyt.addWidget(l)
        layout.addLayout(l_lyt)

        if matched_words:
            w = QLabel(f"KATA TERDETEKSI: {', '.join(matched_words).upper()}")
            w.setStyleSheet("font-size: 16px; font-weight: 900; color: #FFCCCC; background-color: rgba(255, 0, 0, 0.3); border: 2px solid #FF3333; padding: 10px 20px; border-radius: 8px;")
            w.setAlignment(Qt.AlignCenter)
            
            w_lyt = QHBoxLayout()
            w_lyt.setAlignment(Qt.AlignCenter)
            w_lyt.addWidget(w)
            layout.addLayout(w_lyt)

        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("font-family: 'Consolas'; font-size: 80px; font-weight: 900; color: #FF1744;")
        self._countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._countdown_label)

        q = QLabel(f"\"{quote}\"")
        q.setStyleSheet("font-size: 16px; font-style: italic; color: #AAAAAA;")
        q.setAlignment(Qt.AlignCenter)
        layout.addWidget(q)

        layout.addSpacing(30)
        
        # Hidden Password Entry
        self._password_entry = QLineEdit()
        self._password_entry.setEchoMode(QLineEdit.Password)
        self._password_entry.setStyleSheet("background-color: transparent; border: 1px solid rgba(255,255,255,0.05); color: #555555; border-radius: 4px; padding: 5px;")
        self._password_entry.setFixedWidth(200)
        self._password_entry.setAlignment(Qt.AlignCenter)
        self._password_entry.returnPressed.connect(self._on_password_enter)
        layout.addWidget(self._password_entry, alignment=Qt.AlignHCenter)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px; color: #FF5252;")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        i = QLabel("Layar akan otomatis terbuka setelah waktu habis.")
        i.setStyleSheet("font-size: 12px; color: #555555;")
        i.setAlignment(Qt.AlignCenter)
        layout.addWidget(i)

        self._timer_tick() # Initial set
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._timer_tick)
        self._countdown_timer.start(1000)

        QTimer.singleShot(100, self._password_entry.setFocus)

        # Focus enforcement timer (200ms)
        self._focus_timer = QTimer(self)
        self._focus_timer.timeout.connect(self._enforce_lockdown_focus)
        self._focus_timer.start(200)

    def _enforce_lockdown_focus(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _timer_tick(self):
        if self._manager._remaining_seconds <= 0:
            self._manager.dismiss()
            return
        
        minutes = self._manager._remaining_seconds // 60
        secs = self._manager._remaining_seconds % 60
        self._countdown_label.setText(f"{minutes:02d}:{secs:02d}")
        self._manager._remaining_seconds -= 1

    def closeEvent(self, event):
        event.ignore()

    def _on_password_enter(self):
        if not self._manager._auth: return
        now = time.time()
        pwd = self._password_entry.text().strip()
        manager = self._manager
        
        if manager._override_lockout_until > 0 and now < manager._override_lockout_until:
            rem = int(manager._override_lockout_until - now) + 1
            self._status_label.setText(f"Terlalu banyak percobaan! Tunggu {rem}s")
            self._password_entry.clear()
            return

        if manager._override_lockout_until > 0:
            manager._override_lockout_until = 0.0
            manager._override_attempt_count = 0

        if manager._auth.verify_password(pwd):
            self._status_label.setText("✓ Password diterima — membuka...")
            self._status_label.setStyleSheet("font-size: 11px; color: #4CAF50;")
            self._password_entry.clear()
            if manager._on_unlock:
                try: manager._on_unlock()
                except Exception: pass
            QTimer.singleShot(500, manager.dismiss)
        else:
            manager._override_attempt_count += 1
            if manager._override_attempt_count >= manager.MAX_OVERRIDE_ATTEMPTS:
                manager._override_lockout_until = now + manager.OVERRIDE_LOCKOUT_SEC
                self._status_label.setText(f"Terkunci! Tunggu {manager.OVERRIDE_LOCKOUT_SEC} detik.")
            else:
                rem_att = manager.MAX_OVERRIDE_ATTEMPTS - manager._override_attempt_count
                self._status_label.setText(f"Password salah! Sisa percobaan: {rem_att}")
            self._password_entry.clear()
