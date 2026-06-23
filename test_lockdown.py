import sys
import logging
from PySide6.QtWidgets import QApplication

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Import the overlay classes
from app.overlay import LockdownOverlay

def main():
    app = QApplication(sys.argv)
    
    # Mock auth service
    class MockAuth:
        def get_config(self, key, default):
            return default
            
    # Initialize overlay
    print("Initializing LockdownOverlay...")
    overlay = LockdownOverlay(auth_service=MockAuth())
    
    # Try to show it
    print("Calling overlay.show()...")
    try:
        overlay.show(level=3, matched_words=["test_word"], duration=5)
        print("Overlay shown successfully.")
    except Exception as e:
        print(f"EXCEPTION CAUGHT: {e}")
        import traceback
        traceback.print_exc()
        
    # Start event loop to actually render it
    # We use a timer to exit after 6 seconds to not block
    from PySide6.QtCore import QTimer
    QTimer.singleShot(6000, app.quit)
    
    print("Starting app exec...")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
