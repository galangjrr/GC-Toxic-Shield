# =============================================================
# GC Toxic Shield V2 — Auth Service
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
            "WarningDelaySeconds": 5,
            "PenaltyResetMinutes": 60,
            "LockdownDurationSeconds": 60,
            "LockdownTitle": "AREA TERKUNCI",
            "LockdownMessage": "Anda melanggar aturan berbahasa di GC Net.",

            # ── Timers (Customizable) ──
            "Cycle1_WarningDelay": 5,      # Detik
            "Cycle1_LockdownDuration": 60, # Detik (1 menit)

            "Cycle2_WarningDelay": 15,     # Detik
            "Cycle2_LockdownDuration": 180,# Detik (3 menit)

            "Cycle3_WarningDelay": 30,     # Detik
            "Cycle3_LockdownDuration": 300,# Detik (5 menit)

            # ── Customizable Messages ──
            "WarningMessageLevel1": (
                "⚠️ Peringatan Pertama\n\n"
                "Sistem mendeteksi penggunaan kata-kata yang tidak pantas.\n"
                "Mohon jaga tutur kata Anda."
            ),
            "WarningMessageLevel2": (
                "⚠️ Peringatan Kedua\n\n"
                "Anda KEMBALI menggunakan bahasa yang tidak sopan.\n"
                "Ini adalah peringatan terakhir sebelum lockdown."
            ),
        }
        for key, value in defaults.items():
            if key not in self._config:
                self._config[key] = value
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
