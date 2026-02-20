import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.detector import ToxicDetector
from app.audio_engine import AudioEngine

class TestCoreLogic(unittest.TestCase):
    def test_phonetic_mapping(self):
        print("\nTesting Phonetic Mapping...")
        detector = ToxicDetector()
        
        # Test hardcoded aliases
        cases = {
            "peeler": "peler",
            "peller": "peler",
            "PEELER": "peler", # Case insensitive check
        }
        
        for input_word, expected in cases.items():
            mapped = detector._apply_phonetic_mapping(input_word)
            print(f"  '{input_word}' -> '{mapped}'")
            self.assertIn(expected, mapped)
            
        # Verify detection
        res = detector.detect("dasar peeler lu")
        print(f"  Detection for 'dasar peeler lu': IsToxic={res.is_toxic}, Matched={res.matched_words}")
        self.assertTrue(res.is_toxic, "Should detect 'peeler' as toxic via mapping")
        self.assertIn("peler", res.matched_words)

    def test_audio_engine_defaults(self):
        print("\nTesting Audio Engine Defaults...")
        # Mock speech_recognition to avoid needing a mic
        with unittest.mock.patch('speech_recognition.Recognizer') as mock_recog:
            with unittest.mock.patch('speech_recognition.Microphone'):
                engine = AudioEngine()
                
                print(f"  Initial Gain: {engine.gain}")
                self.assertEqual(engine.gain, 1.5, "Default gain should be 1.5")
                
                # Check pause_threshold
                print(f"  Pause Threshold: {engine._recognizer.pause_threshold}")
                self.assertEqual(engine._recognizer.pause_threshold, 1.0, "Pause threshold should be 1.0")
                
                # phrase_time_limit is used in listen(), not init, so we check the constant
                # but we can check if the constant is defined in the module if we import it
                from app.audio_engine import PHRASE_TIME_LIMIT
                print(f"  PHRASE_TIME_LIMIT: {PHRASE_TIME_LIMIT}")
                self.assertEqual(PHRASE_TIME_LIMIT, 5, "Phrase time limit should be 5")

if __name__ == '__main__':
    unittest.main()
