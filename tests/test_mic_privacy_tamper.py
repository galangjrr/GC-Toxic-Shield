from app.system_service import SystemService

def test_microphone_privacy_lock_cycle():
    """Test clean ON and OFF cycle without leaving dirty registry keys."""
    # 1. Test Lock ON
    ok_on = SystemService.toggle_microphone_privacy_lock(True)
    assert ok_on is True, "Failed to lock microphone privacy"
    assert SystemService.is_microphone_privacy_locked() is True

    # 2. Test Lock OFF (Clean Rollback)
    ok_off = SystemService.toggle_microphone_privacy_lock(False)
    assert ok_off is True, "Failed to unlock microphone privacy"
    assert SystemService.is_microphone_privacy_locked() is False
