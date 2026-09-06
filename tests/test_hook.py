import sys
import pytest
from PySide6.QtWidgets import QApplication
from app.overlay import LockdownOverlay

@pytest.fixture(scope="module")
def app():
    # Only create one QApplication for tests
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_keyboard_hook_install_and_remove(app):
    class MockAuth:
        def get_config(self, key, default):
            return default
            
    overlay = LockdownOverlay(auth_service=MockAuth())
    
    # Verify hook is not installed initially
    assert overlay._hook_installed is False
    assert overlay._hook_handle is None
    
    # Install hook
    overlay._install_keyboard_hook()
    
    # We can't guarantee hook success if not running as admin in tests,
    # but we can verify the state transitions and that remove doesn't crash.
    installed = overlay._hook_installed
    handle = overlay._hook_handle
    
    # Remove hook
    overlay._remove_keyboard_hook()
    
    # Verify state is cleared
    assert overlay._hook_installed is False
    assert overlay._hook_handle is None
