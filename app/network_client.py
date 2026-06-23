# =============================================================
# GC Toxic Shield — Network Client
# =============================================================
# Modul komunikasi klien yang berjalan non-blocking di
# background thread. Menghubungkan PC klien ke Admin Server.
#
# Fitur:
# - Auto-reconnect jika koneksi terputus (setiap 15 detik)
# - Heartbeat LISTENING setiap 10 detik
# - Event Reporter: lapor pelanggaran ke server secara instan
# - Remote Command Listener: terima REMOTE_LOCK / REMOTE_WARNING
# =============================================================

import asyncio
import json
import logging
import os
import socket
import threading
import time
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QTimer

from app.logger_service import LoggerService
from app.penalty_manager import PenaltyManager
from app.system_service import SystemService
from app.detector import ToxicDetector
from app.auth_service import AuthService
from PySide6.QtCore import QTimer


logger = logging.getLogger("GCToxicShield.NetworkClient")

# ── Constants ──────────────────────────────────────────────────
HEARTBEAT_INTERVAL = 10      # Detik antar heartbeat
RECONNECT_DELAY    = 15      # Detik sebelum mencoba reconnect
CONNECT_TIMEOUT    = 5       # Detik timeout saat connect
READ_TIMEOUT       = 60      # Detik timeout saat menunggu data server


class NetworkClient(QObject):
    """
    Async TCP client yang berjalan di daemon thread terpisah.

    Gunakan:
        client = NetworkClient(
            server_ip="192.168.1.100",
            server_port=9000,
            pc_name="PC-01",
            root=tk_root,           # tk root untuk root.after() dispatch
            penalty_mgr=penalty_mgr # PenaltyManager instance
        )
        client.start()
        ...
        client.report_violation(level=2, trigger_word="kata")
        ...
        client.stop()
    """
    
    # Signals untuk thread-safe dispatch:
    remote_lock_signal = Signal(int, str)
    remote_warning_signal = Signal(str)
    remote_reset_level_signal = Signal()
    remote_update_signal = Signal()
    update_config_signal = Signal(dict)
    apply_sanctions_signal = Signal(list)
    apply_wordlist_signal = Signal(dict)
    apply_guard_config_signal = Signal(dict)
    remote_wol_signal = Signal(str)

    def __init__(
        self,
        server_ip: str,
        server_port: int = 9000,
        pc_name: Optional[str] = None,
        root=None,          # tkinter root (untuk root.after dispatch)
        penalty_mgr=None,   # PenaltyManager instance
        detector=None,      # ToxicDetector instance untuk hot-reload wordlist
        app_version: str = "v1.0.0",
        auth_service: Optional[AuthService] = None,
        installer_guard=None,  # InstallerGuard instance for hot-reload
    ):
        super().__init__()
        self.server_ip = server_ip
        self.server_port = server_port
        self.pc_name = pc_name or self._get_pc_name()
        self._root = root
        self._penalty_mgr = penalty_mgr
        self._detector = detector
        self._auth_service = auth_service
        self._app_version = app_version
        self._installer_guard = installer_guard

        # Connect signals to slots
        self.remote_lock_signal.connect(self._execute_remote_lock)
        self.remote_warning_signal.connect(self._execute_remote_warning)
        self.remote_reset_level_signal.connect(self._execute_remote_reset_level)
        self.remote_update_signal.connect(self._execute_remote_update)
        self.update_config_signal.connect(self._execute_update_config)
        self.apply_sanctions_signal.connect(self._execute_apply_sanctions)
        self.apply_wordlist_signal.connect(self._execute_apply_wordlist)
        self.apply_guard_config_signal.connect(self._execute_apply_guard_config)
        self.remote_wol_signal.connect(self._execute_remote_wol)

        # ── State ──
        self._running = False
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._writer_lock = asyncio.Lock()
        
        from app._paths import APPDATA_DIR
        self._offline_logs_file = os.path.join(APPDATA_DIR, "offline_logs.json")

        # Queue untuk violation reports (thread-safe)
        self._violation_queue: asyncio.Queue = None

        logger.info(
            "NetworkClient initialized | PC='%s' | Server=%s:%d",
            self.pc_name, self.server_ip, self.server_port
        )

    # ── Public API ──────────────────────────────────────────

    def start(self):
        """Start the async event loop in a daemon thread."""
        if self._running:
            return
        self._running = True
        t = threading.Thread(
            target=self._run_event_loop,
            name="NetworkClient-Loop",
            daemon=True,
        )
        t.start()
        logger.info("NetworkClient started (background thread).")

    def stop(self):
        """Gracefully stop the client."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("NetworkClient stopped.")

    def report_violation(self, level: int, trigger_word: str):
        """
        Thread-safe: report a violation to the server.
        Can be called from any thread (including main/audio thread).
        """
        if not self._loop:
            return
            
        # Create packet once with original timestamp
        packet = {
            "type": "VIOLATION",
            "level": level,
            "trigger": trigger_word,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not self._connected:
            self._save_to_offline_log(packet)
            return
            
        asyncio.run_coroutine_threadsafe(
            self._enqueue_violation(packet), self._loop
        )

    def report_blocked_installer(self, filename: str, trigger: str):
        """
        Melaporkan kejadian terblokirnya installer/setup oleh InstallerGuard.
        """
        if not self._loop:
            return
            
        packet = {
            "type": "INSTALLER_BLOCKED",
            "filename": filename,
            "trigger": trigger,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not self._connected:
            self._save_to_offline_log(packet)
            return
            
        asyncio.run_coroutine_threadsafe(
            self._enqueue_violation(packet), self._loop
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Internal: Event Loop ─────────────────────────────────

    def _run_event_loop(self):
        """Run a new asyncio event loop in this thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._violation_queue = asyncio.Queue()
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error("NetworkClient loop error: %s", e)
        finally:
            logger.info("NetworkClient event loop ended.")

    async def _connect_loop(self):
        """
        Outer reconnect loop.
        Tries to connect, runs session, then waits before retrying.
        """
        while self._running:
            try:
                logger.info(
                    "Connecting to server %s:%d ...",
                    self.server_ip, self.server_port
                )
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.server_ip, self.server_port),
                    timeout=CONNECT_TIMEOUT,
                )
                self._writer = writer
                self._connected = True
                logger.info("✓ Connected to server!")

                # Run the session (heartbeat + listener + reporter)
                await self._run_session(reader, writer)

            except asyncio.TimeoutError:
                logger.warning(
                    "Connection timeout to %s:%d — retrying in %ds",
                    self.server_ip, self.server_port, RECONNECT_DELAY
                )
            except ConnectionRefusedError:
                logger.warning(
                    "Server %s:%d refused connection — retrying in %ds",
                    self.server_ip, self.server_port, RECONNECT_DELAY
                )
            except OSError as e:
                logger.warning("Network error: %s — retrying in %ds", e, RECONNECT_DELAY)
            except Exception as e:
                logger.error("Unexpected error: %s — retrying in %ds", e, RECONNECT_DELAY)
            finally:
                self._connected = False
                self._writer = None

            if self._running:
                await asyncio.sleep(RECONNECT_DELAY)

    def _get_mac_address(self) -> str:
        """
        Mendapatkan MAC Address secara hibrida:
        1. MAC dari LAN card/adapter yang punya rute aktif ke Server Center (via psutil)
        2. MAC bawaan fisik/hardware dari Motherboard (via uuid)
        Menggabungkan keduanya (dengan koma) jika berbeda, agar Server mengirim WOL ke semua kandidat.
        """
        import socket
        import uuid
        
        candidates = []
        
        # 1. Coba dapatkan MAC dari Adapter yang punya rute ke Server
        routed_mac = None
        try:
            import psutil
            # Temukan IP Lokal yang dipakai untuk nge-route ke Server
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self.server_ip, self.server_port))
                local_ip = s.getsockname()[0]

            for interface, addrs in psutil.net_if_addrs().items():
                temp_mac = None
                has_ip = False
                for addr in addrs:
                    if addr.family == psutil.AF_LINK:
                        temp_mac = addr.address
                    elif addr.family == socket.AF_INET and addr.address == local_ip:
                        has_ip = True
                
                if has_ip and temp_mac:
                    routed_mac = temp_mac.replace("-", ":").upper()
                    if len(routed_mac.replace(":", "")) == 12:
                        candidates.append(routed_mac)
        except Exception as e:
            logger.warning("Gagal memperoleh MAC lewat psutil: %s", e)

        # 2. Dapatkan MAC Sistem Hardcoded/Default bawaan OS
        try:
            sys_mac = uuid.getnode()
            formatted_sys_mac = ':'.join(('%012X' % sys_mac)[i:i+2] for i in range(0, 12, 2))
            
            if formatted_sys_mac:
                first_octet = formatted_sys_mac.split(':')[0]
                if int(first_octet, 16) & 1 != 0:
                    pass  # Skip multicast/fake MAC
                else:
                    if formatted_sys_mac not in candidates:
                        candidates.append(formatted_sys_mac)
        except Exception:
            pass
            
        if not candidates:
            return "00:00:00:00:00:00"
            
        return ",".join(candidates)

    async def _run_session(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Single connected session.
        Runs three concurrent tasks:
        1. REGISTER + Heartbeat sender
        2. Incoming command listener
        3. Violation queue sender
        """
        try:
            # Build a sanitized config snapshot for the server dashboard
            _cfg = self._auth_service._config
            sanitized_config = {
                "AdminPassword": _cfg.get("AdminPassword", ""),
                "ServerIP": _cfg.get("ServerIP", ""),
                "AutoStart": SystemService.is_autostart_enabled(),
                "BlockSettings": SystemService.is_windows_settings_locked(),
                "BlockInstaller": SystemService.is_installer_blocked(),
            }
            payload = {
                "type": "REGISTER",
                "name": self.pc_name,
                "version": self._app_version,
                "mac_address": self._get_mac_address(),
                "local_ip": self._get_local_ip(),
                "client_config": sanitized_config,
            }
            if self._detector:
                payload["client_wordlist"] = self._detector.words
                payload["client_phonetic_map"] = getattr(self._detector, "_phonetic_map", {})
            if self._penalty_mgr:
                payload["client_sanctions"] = self._penalty_mgr.sanction_list

            await self._send(writer, payload)
            logger.info("REGISTER sent as '%s' (v%s)", self.pc_name, self._app_version)

            # Run all tasks concurrently — cancel them all on any failure
            await asyncio.gather(
                self._heartbeat_loop(writer),
                self._listen_loop(reader),
                self._violation_sender_loop(writer),
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Session error: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("Session ended — disconnected from server.")

    # ── Heartbeat Loop ───────────────────────────────────────

    async def _heartbeat_loop(self, writer: asyncio.StreamWriter):
        """
        Send HEARTBEAT every HEARTBEAT_INTERVAL seconds.
        Raises on write failure to break the session.
        """
        while self._running and self._connected:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if not self._running or not self._connected:
                break
            try:
                _cfg = self._auth_service._config
                sanitized_config = {
                    "AdminPassword": _cfg.get("AdminPassword", ""),
                    "ServerIP": _cfg.get("ServerIP", ""),
                    "AutoStart": SystemService.is_autostart_enabled(),
                    "BlockSettings": SystemService.is_windows_settings_locked(),
                    "BlockInstaller": SystemService.is_installer_blocked(),
                }
                await self._send(writer, {
                    "type": "HEARTBEAT",
                    "version": self._app_version,
                    "local_ip": self._get_local_ip(),
                    "client_config": sanitized_config,
                })
                logger.debug("♥ Heartbeat sent (v%s)", self._app_version)
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)
                raise  # Break the session to trigger reconnect

    # ── Listen Loop ──────────────────────────────────────────

    async def _listen_loop(self, reader: asyncio.StreamReader):
        """
        Receive and process commands from server.
        Handles: REMOTE_LOCK, REMOTE_WARNING, SYNC_SANCTIONS, ACK.
        """
        while self._running and self._connected:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
            except asyncio.TimeoutError:
                logger.debug("Listen timeout — connection may be idle")
                continue

            if not line:
                logger.warning("Server closed connection.")
                break

            try:
                packet = json.loads(line.decode("utf-8").strip())
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("Invalid packet from server: %s", line[:80])
                continue

            ptype = packet.get("type", "")

            if ptype == "ACK":
                logger.debug("ACK: %s", packet.get("message", ""))

            elif ptype == "REMOTE_LOCK":
                duration = packet.get("duration", 60)
                message = packet.get("message", "")
                logger.warning("⚡ REMOTE_LOCK received (duration=%ds)", duration)
                self._dispatch_remote_lock(duration, message)

            elif ptype == "REMOTE_WARNING":
                message = packet.get("message", "⚠️ Peringatan dari Admin.")
                logger.warning("⚡ REMOTE_WARNING received")
                self._dispatch_remote_warning(message)

            elif ptype == "REMOTE_UPDATE":
                logger.info("⚡ REMOTE_UPDATE command received")
                self._dispatch_remote_update()
                
            elif ptype == "RESET_LEVEL":
                logger.info("⚡ RESET_LEVEL command received")
                self._dispatch_remote_reset_level()

            elif ptype in ("SYNC_SANCTIONS", "SYNC_SANCTIONS_TARGETED"):
                sanction_list = packet.get("sanction_list", [])
                logger.info("📡 %s received (%d items)", ptype, len(sanction_list))
                self._apply_sanctions_sync(sanction_list)
                
            elif ptype in ("SYNC_WORDLIST", "SYNC_WORDLIST_TARGETED"):
                wordlist_data = packet.get("wordlist_data", {})
                logger.info("📖 %s received", ptype)
                self._apply_wordlist_sync(wordlist_data)

            elif ptype in ("SYNC_GUARD_CONFIG", "SYNC_GUARD_CONFIG_TARGETED"):
                guard_config = packet.get("guard_config", {})
                logger.info("🛡️ %s received", ptype)
                self._apply_guard_config_sync(guard_config)

            elif ptype == "UPDATE_CONFIG":
                new_config = packet.get("config", {})
                logger.info("⚙️ UPDATE_CONFIG received: %r", new_config)
                self._dispatch_update_config(new_config)

            elif ptype == "REMOTE_WOL":
                target_mac = packet.get("mac_address", "")
                logger.info("⚡ REMOTE_WOL relay request for %s", target_mac)
                self.remote_wol_signal.emit(target_mac)

            else:
                logger.debug("Unknown server packet type: %s", ptype)

        self._connected = False

    # ── Violation Queue Sender ────────────────────────────────

    def _save_to_offline_log(self, packet: dict):
        """Save packet to offline JSON file synchronously."""
        import os, json
        queue = []
        if os.path.exists(self._offline_logs_file):
            try:
                with open(self._offline_logs_file, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except Exception: pass
            
        queue.append(packet)
        try:
            with open(self._offline_logs_file, "w", encoding="utf-8") as f:
                json.dump(queue, f, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed writing offline log: %s", e)

    async def _sync_offline_logs(self, writer: asyncio.StreamWriter):
        """Send all offline cache before starting normal violation queue."""
        import os, json
        if not os.path.exists(self._offline_logs_file):
            return
            
        try:
            with open(self._offline_logs_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except Exception:
            return
            
        if not queue:
            return
            
        # Send one by one
        sent_count = 0
        for packet in queue:
            try:
                await self._send(writer, packet)
                sent_count += 1
                await asyncio.sleep(0.05) # small delay to prevent overwhelming socket
            except Exception as e:
                logger.warning("Offline sync send error: %s", e)
                break
                
        # Rewrite remaining
        remaining = queue[sent_count:]
        if remaining:
            try:
                with open(self._offline_logs_file, "w", encoding="utf-8") as f:
                    json.dump(remaining, f, ensure_ascii=False)
            except: pass
        else:
            try: os.remove(self._offline_logs_file)
            except: pass
                
        if sent_count > 0:
            logger.info("Synced %d offline violations to server.", sent_count)

    async def _enqueue_violation(self, packet: dict):
        """Put a violation packet on the queue."""
        if self._violation_queue:
            await self._violation_queue.put(packet)

    async def _violation_sender_loop(self, writer: asyncio.StreamWriter):
        """
        Drain the violation queue and send each packet.
        Runs concurrently with heartbeat and listen loops.
        """
        # First sync whatever was stored offline while disconnected
        await self._sync_offline_logs(writer)
        
        while self._running and self._connected:
            try:
                # Wait up to 1 second for a packet
                packet = await asyncio.wait_for(
                    self._violation_queue.get(), timeout=1.0
                )
                try:
                    await self._send(writer, packet)
                    logger.info(
                        "→ Violation reported: Level %d | '%s'",
                        packet.get("level", 0), packet.get("trigger", "")
                    )
                except Exception as e:
                    logger.warning("Violation send error: %s", e)
                    # Jika gagal kirim, simpan di offline log beserta isi queue
                    self._save_to_offline_log(packet)
                    while not self._violation_queue.empty():
                        p = self._violation_queue.get_nowait()
                        self._save_to_offline_log(p)
                    raise  # Break session
            except asyncio.TimeoutError:
                pass  # No violation — keep looping

    # ── Remote Command Dispatcher ─────────────────────────────

    def _dispatch_remote_lock(self, duration: int, message: str = ""):
        """Emit REMOTE_LOCK signal."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring REMOTE_LOCK")
            return
        self.remote_lock_signal.emit(duration, message)

    def _execute_remote_lock(self, duration: int, message: str = ""):
        try:
            lock_msg = message if message else f"🔒 Sanksi dikirim oleh Admin GC Net.\nDurasi: {duration} detik."
            # Force execute a lockdown-style sanction
            # We bypass anti-overlap by directly dispatching
            self._penalty_mgr._is_penalty_active = False
            self._penalty_mgr._dispatch_lockdown(
                level=0,
                message=lock_msg,
                duration=duration,
                matched_words=["[REMOTE]"]
            )
            self._penalty_mgr._is_penalty_active = True
        except Exception as e:
            logger.error("REMOTE_LOCK dispatch error: %s", e)

    def _dispatch_remote_warning(self, message: str):
        """Emit REMOTE_WARNING signal."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring REMOTE_WARNING")
            return
        self.remote_warning_signal.emit(message)

    def _execute_remote_warning(self, message: str):
        try:
            # Bypass current violation level logic and show pure warning
            self._penalty_mgr._is_penalty_active = False
            self._penalty_mgr._dispatch_warning(
                level=0,
                message=f"Pesan dari Admin:\n\n{message}",
                warning_delay=10,
                matched_words=["[REMOTE]"]
            )
            self._penalty_mgr._is_penalty_active = True
        except Exception as e:
            logger.error("REMOTE_WARNING dispatch error: %s", e)

    def _dispatch_remote_reset_level(self):
        """Emit RESET_LEVEL signal."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring RESET_LEVEL")
            return
        self.remote_reset_level_signal.emit()
            
    def _execute_remote_reset_level(self):
        try:
            self._penalty_mgr.reset_level()
        except Exception as e:
            logger.error("RESET_LEVEL dispatch error: %s", e)

    def _dispatch_remote_update(self):
        """Emit REMOTE_UPDATE signal."""
        if not self._penalty_mgr or not self._penalty_mgr._auth:
            logger.warning("Missing penalty_mgr or auth_service, cannot remote update")
            return

        if self._root:
            self.remote_update_signal.emit()
        else:
            threading.Thread(target=self._execute_remote_update, daemon=True).start()

    def _execute_remote_update(self):
        from app.updater import GithubUpdater
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import Qt

        config = self._penalty_mgr._auth._config
        repo = config.get("GithubRepo", "galangjrr/GC-Toxic-Shield")

        # Check update
        updater = GithubUpdater(repo, self._app_version)
        has_update, lat_ver, dl_url, notes = updater.check_for_updates()

        if has_update and dl_url:
            logger.info("V%s found. Downloading from %s (SILENT)", lat_ver, dl_url)
            updater.download_and_install_async(dl_url)
        else:
            logger.info("No newer version found on Github or update failed.")

    def _dispatch_update_config(self, new_config: dict):
        """Emit update config signal."""
        if not self._penalty_mgr or not self._penalty_mgr._auth:
            logger.warning("Missing penalty_mgr or auth_service, cannot remote update config")
            return

        if self._root:
            self.update_config_signal.emit(new_config)
        else:
            threading.Thread(target=self._execute_update_config, args=(new_config,), daemon=True).start()

    def _execute_update_config(self, new_config: dict):
        try:
            auth = self._penalty_mgr._auth
            
            # Apply Password (if changed and not empty)
            new_pw = new_config.get("AdminPassword")
            if new_pw and new_pw != auth.get_config("AdminPassword"):
                if hasattr(auth, 'change_password'):
                    auth.change_password(new_pw)
                    logger.info("✓ Admin password updated via change_password()")
                else:
                    auth._config["AdminPassword"] = new_pw

            # Apply Server IP
            new_ip = new_config.get("ServerIP")
            if new_ip:
                auth._config["ServerIP"] = new_ip
                
            auth._save_config()
            
            # Check Auto-Start Logic (Requires Admin, but SystemService skips if not admin)
            if "AutoStart" in new_config:
                if new_config["AutoStart"]:
                    SystemService.enable_autostart()
                else:
                    SystemService.disable_autostart()
                    
            # Check OS Block Logic (Settings toggle)
            if "BlockSettings" in new_config:
                auth._config["BlockSettings"] = new_config["BlockSettings"]
                if new_config["BlockSettings"]:
                    SystemService.toggle_windows_settings(True)
                else:
                    SystemService.toggle_windows_settings(False)

            # Check Installer Block Logic
            if "BlockInstaller" in new_config:
                auth._config["BlockInstaller"] = new_config["BlockInstaller"]
                if new_config["BlockInstaller"]:
                    SystemService.toggle_installer_block(True)
                else:
                    SystemService.toggle_installer_block(False)

            auth._save_config()
            
            # Hot-reload InstallerGuard state
            if hasattr(self, '_installer_guard') and self._installer_guard:
                self._installer_guard.reload(
                    block_installer=new_config.get('BlockInstaller', None),
                    block_settings=new_config.get('BlockSettings', None)
                )
            
            logger.info("✓ Configuration synced and applied from Server.")

            # If IP Changed, notify and exit to force reconnect
            if new_ip and new_ip != self.server_ip:
                logger.warning("Server IP changed. Closing connection to force reconnect.")
                self._running = False
                if self._writer:
                    self._writer.close()
        except Exception as e:
            logger.error("Failed to apply UPDATE_CONFIG: %s", e)

    def _apply_sanctions_sync(self, sanction_list: list):
        """Emit sync sanctions signal."""
        if not self._penalty_mgr:
            return
        if self._root:
            self.apply_sanctions_signal.emit(sanction_list)
        else:
            self._execute_apply_sanctions(sanction_list)

    def _execute_apply_sanctions(self, sanction_list: list):
        try:
            pm = self._penalty_mgr
            if pm._auth:
                # Save to config via auth_service
                config = pm._auth._config
                config["sanction_list"] = sanction_list
                pm._auth._save_config()
                # Reload into penalty_mgr
                pm.reload_config()
                logger.info(
                    "✓ sanction_list synced: %d items", len(sanction_list)
                )
        except Exception as e:
            logger.error("Sanctions sync error: %s", e)

    def _apply_wordlist_sync(self, wordlist_data: dict):
        """Emit wordlist sync signal."""
        if not self._detector:
            logger.warning("No detector instance — cannot apply remote wordlist")
            return
        if self._root:
            self.apply_wordlist_signal.emit(wordlist_data)
        else:
            self._execute_apply_wordlist(wordlist_data)

    def _execute_apply_wordlist(self, wordlist_data: dict):
        from app._paths import WORDLIST_PATH
        import json
            
        try:
            with open(WORDLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(wordlist_data, f, ensure_ascii=False, indent=2)
            
            # Hot reload detector on main thread
            self._detector.reload_wordlist()
                
            logger.info("✓ wordlist_data synced and applied successfully.")
        except Exception as e:
            logger.error("Wordlist sync error: %s", e)

    def _apply_guard_config_sync(self, guard_config: dict):
        """Emit guard sync signal."""
        if self._root:
            self.apply_guard_config_signal.emit(guard_config)
        else:
            self._execute_apply_guard_config(guard_config)

    def _execute_apply_guard_config(self, guard_config: dict):
        from app._paths import GUARD_CONFIG_PATH
        import json
        
        try:
            with open(GUARD_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(guard_config, f, ensure_ascii=False, indent=2)
            
            # Hot reload guard config if instance available
            if hasattr(self, "_installer_guard") and self._installer_guard:
                self._installer_guard.load_config()
                
            logger.info("✓ guard_config synced and applied successfully.")
        except Exception as e:
            logger.error("Guard config sync error: %s", e)

    def _get_local_ip(self) -> str:
        """Dapatkan local IP yang digunakan untuk komunikasi ke server."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self.server_ip, self.server_port))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _execute_remote_wol(self, mac_address: str):
        """Kirim Magic Packet WOL ke subnet lokal."""
        if not mac_address:
            return
            
        try:
            import psutil
            import socket
            mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            broadcast_ips = set()
            broadcast_ips.add("255.255.255.255")  # fallback
            
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.broadcast:
                        broadcast_ips.add(addr.broadcast)
            
            for bcast_ip in broadcast_ips:
                for port in [7, 9]:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                            s.sendto(magic_packet, (bcast_ip, port))
                    except Exception:
                        pass
            
            logger.info("✓ WOL Magic Packet sent to %s via %d broadcast IPs", mac_address, len(broadcast_ips))
        except Exception as e:
            logger.error("Failed to relay WOL packet: %s", e)


    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _get_pc_name() -> str:
        """Get the PC hostname as a friendly name."""
        try:
            return socket.gethostname()
        except Exception:
            return "Unknown-PC"

    async def _send(self, writer: asyncio.StreamWriter, data: dict):
        """Send a JSON packet to the server."""
        payload = json.dumps(data, ensure_ascii=False) + "\n"
        writer.write(payload.encode("utf-8"))
        await writer.drain()
