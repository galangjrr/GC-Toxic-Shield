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
    """

    def __init__(self, root, network_client=None):
        self._root = root
        self._network_client = network_client
        self._is_enabled = False
        self._stop_event = threading.Event()
        self._last_trigger = 0.0
        
        self._threads = []
        self._watchdog_observer = None
        
        # Blacklist agresif dari instruksi: case-insensitive
        self.blacklist = [
            'setup', 'installer', 'installcore', 'opencandy', 
            'wizard', 'extractor', 'downloader', 'assistant',
            'tiktok', 'bytedance', 'studio', 'live', 'streamer'
        ]
        
        # Exception Path (Hanya mengizinkan aplikasi Sistem, GC Net, Cyberindo)
        self.whitelist_paths = [
            r"c:\windows\\",
            r"c:\gc net\\",
            r"c:\program files\cyberindo\\"
        ]
        
        # Danger folders for path-based heuristic
        user_profile = os.environ.get('USERPROFILE', r'C:\Users\Galang').lower()
        self.danger_zones = [
            os.path.join(user_profile, 'downloads'),
            os.path.join(user_profile, 'desktop'),
            os.path.join(user_profile, 'appdata', 'local', 'temp')
        ]
        
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
            
            p = psutil.Process(pid)
            exe_path = p.exe().lower()
            
            # --- 1. Whitelist Check ---
            for wp in self.whitelist_paths:
                if exe_path.startswith(wp):
                    return
                    
            # --- 2. Triangulasi Metadata & Publisher ---
            metadata_corpus = p_name + self._get_pe_metadata(exe_path)
            
            # --- 3. Path-based Heuristic Modifier ---
            # Jika dijalankan dari Downloads/Desktop, pemeriksaannya lebih agresif (langsung tembak jika metadata cocok)
            is_danger_zone = any(exe_path.startswith(dz) for dz in self.danger_zones)
            
            trigger_keyword = None
            for kw in self.blacklist:
                if kw in metadata_corpus:
                    trigger_keyword = kw
                    break
                    
            if trigger_keyword:
                self._execute_kill(pid, p_name, exe_path, trigger_keyword, "WMI_PE_METADATA")

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
                        for kw in self.blacklist:
                            # Strict match for very common words like live/studio if standalone, 
                            # but direct match for tiktok/setup
                            if kw in ['setup', 'install', 'tiktok', 'bytedance']:
                                if kw in title:
                                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                                    if pid > 0:
                                        p_name = self._get_process_name_safe(pid)
                                        self._execute_kill(pid, p_name, "N/A", kw, "WINDOW_TITLE_SENSOR")
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
                
                # Biarkan system bebas
                is_system = any(exe.startswith(wp) for wp in self.whitelist_paths)
                if is_system:
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
        self._root.after(0, self._show_simple_warning)

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
