# =============================================================
# GC Toxic Shield — Task T4: Direct Match Detection
# =============================================================
# Module ini bertanggung jawab untuk:
# 1. Membaca daftar kata toxic dari word_list.json
# 2. Melakukan Whole Word Matching (case-insensitive) via regex
# 3. Mengembalikan hasil deteksi ke caller (main.py / UI)
#
# CONSTRAINT (PRD §3B):
# - Dilarang menggunakan fuzzy matching
# - Menggunakan regex \b word boundary untuk mencegah
#   false positive (contoh: "kontrol" ≠ "kontol")
# =============================================================

import json
import os
import re
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Pattern

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.Detector")

# ── Constants ──────────────────────────────────────────────────
from app._paths import WORDLIST_PATH as DEFAULT_WORDLIST_PATH


@dataclass
class DetectionResult:
    """
    Hasil deteksi dari ToxicDetector.

    Attributes:
        is_toxic: True jika kata toxic ditemukan.
        original_text: Teks asli dari transkripsi.
        matched_words: Daftar kata toxic yang cocok.
        timestamp: Waktu deteksi (ISO format).
    """
    is_toxic: bool
    original_text: str
    matched_words: List[str] = field(default_factory=list)
    cancelled_words: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")


class ToxicDetector:
    """
    Task T4: Strict Whole-Word Matching Detector.

    Mencocokkan output transkripsi dengan daftar kata toxic
    menggunakan regex word boundary (case-insensitive).

    Contoh:
        "kontrol" → SAFE  (bukan "kontol")
        "anjing"  → TOXIC (whole word match)

    Usage:
        detector = ToxicDetector("assets/word_list.json")
        result = detector.detect("kamu anjing banget")
        if result.is_toxic:
            print(f"TOXIC! Matched: {result.matched_words}")
    """

    def __init__(self, wordlist_path: str = None):
        """
        Inisialisasi ToxicDetector.

        Args:
            wordlist_path: Path ke file word_list.json.
                           Default: assets/word_list.json
        """
        self._wordlist_path = wordlist_path or DEFAULT_WORDLIST_PATH
        self._toxic_words: List[str] = []
        self._patterns: List[tuple] = []  # [(word, compiled_regex), ...]
        self._allowed_words: List[str] = []
        self._allowed_patterns: List[tuple] = []
        self._context_exclusions: dict = {}

        self._load_wordlist()
        
        self._ai_detector = None
        self._init_ai_detector()

    def _init_ai_detector(self):
        try:
            from app.nlp_detector import NLPDetector
            import os
            model_path = os.path.join(os.getcwd(), "nlp_model.pkl")
            if os.path.exists(model_path):
                self._ai_detector = NLPDetector(model_path=model_path)
                if not self._ai_detector.is_loaded:
                    self._ai_detector = None
        except ImportError:
            self._ai_detector = None
            
    def reload_ai_model(self, model_path):
        try:
            from app.nlp_detector import NLPDetector
            self._ai_detector = NLPDetector(model_path=model_path)
            if self._ai_detector.is_loaded:
                logger.info("AI NLP Model di-reload dengan sukses!")
            else:
                self._ai_detector = None
        except Exception as e:
            logger.error(f"Gagal reload AI: {e}")

    # ================================================================
    # PUBLIC API
    # ================================================================

    def detect(self, text: str) -> DetectionResult:
        """
        Melakukan deteksi kata toxic pada teks transkripsi.

        Menggunakan regex word boundary (\\b) untuk whole-word matching.
        Mencegah false positive seperti "kontrol" → "kontol".

        Args:
            text: Teks hasil transkripsi dari AudioEngine.

        Returns:
            DetectionResult dengan is_toxic, matched_words, dll.
        """
        if not text or not text.strip():
            return DetectionResult(
                is_toxic=False,
                original_text=text or "",
            )

        # ── Pre-processing Pipeline ──
        cleaned_text = self._normalize_text(text)
        mapped_text = self._apply_phonetic_mapping(cleaned_text)

        # Simpan teks asli (post-mapping) untuk context exclusion & log.
        # JANGAN mutasi mapped_text dengan menghapus allowed words dari string!
        # Penghapusan sebelumnya menyebabkan kata konteks seperti 'honda', 'kentang'
        # hilang dari teks sebelum context_exclusion sempat diperiksa → root cause
        # false positive 'dealer honda' dan 'peeler kentang'.
        detection_text = mapped_text

        matched = []
        is_toxic = False

        # O(1) Performance via Python Sets untuk kata tunggal
        words_set = set(re.findall(r'\b\w+\b', detection_text.lower()))

        for word, pattern in self._patterns:
            # Skip: kata ini ada di allowed_words → bukan kata kotor
            if word in self._allowed_words:
                continue
            if " " not in word:
                if word in words_set:
                    matched.append(word)
            else:
                if pattern.search(detection_text):
                    matched.append(word)

        # ── NLP Fallback: DINONAKTIFKAN ──
        # Model sklearn lokal (nlp_model.pkl) terbukti tidak akurat:
        # - 'player satu mau main' → diprediksi TOXIC (salah)
        # - 'kontol anjing' → diprediksi SAFE (salah)
        # Akurasi model di bawah batas layak pakai. Jangan aktifkan kembali
        # sebelum model dilatih ulang dengan dataset warnet yang representatif.
        # if self._ai_detector and getattr(self._ai_detector, 'is_loaded', False):
        #     is_toxic_ai = self._ai_detector.is_toxic(detection_text)
        #     if is_toxic_ai and not matched:
        #         matched = ["[AI_DETECTED]"]

        # ── Context Exclusion: batalkan false positives ──
        # Jika kata toxic punya konteks pelindung dan kata konteks itu
        # ADA di detection_text (yang TIDAK dimutasi) → batalkan match.
        cancelled = []
        if matched and self._context_exclusions:
            filtered = []
            text_lower = detection_text.lower()
            for word in matched:
                exclusions = self._context_exclusions.get(word, [])
                if exclusions and any(ctx in text_lower for ctx in exclusions):
                    logger.debug(
                        "Context exclusion: '%s' cancelled (context word found in text)",
                        word
                    )
                    cancelled.append(word)
                    continue
                filtered.append(word)
            matched = filtered

        is_toxic = len(matched) > 0

        result = DetectionResult(
            is_toxic=is_toxic,
            original_text=text,
            matched_words=matched,
            cancelled_words=cancelled,
        )

        if is_toxic:
            logger.warning(
                "🚨 TOXIC DETECTED: \"%s\" | Matched: %s",
                text, matched
            )
        else:
            logger.debug("✓ Clean text: \"%s\"", text)

        return result

    def reload_wordlist(self):
        """
        Memuat ulang word_list.json secara hot-reload.
        Berguna jika admin mengedit daftar kata tanpa restart.
        """
        self._load_wordlist()
        logger.info("⟳ Wordlist reloaded (%d words)", len(self._toxic_words))

    def normalize_stt_text(self, text: str) -> str:
        """
        Terapkan normalisasi (lowercase, hapus char berulang) 
        dan pemetaan fonetik (salah dengar API) agar teks 
        bisa distandardisasi secara global (UI, Log, Detektor).
        """
        cleaned_text = self._normalize_text(text)
        mapped_text = self._apply_phonetic_mapping(cleaned_text)
        return mapped_text

    @property
    def word_count(self) -> int:
        """Jumlah kata toxic yang dimuat."""
        return len(self._toxic_words)

    @property
    def words(self) -> List[str]:
        """Daftar kata toxic (read-only copy)."""
        return self._toxic_words.copy()

    # ================================================================
    # INTERNAL
    # ================================================================

    def _load_wordlist(self):
        """
        Membaca word_list.json dan menyimpan ke memori.
        Semua kata dinormalisasi ke lowercase dan di-compile
        menjadi regex pattern dengan word boundary.
        """
        try:
            if not os.path.exists(self._wordlist_path):
                logger.error(
                    "✗ Wordlist not found: %s", self._wordlist_path
                )
                self._toxic_words = []
                self._patterns = []
                return

            with open(self._wordlist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_words = []
            self._phonetic_map = {}

            # Support format lama (list) dan baru (dict)
            if isinstance(data, list):
                raw_words = data
                raw_allowed_words = []
            elif isinstance(data, dict):
                raw_words = data.get("toxic_words", [])
                self._phonetic_map = data.get("phonetic_mapping", {})
                raw_allowed_words = data.get("allowed_words", [])
                raw_context_exclusions = data.get("context_exclusions", {})
            else:
                logger.error("✗ Wordlist format unknown (must be list or dict)")
                return

            # Normalisasi: lowercase, strip, hapus duplikat, hapus empty
            flattened_words = []
            if isinstance(raw_words, dict):
                for key, aliases in raw_words.items():
                    flattened_words.append(key)
                    if isinstance(aliases, list):
                        flattened_words.extend(aliases)
            elif isinstance(raw_words, list):
                flattened_words = raw_words

            unique_words = list(set(
                word.lower().strip()
                for word in flattened_words
                if isinstance(word, str) and word.strip()
            ))

            # Compile regex patterns dengan word boundary
            compiled = []
            for word in unique_words:
                try:
                    pattern = re.compile(
                        r'\b' + re.escape(word) + r'\b',
                        re.IGNORECASE
                    )
                    compiled.append((word, pattern))
                except re.error as e:
                    logger.warning("Invalid regex for word '%s': %s", word, e)

            self._toxic_words = unique_words
            self._patterns = compiled

            # Compile allowed words
            allowed_compiled = []
            unique_allowed = list(set(
                word.lower().strip()
                for word in raw_allowed_words
                if isinstance(word, str) and word.strip()
            ))
            for word in unique_allowed:
                try:
                    pattern = re.compile(
                        r'\b' + re.escape(word) + r'\b',
                        re.IGNORECASE
                    )
                    allowed_compiled.append((word, pattern))
                except re.error as e:
                    logger.warning("Invalid regex for allowed word '%s': %s", word, e)
            
            self._allowed_words = unique_allowed
            self._allowed_patterns = allowed_compiled

            # Load context exclusions (normalize to lowercase)
            self._context_exclusions = {}
            if isinstance(raw_context_exclusions, dict):
                for toxic_word, ctx_words in raw_context_exclusions.items():
                    if isinstance(ctx_words, list):
                        self._context_exclusions[toxic_word.lower().strip()] = [
                            w.lower().strip() for w in ctx_words if isinstance(w, str) and w.strip()
                        ]

            # Pre-compile phonetic mapping patterns
            self._phonetic_patterns = []
            for misheard, real_word in self._phonetic_map.items():
                try:
                    pat = re.compile(r'\b' + re.escape(misheard) + r'\b', re.IGNORECASE)
                    self._phonetic_patterns.append((pat, real_word))
                except re.error as e:
                    logger.warning("Invalid regex for phonetic map '%s': %s", misheard, e)

            logger.info(
                "✓ Wordlist loaded: %d toxic words, %d mapping, %d allowed, %d context_exclusions from %s",
                len(self._toxic_words),
                len(self._phonetic_map),
                len(self._allowed_words),
                len(self._context_exclusions),
                os.path.basename(self._wordlist_path)
            )

        except json.JSONDecodeError as e:
            logger.error("✗ Invalid JSON in wordlist: %s", e)
            self._toxic_words = []
            self._patterns = []
            self._phonetic_map = {}
            self._phonetic_patterns = []
            self._allowed_words = []
            self._allowed_patterns = []
            self._context_exclusions = {}

        except Exception as e:
            logger.error("✗ Failed to load wordlist: %s", e)
            self._toxic_words = []
            self._patterns = []
            self._phonetic_map = {}
            self._phonetic_patterns = []
            self._allowed_words = []
            self._allowed_patterns = []
            self._context_exclusions = {}

    def _normalize_text(self, text: str) -> str:
        """
        Normalisasi teks:
        1. Lowercase
        2. Reduksi karakter berulang — tangkap teriakan STT seperti
           'kontooool' → 'kontol', 'anjinggg' → 'anjing'
        """
        text = text.lower().strip()
        # Collapse 3+ karakter berulang jadi 1 — cegah STT bypass via teriakan vokal panjang
        text = re.sub(r'(.)\1{2,}', r'\1', text)
        return text

    def _apply_phonetic_mapping(self, text: str) -> str:
        """
        Mengganti kata salah dengar (misheard) dengan kata toxic asli.
        Contoh: "peeler" -> "peler", "fill" -> "itil"
        (Diambil dari word_list.json → phonetic_mapping)
        """
        new_text = text
        for pat, real_word in getattr(self, '_phonetic_patterns', []):
            new_text = pat.sub(real_word, new_text)
        return new_text


# ================================================================
# Standalone test
# ================================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    detector = ToxicDetector()
    print(f"Loaded {detector.word_count} toxic words\n")

    test_sentences = [
        ("halo selamat pagi", False),
        ("kamu anjing banget sih", True),
        ("dasar goblok tolol", True),
        ("selamat datang di warnet", False),
        ("babi lo semua", True),
        ("kontrol suhu ruangan", False),   # "kontrol" ≠ "kontol"
        ("dia mengontrol semuanya", False), # "mengontrol" ≠ "kontol"
        ("", False),
    ]

    print("  Whole-Word Match Test Results:")
    print("  " + "─" * 55)
    for sentence, expected_toxic in test_sentences:
        result = detector.detect(sentence)
        status = "🚨 TOXIC" if result.is_toxic else "✅ SAFE "
        check = "✓" if result.is_toxic == expected_toxic else "✗ FAIL"
        print(f"  {check} {status} | \"{sentence}\"")
        if result.matched_words:
            print(f"              Matched: {result.matched_words}")
    print()
