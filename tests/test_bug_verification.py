import pytest
from app.detector import ToxicDetector
from app.audio_engine import AudioEngine, PHRASE_TIME_LIMIT

@pytest.fixture
def prod_detector():
    return ToxicDetector("assets/word_list.json")

def test_bug_player_mapped_to_peler_false_positive(prod_detector):
    """Bug: Gamer saying 'player' gets flagged as 'peler'."""
    result = prod_detector.detect("player satu mau main")
    # Harusnya SAFE (False), tapi kena bug phonetic mapping -> peler
    assert result.is_toxic is False, f"False Positive! Matched: {result.matched_words}"

def test_bug_context_exclusion_dealer_honda(prod_detector):
    """Bug: Context exclusion 'honda' is deleted by allowed_words before check."""
    result = prod_detector.detect("dealer honda motor resmi")
    # Harusnya SAFE (False), tapi 'honda' dihapus oleh allowed_words sehingga exclusion gagal
    assert result.is_toxic is False, f"False Positive! Matched: {result.matched_words}"

def test_bug_context_exclusion_peeler_kentang(prod_detector):
    """Bug: Context exclusion 'kentang' is deleted by allowed_words before check."""
    result = prod_detector.detect("beli peeler kentang di pasar")
    # Harusnya SAFE (False), tapi 'kentang' dihapus oleh allowed_words sehingga exclusion gagal
    assert result.is_toxic is False, f"False Positive! Matched: {result.matched_words}"

def test_bug_elongated_vowels_shouted(prod_detector):
    """Bug: Shouted words with elongated characters bypass \\b regex."""
    result = prod_detector.detect("dasar kontooool")
    # Harusnya TOXIC (True), tapi lolos karena tidak ada normalisasi char berulang
    assert result.is_toxic is True, "False Negative! Kata teriakan lolos deteksi"

def test_bug_phrase_time_limit_none():
    """Bug: PHRASE_TIME_LIMIT is None, causing listen to hang in noisy rooms."""
    assert PHRASE_TIME_LIMIT is not None, "PHRASE_TIME_LIMIT is None! Audio listen will hang in noisy room"
