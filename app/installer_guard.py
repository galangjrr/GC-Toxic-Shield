import os
import time
import logging
import threading
import wmi
import pythoncom
import psutil
import pefile

import win32gui
import win32process

from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("GCToxicShield.InstallerGuard")


class InstallerGuard:
    """
    T6: Real-Time Installer Guard via Triangulation Detection.
    Lapis Perlindungan:
      1. WMI PE Metadata Scan (FileDescription, ProductName, CompanyName)
      2. Active Window Title Monitor (mendeteksi jendela "Setup" / "TikTok")
      3. AppData Watchdog (mendeteksi pembuatan folder "TikTok Live Studio")
      4. Path-based check untuk Downloads/Desktop activities.
      5. Settings/Control Panel process blocking (systemsettings.exe, control.exe)
    """

    def __init__(self, root, network_client=None):
        self._root = root
        self._network_client = network_client
        self._is_enabled = False
        self._stop_event = threading.Event()
        self._last_trigger = 0.0
        self._threads = []
        self._watchdog_observer = None

        # ── Block mode flags ──
        self._block_installer = False
        self._block_settings = False

        # ── Separated keyword lists for smart triangulation ──
        self.generic_keywords = [
            'setup', 'installer', 'installcore', 'opencandy',
            'wizard', 'extractor', 'downloader',
        ]
        self.specific_keywords = [
            'tiktok live studio', 'tiktoklivestudio', 'bytedance',
            'tiktok-live-studio', 'tiktok',
        ]
        # Combined blacklist for backward compat with load_config()
        self.blacklist = self.generic_keywords + self.specific_keywords

        # ── Settings/Control Panel processes to block ──
        self.settings_processes = {
            'systemsettings.exe',  # Windows Settings app
            'control.exe',         # Control Panel
        }

        # ── Browser whitelist (eliminate false positives) ──
        self.browser_processes = {
            'chrome.exe', 'msedge.exe', 'firefox.exe', 'opera.exe',
            'brave.exe', 'vivaldi.exe', 'iexplore.exe', 'chromium.exe',
            'browser.exe', 'waterfox.exe', 'librewolf.exe',
        }

        # ── Safe install paths (trusted locations for generic keyword matches) ──
        self.safe_install_paths = [
            r'c:\program files\\',
            r'c:\program files (x86)\\',
        ]

        user_profile = os.environ.get('USERPROFILE', r'C:\Users\Default').lower()

        # Path whitelist — processes from these dirs are always allowed
        self.whitelist_paths = [
            r"c:\windows\\",
            r"c:\gc net\\",
            r"c:\program files\cyberindo\\",
            r"c:\program files (x86)\roblox\\",
            os.path.join(user_profile, 'appdata', 'local', 'roblox').lower() + '\\',
        ]
        
        # Process name whitelist — these EXE names are always allowed
        self.whitelist_processes = {
            'robloxplayerlauncher.exe',
            'robloxcrashhandler.exe',
            'pointblank.exe',
            'pblauncher.exe',
            'garena.exe',
            'garenamessenger.exe',
            'lc.exe',
        }
        
        self.danger_zones = [
            os.path.join(user_profile, 'downloads'),
            os.path.join(user_profile, 'desktop'),
            os.path.join(user_profile, 'appdata', 'local', 'temp')
        ]
        
        self.load_config()

    def load_config(self):
        """Muat konfigurasi whitelist/blacklist dari file."""
        import os, json
        from app._paths import GUARD_CONFIG_PATH
        if not os.path.exists(GUARD_CONFIG_PATH):
            return
            
        try:
            with open(GUARD_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "whitelist_paths" in data:
                self.whitelist_paths = [str(p).lower() for p in data["whitelist_paths"]]
            if "whitelist_processes" in data:
                self.whitelist_processes = {str(p).lower() for p in data["whitelist_processes"]}
            if "blacklist" in data:
                self.blacklist = [str(kw).lower() for kw in data["blacklist"]]
                
            logger.info("Loaded custom installer guard configuration (Paths: %d, Procs: %d)", 
                        len(self.whitelist_paths), len(self.whitelist_processes))
        except Exception as e:
            logger.error("Failed to load installer guard configuration: %s", e)

    # ── Block mode control ──────────────────────────────────────

    def set_block_installer(self, enabled: bool):
        """Set whether installer blocking is active."""
        self._block_installer = enabled

    def set_block_settings(self, enabled: bool):
        """Set whether Settings/Control Panel blocking is active."""
        self._block_settings = enabled

    def reload(self, block_installer=None, block_settings=None):
        """
        Hot-reload: update block flags and reload config.
        Stops/starts threads only if overall enabled state changes.
        """
        if block_installer is not None:
            self._block_installer = bool(block_installer)
        if block_settings is not None:
            self._block_settings = bool(block_settings)

        self.load_config()

        should_be_enabled = self._block_installer or self._block_settings
        if should_be_enabled and not self._is_enabled:
            self.enable()
        elif not should_be_enabled and self._is_enabled:
            self.disable()

        logger.info("InstallerGuard reloaded (installer=%s, settings=%s, enabled=%s)",
                     self._block_installer, self._block_settings, self._is_enabled)

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    def enable(self):
        if self._is_enabled:
            return
        
        logger.info("Enabling Triangulation Installer Guard...")
        self._stop_event.clear()
        
        # 1. WMI Process Monitor
        t1 = threading.Thread(target=self._monitor_processes_wmi, daemon=True)
        t1.start()
        self._threads.append(t1)
        
        # 2. UI Window Title Monitor
        t2 = threading.Thread(target=self._monitor_window_titles, daemon=True)
        t2.start()
        self._threads.append(t2)
        
        # 3. Behavioral Watchdog (%LocalAppData%)
        self._start_appdata_watchdog()
        
        self._is_enabled = True

    def disable(self):
        if not self._is_enabled:
            return
            
        logger.info("Disabling Triangulation Installer Guard (Maintenance Mode ON)...")
        self._stop_event.set()
        
        if self._watchdog_observer:
            self._watchdog_observer.stop()
            self._watchdog_observer.join(timeout=2.0)
            
        for t in self._threads:
            if t.is_alive():
                t.join(timeout=2.0)
        self._threads.clear()
        
        self._is_enabled = False

    # =========================================================================
    # LAYER 1 & 4: WMI Process & PE Metadata (Publisher Check) + Path Rule
    # =========================================================================
    def _monitor_processes_wmi(self):
        try:
            # Low priority IO/CPU (via priority class)
            psutil.Process(os.getpid()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except:
            pass
            
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            process_watcher = c.Win32_ProcessStartTrace.watch_for("creation")
            
            while not self._stop_event.is_set():
                try:
                    new_process = process_watcher(timeout_ms=1000)
                    if new_process:
                        p_name = str(new_process.ProcessName).lower()

                        # Settings/Control Panel process blocking (top-level)
                        if self._block_settings and p_name in self.settings_processes:
                            pid = int(new_process.ProcessId)
                            self._execute_kill(pid, p_name, "N/A", p_name, "SETTINGS_BLOCK")
                            continue

                        # Normal installer blacklist check
                        if self._block_installer:
                            self._analyze_and_kill(new_process)
                except wmi.x_wmi_timed_out:
                    continue
                except Exception:
                    pass
        except Exception as e:
            logger.error("Installer Guard WMI crashed: %s", e)
        finally:
            pythoncom.CoUninitialize()

    def _get_pe_metadata(self, exe_path: str) -> str:
        """Mengambil string metadata lengkap termasuk CompanyName / Publisher."""
        meta_str = ""
        try:
            pe = pefile.PE(exe_path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            
            if hasattr(pe, 'FileInfo'):
                for finfo in pe.FileInfo:
                    for info in finfo:
                        if hasattr(info, 'StringTable'):
                            for st in info.StringTable:
                                for key_raw, val_raw in st.entries.items():
                                    try:
                                        key = key_raw.decode('utf-8', 'ignore').strip()
                                        val = val_raw.decode('utf-8', 'ignore').strip()
                                        # Termasuk ekstrak Publisher / Signer
                                        target_keys = [
                                            'FileDescription', 'ProductName', 
                                            'InternalName', 'OriginalFilename',
                                            'CompanyName', 'LegalCopyright'
                                        ]
                                        if key in target_keys:
                                            meta_str += " " + val
                                    except Exception:
                                        pass
        except Exception:
            pass
        return meta_str.lower()

    def _analyze_and_kill(self, process_event):
        try:
            pid = int(process_event.ProcessId)
            p_name = str(process_event.ProcessName).lower()
            
            if p_name in self.whitelist_processes:
                return

            # Skip browser processes (eliminate false positives)
            if p_name in self.browser_processes:
                return
            
            p = psutil.Process(pid)
            exe_path = p.exe().lower()
            
            for wp in self.whitelist_paths:
                if exe_path.startswith(wp):
                    return
                    
            # --- 2. Triangulasi Metadata & Publisher ---
            metadata_corpus = p_name + self._get_pe_metadata(exe_path)
            
            # --- 3. Path-based Heuristic Modifier ---
            # Jika dijalankan dari Downloads/Desktop, pemeriksaannya lebih agresif (langsung tembak jika metadata cocok)
            is_danger_zone = any(exe_path.startswith(dz) for dz in self.danger_zones)

            # --- Smart Triangulation Algorithm ---
            # 1. Check specific keywords first — BLOCK immediately anywhere
            specific_match = None
            for kw in self.specific_keywords:
                if kw in metadata_corpus:
                    specific_match = kw
                    break

            if specific_match:
                self._execute_kill(pid, p_name, exe_path, specific_match, "WMI_PE_SPECIFIC")
                return

            # 2. Check generic keywords — BLOCK only if in danger zone or NOT in safe path
            generic_match = None
            for kw in self.generic_keywords:
                if kw in metadata_corpus:
                    generic_match = kw
                    break

            if generic_match:
                # If exe is in a safe install path and only generic keywords matched, skip
                is_safe_path = any(exe_path.startswith(sp) for sp in self.safe_install_paths)
                if is_safe_path:
                    return  # Trusted location, generic keyword — skip

                # Block if in danger zone OR not in safe path
                self._execute_kill(pid, p_name, exe_path, generic_match, "WMI_PE_METADATA")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass

    # =========================================================================
    # LAYER 2: Window Title Monitoring (UI Sensor)
    # =========================================================================
    def _monitor_window_titles(self):
        """Memantau Foreground Window Title secara terus-menerus (Polling 1.5s)."""
        while not self._stop_event.is_set():
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd).strip().lower()
                    if title:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        owner_process = self._get_process_name_safe(pid).lower()

                        # Skip browser windows entirely (prevent false positives)
                        if owner_process in self.browser_processes:
                            time.sleep(1.5)
                            continue

                        # Settings/Control Panel window blocking
                        if self._block_settings:
                            if owner_process in self.settings_processes:
                                if any(kw in title for kw in ['settings', 'control panel', 'pengaturan']):
                                    if pid > 0:
                                        self._execute_kill(pid, owner_process, "N/A", "settings_window", "WINDOW_SETTINGS_BLOCK")
                                        time.sleep(1.5)
                                        continue

                        # Installer window title blocking
                        if self._block_installer:
                            for kw in self.blacklist:
                                # Hanya tembak title bar yang mengandung kata-kata spesifik instalasi/target
                                # Tingkatkan akurasi: abaikan kata umum jika terdeteksi di launcher game yang sah
                                if kw in title:
                                    if kw in ['live', 'studio', 'streamer', 'assistant']:
                                        continue
                                    
                                    # Deteksi apakah ini jendela launcher game yang sah (false positive mitigation)
                                    safe_keywords = ['roblox', 'point blank', 'garena', 'pointblank']
                                    if any(sk in title for sk in safe_keywords) and kw == 'installer':
                                        continue
                                        
                                    if pid > 0:
                                        self._execute_kill(pid, owner_process, "N/A", kw, "WINDOW_TITLE_SENSOR")
                                    break
            except Exception:
                pass
            time.sleep(1.5)
            
    def _get_process_name_safe(self, pid: int) -> str:
        try:
            return psutil.Process(pid).name()
        except:
            return f"PID_{pid}"

    # =========================================================================
    # LAYER 3: Behavioral Watchdog (TikTok Live Studio LOCALAPPDATA Pattern)
    # =========================================================================
    def _start_appdata_watchdog(self):
        local_app_data = os.environ.get('LOCALAPPDATA', r'C:\Users\Galang\AppData\Local')
        if not os.path.exists(local_app_data):
            return
            
        handler = AppDataFolderHandler(self)
        self._watchdog_observer = Observer()
        self._watchdog_observer.schedule(handler, local_app_data, recursive=False)
        self._watchdog_observer.start()
        
    def handle_behavioral_violation(self, folder_name: str, path: str):
        """Dipanggil dari Watchdog Event ketika ada pembuatan folder terlarang (cth: 'TikTok Live Studio')."""
        logger.warning("🚨 [INSTALLER GUARD] Behavioral violation: Folder setup detected -> %s", path)
        
        # Lacak siapa (proses mana) yang sedang banyak menulis/terakhir aktif di direktori tersebut.
        # Atau sebagai brute force defense: matikan installer-installer yg sedang berjalan
        self._kill_suspect_installers("APP_DATA_BEHAVIORAL")

    def _kill_suspect_installers(self, trigger_source: str):
        """Brute force scan untuk mematikan setup wizard aktif ketika file path pattern terpicu."""
        try:
            for p in psutil.process_iter(['pid', 'name', 'exe']):
                name = (p.info['name'] or '').lower()
                exe = (p.info['exe'] or '').lower()
                
                if name in self.whitelist_processes:
                    continue
                # Skip browser processes
                if name in self.browser_processes:
                    continue
                if any(exe.startswith(wp) for wp in self.whitelist_paths):
                    continue
                    
                metadata = name + self._get_pe_metadata(exe)
                for kw in self.blacklist:
                    if kw in metadata:
                        self._execute_kill(p.info['pid'], name, exe, kw, trigger_source)
                        break
        except Exception:
            pass

    # =========================================================================
    # ACTION: Kill & Report
    # =========================================================================
    def _execute_kill(self, pid: int, process_name: str, path: str, keyword: str, source: str):
        """Eksekusi pemblokiran tunggal."""
        try:
            target = psutil.Process(pid)
            target.terminate()
            
            logger.warning(
                "🚨 [INSTALLER GUARD] (%s) Blocked %s (Trigger Keyword: '%s')", 
                source, process_name, keyword
            )
            
            if self._network_client:
                # Modifikasi packet di center report
                report_str = f"[{source}] {process_name} (Kw: {keyword})"
                self._report_blocked(process_name, report_str)
            
            now = time.time()
            if now - self._last_trigger > 3.0:
                self._last_trigger = now
                self._trigger_warning()
        except Exception:
            pass

    def _report_blocked(self, filename: str, trigger: str):
        if hasattr(self._network_client, "report_blocked_installer"):
            self._network_client.report_blocked_installer(filename, trigger)
        elif hasattr(self._network_client, "report_violation"):
            self._network_client.report_violation(
                level=0, 
                trigger_word=f"[INSTALL_BLOCKED] {filename} ({trigger})"
            )

    def _trigger_warning(self):
        if self._root:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._root, self._show_simple_warning)

    def _show_simple_warning(self):
        from app.overlay import SimpleWarningBox
        if getattr(SimpleWarningBox, "_instance", None) is None:
            msg = "Instalasi mandiri dilarang demi stabilitas komputer. Silahkan hubungi admin jika ingin menginstall aplikasi tertentu"
            SimpleWarningBox(self._root, custom_text=msg)

    def cleanup(self):
        self.disable()


class AppDataFolderHandler(FileSystemEventHandler):
    """
    Watchdog khusus %LocalAppData%.
    Deteksi jika installer mencoba "unpacking" file kerjanya layaknya TikTok Live Studio.
    """
    def __init__(self, guard: InstallerGuard):
        super().__init__()
        self.guard = guard

    def on_created(self, event):
        if event.is_directory:
            folder_name = os.path.basename(event.src_path).lower()
            if 'tiktok' in folder_name or 'bytedance' in folder_name:
                self.guard.handle_behavioral_violation(folder_name, event.src_path)
