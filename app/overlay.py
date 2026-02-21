# =============================================================
# GC Toxic Shield V2 — Tiered Warning & Lockdown Overlay
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

import threading
import time
import logging
import tkinter as tk
from typing import Optional, Callable

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from app import static_data

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.Overlay")


# ================================================================
# WARNING BOX (Level 1-2 dalam siklus 3)
# ================================================================

class WarningBox:
    """
    Jendela peringatan yang muncul di tengah layar.
    Tombol 'Saya Mengerti' di-disable selama WarningDelaySeconds.
    """

    def __init__(
        self,
        root: tk.Tk,
        level: int,
        matched_words: list,
        auth_service=None,
        warning_delay: int = 5,
        message: str = None,
        on_dismiss: Callable = None,
    ):
        self._root = root
        self._auth = auth_service
        self._delay = warning_delay
        self._custom_message = message
        self._countdown_job = None
        self._on_dismiss = on_dismiss

        # ── Build Window ──
        self._win = ctk.CTkToplevel(root) if ctk else tk.Toplevel(root)
        self._win.title("⚠️ Peringatan — GC Toxic Shield")
        self._win.geometry("520x420")
        self._win.resizable(False, False)
        self._win.attributes("-topmost", True)
        self._win.transient(root)

        # Center on screen
        self._win.update_idletasks()
        x = (self._win.winfo_screenwidth() // 2) - 260
        y = (self._win.winfo_screenheight() // 2) - 210
        self._win.geometry(f"520x420+{x}+{y}")

        # Secure close
        self._win.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self._build_ui(level, matched_words)

        # Modal
        self._win.grab_set()
        self._win.focus_force()

        # Start button countdown
        self._start_delay_countdown(self._delay)

        logger.info("WarningBox shown (level %d, delay %ds)", level, warning_delay)

    def _build_ui(self, level: int, matched_words: list):
        """Build warning UI elements."""
        # Header
        header = ctk.CTkFrame(self._win, height=50, corner_radius=0,
                               fg_color=("#FFA726", "#E65100"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=f"⚠️ Peringatan Level {level}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(expand=True)

        # Content
        content = ctk.CTkFrame(self._win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=25, pady=15)

        # Message from Config or StaticData
        message = self._custom_message
        if not message:
            message = static_data.get_message(level)

        ctk.CTkLabel(
            content,
            text=message,
            font=ctk.CTkFont(size=14),
            justify="center",
            wraplength=470,
        ).pack(pady=(10, 15))

        # Matched words
        if matched_words:
            words_text = f"Kata terdeteksi: {', '.join(matched_words)}"
            ctk.CTkLabel(
                content,
                text=words_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#FF5252",
                wraplength=470,
            ).pack(pady=(0, 15))

        # Acknowledge button (disabled during delay)
        self._ack_btn = ctk.CTkButton(
            content,
            text=f"Saya Mengerti ({self._delay}s)",
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color="#616161",
            hover_color="#616161",
            state="disabled",
            command=self._dismiss,
        )
        self._ack_btn.pack(fill="x", pady=(10, 0))

    def _start_delay_countdown(self, remaining: int):
        """Countdown sebelum tombol aktif."""
        if remaining <= 0:
            self._ack_btn.configure(
                text="Saya Mengerti ✓",
                state="normal",
                fg_color="#1565C0",
                hover_color="#0D47A1",
            )
            self._countdown_job = None
            return

        self._ack_btn.configure(text=f"Saya Mengerti ({remaining}s)")
        self._countdown_job = self._win.after(
            1000, self._start_delay_countdown, remaining - 1
        )

    def _on_close_attempt(self):
        """Intercept X button — require password."""
        if self._auth:
            self._show_password_prompt()
        else:
            pass

    def _show_password_prompt(self):
        """Show password dialog to force-close warning."""
        from app.login_dialog import LoginDialog
        LoginDialog(
            parent=self._root,
            auth_service=self._auth,
            on_success=self._force_dismiss,
            on_cancel=None,
            exit_mode=True,
        )

    def _force_dismiss(self):
        """Force dismiss after successful password."""
        logger.info("WarningBox force-dismissed via password")
        self._dismiss()

    def _dismiss(self):
        """Close the warning box."""
        if self._countdown_job:
            try:
                self._win.after_cancel(self._countdown_job)
            except Exception:
                pass
        try:
            self._win.grab_release()
            self._win.destroy()
        except Exception:
            pass
        logger.info("WarningBox dismissed")
        # Notify manager that penalty is done
        if self._on_dismiss:
            try:
                self._on_dismiss()
            except Exception:
                pass


# ================================================================
# SIMPLE WARNING BOX (Surgical Desktop Guard)
# ================================================================

class SimpleWarningBox:
    """
    Jendela peringatan sederhana untuk Desktop Guard.
    Tanpa timer, hanya tombol OK, dan tidak menutupi seluruh layar.
    """
    
    _instance = None
    
    def __init__(self, root: tk.Tk):
        # Prevent multiple popups at once
        if SimpleWarningBox._instance is not None:
            return
            
        SimpleWarningBox._instance = self
        self._root = root
        
        self._win = ctk.CTkToplevel(root) if ctk else tk.Toplevel(root)
        self._win.title("⚠️ Peringatan Sistem")
        self._win.geometry("450x200")
        self._win.resizable(False, False)
        self._win.attributes("-topmost", True)
        self._win.transient(root)
        
        # Center on screen
        self._win.update_idletasks()
        x = (self._win.winfo_screenwidth() // 2) - 225
        y = (self._win.winfo_screenheight() // 2) - 100
        self._win.geometry(f"+{x}+{y}")
        
        self._win.protocol("WM_DELETE_WINDOW", self._dismiss)
        
        content = ctk.CTkFrame(self._win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            content,
            text="🚨 DILARANG 🚨",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FF5252"
        ).pack(pady=(0, 10))
        
        ctk.CTkLabel(
            content,
            text="Dilarang menambah, menghapus, atau mengubah nama file di Desktop.",
            font=ctk.CTkFont(size=14),
            justify="center",
            wraplength=400
        ).pack(pady=(0, 20))
        
        ctk.CTkButton(
            content,
            text="OK, Saya Mengerti",
            font=ctk.CTkFont(weight="bold"),
            width=200,
            command=self._dismiss
        ).pack()
        
        # Modal
        self._win.grab_set()
        self._win.focus_force()
        logger.info("SimpleWarningBox shown for Desktop Guard")
        
    def _dismiss(self):
        try:
            self._win.grab_release()
            self._win.destroy()
        except Exception:
            pass
        finally:
            SimpleWarningBox._instance = None
            logger.info("SimpleWarningBox dismissed")


# ================================================================
# LOCKDOWN OVERLAY (Level 3 dalam siklus 3)
# ================================================================

class LockdownOverlay:
    """
    Fullscreen overlay yang muncul saat lockdown aktif (kelipatan 3).

    Features:
    - Jendela fullscreen, hitam 90% opacity, topmost
    - Judul dan pesan dari config
    - Kutipan acak dari StaticData
    - Countdown timer
    - Input blocking (keyboard hooks)
    - Hidden password input + Enter = admin override (anti-brute force)
    """

    # Anti-brute force constants
    MAX_OVERRIDE_ATTEMPTS = 3
    OVERRIDE_LOCKOUT_SEC = 30

    def __init__(self, root: tk.Tk, auth_service=None):
        self._root = root
        self._auth = auth_service
        self._overlay_window: Optional[tk.Toplevel] = None
        self._countdown_label: Optional[tk.Label] = None
        self._is_active = False
        self._remaining_seconds = 0
        self._countdown_timer_id = None
        self._on_dismiss: Optional[Callable] = None

        # ── Admin Override State ──
        self._override_attempt_count = 0
        self._override_lockout_until: float = 0.0
        self._password_var: Optional[tk.StringVar] = None
        self._password_entry: Optional[tk.Entry] = None
        self._status_label: Optional[tk.Label] = None

        # ── Input Blocking ──
        self._hook_installed = False
        self._hook_handle = None
        self._hook_callback = None  # prevent GC

    @property
    def is_active(self) -> bool:
        return self._is_active

    def show(self, level: int, matched_words: list = None, duration: int = 60,
             on_dismiss: Callable = None, on_unlock: Callable = None):
        """Menampilkan lockdown overlay."""
        if self._is_active:
            logger.warning("Overlay already active, ignoring")
            return

        self._on_dismiss = on_dismiss
        self._on_unlock = on_unlock

        # Config values
        lockdown_title = "AREA TERKUNCI"
        lockdown_message = "Anda melanggar aturan berbahasa di GC Net."
        if self._auth:
            lockdown_title = self._auth.get_config("LockdownTitle", lockdown_title)
            lockdown_message = self._auth.get_config("LockdownMessage", lockdown_message)

        logger.warning(
            "🔒 LOCKDOWN ACTIVATED | Level %d | Duration: %ds",
            level, duration
        )

        self._is_active = True
        self._remaining_seconds = duration

        # Reset override state for this session
        self._override_attempt_count = 0
        self._override_lockout_until = 0.0

        quote = static_data.get_random_quote(level)
        self._create_overlay(level, lockdown_title, lockdown_message, duration, matched_words or [], quote)
        self._install_keyboard_hook()
        self._update_countdown()

    def dismiss(self):
        """Menutup overlay (dipanggil saat countdown selesai atau admin override)."""
        self._is_active = False

        if self._countdown_timer_id:
            try:
                self._root.after_cancel(self._countdown_timer_id)
            except Exception:
                pass
            self._countdown_timer_id = None

        self._remove_keyboard_hook()

        if self._overlay_window:
            try:
                self._overlay_window.destroy()
            except Exception:
                pass
            self._overlay_window = None

        logger.info("🔓 LOCKDOWN DISMISSED")

        # Notify manager that penalty is done
        if self._on_dismiss:
            try:
                self._on_dismiss()
            except Exception:
                pass

    # ================================================================
    # OVERLAY WINDOW
    # ================================================================

    def _create_overlay(self, level, title, message, duration, matched_words, quote):
        """Membuat jendela overlay fullscreen."""
        self._overlay_window = tk.Toplevel(self._root)
        win = self._overlay_window

        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.90)
        win.configure(bg="#0a0a0a")
        win.overrideredirect(True)
        win.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        container = tk.Frame(win, bg="#0a0a0a")
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Shield Icon
        tk.Label(
            container, text="🔒",
            font=("Segoe UI Emoji", 72), bg="#0a0a0a", fg="white",
        ).pack(pady=(0, 10))

        # Title
        tk.Label(
            container, text=title,
            font=("Segoe UI", 32, "bold"), bg="#0a0a0a", fg="#FF1744",
        ).pack(pady=(0, 10))

        # Message
        tk.Label(
            container, text=message,
            font=("Segoe UI", 18), bg="#0a0a0a", fg="white",
            justify="center", wraplength=800,
        ).pack(pady=(0, 20))

        # Level indicator
        tk.Label(
            container,
            text=f"⚠ Pelanggaran ke-{level}",
            font=("Segoe UI", 16, "bold"), bg="#0a0a0a", fg="#FF6D00",
        ).pack(pady=(0, 10))

        # Matched Words
        if matched_words:
            tk.Label(
                container,
                text=f"Kata terdeteksi: {', '.join(matched_words)}",
                font=("Segoe UI", 14), bg="#0a0a0a", fg="#FF6B6B",
            ).pack(pady=(0, 15))

        # Countdown
        self._countdown_label = tk.Label(
            container,
            text=self._format_countdown(duration),
            font=("Consolas", 52, "bold"), bg="#0a0a0a", fg="#FF1744",
        )
        self._countdown_label.pack(pady=(10, 15))

        # Quote
        tk.Label(
            container, text=quote,
            font=("Segoe UI", 13, "italic"), bg="#0a0a0a", fg="#888888",
            justify="center", wraplength=700,
        ).pack(pady=(10, 10))

        # ── Hidden Admin Password Input ──
        # Invisible password field — admin types password and presses Enter
        self._password_var = tk.StringVar()
        self._password_entry = tk.Entry(
            container,
            textvariable=self._password_var,
            show="•",
            font=("Consolas", 12),
            bg="#1a1a1a",
            fg="#666666",
            insertbackground="#666666",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#333333",
            highlightcolor="#555555",
            width=25,
            justify="center",
        )
        self._password_entry.pack(pady=(15, 3))
        self._password_entry.bind("<Return>", self._on_password_enter)

        # Status label for override feedback
        self._status_label = tk.Label(
            container,
            text="",
            font=("Segoe UI", 10), bg="#0a0a0a", fg="#FF5252",
        )
        self._status_label.pack(pady=(0, 5))

        # Instruction
        tk.Label(
            container,
            text="Layar akan otomatis terbuka setelah waktu habis.",
            font=("Segoe UI", 11), bg="#0a0a0a", fg="#555555",
            justify="center",
        ).pack(pady=(10, 0))

        win.focus_force()
        win.grab_set()

        # Focus the password entry so admin can type immediately
        self._password_entry.focus_set()

    # ================================================================
    # ADMIN OVERRIDE (Hidden Password + Enter)
    # ================================================================

    def _on_password_enter(self, event=None):
        """Admin menekan Enter pada hidden password field."""
        if not self._auth:
            return

        # Check override lockout
        now = time.time()
        if self._override_lockout_until > 0 and now < self._override_lockout_until:
            remaining = int(self._override_lockout_until - now) + 1
            self._show_override_status(
                f"Terlalu banyak percobaan! Tunggu {remaining}s",
                "#FF5252"
            )
            self._password_var.set("")
            return

        # Reset lockout if expired
        if self._override_lockout_until > 0 and now >= self._override_lockout_until:
            self._override_lockout_until = 0.0
            self._override_attempt_count = 0

        password = self._password_var.get().strip()
        if not password:
            return

        # Verify using AuthService (SHA256 + Salt)
        if self._auth.verify_password(password):
            logger.info("✓ Lockdown admin override — password accepted")
            self._show_override_status("✓ Password diterima — membuka...", "#4CAF50")
            self._password_var.set("")

            # Trigger unlock callback (reset violation count)
            if self._on_unlock:
                try:
                    self._on_unlock()
                except Exception as e:
                    logger.error("Unlock callback error: %s", e)

            # Dismiss after short delay for visual feedback
            self._overlay_window.after(500, self._force_dismiss)
        else:
            self._override_attempt_count += 1
            remaining_attempts = self.MAX_OVERRIDE_ATTEMPTS - self._override_attempt_count
            logger.warning(
                "✗ Override failed (attempt %d/%d)",
                self._override_attempt_count, self.MAX_OVERRIDE_ATTEMPTS
            )

            if self._override_attempt_count >= self.MAX_OVERRIDE_ATTEMPTS:
                self._override_lockout_until = time.time() + self.OVERRIDE_LOCKOUT_SEC
                self._show_override_status(
                    f"Terkunci! Tunggu {self.OVERRIDE_LOCKOUT_SEC} detik.",
                    "#FF5252"
                )
                logger.warning(
                    "⚠ Override locked out for %ds",
                    self.OVERRIDE_LOCKOUT_SEC
                )
            else:
                self._show_override_status(
                    f"Password salah! Sisa: {remaining_attempts}",
                    "#FF5252"
                )

            self._password_var.set("")

    def _show_override_status(self, text: str, color: str):
        """Update status label on lockdown screen."""
        if self._status_label:
            try:
                self._status_label.configure(text=text, fg=color)
            except Exception:
                pass

    def _on_close_attempt(self):
        """Intercept close — ignore (use password instead)."""
        # Do nothing — lockdown cannot be closed via X button
        pass

    def _force_dismiss(self):
        """Force dismiss after successful password auth."""
        logger.info("Lockdown force-dismissed via admin override")
        self.dismiss()

    def _update_countdown(self):
        """Update countdown timer setiap detik."""
        if not self._is_active or not self._overlay_window:
            return

        if self._remaining_seconds <= 0:
            self.dismiss()
            return

        if self._countdown_label:
            try:
                self._countdown_label.configure(
                    text=self._format_countdown(self._remaining_seconds)
                )
            except Exception:
                pass

        self._remaining_seconds -= 1
        self._countdown_timer_id = self._root.after(
            1000, self._update_countdown
        )

    @staticmethod
    def _format_countdown(seconds: int) -> str:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    # ================================================================
    # INPUT BLOCKING — SINGLE ATTEMPT, NON-BLOCKING
    # ================================================================

    def _install_keyboard_hook(self):
        """
        Install low-level keyboard hook (single attempt).
        Jika gagal → warn saja, ZERO lag.
        """
        if self._hook_installed:
            return

        try:
            import ctypes
            import ctypes.wintypes

            WH_KEYBOARD_LL = 13
            WM_SYSKEYDOWN = 0x0104
            VK_TAB = 0x09
            VK_LWIN = 0x5B
            VK_RWIN = 0x5C
            VK_ESCAPE = 0x1B

            HOOKPROC = ctypes.CFUNCTYPE(
                ctypes.wintypes.LPARAM,
                ctypes.c_int,
                ctypes.wintypes.WPARAM,
                ctypes.wintypes.LPARAM,
            )

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            def keyboard_hook_proc(nCode, wParam, lParam):
                if nCode >= 0 and self._is_active:
                    vk_code = ctypes.cast(
                        lParam,
                        ctypes.POINTER(ctypes.wintypes.DWORD)
                    ).contents.value

                    if wParam == WM_SYSKEYDOWN and vk_code == VK_TAB:
                        return 1
                    if vk_code in (VK_LWIN, VK_RWIN):
                        return 1
                    if vk_code == VK_ESCAPE:
                        if user32.GetAsyncKeyState(0x11) & 0x8000:
                            return 1

                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            self._hook_callback = HOOKPROC(keyboard_hook_proc)

            self._hook_handle = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._hook_callback,
                kernel32.GetModuleHandleW(None),
                0,
            )

            if self._hook_handle:
                self._hook_installed = True
                logger.info("✓ Keyboard hook installed")
            else:
                err = kernel32.GetLastError()
                logger.warning(
                    "⚠ Hook unavailable (err=%d). Run as Admin. Continuing.",
                    err
                )

        except Exception as e:
            logger.warning("Hook error: %s — continuing without hook", e)

    def _remove_keyboard_hook(self):
        """Remove keyboard hook saat overlay ditutup."""
        if not self._hook_installed or not self._hook_handle:
            return
        try:
            import ctypes
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_installed = False
            self._hook_handle = None
            logger.info("✓ Keyboard hook removed")
        except Exception as e:
            logger.error("Failed to remove hook: %s", e)

