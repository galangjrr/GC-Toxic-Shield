# =============================================================
# GC Toxic Shield V2 — Task T4: Direct Match Detection
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

        self._load_wordlist()

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

        # ── T12: Pre-processing Pipeline ──
        # 1. Normalisasi (lowercase, repeat chars)
        cleaned_text = self._normalize_text(text)

        # 2. Phonetic Mapping (fix misheard words)
        mapped_text = self._apply_phonetic_mapping(cleaned_text)

        matched = []

        for word, pattern in self._patterns:
            if pattern.search(mapped_text):
                matched.append(word)

        is_toxic = len(matched) > 0

        result = DetectionResult(
            is_toxic=is_toxic,
            original_text=text,
            matched_words=matched,
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
            elif isinstance(data, dict):
                raw_words = data.get("toxic_words", [])
                self._phonetic_map = data.get("phonetic_mapping", {})
            else:
                logger.error("✗ Wordlist format unknown (must be list or dict)")
                return

            # Normalisasi: lowercase, strip, hapus duplikat, hapus empty
            unique_words = list(set(
                word.lower().strip()
                for word in raw_words
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

            logger.info(
                "✓ Wordlist loaded: %d toxic words, %d mappings from %s",
                len(self._toxic_words),
                len(self._phonetic_map),
                os.path.basename(self._wordlist_path)
            )

        except json.JSONDecodeError as e:
            logger.error("✗ Invalid JSON in wordlist: %s", e)
            self._toxic_words = []
            self._patterns = []
            self._phonetic_map = {}

        except Exception as e:
            logger.error("✗ Failed to load wordlist: %s", e)
            self._toxic_words = []
            self._patterns = []
            self._phonetic_map = {}

    def _normalize_text(self, text: str) -> str:
        """
        Normalisasi teks:
        1. Lowercase
        2. Condense repeated chars > 2 (e.g. "anjiiiing" -> "anjing")
        """
        text = text.lower().strip()
        # Regex: (karakter apa saja)\1{2,} -> ganti dengan \1
        # Mengubah 3+ karakter sama berturut-turut jadi 1
        # Contoh: anjiiiing -> anjing, gobloook -> goblok
        # Note: Kita sisakan 1 char, karena bahasa Indonesia jarang double char
        # kecuali 'taat', 'maaf'. Tapi user toxic biasanya 'anjiiiing'.
        # Safe bet: reduce to 1 or 2. Let's reduce to 1 for simplicity regarding slang.
        text = re.sub(r'(.)\1{2,}', r'\1', text)
        return text

    def _apply_phonetic_mapping(self, text: str) -> str:
        """
        Mengganti kata salah dengar (misheard) dengan kata toxic asli.
        Contoh: "peeler" -> "peler", "fill" -> "itil"
        """
        # T13: Hardcoded aliases verification
        # Ensure peeler/peller -> peler is always present
        hardcoded_map = {
            "peeler": "peler",
            "peller": "peler"
        }
        
        # Merge with loaded map (priority to loaded map if exists, or hardcoded? 
        # User said "map automatically", implying these MUST work. 
        # I'll use hardcoded as fallback or override. Let's treat them as default.)
        
        words = text.split()
        new_words = []
        for w in words:
            w_lower = w.lower()
            # Priority: 1. Hardcoded, 2. JSON Map
            if w_lower in hardcoded_map:
                new_words.append(hardcoded_map[w_lower])
            elif w_lower in self._phonetic_map:
                new_words.append(self._phonetic_map[w_lower])
            else:
                new_words.append(w)
        
        return " ".join(new_words)


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
