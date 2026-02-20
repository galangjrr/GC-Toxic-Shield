# =============================================================
# GC Toxic Shield V2 — Login Dialog (CustomTkinter)
# =============================================================
# Modal login dialog yang muncul:
# - Saat aplikasi pertama dibuka
# - Saat dashboard dipanggil dari System Tray
# - Saat user ingin Exit dari tray
#
# Non-blocking: menggunakan CTkToplevel + grab_set()
# sehingga background process tetap berjalan.
# =============================================================

import logging
import customtkinter as ctk
from typing import Callable, Optional

logger = logging.getLogger("GCToxicShield.Login")


class LoginDialog:
    """
    Modal login dialog menggunakan CustomTkinter.

    Fitur:
    - Password entry + Login button
    - Status label (error / lockout message)
    - Anti-brute force countdown display
    - Non-closeable tanpa login (kecuali mode exit_mode=False)
    """

    def __init__(
        self,
        parent: ctk.CTk,
        auth_service,
        on_success: Callable,
        on_cancel: Optional[Callable] = None,
        exit_mode: bool = False,
    ):
        """
        Args:
            parent: Root window (CTk)
            auth_service: AuthService instance
            on_success: Callback dipanggil jika login berhasil
            on_cancel: Callback jika dialog ditutup tanpa login (exit_mode only)
            exit_mode: Jika True, memperbolehkan cancel (untuk exit auth)
        """
        self._auth = auth_service
        self._on_success = on_success
        self._on_cancel = on_cancel
        self._exit_mode = exit_mode
        self._parent = parent
        self._countdown_job = None

        # ── Build Window ──
        self._win = ctk.CTkToplevel(parent)
        self._win.title("🔒 Login — GC Toxic Shield")
        self._win.geometry("400x300")
        self._win.resizable(False, False)
        self._win.transient(parent)

        # Center on screen
        self._win.update_idletasks()
        x = (self._win.winfo_screenwidth() // 2) - 200
        y = (self._win.winfo_screenheight() // 2) - 150
        self._win.geometry(f"400x300+{x}+{y}")

        # ── Close behavior ──
        self._win.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        # ── UI Elements ──
        self._build_ui()

        # ── Modal grab ──
        self._win.grab_set()
        self._win.focus_force()

        # Check if currently locked out
        self._check_lockout_on_open()

        logger.info("Login dialog opened (exit_mode=%s)", exit_mode)

    def _build_ui(self):
        """Build all UI elements."""
        # Header
        header_frame = ctk.CTkFrame(self._win, height=60, corner_radius=0,
                                     fg_color=("#1a1a2e", "#1a1a2e"))
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        ctk.CTkLabel(
            header_frame,
            text="🔒 Authentication Required",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#e0e0e0",
        ).pack(expand=True)

        # Content frame
        content = ctk.CTkFrame(self._win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=15)

        # Info label
        if self._exit_mode:
            info_text = "Masukkan password untuk keluar dari aplikasi"
        else:
            info_text = "Masukkan password administrator"

        ctk.CTkLabel(
            content,
            text=info_text,
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa",
        ).pack(pady=(10, 15))

        # Password entry
        self._password_entry = ctk.CTkEntry(
            content,
            placeholder_text="Password...",
            show="●",
            height=42,
            font=ctk.CTkFont(size=14),
            corner_radius=8,
        )
        self._password_entry.pack(fill="x", pady=(0, 10))
        self._password_entry.bind("<Return>", lambda e: self._attempt_login())
        self._password_entry.focus_set()

        # Login button
        self._login_btn = ctk.CTkButton(
            content,
            text="🔓 Login",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self._attempt_login,
        )
        self._login_btn.pack(fill="x", pady=(0, 5))

        # Cancel button
        ctk.CTkButton(
            content,
            text="Batal",
            height=35,
            font=ctk.CTkFont(size=13),
            corner_radius=8,
            fg_color="#424242",
            hover_color="#616161",
            command=self._cancel,
        ).pack(fill="x", pady=(0, 5))

        # Status label
        self._status_label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#FF5252",
            wraplength=340,
        )
        self._status_label.pack(pady=(5, 0))

    def _check_lockout_on_open(self):
        """Jika sudah lockout saat dialog dibuka, tampilkan countdown."""
        locked, remaining = self._auth.is_locked_out()
        if locked:
            self._start_lockout_countdown(remaining)

    def _attempt_login(self):
        """Handle login button click."""
        password = self._password_entry.get()

        if not password.strip():
            self._status_label.configure(
                text="⚠ Password tidak boleh kosong!",
                text_color="#FFA726",
            )
            return

        success, message = self._auth.login(password)

        if success:
            self._status_label.configure(
                text="✅ " + message,
                text_color="#66BB6A",
            )
            logger.info("✓ Login successful via dialog")
            self._close_dialog()
            if self._on_success:
                self._on_success()
        else:
            self._status_label.configure(
                text="❌ " + message,
                text_color="#FF5252",
            )
            self._password_entry.delete(0, "end")
            self._password_entry.focus_set()

            # Check if now locked out → start countdown
            locked, remaining = self._auth.is_locked_out()
            if locked:
                self._start_lockout_countdown(remaining)

    def _start_lockout_countdown(self, seconds: int):
        """Disable input and show countdown timer."""
        self._password_entry.configure(state="disabled")
        self._login_btn.configure(state="disabled")
        self._update_countdown(seconds)

    def _update_countdown(self, remaining: int):
        """Update countdown setiap detik."""
        if remaining <= 0:
            # Lockout selesai
            self._password_entry.configure(state="normal")
            self._login_btn.configure(state="normal")
            self._status_label.configure(
                text="🔓 Silakan coba lagi",
                text_color="#66BB6A",
            )
            self._password_entry.focus_set()
            self._countdown_job = None
            return

        self._status_label.configure(
            text=f"🔒 Terkunci! Tunggu {remaining} detik...",
            text_color="#FF5252",
        )
        self._countdown_job = self._win.after(
            1000, self._update_countdown, remaining - 1
        )

    def _on_close_attempt(self):
        """Intercept window close (X button)."""
        self._cancel()

    def _cancel(self):
        """Cancel dialog (exit mode only)."""
        logger.info("Login dialog cancelled")
        self._close_dialog()
        if self._on_cancel:
            self._on_cancel()

    def _close_dialog(self):
        """Safely close the dialog."""
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
