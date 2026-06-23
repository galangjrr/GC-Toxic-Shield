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
APP_NAME = "GC Toxic Shield"
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
        Registry cleanup for Windows Settings & Control Panel.

        ALWAYS deletes NoControlPanel from the registry (cleanup).
        The actual Settings/Control Panel blocking is now handled by
        InstallerGuard at the process level.

        Target: HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer
        Value:  NoControlPanel (REG_DWORD)

        Args:
            enable_lock: Kept for backward compat. Both True and False
                         perform the same cleanup (delete NoControlPanel).

        Returns:
            True if operation succeeded.
        """
        try:
            import winreg

            # Always clean up the registry value (both enable and disable)
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    SystemService.POLICIES_EXPLORER_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                winreg.DeleteValue(key, "NoControlPanel")
                winreg.CloseKey(key)
                logger.info("✓ Registry cleanup: NoControlPanel removed (enforcement via InstallerGuard)")
            except FileNotFoundError:
                logger.info("NoControlPanel was not set — registry already clean")

            # Broadcast WM_SETTINGCHANGE to all windows immediately after registry changes
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            try:
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "Policy",
                    SMTO_ABORTIFHUNG,
                    5000,
                    None
                )
            except Exception as e:
                logger.warning("Failed to broadcast WM_SETTINGCHANGE: %s", e)

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

    @staticmethod
    def is_windows_settings_locked() -> bool:
        """
        Mengecek apakah pengaturan Windows (NoControlPanel) sedang terkunci di Registry.
        """
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                SystemService.POLICIES_EXPLORER_PATH,
                0,
                winreg.KEY_READ,
            )
            try:
                value, _ = winreg.QueryValueEx(key, "NoControlPanel")
                winreg.CloseKey(key)
                return value == 1
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    # ================================================================
    # INSTALLER BLOCKER (MSI & EXE)
    # ================================================================

    POLICIES_INSTALLER_PATH = r"Software\Policies\Microsoft\Windows\Installer"

    @staticmethod
    def toggle_installer_block(enable_block: bool) -> bool:
        """
        Registry cleanup for installer blocking (MSI & EXE).

        ALWAYS deletes DisableMSI from HKLM and DisallowRun + its subkey
        from HKCU, regardless of the enable_block parameter.
        The actual installer blocking is now handled by InstallerGuard's
        WMI/Window monitoring.

        Target: HKLM & HKCU Policies
        Args:
            enable_block: Kept for backward compat. Both True and False
                          perform the same cleanup (delete registry values).
        Returns: True jika berhasil.
        """
        try:
            import winreg

            # Always clean up: delete DisableMSI from HKLM
            try:
                key_msi = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    SystemService.POLICIES_INSTALLER_PATH,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
                )
                winreg.DeleteValue(key_msi, "DisableMSI")
                winreg.CloseKey(key_msi)
                logger.info("✓ Registry cleanup: DisableMSI removed")
            except FileNotFoundError:
                logger.info("DisableMSI was not set — registry already clean")

            # Always clean up: delete DisallowRun subkey from HKCU
            try:
                disallow_path = SystemService.POLICIES_EXPLORER_PATH + r"\DisallowRun"
                key_disallow = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    disallow_path,
                    0,
                    winreg.KEY_ALL_ACCESS,
                )
                # Enumerate and delete all values in the subkey
                try:
                    while True:
                        name, _, _ = winreg.EnumValue(key_disallow, 0)
                        winreg.DeleteValue(key_disallow, name)
                except OSError:
                    pass
                winreg.CloseKey(key_disallow)
                # Delete the subkey itself
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    disallow_path,
                )
            except FileNotFoundError:
                pass

            # Always clean up: delete DisallowRun value from Explorer policies
            try:
                key_expl = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    SystemService.POLICIES_EXPLORER_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                winreg.DeleteValue(key_expl, "DisallowRun")
                winreg.CloseKey(key_expl)
                logger.info("✓ Registry cleanup: DisallowRun removed")
            except FileNotFoundError:
                logger.info("DisallowRun was not set — registry already clean")

            logger.info("✓ Installer registry cleanup complete (enforcement via InstallerGuard)")
            
            # Broadcast WM_SETTINGCHANGE to all windows immediately after registry changes
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            try:
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "Policy",
                    SMTO_ABORTIFHUNG,
                    5000,
                    None
                )
            except Exception as e:
                logger.warning("Failed to broadcast WM_SETTINGCHANGE for Installer: %s", e)

            return True

        except ImportError:
            logger.error("winreg not available (non-Windows OS)")
            return False
        except PermissionError:
            logger.error("✗ Permission denied — run as Administrator to toggle installer blocks")
            return False
        except Exception as e:
            logger.error("✗ Failed to toggle installer block: %s", e)
            return False

    @staticmethod
    def is_installer_blocked() -> bool:
        """
        Mengecek apakah pengaturan instalasi (DisableMSI) sedang terkunci di Registry.
        """
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                SystemService.POLICIES_INSTALLER_PATH,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            try:
                value, _ = winreg.QueryValueEx(key, "DisableMSI")
                winreg.CloseKey(key)
                return value == 2
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
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
