import os
import time
import logging
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("GCToxicShield.DesktopGuard")

class DesktopEventHandler(FileSystemEventHandler):
    """
    Handler untuk watchdog.
    Menangkap event pembuatan, penghapusan, dan pemindahan file di Desktop.
    """
    def __init__(self, on_violation_callback: Callable):
        super().__init__()
        self._on_violation = on_violation_callback
        # Rate limiting prevent UI flood
        self._last_trigger = 0

    def _handle_event(self, event):
        if event.is_directory:
            return
            
        now = time.time()
        # Cooldown 2 detik antar notifikasi
        if now - self._last_trigger > 2.0:
            self._last_trigger = now
            logger.warning("Desktop Guard Violation: %s %s", event.event_type, event.src_path)
            self._on_violation()

    def on_created(self, event):
        def _delete():
            # Abaikan penghapusan otomatis untuk file shortcut system/game launcher dan dekstop.ini
            if str(event.src_path).lower().endswith(('.lnk', '.ini', '.tmp')):
                return
                
            # Beri sedikit jeda agar proses copy/create Windows selesai
            time.sleep(0.5)
            try:
                if os.path.exists(event.src_path):
                    if os.path.isfile(event.src_path):
                        os.remove(event.src_path)
                        logger.info("Auto-deleted new file: %s", event.src_path)
                    elif os.path.isdir(event.src_path):
                        import shutil
                        shutil.rmtree(event.src_path)
                        logger.info("Auto-deleted new folder: %s", event.src_path)
            except Exception as e:
                logger.error("Failed to auto-delete %s: %s", event.src_path, e)
                
        # Jalankan di background thread agar tidak memblokir event loop
        threading.Thread(target=_delete, daemon=True).start()
        self._handle_event(event)
        
    def on_deleted(self, event):
        self._handle_event(event)
        
    def on_moved(self, event):
        self._handle_event(event)


class DesktopGuard:
    """
    T6: Surgical Desktop Guard.
    - Menggunakan icacls untuk memblokir Write/Delete (WD, D, WA).
    - Membiarkan Read/Execute (R, RX) agar icon masih interaktif.
    - Menggunakan watchdog untuk memunculkan peringatan responsif.
    """

    def __init__(self, root: tk.Tk):
        self._root = root
        self._is_enabled = False
        
        # Resolve Desktop paths
        user_profile = os.environ.get('USERPROFILE', '')
        public_profile = os.environ.get('PUBLIC', '')
        
        self._targets = []
        if user_profile:
            self._targets.append(os.path.join(user_profile, 'Desktop'))
        if public_profile:
            self._targets.append(os.path.join(public_profile, 'Desktop'))
            
        # Filter existing paths
        self._targets = [p for p in self._targets if os.path.exists(p)]
        
        self._observer: Optional[Observer] = None

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    def enable(self):
        """Aktifkan Guard: set ACL dan mulai Watchdog."""
        if self._is_enabled:
            return
            
        logger.info("Enabling Surgical Desktop Guard...")
        self._set_acl(lock=True)
        self._start_observer()
        self._is_enabled = True

    def disable(self):
        """Matikan Guard: restore ACL dan hentikan Watchdog."""
        if not self._is_enabled:
            # Force disable ACL just in case app crashed before
            self._set_acl(lock=False)
            return
            
        logger.info("Disabling Surgical Desktop Guard (Maintenance Mode ON)...")
        self._stop_observer()
        self._set_acl(lock=False)
        self._is_enabled = False

    # ── ACL Management (icacls) ──

    def _set_acl(self, lock: bool):
        """
        Modifikasi Permission Desktop menggunakan icacls.
        lock=True  -> Deny Delete(D), WriteData/AddFile(WD), WriteAttributes(WA)
        lock=False -> Remove Deny rules.
        """
        for path in self._targets:
            try:
                if lock:
                    # *S-1-1-0 is Everyone
                    # (OI)(CI)(IO) = Object Inherit, Container Inherit, Inherit Only
                    # Deny ONLY: Delete (D), Delete Subfolders and Files (DC)
                    # Do NOT deny WD or WEA because it breaks Explorer refresh icons.
                    # MUST use (IO) so the rule applies to the folder's contents, not the Desktop folder itself.
                    # TIDAK MENGGUNAKAN /T PADA COMMAND DENY agar tidak mengubah permissions file yang sudah ada secara paksa (menghindari bug icon hilang)
                    cmd = f'icacls "{path}" /deny *S-1-1-0:(OI)(CI)(IO)(D,DC) /C /Q'
                    logger.debug(f"Locking {path}")
                else:
                    # Remove the explicit deny
                    # KITA MENGGUNAKAN /T DI SINI HANYA UNTUK MEMBERSIHKAN KEKACAUAN VERSI SEBELUMNYA JIKA SUDAH TERLANJUR MENYEBAR
                    cmd = f'icacls "{path}" /remove:d *S-1-1-0 /T /C /Q'
                    logger.debug(f"Unlocking {path}")
                    
                subprocess.run(
                    cmd, shell=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                logger.error("Failed to set ACL via icacls on %s: %s", path, e)

    # ── Reactive Monitoring (Watchdog) ──

    def _start_observer(self):
        try:
            self._observer = Observer()
            handler = DesktopEventHandler(self._trigger_warning)
            
            for path in self._targets:
                self._observer.schedule(handler, path, recursive=False)
                
            self._observer.start()
            logger.info("Watchdog observer started for %d paths", len(self._targets))
        except Exception as e:
            logger.error("Failed to start watchdog: %s", e)

    def _stop_observer(self):
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception as e:
                logger.error("Failed to stop watchdog: %s", e)
            finally:
                self._observer = None

    # ── UI Callback ──

    def _trigger_warning(self):
        """Dipanggil dari background thread oleh watchdog."""
        if not self._is_enabled:
            return
            
        # Lempar eksekusi UI ke main thread
        try:
            self._root.after(0, self._show_simple_warning)
        except Exception as e:
            logger.error("Failed to dispatch SimpleWarningBox: %s", e)

    def _show_simple_warning(self):
        """Menampilkan SimpleWarningBox custom lewat overlay.py."""
        from app.overlay import SimpleWarningBox
        SimpleWarningBox(self._root)

    def cleanup(self):
        """Dipanggil saat aplikasi shutdown."""
        self.disable()
