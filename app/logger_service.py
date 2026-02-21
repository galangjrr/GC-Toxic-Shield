# =============================================================
# GC Toxic Shield — Task T3: Self-Cleaning Monitor & Logger
# =============================================================
# Module ini bertanggung jawab untuk:
# 1. Menyimpan transkripsi aman di temp_buffer (volatile/RAM)
# 2. Menyimpan toxic incident ke permanent file (CSV)
# 3. Auto-purge temp_buffer setiap 60 detik (RULE #5)
#
# RULES yang dipatuhi:
# - RULE #5: purge_logs tiap 60 detik, data aman tidak boleh
#            ada jejaknya di storage permanen.
# =============================================================

import csv
import os
import threading
import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Callable

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.Logger")

# ── Constants ──────────────────────────────────────────────────
from app._paths import LOGS_DIR as DEFAULT_LOG_DIR
DEFAULT_CSV_FILENAME = "toxic_incidents.csv"
PURGE_INTERVAL_SEC = 60  # RULE #5: Wajib 60 detik
CSV_HEADERS = ["timestamp", "transcription", "matched_words", "severity"]


@dataclass
class TranscriptionEntry:
    """
    Entry tunggal dalam buffer transkripsi.

    Attributes:
        text: Teks transkripsi.
        timestamp: Waktu transkripsi.
        is_toxic: Apakah mengandung kata toxic.
        matched_words: Kata toxic yang ditemukan.
    """
    text: str
    timestamp: str
    is_toxic: bool = False
    matched_words: Optional[List[str]] = None

    def __post_init__(self):
        if self.matched_words is None:
            self.matched_words = []


class LoggerService:
    """
    Task T3: Self-Cleaning Monitor & Logger.

    Mengelola dua jenis penyimpanan:
    - temp_buffer: Transkripsi aman (volatile, di RAM saja)
    - permanent_file: Toxic incident (persistent, CSV)

    Auto-purge membersihkan temp_buffer setiap 60 detik
    untuk menjaga privasi dan menghemat RAM.

    Usage:
        logger_svc = LoggerService()
        logger_svc.start()

        # Log transkripsi aman
        logger_svc.log("halo selamat pagi", is_toxic=False)

        # Log toxic incident
        logger_svc.log("dasar anjing", is_toxic=True, matched_words=["anjing"])

        logger_svc.stop()
    """

    def __init__(
        self,
        log_dir: str = None,
        csv_filename: str = DEFAULT_CSV_FILENAME,
        purge_interval: int = PURGE_INTERVAL_SEC,
        on_purge: Optional[Callable[[int], None]] = None,
    ):
        """
        Inisialisasi LoggerService.

        Args:
            log_dir: Direktori untuk menyimpan CSV toxic incidents.
            csv_filename: Nama file CSV.
            purge_interval: Interval auto-purge dalam detik (default: 60).
            on_purge: Callback opsional saat purge terjadi. Menerima jumlah
                      entry yang dibersihkan.
        """
        self._log_dir = log_dir or DEFAULT_LOG_DIR
        self._csv_path = os.path.join(self._log_dir, csv_filename)
        self._purge_interval = purge_interval
        self._on_purge = on_purge

        # ── Buffers ──
        self._temp_buffer: List[TranscriptionEntry] = []
        self._buffer_lock = threading.Lock()

        # ── State ──
        self._running = False
        self._purge_thread: Optional[threading.Thread] = None

        # ── Stats ──
        self._total_logged = 0
        self._total_toxic = 0
        self._total_purged = 0

        # Pastikan direktori log ada
        os.makedirs(self._log_dir, exist_ok=True)

        # Inisialisasi CSV jika belum ada
        self._init_csv()

        logger.info(
            "LoggerService initialized | csv=%s | purge_interval=%ds",
            self._csv_path, self._purge_interval
        )

    # ================================================================
    # PUBLIC API
    # ================================================================

    def start(self):
        """Memulai auto-purge background thread."""
        if self._running:
            logger.warning("LoggerService already running")
            return

        self._running = True

        self._purge_thread = threading.Thread(
            target=self._purge_loop,
            name="LoggerService-Purge",
            daemon=True,
        )
        self._purge_thread.start()

        logger.info("✓ LoggerService started (auto-purge every %ds)", self._purge_interval)

    def stop(self):
        """Menghentikan LoggerService dan melakukan final purge."""
        if not self._running:
            return

        self._running = False

        # Final purge sebelum shutdown
        self._execute_purge()

        if self._purge_thread and self._purge_thread.is_alive():
            self._purge_thread.join(timeout=3)

        logger.info(
            "✓ LoggerService stopped | total_logged=%d | total_toxic=%d | total_purged=%d",
            self._total_logged, self._total_toxic, self._total_purged
        )

    def log(
        self,
        text: str,
        is_toxic: bool = False,
        matched_words: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ):
        """
        Mencatat hasil transkripsi.

        - Jika TOXIC: Simpan ke permanent CSV + temp_buffer.
        - Jika SAFE: Simpan ke temp_buffer saja (akan di-purge).

        Args:
            text: Teks transkripsi.
            is_toxic: Apakah mengandung kata toxic.
            matched_words: Kata-kata toxic yang ditemukan.
            timestamp: Waktu (auto-generated jika None).
        """
        if not text or not text.strip():
            return

        ts = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")

        entry = TranscriptionEntry(
            text=text.strip(),
            timestamp=ts,
            is_toxic=is_toxic,
            matched_words=matched_words or [],
        )

        # ── Tambah ke temp buffer ──
        with self._buffer_lock:
            self._temp_buffer.append(entry)
            self._total_logged += 1

        # ── Jika TOXIC: simpan ke permanent CSV ──
        if is_toxic:
            self._write_to_csv(entry)
            self._total_toxic += 1
            logger.warning(
                "📝 TOXIC logged to CSV: \"%s\" | words=%s",
                text, matched_words
            )
        else:
            logger.debug("📝 Safe text buffered: \"%s\"", text)

    def get_buffer(self) -> List[TranscriptionEntry]:
        """
        Mengambil salinan temp_buffer saat ini.
        Digunakan oleh UI untuk menampilkan Live Monitor.
        """
        with self._buffer_lock:
            return self._temp_buffer.copy()

    def get_buffer_size(self) -> int:
        """Jumlah entry dalam temp_buffer."""
        with self._buffer_lock:
            return len(self._temp_buffer)

    @property
    def stats(self) -> dict:
        """Statistik logger."""
        return {
            "total_logged": self._total_logged,
            "total_toxic": self._total_toxic,
            "total_purged": self._total_purged,
            "buffer_size": self.get_buffer_size(),
        }

    # ================================================================
    # AUTO-PURGE (RULE #5)
    # ================================================================

    def _purge_loop(self):
        """
        Background thread: menjalankan auto_purge setiap 60 detik.
        RULE #5: Data aman tidak boleh ada jejaknya.
        """
        while self._running:
            # Sleep dalam interval kecil agar bisa di-stop cepat
            elapsed = 0.0
            while elapsed < self._purge_interval and self._running:
                time.sleep(1.0)
                elapsed += 1.0

            if self._running:
                self._execute_purge()

    def _execute_purge(self):
        """
        Menghapus semua transkripsi AMAN dari temp_buffer.
        Transkripsi TOXIC tetap dipertahankan di buffer
        (karena sudah disimpan di CSV juga).

        RULE #5: purge_logs secara ketat, data aman tidak
        boleh ada jejaknya di storage permanen.
        """
        with self._buffer_lock:
            before_count = len(self._temp_buffer)

            # Hapus semua entry yang TIDAK toxic
            self._temp_buffer = [
                entry for entry in self._temp_buffer
                if entry.is_toxic
            ]

            purged_count = before_count - len(self._temp_buffer)
            self._total_purged += purged_count

        if purged_count > 0:
            logger.info(
                "🧹 Auto-purge: %d safe entries cleared | remaining=%d (toxic only)",
                purged_count, len(self._temp_buffer)
            )

            # Callback opsional
            if self._on_purge:
                try:
                    self._on_purge(purged_count)
                except Exception as e:
                    logger.error("Purge callback error: %s", e)
        else:
            logger.debug("🧹 Auto-purge: nothing to clean")

    # ================================================================
    # CSV PERSISTENCE
    # ================================================================

    def _init_csv(self):
        """Inisialisasi file CSV dengan header jika belum ada."""
        if not os.path.exists(self._csv_path):
            try:
                with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
                logger.info("✓ CSV file created: %s", self._csv_path)
            except Exception as e:
                logger.error("✗ Failed to create CSV: %s", e)

    def _write_to_csv(self, entry: TranscriptionEntry):
        """
        Menulis satu toxic incident ke CSV file.
        Format: timestamp, transcription, matched_words, severity
        """
        try:
            severity = self._calculate_severity(entry.matched_words)

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    entry.timestamp,
                    entry.text,
                    "|".join(entry.matched_words),
                    severity,
                ])

        except Exception as e:
            logger.error("✗ Failed to write to CSV: %s", e)

    def _calculate_severity(self, matched_words: List[str]) -> str:
        """
        Menghitung severity berdasarkan jumlah kata toxic yang cocok.
        Digunakan untuk sistem level peringatan progresif (T5).
        """
        count = len(matched_words)
        if count >= 3:
            return "HIGH"
        elif count >= 2:
            return "MEDIUM"
        else:
            return "LOW"


# ================================================================
# Standalone test
# ================================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    def on_purge(count):
        print(f"  [PURGE CALLBACK] {count} entries cleaned!")

    svc = LoggerService(purge_interval=10, on_purge=on_purge)  # 10s for testing
    svc.start()

    print("LoggerService test — purge interval: 10s\n")

    # Simulate logging
    svc.log("halo selamat pagi", is_toxic=False)
    svc.log("apa kabar semua", is_toxic=False)
    svc.log("dasar anjing lo", is_toxic=True, matched_words=["anjing"])
    svc.log("cuaca hari ini cerah", is_toxic=False)
    svc.log("goblok banget sih", is_toxic=True, matched_words=["goblok"])

    print(f"  Buffer size: {svc.get_buffer_size()}")
    print(f"  Stats: {svc.stats}\n")

    print("  Waiting 12 seconds for auto-purge...\n")
    time.sleep(12)

    print(f"  Buffer size after purge: {svc.get_buffer_size()}")
    print(f"  Stats after purge: {svc.stats}\n")

    # Show remaining buffer (should only have toxic entries)
    for entry in svc.get_buffer():
        print(f"  Remaining: [{entry.timestamp}] \"{entry.text}\" (toxic={entry.is_toxic})")

    svc.stop()
    print("\n✓ Test completed")
