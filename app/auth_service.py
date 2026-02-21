# =============================================================
# GC Toxic Shield — Auth Service
# =============================================================
# Module ini bertanggung jawab untuk:
# 1. Password hashing (SHA256 + random salt)
# 2. Password verification dengan anti-brute force
# 3. Session management (login / logout)
# 4. Config persistence (config.json)
#
# Terinspirasi dari AuthService.cs & ConfigManager.cs
# =============================================================

import os
import json
import time
import hashlib
import secrets
import logging

from app._paths import CONFIG_PATH

logger = logging.getLogger("GCToxicShield.Auth")

# ── Constants ──────────────────────────────────────────────────
DEFAULT_PASSWORD = "admin123"
MAX_ATTEMPTS = 3
LOCKOUT_DURATION_SEC = 30


class AuthService:
    """
    Service untuk autentikasi password dengan fitur:
    - SHA256 + salt hashing
    - Anti-brute force (3x percobaan, lockout 30 detik)
    - Session state (authenticated / not)
    - Persistent config via config.json
    """

    def __init__(self):
        self._authenticated: bool = False
        self._attempt_count: int = 0
        self._lockout_until: float = 0.0  # timestamp

        # Load or initialize config
        self._config: dict = self._load_config()
        self._ensure_password_exists()

        logger.info("✓ AuthService initialized")

    # ================================================================
    # CONFIG MANAGEMENT
    # ================================================================

    def _load_config(self) -> dict:
        """Load config.json, return empty dict if not found."""
        try:
            if os.path.isfile(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("✓ Config loaded from %s", CONFIG_PATH)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error("Failed to load config: %s", e)
        return {}

    def _save_config(self):
        """Save current config to config.json."""
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(CONFIG_PATH)
            if config_dir and not os.path.isdir(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
            logger.info("✓ Config saved to %s", CONFIG_PATH)
        except Exception as e:
            logger.error("✗ Failed to save config: %s", e)

    def _ensure_password_exists(self):
        """
        Jika belum ada password_hash / password_salt di config,
        set default password 'admin123'.
        Juga memastikan config lockdown/warning ada.
        """
        changed = False

        if not self._config.get("password_hash") or not self._config.get("password_salt"):
            logger.info("No password configured — setting default password")
            salt = secrets.token_hex(16)  # 32-char hex salt
            hashed = self._hash_password(DEFAULT_PASSWORD, salt)
            self._config["password_hash"] = hashed
            self._config["password_salt"] = salt
            changed = True

        # ── Lockdown / Warning Defaults ──
        defaults = {
            "PenaltyResetMinutes": 60,
            "LockdownTitle": "AREA TERKUNCI",
            "LockdownMessage": "Anda melanggar aturan berbahasa di GC Net.",
            "sanction_list": [
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Pertama\n\nSistem mendeteksi penggunaan kata-kata yang tidak pantas.\nMohon jaga tutur kata Anda.",
                    "duration": 0,
                    "warning_delay": 5,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Kedua\n\nAnda KEMBALI menggunakan bahasa yang tidak sopan.\nIni adalah peringatan terakhir sebelum lockdown.",
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
                    "message": "⚠️ Peringatan Lanjutan\n\nAnda sudah melewati satu siklus hukuman.\nPelanggaran berikutnya akan mendapat sanksi lebih berat.",
                    "duration": 0,
                    "warning_delay": 15,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Serius\n\nPelanggaran berulang terdeteksi.\nLockdown berikutnya akan lebih lama.",
                    "duration": 0,
                    "warning_delay": 30,
                },
                {
                    "type": "LOCKDOWN",
                    "message": "Pelanggaran berulang. Akses dikunci 3 Menit.",
                    "duration": 180,
                    "warning_delay": 0,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Kritis Ke-1\n\nSegera hentikan kebiasaan buruk Anda.\nSanksi 5 Menit menanti.",
                    "duration": 0,
                    "warning_delay": 30,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Kritis Ke-2\n\nIni adalah peringatan terakhir sebelum 5 Menit.",
                    "duration": 0,
                    "warning_delay": 45,
                },
                {
                    "type": "LOCKDOWN",
                    "message": "Pelanggaran berat. Akses dikunci 5 Menit.",
                    "duration": 300,
                    "warning_delay": 0,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Ekstrim Ke-1\n\nApakah Anda masih bertindak kasar?\nSanksi 10 Menit menanti.",
                    "duration": 0,
                    "warning_delay": 45,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Ekstrim Ke-2\n\nSatu kata lagi dan PC ini terkunci 10 Menit.",
                    "duration": 0,
                    "warning_delay": 60,
                },
                {
                    "type": "LOCKDOWN",
                    "message": "Pelanggaran sangat berat. Akses dikunci 10 Menit.",
                    "duration": 600,
                    "warning_delay": 0,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Final Ke-1\n\nAnda telah mencapai batas toleransi.\nSanksi Maksimal 20 Menit menanti.",
                    "duration": 0,
                    "warning_delay": 60,
                },
                {
                    "type": "WARNING",
                    "message": "⚠️ Peringatan Final Ke-2\n\nSIAP-SIAP LOCKDOWN MAKSIMAL.",
                    "duration": 0,
                    "warning_delay": 60,
                },
                {
                    "type": "LOCKDOWN",
                    "message": "PELANGGARAN MAKSIMAL. Akses dikunci 20 Menit.",
                    "duration": 1200,
                    "warning_delay": 0,
                },
            ],
        }
        for key, value in defaults.items():
            if key not in self._config:
                self._config[key] = value
                changed = True
                
        # Auto-migrate old default (7 items) to new default (15 items)
        if "sanction_list" in self._config and len(self._config["sanction_list"]) == 7:
            logger.info("Auto-migrating legacy 7-step sanction list to 15-step")
            self._config["sanction_list"] = defaults["sanction_list"]
            changed = True

        if changed:
            self._save_config()

    def get_config(self, key: str, default=None):
        """Get a config value by key."""
        return self._config.get(key, default)

    def update_config(self, key: str, value):
        """Update a config value and save to file."""
        self._config[key] = value
        self._save_config()

    # ================================================================
    # HASHING
    # ================================================================

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """
        Hash password menggunakan SHA256 dengan salt.
        Format: SHA256(salt + password) → hex digest
        """
        combined = (salt + password).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    # ================================================================
    # VERIFICATION & BRUTE FORCE
    # ================================================================

    def is_locked_out(self) -> tuple:
        """
        Cek apakah sedang dalam lockout period.

        Returns:
            (is_locked: bool, remaining_seconds: int)
        """
        if self._lockout_until <= 0:
            return False, 0

        now = time.time()
        if now < self._lockout_until:
            remaining = int(self._lockout_until - now) + 1
            return True, remaining

        # Lockout expired — reset
        self._lockout_until = 0.0
        self._attempt_count = 0
        return False, 0

    def verify_password(self, password: str) -> bool:
        """
        Verifikasi password terhadap hash di config.

        Returns:
            True jika password cocok.
        """
        stored_hash = self._config.get("password_hash", "")
        stored_salt = self._config.get("password_salt", "")

        if not stored_hash or not stored_salt:
            logger.warning("No password hash/salt in config")
            return False

        computed = self._hash_password(password, stored_salt)
        return computed == stored_hash

    # ================================================================
    # SESSION MANAGEMENT
    # ================================================================

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def login(self, password: str) -> tuple:
        """
        Attempt login.

        Returns:
            (success: bool, message: str)
        """
        # Check lockout
        locked, remaining = self.is_locked_out()
        if locked:
            msg = f"Terlalu banyak percobaan! Coba lagi dalam {remaining} detik."
            logger.warning("Login blocked — lockout active (%ds remaining)", remaining)
            return False, msg

        # Verify
        if self.verify_password(password):
            self._authenticated = True
            self._attempt_count = 0
            self._lockout_until = 0.0
            logger.info("✓ Login successful")
            return True, "Login berhasil"
        else:
            self._attempt_count += 1
            remaining_attempts = MAX_ATTEMPTS - self._attempt_count
            logger.warning(
                "✗ Login failed (attempt %d/%d)",
                self._attempt_count, MAX_ATTEMPTS
            )

            if self._attempt_count >= MAX_ATTEMPTS:
                self._lockout_until = time.time() + LOCKOUT_DURATION_SEC
                msg = f"Password salah! Akun terkunci selama {LOCKOUT_DURATION_SEC} detik."
                logger.warning("⚠ Account locked out for %ds", LOCKOUT_DURATION_SEC)
                return False, msg
            else:
                msg = f"Password salah! Sisa percobaan: {remaining_attempts}"
                return False, msg

    def logout(self):
        """Clear session — user harus login ulang."""
        self._authenticated = False
        logger.info("Session cleared (logout)")

    def change_password(self, new_password: str) -> bool:
        """
        Ganti password. Menghasilkan salt baru.

        Returns:
            True jika berhasil.
        """
        try:
            salt = secrets.token_hex(16)
            hashed = self._hash_password(new_password, salt)

            self._config["password_hash"] = hashed
            self._config["password_salt"] = salt
            self._save_config()

            logger.info("✓ Password changed successfully")
            return True
        except Exception as e:
            logger.error("✗ Failed to change password: %s", e)
            return False
