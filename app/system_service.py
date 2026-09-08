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
    # MICROPHONE PRIVACY POLICY — LOCK MICROPHONE ACCESS TOGGLE
    # ================================================================

    POLICIES_APPPRIVACY_PATH = r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy"

    @staticmethod
    def toggle_microphone_privacy_lock(enable_lock: bool) -> bool:
        """
        Kunci atau buka izin Microphone Privacy di Windows Settings (HKLM).
        Reversibel 100% dan tidak merusak sistem registry:
        
        enable_lock = True:
            Set LetAppsAccessMicrophone = 1 (REG_DWORD)
            -> Force Allow: toggle 'Microphone access' di Windows Settings
               dikunci ON dan membeku abu-abu ('Some of these settings are managed by your organization').
        enable_lock = False:
            Hapus nilai LetAppsAccessMicrophone (clean rollback)
            -> Mengembalikan kontrol normal ke user.
        """
        try:
            import winreg
            import ctypes

            if enable_lock:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_LOCAL_MACHINE,
                    SystemService.POLICIES_APPPRIVACY_PATH,
                    0,
                    winreg.KEY_SET_VALUE,
                )
                winreg.SetValueEx(key, "LetAppsAccessMicrophone", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                logger.info("✓ Microphone Privacy LOCKED (LetAppsAccessMicrophone=1)")
            else:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        SystemService.POLICIES_APPPRIVACY_PATH,
                        0,
                        winreg.KEY_SET_VALUE,
                    )
                    winreg.DeleteValue(key, "LetAppsAccessMicrophone")
                    winreg.CloseKey(key)
                    logger.info("✓ Microphone Privacy UNLOCKED (LetAppsAccessMicrophone removed)")
                except FileNotFoundError:
                    pass

            # Siarkan sinyal WM_SETTINGCHANGE agar Windows langsung refresh seketika
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
                    3000,
                    None,
                )
            except Exception:
                pass

            return True

        except PermissionError:
            logger.warning("Permission denied writing HKLM policy — run as Administrator")
            return False
        except Exception as e:
            logger.error("Failed to toggle microphone privacy lock: %s", e)
            return False

    @staticmethod
    def is_microphone_privacy_locked() -> bool:
        """Cek apakah Microphone Privacy sedang terkunci di Registry (HKLM)."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                SystemService.POLICIES_APPPRIVACY_PATH,
                0,
                winreg.KEY_READ,
            )
            val, _ = winreg.QueryValueEx(key, "LetAppsAccessMicrophone")
            winreg.CloseKey(key)
            return val == 1
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

    # ================================================================
    # APP SOVEREIGNTY & HARDENING
    # ================================================================

    @staticmethod
    def harden_app_directory():
        """
        Melindungi folder instalasi agar tidak bisa dihapus oleh siapapun (termasuk Antivirus),
        serta menetapkan status kedaulatan tinggi.
        """
        try:
            import subprocess
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Gunakan icacls untuk menolak izin Delete (DE) untuk Everyone
            # Tanpa /T agar tidak mengunci file temporer/cache di dalam subfolder yang mungkin dibutuhkan sistem
            cmd = f'icacls "{app_dir}" /deny Everyone:(DE) /C /Q'
            subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            logger.info("✓ Folder hardened: %s", app_dir)
            return True
        except Exception as e:
            logger.error("Failed to harden app directory: %s", e)
            return False

    @staticmethod
    def unharden_app_directory():
        """
        Melepas perlindungan folder saat Maintenance Mode.
        """
        try:
            import subprocess
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Hapus rule deny dari folder
            cmd = f'icacls "{app_dir}" /remove:d Everyone /C /Q'
            subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            logger.info("✓ Folder unhardened: %s", app_dir)
            return True
        except Exception as e:
            logger.error("Failed to unharden app directory: %s", e)
            return False

    @staticmethod
    def set_high_priority():
        """
        Menyetel proses aplikasi menjadi Above Normal Priority.
        Catatan: Tidak menggunakan HIGH_PRIORITY agar tidak menyebabkan audio driver starvation.
        """
        try:
            import psutil
            p = psutil.Process(os.getpid())
            # Menggunakan ABOVE_NORMAL_PRIORITY_CLASS (0x00008000) agar aman untuk Audio Driver
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            logger.info("✓ Process priority set to ABOVE_NORMAL")
            return True
        except Exception as e:
            logger.error("Failed to set high priority: %s", e)
            return False

    # ================================================================
    # WAKE ON LAN (WOL) AUDIT & DIAGNOSTIC (100% READ-ONLY)
    # ================================================================

    @staticmethod
    def audit_wake_on_lan() -> dict:
        """
        Audit kelayakan Wake-on-LAN secara murni READ-ONLY.
        Tidak melakukan modifikasi file, registry, atau service apapun.
        """
        import json
        import subprocess

        result = {
            "fast_startup": {"status": "UNKNOWN", "value": None, "detail": ""},
            "adapters": [],
            "eligible": False,
            "issues": [],
            "recommendations": []
        }

        # 1. Cek Fast Startup (HiberbootEnabled)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                0,
                winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
            winreg.CloseKey(key)
            result["fast_startup"]["value"] = val
            if val == 1:
                result["fast_startup"]["status"] = "FAIL"
                result["fast_startup"]["detail"] = "Aktif (Memutus arus siaga LAN saat Windows shutdown)"
                result["issues"].append("Fast Startup Windows aktif.")
                result["recommendations"].append("Matikan Fast Startup di Control Panel -> Power Options -> 'Choose what the power buttons do'.")
            else:
                result["fast_startup"]["status"] = "PASS"
                result["fast_startup"]["detail"] = "Nonaktif (S5 power standby aman)"
        except Exception as e:
            result["fast_startup"]["status"] = "WARN"
            result["fast_startup"]["detail"] = f"Tidak dapat dibaca: {e}"

        # 2. Cek Network Adapter & Driver via PowerShell (Read-only)
        try:
            ps_code = (
                "$item = [PSCustomObject]@{"
                "  Nics = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | ForEach-Object {"
                "    $n = $_.Name;"
                "    $pwr = Get-NetAdapterPowerManagement -Name $n -ErrorAction SilentlyContinue;"
                "    $adv = Get-NetAdapterAdvancedProperty -Name $n -ErrorAction SilentlyContinue;"
                "    [PSCustomObject]@{"
                "      Name = $n;"
                "      Description = $_.InterfaceDescription;"
                "      DriverProvider = $_.DriverProvider;"
                "      DriverVersion = $_.DriverVersion;"
                "      WakeOnMagicPacket = if ($pwr) { [int]$pwr.WakeOnMagicPacket } else { 0 };"
                "      AllowTurnOff = if ($pwr) { [int]$pwr.AllowComputerToTurnOffDevice } else { 0 };"
                "      ShutdownWake = ($adv | Where-Object { $_.DisplayName -match 'Shutdown Wake' }).DisplayValue;"
                "      LinkSpeed = ($adv | Where-Object { $_.DisplayName -match 'Link Speed' }).DisplayValue;"
                "    }"
                "  })"
                "};"
                "$item | ConvertTo-Json -Depth 3 -Compress"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10
            )
            if proc.stdout and proc.stdout.strip():
                data = json.loads(proc.stdout.strip())
                raw_nics = data.get("Nics", [])
                if isinstance(raw_nics, dict):
                    raw_nics = [raw_nics]
                result["adapters"] = raw_nics

                for nic in raw_nics:
                    name = nic.get("Name", "NIC")
                    provider = str(nic.get("DriverProvider", ""))
                    if "Microsoft" in provider:
                        result["issues"].append(f"Adapter '{name}' memakai driver generic Microsoft ({provider}).")
                        result["recommendations"].append(f"Ganti driver '{name}' dengan installer resmi Realtek/Intel OEM agar mendukung daya S5.")

                    magic = nic.get("WakeOnMagicPacket")
                    # CIM: 2 = Enabled, 3 = Disabled, 0/1 depend on schema
                    if magic not in (1, 2, "Enabled"):
                        result["issues"].append(f"Adapter '{name}' Wake-on-Magic-Packet belum diaktifkan.")
                        result["recommendations"].append(f"Aktifkan 'Wake on Magic Packet' di Device Manager -> Properties '{name}' -> Advanced.")

                    shut = str(nic.get("ShutdownWake", "") or "")
                    if shut and shut.lower() == "disabled":
                        result["issues"].append(f"Adapter '{name}' Shutdown Wake-On-Lan status Disabled.")
                        result["recommendations"].append(f"Ubah 'Shutdown Wake-On-Lan' ke 'Enabled' di Device Manager -> '{name}'.")
        except Exception as e:
            logger.warning("WOL audit adapter query error: %s", e)
            result["issues"].append(f"Gagal memeriksa adapter: {e}")

        # 3. Cek Kernel Wake Armed Devices (powercfg /devicequery wake_armed)
        try:
            armed_proc = subprocess.run(
                ["powercfg", "/devicequery", "wake_armed"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            armed_lines = [line.strip() for line in armed_proc.stdout.splitlines() if line.strip()]
            result["wake_armed_devices"] = armed_lines
            
            # Cek apakah ada adapter fisik yang terdaftar di wake_armed
            nic_armed = False
            for nic in result["adapters"]:
                desc = nic.get("Description", "")
                if any(desc.lower() in a.lower() for a in armed_lines):
                    nic_armed = True
                    break
            result["nic_is_wake_armed"] = nic_armed
            if not nic_armed:
                result["issues"].append("NIC fisik belum terdaftar di daftar 'wake_armed' Windows kernel.")
                result["recommendations"].append("Centang 'Allow this device to wake the computer' di tab Power Management kartu LAN.")
        except Exception as e:
            result["wake_armed_devices"] = []
            result["nic_is_wake_armed"] = False

        # 4. Catatan ErP / EuP (Tingkat Firmware Motherboard)
        result["erp_bios_note"] = "ErP/EuP adalah saklar sirkuit daya fisik di BIOS. OS tidak punya API langsung untuk membacanya. Indikator mutlak: jika lampu port LAN mati saat PC shutdown, ErP aktif atau FastBoot memutus daya."

        # 5. Overall Verdict
        result["eligible"] = (
            result["fast_startup"]["status"] == "PASS" and
            len(result["issues"]) == 0 and
            len(result["adapters"]) > 0
        )

        return result
