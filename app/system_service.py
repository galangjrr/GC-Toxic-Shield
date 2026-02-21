# =============================================================
# GC Toxic Shield — Task T6: System Service Utilities
# =============================================================
# Module ini bertanggung jawab untuk:
# 1. Auto-Start via Windows Registry (HKCU\...\Run)
# 2. Emergency safety exit (release all hooks)
# 3. System-level utilities
# =============================================================

import os
import sys
import logging
from typing import Optional

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.System")

# ── Constants ──────────────────────────────────────────────────
APP_NAME = "GCToxicShield"
REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


class SystemService:
    """
    Utility untuk mengelola integrasi sistem Windows:
    - Registry auto-start
    - Emergency safety exit
    """

    # ================================================================
    # AUTO-START (REGISTRY)
    # ================================================================

    @staticmethod
    def enable_autostart(app_path: Optional[str] = None) -> bool:
        """
        Mendaftarkan aplikasi ke Windows Registry agar
        otomatis berjalan saat startup.

        Key: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
        Value: Path ke executable

        Args:
            app_path: Path ke executable. Default: sys.executable + script.

        Returns:
            True jika berhasil.
        """
        try:
            import winreg

            if app_path is None:
                # Jika dijalankan sebagai .exe (PyInstaller)
                if getattr(sys, 'frozen', False):
                    app_path = f'"{sys.executable}"'
                else:
                    # Jalankan sebagai Python script
                    script_path = os.path.abspath(
                        os.path.join(
                            os.path.dirname(os.path.dirname(__file__)),
                            "main.py"
                        )
                    )
                    app_path = f'"{sys.executable}" "{script_path}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REGISTRY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)

            logger.info("✓ Auto-start enabled: %s", app_path)
            return True

        except ImportError:
            logger.error("winreg not available (non-Windows OS)")
            return False
        except PermissionError:
            logger.error("✗ Permission denied — run as Administrator")
            return False
        except Exception as e:
            logger.error("✗ Failed to enable auto-start: %s", e)
            return False

    @staticmethod
    def disable_autostart() -> bool:
        """
        Menghapus entri auto-start dari Windows Registry.

        Returns:
            True jika berhasil.
        """
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REGISTRY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info("✓ Auto-start disabled")
            except FileNotFoundError:
                logger.info("Auto-start was not enabled")
            winreg.CloseKey(key)
            return True

        except ImportError:
            logger.error("winreg not available")
            return False
        except Exception as e:
            logger.error("✗ Failed to disable auto-start: %s", e)
            return False

    @staticmethod
    def is_autostart_enabled() -> bool:
        """
        Cek apakah auto-start sudah aktif di Registry.
        """
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REGISTRY_PATH,
                0,
                winreg.KEY_READ,
            )
            try:
                winreg.QueryValueEx(key, APP_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False

        except Exception:
            return False

    # ================================================================
    # GROUP POLICY — LOCK WINDOWS SETTINGS
    # ================================================================

    POLICIES_EXPLORER_PATH = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"

    @staticmethod
    def toggle_windows_settings(enable_lock: bool) -> bool:
        """
        Lock/unlock Windows Settings & Control Panel via Registry.

        Target: HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer
        Value:  NoControlPanel (REG_DWORD)

        Args:
            enable_lock: True  → set NoControlPanel=1 (Settings blocked)
                         False → delete NoControlPanel   (Settings accessible)

        Returns:
            True if operation succeeded.
        """
        try:
            import winreg

            if enable_lock:
                # Create key if it doesn't exist, then set value
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    SystemService.POLICIES_EXPLORER_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                winreg.SetValueEx(key, "NoControlPanel", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                logger.info("✓ Windows Settings LOCKED (NoControlPanel=1)")
            else:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        SystemService.POLICIES_EXPLORER_PATH,
                        0,
                        winreg.KEY_SET_VALUE,
                    )
                    winreg.DeleteValue(key, "NoControlPanel")
                    winreg.CloseKey(key)
                    logger.info("✓ Windows Settings UNLOCKED (NoControlPanel removed)")
                except FileNotFoundError:
                    logger.info("NoControlPanel was not set — already unlocked")

            return True

        except ImportError:
            logger.error("winreg not available (non-Windows OS)")
            return False
        except PermissionError:
            logger.error("✗ Permission denied — run as Administrator")
            return False
        except Exception as e:
            logger.error("✗ Failed to toggle Windows Settings: %s", e)
            return False

    # ================================================================
    # EMERGENCY SAFETY EXIT
    # ================================================================

    @staticmethod
    def emergency_release_hooks():
        """
        Emergency: melepas semua keyboard hooks.
        Dipanggil via global hotkey admin atau dashboard button.
        """
        try:
            import ctypes
            # Unhook all — membersihkan semua hook secara paksa
            # Ini aman karena hanya melepas hook dari thread ini
            logger.warning("🆘 EMERGENCY: Releasing all keyboard hooks...")

            # Force unhook — akan dicoba meskipun handle tidak tersimpan
            # Pendekatan ini mem-broadcast pesan ke event loop
            # agar Windows melepas hook
            user32 = ctypes.windll.user32
            user32.PostThreadMessageW(
                ctypes.windll.kernel32.GetCurrentThreadId(),
                0x0012,  # WM_QUIT
                0, 0,
            )

            logger.info("✓ Emergency release completed")
            return True

        except Exception as e:
            logger.error("✗ Emergency release failed: %s", e)
            return False

    @staticmethod
    def force_shutdown(engine=None, logger_svc=None, overlay=None):
        """
        Force shutdown seluruh aplikasi dengan graceful cleanup.

        Args:
            engine: AudioEngine instance
            logger_svc: LoggerService instance
            overlay: LockdownOverlay instance
        """
        logger.warning("🆘 FORCE SHUTDOWN initiated")

        try:
            # Dismiss overlay jika aktif
            if overlay and overlay.is_active:
                overlay.dismiss()

            # Stop engine
            if engine:
                engine.stop()

            # Stop logger
            if logger_svc:
                logger_svc.stop()

            # Release hooks
            SystemService.emergency_release_hooks()

            logger.info("✓ Force shutdown completed")

        except Exception as e:
            logger.error("Force shutdown error: %s", e)

        # Exit
        sys.exit(0)
