import os
import sys
import json
import time
import zipfile
import urllib.request
import threading
import subprocess
import logging

logger = logging.getLogger("GCToxicShield.Updater")

class GithubUpdater:
    """
    Modul untuk memeriksa pembaruan dari Release GitHub,
    mengunduh file ZIP aset rilis terbaru, dan menimpanya ke direktori aktif.
    """

    def __init__(self, repo_path: str, current_version: str):
        self.repo = repo_path
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        self._dl_thread = None

    def check_for_updates(self):
        """
        Mengecek API Github.
        Returns Tuple: (has_update, latest_version_string, download_zip_url, release_notes)
        """
        if not self.repo or self.repo == "USERNAME/REPO_NAME":
            return False, "", "", "Repository belum dikonfigurasi. Ubah di file main.py."

        try:
            req = urllib.request.Request(self.api_url, headers={'User-Agent': 'GCToxicShield-Updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
            latest_version = data.get("tag_name", "")
            if not latest_version:
                return False, "", "", ""
                
            curr = self.current_version.replace("v", "").strip()
            lat = latest_version.replace("v", "").strip()
            
            # Simple version parsing (e.g., "1.0.5" -> (1, 0, 5))
            def parse_ver(v_str):
                try:
                    return tuple(map(int, (v_str.split(".") + ["0", "0"])[:3]))
                except ValueError:
                    return (0, 0, 0)
                
            if parse_ver(lat) > parse_ver(curr):
                assets = data.get("assets", [])
                zip_url = ""
                for asset in assets:
                    if asset.get("name", "").endswith(".zip"):
                        zip_url = asset.get("browser_download_url")
                        break
                
                if zip_url:
                    return True, latest_version, zip_url, data.get("body", "Ada pembaruan sistem baru.")
                    
            return False, latest_version, "", ""
                
        except Exception as e:
            logger.error("Gagal mengecek update: %s", e)
            return False, "", "", f"Gagal mengecek update: {e}"

    def download_and_install_async(self, download_url: str, on_progress=None, on_complete=None, on_error=None):
        """
        Mengunduh .zip dari GitHub, dan membuat script .bat untuk men-timpa
        file instalasi ketika aplikasi (GCToxicShield.exe) ditutup, lalu restart otomatis.
        """
        if self._dl_thread and self._dl_thread.is_alive():
            return
            
        def _worker():
            try:
                temp_dir = os.environ.get("TEMP", "C:\\Temp")
                zip_path = os.path.join(temp_dir, "GCToxicShield_Update.zip")
                
                # 1. Download File
                if on_progress: on_progress("Mengunduh pembaruan dari GitHub...")
                req = urllib.request.Request(download_url, headers={'User-Agent': 'GCToxicShield-Updater'})
                with urllib.request.urlopen(req, timeout=30) as response, open(zip_path, 'wb') as out_file:
                    total_size_str = response.info().get('Content-Length')
                    total_size = int(total_size_str.strip()) if total_size_str else 0
                    
                    downloaded = 0
                    chunk_size = 16384
                    while True:
                        buffer = response.read(chunk_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        
                        if total_size > 0 and on_progress:
                            percent = int(downloaded * 100 / total_size)
                            # Update UI state secara berkala
                            if percent % 5 == 0: 
                                on_progress(f"Mengunduh... {percent}%")
                            
                # 2. Persiapkan Script Batch Instalasi
                if on_progress: on_progress("Menyiapkan instalasi otomatis...")
                self._spawn_update_script(zip_path)
                
                if on_complete: on_complete("Siap! Aplikasi akan direstart dalam 3 detik untuk menerapkan pembaruan.")
                
            except Exception as e:
                logger.error("Pembaruan gagal: %s", e)
                if on_error: on_error(str(e))
                
        self._dl_thread = threading.Thread(target=_worker, daemon=True)
        self._dl_thread.start()
        
    def _spawn_update_script(self, zip_path: str):
        """
        Membuat dan mengeksekusi script Batch lepas kendali yang akan membumi-hanguskan
        proses GCToxicShield saat ini, mengekstrak rilis terbaru, dan menyalakannya lagi.
        """
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        # Koreksi path jika jalan di dev Python (bukan dicompile)
        if "app" in app_dir or "build_tools" in app_dir:
            app_dir = os.path.dirname(app_dir)
            
        exe_name = os.path.basename(sys.argv[0])
        if not exe_name.endswith(".exe"):
            exe_name = "GCToxicShield.exe"
            
        bat_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "gctoxic_update.bat")
        
        # Script bat:
        # PING sbg sleep 4 dtk -> KILL exe lama -> PowerShell ekstrak ZIP -> START exe baru -> DELETE ZIP & script
        bat_content = f"""@echo off
echo Mengkonfigurasi pembaruan GC Toxic Shield...
echo JANGAN TUTUP JENDELA INI. Aplikasi akan terbuka otomatis setelah instalasi selesai.
ping 127.0.0.1 -n 4 > nul
taskkill /F /IM "{exe_name}" /T > nul 2>&1
ping 127.0.0.1 -n 2 > nul

echo Mengekstrak rancangan terbaru...
powershell -WindowStyle Hidden -NoProfile -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{app_dir}' -Force"

echo Memulai ulang aplikasi GC Toxic Shield...
start "" "{os.path.join(app_dir, exe_name)}"

del "{zip_path}"
del "%~f0"
"""
        with open(bat_path, "w") as f:
            f.write(bat_content)
            
        # Spawn execution in background without locking current process
        subprocess.Popen(
            [bat_path], 
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        # Self-destruct thread to allow the batch script to kill it safely and replace files
        def _exit_app():
            time.sleep(1.5)
            # Exit brutal ensuring no locks
            os._exit(0)
            
        threading.Thread(target=_exit_app, daemon=True).start()
