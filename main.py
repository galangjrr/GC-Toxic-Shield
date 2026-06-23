# =============================================================
# GC Toxic Shield — Main Entry Point
# =============================================================
# Runner utama yang menghubungkan semua modul:
# - T1: AudioEngine  (faster-whisper + VAD, OFFLINE ONLY)
# - T4: ToxicDetector (Whole-Word Regex Match)
# - T3: LoggerService (Self-Cleaning Monitor)
# - T5: AdminDashboard + LockdownOverlay (12 levels)
# - T14: System Tray Integration (pystray)
#
# PyInstaller compatible: uses app._paths for path resolution.
# =============================================================

import sys
import os
import ctypes
import logging
import threading
import time

# ── CRITICAL: Set working directory untuk PyInstaller ────────
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# ── Logging Configuration ────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Ensure stdout can support UTF-8 (emojis) on Windows
if sys.platform == "win32":
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("GCToxicShield")

# ── Constants ────────────────────────────────────────────────
APP_NAME = "GC Toxic Shield"
APP_VERSION = "2.0.0"
BRAND = "GC Net Security Suite"
GITHUB_REPO = "galangjrr/GC-Toxic-Shield"  # <-- Admin warns to replace this


def show_messagebox(title: str, message: str, icon_type: int = 0x10):
    """
    Menampilkan MessageBox Windows.
    icon_type: 0x10 (Error), 0x30 (Warning), 0x40 (Info)
    """
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, icon_type)
    except Exception as e:
        print(f"\n  [{title}] {message}\n")
        logger.error("Failed to show MessageBox: %s", e)


def check_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return True
    except Exception as e:
        logger.error("Admin check failed: %s", e)
        return False


def validate_assets_directory() -> bool:
    import shutil
    from app._paths import WORDLIST_PATH, ASSETS_DIR, CONFIG_PATH, APP_ROOT
    
    # Kemungkinan folder assets di samping executable pada v1.0.6
    legacy_assets_folder = os.path.join(APP_ROOT, "assets")

    # ── Migration: config.json ──
    if not os.path.isfile(CONFIG_PATH):
        legacy_config_candidates = [
            os.path.join(APP_ROOT, "config.json"),
            os.path.join(legacy_assets_folder, "config.json")
        ]
        for cand in legacy_config_candidates:
            if os.path.isfile(cand):
                try:
                    shutil.copy2(cand, CONFIG_PATH)
                    logger.info("✓ Legacy config.json migrated to APPDATA from %s", cand)
                    break
                except Exception as e:
                    logger.error("Failed to migrate config.json from %s: %s", cand, e)

    # ── Fallback/Migration: word_list.json ──
    if not os.path.isfile(WORDLIST_PATH):
        legacy_wordlist_candidates = [
            os.path.join(APP_ROOT, "word_list.json"),
            os.path.join(legacy_assets_folder, "word_list.json"),
            os.path.join(ASSETS_DIR, "word_list.json") # Default internal bundled
        ]
        for cand in legacy_wordlist_candidates:
            if os.path.isfile(cand):
                try:
                    shutil.copy2(cand, WORDLIST_PATH)
                    logger.info("✓ word_list.json setup in APPDATA from %s", cand)
                    return True
                except Exception as e:
                    logger.error("Failed to copy word_list.json from %s: %s", cand, e)

        msg = f"File 'word_list.json' tidak ditemukan!\n{WORDLIST_PATH}"
        logger.error("✗ Wordlist not found: %s", WORDLIST_PATH)
        show_messagebox("GC Toxic Shield — Error", msg, 0x10)
        return False
        
    return True


def enforce_singleton():
    """
    Memastikan hanya satu instance aplikasi yang berjalan.
    """
    mutex_name = "Global\\GC_Toxic_Shield_Mutex_v2"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        logger.warning("Another instance is already running.")
        show_messagebox(
            "GC Toxic Shield",
            "Aplikasi GC Toxic Shield sudah berjalan di System Tray.\n"
            "Cek ikon perisai merah di pojok kanan bawah.",
            0x30 # Warning Icon
        )
        sys.exit(0)
    return mutex

_app_mutex = None


def create_tray_image():
    """
    Membuat icon untuk System Tray.
    Mencoba load dari assets/icon.png terlebih dahulu.
    Fallback ke gambar perisai jika file tidak ditemukan.
    """
    try:
        from PIL import Image, ImageDraw
        from app._paths import ICON_PNG_PATH
        
        if os.path.exists(ICON_PNG_PATH):
            return Image.open(ICON_PNG_PATH)
        
        # Buat icon sederhana (Perisai Merah 64x64) fallback
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Draw Shield shape
        dc.polygon(
            [(32, 60), (4, 20), (4, 4), (60, 4), (60, 20)],
            fill="#D32F2F", outline="white"
        )
        # Draw "GC" text placeholder (white rect)
        dc.rectangle([20, 15, 44, 40], fill="white")
        
        return image

    except Exception as e:
        logger.error("Failed to generate tray icon: %s", e)
        # Fallback: Solid Red Box
        try:
            from PIL import Image
            return Image.new('RGB', (64, 64), color='red')
        except ImportError:
            # Should be caught by main import check, but just in case
            raise RuntimeError("PIL not installed")


def main():
    global _app_mutex

    # ── Global Exception Handler for Startup ──
    try:
        logger.info("━" * 50)
        logger.info("  %s V%s", APP_NAME, APP_VERSION)
        logger.info("  %s", BRAND)
        logger.info("━" * 50)
        
        # Step 0: Dependency Check (Tray libs)
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as e:
            msg = (
                f"Library System Tray tidak ditemukan:\n{e}\n\n"
                f"Mohon install dependencies:\n"
                f"pip install -r requirements.txt"
            )
            show_messagebox("GC Toxic Shield — Dependency Error", msg, 0x10)
            sys.exit(1)

        _app_mutex = enforce_singleton()

        if getattr(sys, 'frozen', False):
            logger.info("Running as PyInstaller bundle")
        else:
            logger.info("Running in development mode")

        if not check_admin():
            logger.warning("⚠ Tidak berjalan sebagai Administrator!")

        if not validate_assets_directory():
            sys.exit(1)

        # ── Import App Modules ──
        try:
            from app.audio_engine import AudioEngine
            from app.detector import ToxicDetector
            from app.logger_service import LoggerService
            from app.overlay import LockdownOverlay
            from app.penalty_manager import PenaltyManager
            from app.ui_manager import AdminDashboard
            from app.system_service import SystemService
            from app.auth_service import AuthService
            from app.login_dialog import LoginDialog
            from app.network_client import NetworkClient
            from app.installer_guard import InstallerGuard
        except ImportError as e:
            show_messagebox("GC Toxic Shield — Import Error", str(e), 0x10)
            sys.exit(1)

        # --- Init Services ---
        logger.info("Initializing Services...")
        detector = ToxicDetector()
        logger_svc = LoggerService()
        auth_service = AuthService()

        # --- Init PySide6 Application ---
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        # Biarkan import tidak crash jika dipanggil dua kali (PyInstaller)
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

        # --- Init Dashboard ---
        dashboard = AdminDashboard(
            logger_service=logger_svc,
            detector=detector,
            auth_service=auth_service,
            app_version=APP_VERSION,
            github_repo=GITHUB_REPO,
        )
        # root in PySide6 context is the QMainWindow instance
        root = dashboard
        
        # --- Init Overlay & Penalty Manager ---
        overlay = LockdownOverlay(root, auth_service=auth_service)

        def on_violation(level, count, matched_words):
            logger.warning("⚠ VIOLATION #%d → Level %d", count, level)

        penalty_mgr = PenaltyManager(
            overlay=overlay,
            auth_service=auth_service,
            on_violation=on_violation,
        )
        dashboard._penalty_mgr = penalty_mgr
        penalty_mgr.on_sync_callback = dashboard._on_penalty_sync

        # ── Init Network Client (Background Comm) ──
        server_ip = auth_service.get_config("ServerIP", "")
        server_port = auth_service.get_config("ServerPort", 9000)
        network_client = None

        if server_ip:
            try:
                network_client = NetworkClient(
                    server_ip=server_ip,
                    server_port=int(server_port),
                    root=root,
                    penalty_mgr=penalty_mgr,
                    detector=detector,
                    app_version=f"v{APP_VERSION}"
                )
                penalty_mgr.network_client = network_client
                logger.info("NetworkClient configured → %s:%d", server_ip, server_port)
            except Exception as e:
                logger.error("NetworkClient init failed: %s", e)
        else:
            logger.info("NetworkClient DISABLED (ServerIP not configured)")

        # --- Init Audio Engine ---
        def on_transcription(text: str):
            # State Machine: if penalty active, ignore all input
            if penalty_mgr.is_penalty_active:
                logger.debug("Ignored input while penalty active: %s", text)
                return

            result = detector.detect(text)
            logger_svc.log(text, result.is_toxic, result.matched_words)
            if result.is_toxic:
                penalty_mgr.execute_sanction(result.matched_words)

        # ── Load Saved Audio Configurations ──
        saved_device_idx = auth_service.get_config("InputDeviceIndex", None)
        saved_gain = auth_service.get_config("AudioGain", 1.0)
        
        engine = AudioEngine(
            language="id-ID", 
            on_transcription=on_transcription,
            input_device_index=saved_device_idx,
            initial_gain=saved_gain
        )
        engine.normalizer_callback = detector.normalize_stt_text
        dashboard._engine = engine
        dashboard.set_audio_engine(engine)

        # ── Start Services ──
        if SystemService.is_autostart_enabled():
            logger.info("✓ Auto-start ENABLED")
        
        logger_svc.start()

        # ── Enforce toggle states from config on each startup ──
        block_settings_cfg = auth_service.get_config("BlockSettings", False)
        SystemService.toggle_windows_settings(bool(block_settings_cfg))
        logger.info("BlockSettings enforced on startup: %s", block_settings_cfg)

        block_installer_cfg = auth_service.get_config("BlockInstaller", False)
        SystemService.toggle_installer_block(bool(block_installer_cfg))
        logger.info("BlockInstaller enforced on startup: %s", block_installer_cfg)

        engine.start()

        # ── Start Network Client ──
        if network_client:
            network_client.start()
            dashboard._network_client = network_client
            logger.info("✓ NetworkClient started → %s:%d", server_ip, server_port)

        # ── Start Installer Guard (Real-time setup execution block) ──
        installer_guard = InstallerGuard(root=root, network_client=network_client)
        installer_guard.set_block_installer(bool(block_installer_cfg))
        installer_guard.set_block_settings(bool(block_settings_cfg))
        if block_installer_cfg or block_settings_cfg:
            installer_guard.enable()
        dashboard._installer_guard = installer_guard
        if network_client:
            network_client._installer_guard = installer_guard

        # ── Login Helper ──

        def show_login_dialog_async(on_success, exit_mode=False, on_cancel=None):
            """Show login dialog on the main thread."""
            def _show():
                # Di PySide6, parent adalah root (AdminDashboard QMainWindow)
                LoginDialog(
                    auth_service=auth_service,
                    on_success=on_success,
                    on_cancel=on_cancel,
                    exit_mode=exit_mode,
                    parent=root
                ).exec()
            # QTimer.singleShot digunakan untuk melepas eksekusi ke main thread (mirip root.after)
            QTimer.singleShot(0, _show)

        # ── System Tray Setup ──
        
        from PySide6.QtCore import QObject, Signal

        class TrayCommunicator(QObject):
            sig_open_dashboard = Signal()
            sig_restart_engine = Signal()
            sig_exit_app = Signal()

        tray_comm = TrayCommunicator()

        def _handle_open_dashboard():
            """Executes on MAIN thread"""
            auth_service.logout()
            def _on_login_success():
                root.show()
                root.raise_()
                root.activateWindow()
                logger.info("Dashboard opened after login")
            show_login_dialog_async(on_success=_on_login_success)

        def _handle_restart_engine():
            """Executes on MAIN thread"""
            engine.stop()
            QTimer.singleShot(1000, lambda: engine.start())
            logger.info("⟳ Engine restarted via Tray")

        def _handle_exit_app():
            """Executes on MAIN thread"""
            auth_service.logout()
            def _on_exit_success():
                logger.info("Exit authenticated — shutting down")
                tray_icon.stop()
                app.quit()
            def _on_exit_cancel():
                logger.info("Exit cancelled by user")
            show_login_dialog_async(
                on_success=_on_exit_success,
                exit_mode=True,
                on_cancel=_on_exit_cancel,
            )

        tray_comm.sig_open_dashboard.connect(_handle_open_dashboard)
        tray_comm.sig_restart_engine.connect(_handle_restart_engine)
        tray_comm.sig_exit_app.connect(_handle_exit_app)

        def on_open_dashboard_tray(icon, item):
            """Tray → Show Dashboard (Emits signal to main thread)"""
            tray_comm.sig_open_dashboard.emit()

        def on_restart_engine_tray(icon, item):
            """Tray → Restart (Emits signal to main thread)"""
            tray_comm.sig_restart_engine.emit()

        def on_exit_app_tray(icon, item):
            """Tray → Exit (Emits signal to main thread)"""
            tray_comm.sig_exit_app.emit()

        tray_menu = pystray.Menu(
            pystray.MenuItem("Settings...", on_open_dashboard_tray, default=True),
            pystray.MenuItem("Restart Engine", on_restart_engine_tray),
            pystray.MenuItem("Exit", on_exit_app_tray),
        )

        try:
            icon_image = create_tray_image()
            tray_icon = pystray.Icon(
                "GCToxicShield",
                icon_image,
                "GC Toxic Shield",
                menu=tray_menu
            )
        except Exception as e:
            logger.error("Tray init failed: %s", e)
            show_messagebox("GC Toxic Shield — Tray Error", f"Gagal memuat Tray Icon: {e}", 0x10)
            sys.exit(1)

        # ── Window Management ──

        def withdraw_window(event=None):
            auth_service.logout()
            root.hide() # PySide6 hide() bukannya withdraw()
            logger.info("Dashboard hidden — session cleared")
            if event:
                event.ignore()

        # Implementasi closeEvent override kalau AdminDashboard adalah turunan class
        # Karena kita patch `closeEvent` object langsung, ini bisa dilakukan di PySide6
        root.closeEvent = withdraw_window

        # ── Silent Startup: Always start in Tray (no login dialog) ──
        # Auth is triggered only when user clicks "Show Dashboard" or "Exit"
        start_hidden = "--background" in sys.argv
        if start_hidden:
            logger.info("Starting in BACKGROUND mode (Tray only)")
            root.hide()
        else:
            logger.info("Starting in FOREGROUND mode (Silent — Tray only)")
            root.hide()

        # Run Tray in Thread
        threading.Thread(target=tray_icon.run, daemon=True).start()

        # Status Banner
        logger.info("━" * 50)
        logger.info("  🎙  Audio Engine   : ACTIVE (online, Google Speech)")
        logger.info("  🛡  System Tray    : ACTIVE")
        logger.info("  🖥️  Dashboard      : %s", "HIDDEN" if start_hidden else "VISIBLE")
        logger.info("━" * 50)

        # ── Main Loop ──
        sys.exit(app.exec())

        # Cleanup
        installer_guard.disable()
        engine.stop()
        logger_svc.stop()
        tray_icon.stop()
        if network_client:
            network_client.stop()

    except Exception as e:
        # Catch-all for any startup crash
        logger.critical("✗ Fatal error: %s", e, exc_info=True)
        show_messagebox("GC Toxic Shield — Fatal Error", f"Terjadi error fatal:\n{e}", 0x10)
        sys.exit(1)


if __name__ == "__main__":
    main()
