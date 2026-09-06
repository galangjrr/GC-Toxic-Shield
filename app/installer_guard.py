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

    def __init__(self, root=None, network_client=None):
        self._root = root
        self._network_client = network_client
        self._is_enabled = False
        self._stop_event = threading.Event()
        self._last_trigger = 0.0
        self._threads = []
        self._watchdog_observer = None
        self._currently_blocking = set()
        self._block_lock = threading.Lock()

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
        self._base_blacklist = self.generic_keywords + self.specific_keywords
        self.blacklist = list(self._base_blacklist)

        # ── Settings/Control Panel processes to block ──
        self.settings_processes = {
            'systemsettings.exe',  # Windows Settings app
            'control.exe',         # Control Panel
            'mmc.exe',             # Microsoft Management Console
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
            r'c:\windows\\',
            r'c:\programdata\\',
        ]

        user_profile = os.environ.get('USERPROFILE', r'C:\Users\Default').lower()

        # Path whitelist — processes from these dirs are always allowed
        self._base_whitelist_paths = [
            r"c:\windows\\",
            r"c:\programdata\\",
            r"c:\gc net\\",
            r"c:\program files\cyberindo\\",
            r"c:\program files (x86)\roblox\\",
            r"c:\program files (x86)\steam\\",
            r"c:\program files\epic games\\",
            r"c:\riot games\\",
            r"c:\program files\ea games\\",
            r"c:\xboxgames\\",
        ]
        self.whitelist_paths = list(self._base_whitelist_paths)
        
        # Publisher whitelist — PE metadata must contain one of these
        self.trusted_publishers = {
            'roblox corporation',
            'valve corporation',
            'epic games',
            'riot games',
            'zepetto',
            'garena',
        }
        
        # Process name whitelist — these EXE names are always allowed
        self._base_whitelist_processes = {
            'robloxplayerlauncher.exe',
            'robloxplayerinstaller.exe',
            'robloxstudiolauncherbeta.exe',
            'robloxcrashhandler.exe',
            'pointblank.exe',
            'pblauncher.exe',
            'garena.exe',
            'garenamessenger.exe',
            'lc.exe',
            'antigravity.exe',
            'code.exe',
            'cursor.exe',
            'devenv.exe',
        }
        self.whitelist_processes = set(self._base_whitelist_processes)
        
        self.load_config()

    def load_config(self):
        """Muat konfigurasi whitelist/blacklist dari file."""
        import os, json
        from app._paths import GUARD_CONFIG_PATH
        
        # 1. Reset to base/hardcoded arrays safely first
        self.whitelist_paths = list(self._base_whitelist_paths)
        self.whitelist_processes = set(self._base_whitelist_processes)
        self.blacklist = list(self._base_blacklist)
        
        if not os.path.exists(GUARD_CONFIG_PATH):
            return
            
        try:
            with open(GUARD_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # 2. Safely merge custom items from disk
            if "whitelist_paths" in data:
                for p in data["whitelist_paths"]:
                    val = str(p).lower()
                    if val not in self.whitelist_paths:
                        self.whitelist_paths.append(val)
            if "whitelist_processes" in data:
                for p in data["whitelist_processes"]:
                    self.whitelist_processes.add(str(p).lower())
            if "blacklist" in data:
                for kw in data["blacklist"]:
                    val = str(kw).lower()
                    if val not in self.blacklist:
                        self.blacklist.append(val)
                
            logger.info("Loaded custom installer guard configuration (Paths: %d, Procs: %d, Blk: %d)", 
                        len(self.whitelist_paths), len(self.whitelist_processes), len(self.blacklist))
        except Exception as e:
            logger.error("Failed to load installer guard configuration: %s", e)

    # ── Block mode control ──────────────────────────────────────

    def set_block_installer(self, enabled: bool):
        """Set whether installer blocking is active."""
        self._block_installer = enabled

    def set_block_settings(self, enabled: bool):
        """Set whether Settings/Control Panel blocking is active."""
        self._block_settings = enabled
        if enabled:
            self._kill_running_settings_processes()

    def _kill_running_settings_processes(self):
        """Mencari dan mematikan semua instance systemsettings.exe / control.exe yang sedang aktif seketika."""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pname = str(proc.info['name']).lower()
                    if pname in self.settings_processes:
                        pid = proc.info['pid']
                        self._execute_settings_kill(pid, pname, "SETTINGS_BLOCK_INSTANT")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug("Error scanning running settings processes: %s", e)

    def reload(self, block_installer=None, block_settings=None):
        """
        Hot-reload: update block flags and reload config.
        Stops/starts threads only if overall enabled state changes.
        """
        if block_installer is not None:
            self._block_installer = bool(block_installer)
        if block_settings is not None:
            self._block_settings = bool(block_settings)
            if self._block_settings:
                self._kill_running_settings_processes()

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
        
        # Bypass enabling if root dashboard is in maintenance mode
        if getattr(self._root, "is_maintenance_mode", False):
            logger.info("Maintenance Mode is active. InstallerGuard enable bypassed.")
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
                            self._execute_settings_kill(pid, p_name, "SETTINGS_BLOCK")
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
        pe = None
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
        finally:
            if pe and hasattr(pe, 'close'):
                pe.close()
        return meta_str.lower()
    def _analyze_installer_heuristics(self, exe_path: str, p_name: str) -> tuple[int, str]:
        """Menghitung Heuristic Threat Score (0-100) berdasarkan indikator file PE."""
        score = 0
        reasons = []
        
        metadata_corpus = (p_name + " " + self._get_pe_metadata(exe_path)).lower()
        
        # 1. Cek Trusted Publishers (Otomatis Lolos)
        if any(pub in metadata_corpus for pub in self.trusted_publishers):
            return 0, "Trusted Publisher"
            
        # 2. NLP Metadata Analysis
        keyword_weights = {
            'setup': 40,
            'install': 40,
            'wizard': 20,
            'extractor': 30,
            'downloader': 30,
            'unpack': 20
        }
        for kw, weight in keyword_weights.items():
            if kw in metadata_corpus:
                score += weight
                reasons.append(f"Keyword '{kw}' (+{weight})")
                
        # 3. Pengecekan Manifest (Admin Privilege) & Resource Ratio
        try:
            pe = pefile.PE(exe_path, fast_load=True)
            rsrc_size = 0
            text_size = 0
            for section in pe.sections:
                s_name = section.Name.decode('utf-8', 'ignore').strip('\x00')
                if s_name == '.rsrc': rsrc_size = section.SizeOfRawData
                elif s_name == '.text': text_size = section.SizeOfRawData
                
            if rsrc_size > 0 and text_size > 0:
                if rsrc_size > text_size * 2:
                    score += 20
                    reasons.append("High Resource Ratio (+20)")

            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
                for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                    if entry.id == 24: # RT_MANIFEST
                        for res_id in entry.directory.entries:
                            for res_lang in res_id.directory.entries:
                                data_rva = res_lang.data.struct.OffsetToData
                                size = res_lang.data.struct.Size
                                data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
                                manifest = data.decode('utf-8', 'ignore').lower()
                                if 'requireadministrator' in manifest or 'highestavailable' in manifest:
                                    score += 35
                                    reasons.append("Admin Privilege Request (+35)")
                                    break
        except Exception:
            pass
            
        return score, " | ".join(reasons)

    def _analyze_and_kill(self, process_event):
        p = None
        is_suspended = False
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
            
            # --- SUSPEND SUSPICIOUS PROCESS IMMEDIATELY ---
            # Suspend right away to prevent its UI from rendering before PE/Path analysis
            p.suspend()
            is_suspended = True
            logger.debug("Temporarily suspended potential installer %s (PID %d) for analysis", p_name, pid)
                    
            # --- 2. Triangulasi Heuristic AI ---
            score, reason = self._analyze_installer_heuristics(exe_path, p_name)
            
            if score == 0 and "Trusted Publisher" in reason:
                logger.info("✅ Trusted publisher detected in %s. Allowing execution.", p_name)
                if is_suspended:
                    try: p.resume()
                    except Exception: pass
                return
                
            if score >= 75:
                # Target terblokir oleh Heuristic Score
                trigger_msg = f"Skor Heuristic {score} ({reason})"
                self._execute_kill(pid, p_name, exe_path, trigger_msg, "HEURISTIC_ENGINE", already_suspended=True)
                return

            # --- Cek Blacklist Spesifik (Fallback) ---
            matched_keyword = None
            for kw in self.specific_keywords:
                metadata_corpus = (p_name + self._get_pe_metadata(exe_path)).lower()
                if kw in metadata_corpus:
                    matched_keyword = kw
                    break

            if matched_keyword:
                self._execute_kill(pid, p_name, exe_path, matched_keyword, "WMI_SPECIFIC_BLACKLIST", already_suspended=True)
                return

            # If we reach here, it is NOT blocked! Resume it immediately.
            if is_suspended:
                p.resume()

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            logger.error("Error in _analyze_and_kill: %s", e)
            # Safe fallback: if we suspended it and something errored out, resume it
            if p and is_suspended:
                try:
                    p.resume()
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

                        if owner_process in self.whitelist_processes:
                            time.sleep(1.5)
                            continue

                        # Skip browser windows entirely (prevent false positives)
                        if owner_process in self.browser_processes:
                            time.sleep(1.5)
                            continue

                        # Check if process path is whitelisted
                        try:
                            exe_path = psutil.Process(pid).exe().lower()
                            if any(exe_path.startswith(wp) for wp in self.whitelist_paths):
                                time.sleep(1.5)
                                continue
                        except Exception:
                            pass

                        # Settings/Control Panel window blocking
                        if self._block_settings:
                            is_settings_process = owner_process in self.settings_processes
                            is_host_process = owner_process in ['explorer.exe', 'applicationframehost.exe']
                            
                            if is_settings_process or is_host_process:
                                if any(kw in title for kw in ['settings', 'control panel', 'pengaturan', 'all control panel items']):
                                    if is_host_process:
                                        import win32con
                                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                                        logger.warning("🚨 [INSTALLER GUARD] Closed '%s' window gracefully (owned by %s)", title, owner_process)
                                    else:
                                        if pid > 0:
                                            self._execute_settings_kill(pid, owner_process, "WINDOW_SETTINGS_BLOCK")
                                    time.sleep(1.5)
                                    continue

                        # Installer window title blocking & Deep Window UI Scanning
                        if self._block_installer:
                            child_texts = []
                            def enum_child_callback(chwnd, ctx):
                                try:
                                    if win32gui.IsWindowVisible(chwnd):
                                        txt = win32gui.GetWindowText(chwnd).strip().lower()
                                        if txt: ctx.append(txt)
                                except: pass
                                return True
                                
                            try:
                                win32gui.EnumChildWindows(hwnd, enum_child_callback, child_texts)
                            except: pass
                            
                            # Cek Judul (Title Bar) menggunakan specific blacklist
                            title_blocked = False
                            for kw in self.specific_keywords:
                                if kw in title:
                                    if pid > 0:
                                        self._execute_kill(pid, owner_process, "N/A", kw, "WINDOW_TITLE_SENSOR")
                                    title_blocked = True
                                    break
                                    
                            if title_blocked:
                                continue
                                
                            # Cek Teks dalam tombol/jendela (Deep UI Scan) menggunakan generic keywords
                            installer_buttons = ['next >', 'i agree', 'install', 'setup', 'extract']
                            # Kalau ada lebih dari 2 kata tombol installer ditemukan dalam satu layar
                            found_buttons = sum(1 for b in installer_buttons if any(b == txt or b in txt for txt in child_texts))
                            
                            if found_buttons >= 2 or any(kw in title for kw in self.generic_keywords):
                                # Pastikan bukan aplikasi legal (game launcher mitigation)
                                safe_keywords = ['roblox', 'point blank', 'garena', 'pointblank', 'live', 'studio']
                                if not any(sk in title for sk in safe_keywords):
                                    trigger = "DeepUI: " + " | ".join([b for b in installer_buttons if any(b in txt for txt in child_texts)])
                                    if not trigger.strip("DeepUI: | "): 
                                        trigger = "Title Keyword"
                                    if pid > 0:
                                        self._execute_kill(pid, owner_process, "N/A", trigger, "DEEP_WINDOW_SCANNER")
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
                
                if any(pub in metadata for pub in self.trusted_publishers):
                    continue

                for kw in self.blacklist:
                    if kw in metadata:
                        self._execute_kill(p.info['pid'], name, exe, kw, trigger_source)
                        break
        except Exception:
            pass

    # =========================================================================
    # ACTION: Kill & Report
    # =========================================================================
    def _execute_kill(self, pid: int, process_name: str, path: str, keyword: str, source: str, already_suspended: bool = False):
        """Eksekusi pemblokiran tunggal."""
        with self._block_lock:
            if pid in self._currently_blocking:
                logger.info("Process %d is already in block list, skipping duplicate prompt.", pid)
                return
            self._currently_blocking.add(pid)

        try:
            target = psutil.Process(pid)
            
            # SUSPEND & OVERRIDE LOGIC
            if not already_suspended:
                target.suspend()
                logger.warning("🚨 [INSTALLER GUARD] (%s) SUSPENDED %s (Trigger Keyword: '%s')", source, process_name, keyword)
            else:
                logger.warning("🚨 [INSTALLER GUARD] (%s) Already suspended %s (Trigger Keyword: '%s')", source, process_name, keyword)
            
            allow = False
            if hasattr(self, 'on_blocked_callback') and callable(self.on_blocked_callback):
                # This call blocks the thread until the main thread dialog is closed
                allow = self.on_blocked_callback(process_name, keyword, source)
                
            if allow:
                logger.info("✅ [INSTALLER GUARD] Admin override granted. Resuming %s", process_name)
                target.resume()
                self.whitelist_processes.add(process_name.lower())
                return
            else:
                logger.warning("🚫 [INSTALLER GUARD] Override denied. Terminating %s", process_name)
                try: target.resume() 
                except: pass
                target.kill()
            
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
        finally:
            with self._block_lock:
                self._currently_blocking.discard(pid)

    def _execute_settings_kill(self, pid: int, process_name: str, source: str):
        """Eksekusi pemblokiran khusus untuk System Settings & Control Panel (tanpa prompt password)."""
        with self._block_lock:
            if pid in self._currently_blocking:
                return
            self._currently_blocking.add(pid)

        try:
            target = psutil.Process(pid)
            logger.warning("🚫 [SETTINGS GUARD] (%s) Terminating Settings/Control Panel: %s", source, process_name)
            target.terminate()
            
            if self._network_client:
                self._report_blocked(process_name, f"[{source}] {process_name} (Settings Block)")
                
            now = time.time()
            if now - self._last_trigger > 3.0:
                self._last_trigger = now
                self._trigger_settings_warning()
        except Exception:
            pass
        finally:
            with self._block_lock:
                self._currently_blocking.discard(pid)

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
            SimpleWarningBox(custom_text=msg, parent=self._root)

    def _trigger_settings_warning(self):
        if self._root:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._root, self._show_settings_warning)

    def _show_settings_warning(self):
        from app.overlay import SimpleWarningBox
        if getattr(SimpleWarningBox, "_instance", None) is None:
            msg = "Akses ke Control Panel / System Settings diblokir oleh Administrator. Silakan gunakan Mode Maintenance jika ingin mengaksesnya."
            SimpleWarningBox(custom_text=msg, parent=self._root)

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
