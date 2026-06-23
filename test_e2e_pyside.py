import sys
import os
import time

# Ensure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.auth_service import AuthService
from app.logger_service import LoggerService
from app.detector import ToxicDetector
from app.penalty_manager import PenaltyManager
from app.overlay import LockdownOverlay
from app.ui_manager import AdminDashboard
from app.audio_engine import AudioEngine

def run_tests():
    print("[TEST] Inisialisasi QApplication...")
    app = QApplication.instance() or QApplication(sys.argv)
    
    print("[TEST] Setup Backend Services...")
    auth_service = AuthService()
    logger_svc = LoggerService()
    detector = ToxicDetector()
    
    class MockAudioEngine:
        def __init__(self):
            self.on_transcription = None
            self.is_running = True
            self.gain = 1.0 # Property used by ui_manager sync
            self.input_device_index = None
            self.language = "id-ID"
            
        def start(self): pass
        def stop(self): pass
        def set_gain(self, v): self.gain = v
        def get_vu_level(self): return 50
        def list_devices(self): return [(0, "Mock Default Device")]
        def reset_calibration_peaks(self): pass
    
    engine = MockAudioEngine()
    
    # Setup Overlay & Penalty
    print("[TEST] Inisialisasi Overlay & PenaltyManager...")
    overlay = LockdownOverlay(auth_service=auth_service)
    penalty_mgr = PenaltyManager(
        overlay=overlay,
        auth_service=auth_service,
        on_violation=None
    )
    
    print("[TEST] Inisialisasi AdminDashboard...")
    dashboard = AdminDashboard(
        auth_service=auth_service,
        logger_service=logger_svc,
        detector=detector,
        penalty_mgr=penalty_mgr,
        on_close=lambda: print("[TEST] App closed")
    )
    
    # Simulate root injection for overlay
    overlay._parent = dashboard
    
    dashboard.set_audio_engine(engine)
    dashboard.show()
    
    def simulate_events():
        try:
            print("[TEST] Menguji Navigasi Tab...")
            for i in range(6):
                dashboard._switch_tab(i)
                QApplication.processEvents()
                time.sleep(0.1)
                
            print("[TEST] Menguji Emisi Pelanggaran (WarningBox)...")
            penalty_mgr.execute_sanction(["anjing", "babi"])
            QApplication.processEvents()
            
            print("[TEST] Menguji Sistem Kalibrasi...")
            dashboard._switch_tab(4) # Calibration
            QApplication.processEvents()
            
            print("[TEST] Semua pengujian UI dasar selesai tanpa crash.")
            app.quit()
        except Exception as e:
            print(f"[ERROR] Uji E2E gagal: {e}")
            import traceback
            traceback.print_exc()
            app.exit(1)

    QTimer.singleShot(1000, simulate_events)
    exit_code = app.exec()
    print(f"[TEST] Selesai dengan kode {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    run_tests()
