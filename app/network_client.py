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

from app.logger_service import LoggerService
from app.penalty_manager import PenaltyManager
from app.system_service import SystemService
from app.detector import ToxicDetector
from app.auth_service import AuthService


logger = logging.getLogger("GCToxicShield.NetworkClient")

# ── Constants ──────────────────────────────────────────────────
HEARTBEAT_INTERVAL = 10      # Detik antar heartbeat
RECONNECT_DELAY    = 15      # Detik sebelum mencoba reconnect
CONNECT_TIMEOUT    = 5       # Detik timeout saat connect
READ_TIMEOUT       = 60      # Detik timeout saat menunggu data server


class NetworkClient:
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
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.pc_name = pc_name or self._get_pc_name()
        self._root = root
        self._penalty_mgr = penalty_mgr
        self._detector = detector
        self._auth_service = auth_service or AuthService()
        self._app_version = app_version

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
        """Mendapatkan MAC Address fisik dari PC."""
        import uuid
        mac = uuid.getnode()
        formatted_mac = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        return formatted_mac

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
            payload = {
                "type": "REGISTER",
                "name": self.pc_name,
                "version": self._app_version,
                "mac_address": self._get_mac_address(),
                "client_config": self._auth_service._config,
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
                await self._send(writer, {
                    "type": "HEARTBEAT",
                    "version": self._app_version,
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
                logger.warning("⚡ REMOTE_LOCK received (duration=%ds)", duration)
                self._dispatch_remote_lock(duration)

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

            elif ptype == "UPDATE_CONFIG":
                new_config = packet.get("config", {})
                logger.info("⚙️ UPDATE_CONFIG received: %r", new_config)
                self._dispatch_update_config(new_config)

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

    def _dispatch_remote_lock(self, duration: int):
        """Dispatch REMOTE_LOCK to penalty_mgr via main thread."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring REMOTE_LOCK")
            return

        def _execute():
            try:
                # Force execute a lockdown-style sanction
                # We bypass anti-overlap by directly dispatching
                self._penalty_mgr._is_penalty_active = False
                self._penalty_mgr._dispatch_lockdown(
                    level=0,
                    message=f"🔒 Sanksi dikirim oleh Admin GC Net.\nDurasi: {duration} detik.",
                    duration=duration,
                    matched_words=["[REMOTE]"]
                )
                self._penalty_mgr._is_penalty_active = True
            except Exception as e:
                logger.error("REMOTE_LOCK dispatch error: %s", e)

        self._root.after(0, _execute)

    def _dispatch_remote_warning(self, message: str):
        """Dispatch REMOTE_WARNING to penalty_mgr via main thread."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring REMOTE_WARNING")
            return

        def _execute():
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

        self._root.after(0, _execute)

    def _dispatch_remote_reset_level(self):
        """Dispatch RESET_LEVEL to penalty_mgr via main thread."""
        if not self._penalty_mgr or not self._root:
            logger.warning("No penalty_mgr — ignoring RESET_LEVEL")
            return
            
        def _execute():
            try:
                self._penalty_mgr.reset_level()
            except Exception as e:
                logger.error("RESET_LEVEL dispatch error: %s", e)
                
        self._root.after(0, _execute)

    def _dispatch_remote_update(self):
        """Dispatch REMOTE_UPDATE command to check github and download update."""
        if not self._penalty_mgr or not self._penalty_mgr._auth:
            logger.warning("Missing penalty_mgr or auth_service, cannot remote update")
            return

        def _execute():
            from app.updater import GithubUpdater
            import tkinter.messagebox as messagebox

            config = self._penalty_mgr._auth._config
            repo = config.get("GithubRepo", "galangjrr/GC-Toxic-Shield")

            # Check update
            updater = GithubUpdater(repo, self._app_version)
            has_update, lat_ver, dl_url, notes = updater.check_for_updates()

            if has_update and dl_url:
                logger.info("V%s found. Downloading from %s", lat_ver, dl_url)
                # Show an overlay/message so user knows why app is downloading
                if self._root:
                    self._root.attributes("-topmost", True)
                    messagebox.showinfo(
                        "Pembaruan Otomatis",
                        f"Admin mengirimkan perintah update ke veri {lat_ver}.\n"
                        "Aplikasi sedang mengunduh pembaruan di latar belakang dan akan restart otomatis.",
                        parent=self._root
                    )
                updater.download_and_install_async(dl_url)
            else:
                logger.info("No newer version found on Github or update failed.")

        if self._root:
            self._root.after(0, _execute)
        else:
            # Fallback if no root (headless)
            threading.Thread(target=_execute, daemon=True).start()

    def _dispatch_update_config(self, new_config: dict):
        """Apply remote configuration changes passed by the server."""
        if not self._penalty_mgr or not self._penalty_mgr._auth:
            logger.warning("Missing penalty_mgr or auth_service, cannot remote update config")
            return

        def _execute():
            try:
                auth = self._penalty_mgr._auth
                
                # Apply Password (if changed and not empty)
                new_pw = new_config.get("AdminPassword")
                if new_pw and new_pw != auth.get_config("AdminPassword"):
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
                
                logger.info("✓ Configuration synced and applied from Server.")

                # If IP Changed, notify and exit to force reconnect
                if new_ip and new_ip != self.server_ip:
                    logger.warning("Server IP changed. Closing connection to force reconnect.")
                    self._running = False
                    if self._writer:
                        self._writer.close()
            except Exception as e:
                logger.error("Failed to apply UPDATE_CONFIG: %s", e)

        if self._root:
            self._root.after(0, _execute)
        else:
            threading.Thread(target=_execute, daemon=True).start()

    def _apply_sanctions_sync(self, sanction_list: list):
        """Update local config with server-provided sanction_list."""
        if not self._penalty_mgr:
            return
        try:
            pm = self._penalty_mgr
            if pm._auth:
                # Save to config via auth_service
                config = pm._auth._config
                config["sanction_list"] = sanction_list
                pm._auth._save_config()
                # Reload into penalty_mgr
                if self._root:
                    self._root.after(0, pm.reload_config)
                logger.info(
                    "✓ sanction_list synced: %d items", len(sanction_list)
                )
        except Exception as e:
            logger.error("Sanctions sync error: %s", e)

    def _apply_wordlist_sync(self, wordlist_data: dict):
        """Update local wordlist.json with server-provided wordlist_data."""
        from app._paths import WORDLIST_PATH
        import json
        
        if not self._detector:
            logger.warning("No detector instance — cannot apply remote wordlist")
            return
            
        try:
            with open(WORDLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(wordlist_data, f, ensure_ascii=False, indent=2)
            
            # Hot reload detector on main thread
            if self._root:
                self._root.after(0, self._detector.reload_wordlist)
            else:
                self._detector.reload_wordlist()
                
            logger.info("✓ wordlist_data synced and applied successfully.")
        except Exception as e:
            logger.error("Wordlist sync error: %s", e)

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
