import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import what we can test
from app.detector import ToxicDetector
from app.audio_engine import AudioEngine
from app.system_service import SystemService
from app.penalty_manager import PenaltyManager
from app.auth_service import AuthService


class TestSurgicalGuard(unittest.TestCase):
    """Tests for the new Surgical Desktop Guard."""

    def test_desktop_guard_import_and_init(self):
        print("\nTesting Desktop Guard...")
        from app.desktop_guard import DesktopGuard
        
        mock_root = MagicMock()
        guard = DesktopGuard(mock_root)
        
        self.assertFalse(guard.is_enabled, "Should be disabled by default")
        self.assertTrue(len(guard._targets) > 0, "Should have discovered desktop paths")
        print(f"  ✓ Discovered paths: {guard._targets}")
        
    def test_simple_warning_box_exists(self):
        from app.overlay import SimpleWarningBox
        self.assertTrue(callable(SimpleWarningBox))
        self.assertTrue(hasattr(SimpleWarningBox, '_instance'))
        print("  ✓ SimpleWarningBox exists in overlay.py")


class TestPreviousFeatures(unittest.TestCase):
    def test_phonetic_mapping(self):
        detector = ToxicDetector()
        res = detector._apply_phonetic_mapping("peeler")
        self.assertIn("peler", res)

    def test_audio_engine_defaults(self):
        with patch('speech_recognition.Recognizer'):
            with patch('speech_recognition.Microphone'):
                from app.audio_engine import PHRASE_TIME_LIMIT
                self.assertEqual(PHRASE_TIME_LIMIT, 5)

if __name__ == '__main__':
    unittest.main()
