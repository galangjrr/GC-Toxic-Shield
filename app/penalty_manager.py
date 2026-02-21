# =============================================================
# GC Toxic Shield — Penalty Manager (Config-Driven)
# =============================================================
# Modular sanction executor yang sepenuhnya dikendalikan oleh
# data sanction_list di config.json.
#
# Setiap sanksi memiliki atribut:
#   type          : "WARNING" atau "LOCKDOWN"
#   message       : Pesan yang ditampilkan
#   duration      : Durasi lockdown (detik), 0 untuk WARNING
#   warning_delay : Detik tombol "Saya Mengerti" di-disable
#
# State Machine:
#   - is_penalty_active = True → semua input diabaikan
#   - Auto-reset setelah PenaltyResetMinutes tanpa pelanggaran
#
# Admin Override:
#   - Password SHA256+Salt via AuthService → dismiss + reset
# =============================================================

import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger("GCToxicShield.PenaltyManager")

# Default sanction list — used if config.json has no sanction_list
DEFAULT_SANCTION_LIST = [
    {
        "type": "WARNING",
        "message": (
            "⚠️ Peringatan Pertama\n\n"
            "Sistem mendeteksi penggunaan kata-kata yang tidak pantas.\n"
            "Mohon jaga tutur kata Anda."
        ),
        "duration": 0,
        "warning_delay": 5,
    },
    {
        "type": "WARNING",
        "message": (
            "⚠️ Peringatan Kedua\n\n"
            "Anda KEMBALI menggunakan bahasa yang tidak sopan.\n"
            "Ini adalah peringatan terakhir sebelum lockdown."
        ),
        "duration": 0,
        "warning_delay": 15,
    },
    {
        "type": "LOCKDOWN",
        "message": "Anda melanggar aturan berbahasa di GC Net.",
        "duration": 60,
        "warning_delay": 0,
    },
    {
        "type": "WARNING",
        "message": (
            "⚠️ Peringatan Lanjutan\n\n"
            "Anda sudah melewati satu siklus hukuman.\n"
            "Pelanggaran berikutnya akan mendapat sanksi lebih berat."
        ),
        "duration": 0,
        "warning_delay": 15,
    },
    {
        "type": "WARNING",
        "message": (
            "⚠️ Peringatan Serius\n\n"
            "Pelanggaran berulang terdeteksi.\n"
            "Lockdown berikutnya akan lebih lama."
        ),
        "duration": 0,
        "warning_delay": 30,
    },
    {
        "type": "LOCKDOWN",
        "message": "Pelanggaran berulang. Akses dikunci lebih lama.",
        "duration": 180,
        "warning_delay": 0,
    },
    {
        "type": "LOCKDOWN",
        "message": "Pelanggaran berat. Ini adalah sanksi maksimum.",
        "duration": 300,
        "warning_delay": 0,
    },
]


class PenaltyManager:
    """
    Config-driven sanction executor.

    Alur:
    1. Toxic terdeteksi → execute_sanction() dipanggil
    2. Ambil resep dari sanction_list[current_level]
    3. Jika type=WARNING → tampilkan WarningBox
    4. Jika type=LOCKDOWN → tampilkan LockdownOverlay
    5. is_penalty_active = True selama sanksi berlangsung
    6. Auto-reset setelah PenaltyResetMinutes tanpa pelanggaran
    """

    def __init__(
        self,
        overlay,  # LockdownOverlay instance
        auth_service=None,
        on_violation: Optional[Callable] = None,
    ):
        self._overlay = overlay
        self._auth = auth_service
        self._on_violation = on_violation

        # ── State ──
        self._current_level = 0
        self._last_violation_time: float = 0.0
        self._lock = threading.Lock()
        self._is_penalty_active = False

        # ── Penalty Reset Timer ──
        self._reset_timer: Optional[threading.Timer] = None
        self._penalty_reset_minutes = 60
        if auth_service:
            self._penalty_reset_minutes = auth_service.get_config(
                "PenaltyResetMinutes", 60
            )

        # ── Load sanction list from config ──
        self._sanction_list = self._load_sanction_list()

        logger.info(
            "PenaltyManager initialized | %d sanctions loaded | reset=%d min",
            len(self._sanction_list),
            self._penalty_reset_minutes,
        )

    # ================================================================
    # PROPERTIES
    # ================================================================

    @property
    def current_level(self) -> int:
        return self._current_level

    @property
    def violation_count(self) -> int:
        """Alias for current_level (backward compat)."""
        return self._current_level

    @property
    def is_penalty_active(self) -> bool:
        """True saat Warning/Lockdown sedang ditampilkan."""
        return self._is_penalty_active

    @property
    def sanction_list(self) -> list:
        """Current sanction list (read-only copy)."""
        return list(self._sanction_list)

    # ================================================================
    # CORE: EXECUTE SANCTION
    # ================================================================

    def execute_sanction(self, matched_words: list = None):
        """
        Eksekusi sanksi berdasarkan current_level.

        State Machine:
        - Jika is_penalty_active == True → return (anti-overlap)
        - Ambil resep dari sanction_list[current_level]
        - Jika index >= len(list), gunakan item terakhir
        - Increment current_level setelah eksekusi
        """
        # ── Anti-Overlap: Block if penalty is active ──
        if self._is_penalty_active:
            logger.info("⏸ Sanction ignored — penalty is currently active")
            return

        with self._lock:
            self._last_violation_time = time.time()
            level_index = self._current_level
            self._current_level += 1

        # ── Get sanction recipe ──
        sanction = self._get_sanction(level_index)
        sanction_type = sanction.get("type", "WARNING").upper()
        message = sanction.get("message", "Pelanggaran terdeteksi.")
        duration = sanction.get("duration", 60)
        warning_delay = sanction.get("warning_delay", 5)

        # ── Mark penalty as active ──
        self._is_penalty_active = True

        # ── Restart auto-reset timer ──
        self._restart_penalty_timer()

        # ── Log ──
        logger.warning(
            "⚠ Violation #%d → %s (index=%d, delay=%ds, duration=%ds)",
            self._current_level,
            sanction_type,
            level_index,
            warning_delay,
            duration,
        )

        # ── Violation callback ──
        if self._on_violation:
            try:
                self._on_violation(
                    self._current_level, self._current_level, matched_words
                )
            except Exception as e:
                logger.error("Violation callback error: %s", e)

        # ── Dispatch to main thread ──
        try:
            if sanction_type == "LOCKDOWN":
                self._dispatch_lockdown(
                    level_index, message, duration, matched_words
                )
            else:
                self._dispatch_warning(
                    level_index, message, warning_delay, matched_words
                )
        except Exception as e:
            logger.error("Failed to dispatch sanction: %s", e)
            self._is_penalty_active = False

    # ================================================================
    # DISPATCH — UI THREAD
    # ================================================================

    def _dispatch_warning(self, level, message, warning_delay, matched_words):
        """Dispatch WarningBox to main thread."""
        from app.overlay import WarningBox

        self._overlay._root.after(
            0,
            lambda: WarningBox(
                root=self._overlay._root,
                level=level + 1,  # Display as 1-indexed
                matched_words=matched_words or [],
                auth_service=self._auth,
                warning_delay=warning_delay,
                message=message,
                on_dismiss=self._on_penalty_done,
            ),
        )

    def _dispatch_lockdown(self, level, message, duration, matched_words):
        """Dispatch LockdownOverlay to main thread."""
        # Update lockdown message in overlay config
        self._overlay._root.after(
            0,
            lambda: self._overlay.show(
                level=level + 1,  # Display as 1-indexed
                matched_words=matched_words,
                duration=duration,
                on_dismiss=self._on_penalty_done,
                on_unlock=None,  # Do not reset violation count on manual override
            ),
        )

    # ================================================================
    # STATE MANAGEMENT
    # ================================================================

    def _on_penalty_done(self):
        """Called when WarningBox/LockdownOverlay is dismissed."""
        self._is_penalty_active = False
        logger.info("✓ Penalty completed — accepting new violations")

    def reset(self):
        """Reset current_level ke 0 (admin override atau auto-reset)."""
        with self._lock:
            old = self._current_level
            self._current_level = 0
        self._is_penalty_active = False
        if self._reset_timer:
            self._reset_timer.cancel()
            self._reset_timer = None
        logger.info("⟳ Violations reset: %d → 0", old)

    # ================================================================
    # CONFIG
    # ================================================================

    def _load_sanction_list(self) -> list:
        """Load sanction_list from AuthService config."""
        if not self._auth:
            return list(DEFAULT_SANCTION_LIST)

        config_list = self._auth.get_config("sanction_list", None)
        if config_list and isinstance(config_list, list) and len(config_list) > 0:
            # Validate each item has required keys
            validated = []
            for item in config_list:
                if isinstance(item, dict) and "type" in item:
                    validated.append({
                        "type": item.get("type", "WARNING"),
                        "message": item.get("message", "Pelanggaran terdeteksi."),
                        "duration": item.get("duration", 60),
                        "warning_delay": item.get("warning_delay", 5),
                    })
            if validated:
                return validated

        return list(DEFAULT_SANCTION_LIST)

    def reload_config(self):
        """Reload sanction_list from config (called after UI save)."""
        self._sanction_list = self._load_sanction_list()
        if self._auth:
            self._penalty_reset_minutes = self._auth.get_config(
                "PenaltyResetMinutes", 60
            )
        logger.info(
            "Config reloaded | %d sanctions | reset=%d min",
            len(self._sanction_list),
            self._penalty_reset_minutes,
        )

    def _get_sanction(self, level_index: int) -> dict:
        """
        Get sanction recipe by index.
        If index >= len(list), use the last item (heaviest sanction).
        """
        if not self._sanction_list:
            return DEFAULT_SANCTION_LIST[-1]

        if level_index >= len(self._sanction_list):
            return self._sanction_list[-1]

        return self._sanction_list[level_index]

    # ================================================================
    # AUTO-RESET TIMER
    # ================================================================

    def _restart_penalty_timer(self):
        """Restart timer penalty reset."""
        if self._reset_timer:
            self._reset_timer.cancel()

        reset_seconds = self._penalty_reset_minutes * 60
        self._reset_timer = threading.Timer(
            reset_seconds, self._penalty_reset_callback
        )
        self._reset_timer.daemon = True
        self._reset_timer.start()

        logger.info(
            "Penalty reset timer set: %d minutes",
            self._penalty_reset_minutes,
        )

    def _penalty_reset_callback(self):
        """Called when penalty reset timer expires."""
        with self._lock:
            elapsed = time.time() - self._last_violation_time
            required = self._penalty_reset_minutes * 60

            if elapsed >= required:
                old = self._current_level
                self._current_level = 0
                logger.info(
                    "⟳ Penalty auto-reset: %d → 0 (no violations for %d min)",
                    old,
                    self._penalty_reset_minutes,
                )
            else:
                logger.info(
                    "Penalty reset skipped — recent violation detected"
                )
