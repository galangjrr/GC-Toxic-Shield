import os
import tempfile
import json
import pytest
from app.detector import ToxicDetector, DetectionResult
from unittest.mock import MagicMock

@pytest.fixture
def temp_wordlist():
    data = {
        "toxic_words": ["kontol", "goblok", "anjing", "peler"],
        "allowed_words": ["mengontrol", "anjing laut"],
        "phonetic_mapping": {
            "peeler": "peler"
        },
        "context_exclusions": {
            "peler": ["motor honda ada peler rusak", "beli peler buat kentang"]
        }
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    yield path
    os.remove(path)

@pytest.fixture
def detector(temp_wordlist):
    d = ToxicDetector(temp_wordlist)
    d.reload_wordlist()
    return d

test_cases = [
    ("kontrol suhu ruangan", False),
    ("dia mengontrol semuanya", False),
    ("beli peeler buat kentang", False),
    ("motor honda ada peler rusak", False),
    ("goblok,", True),
]

@pytest.mark.parametrize("text,expected_toxic", test_cases)
def test_detector_without_ai(detector, text, expected_toxic):
    detector._ai_detector = None
    result = detector.detect(text)
    assert result.is_toxic == expected_toxic

@pytest.mark.parametrize("text,expected_toxic", test_cases)
def test_detector_with_mock_ai(detector, text, expected_toxic):
    class MockAI:
        is_loaded = True
        def is_toxic(self, t):
            # Realistic mock: AI thinks 'peler', 'anjing', 'goblok' are toxic
            return any(w in t.lower() for w in ["peler", "anjing", "goblok"])
            
    detector._ai_detector = MockAI()
    result = detector.detect(text)
    assert result.is_toxic == expected_toxic
