# 🎯 Prompt Eksekusi — GC Toxic Shield Bugfix & Improvement Pass
**Target Agent:** Gemini
**Scope:** Bugfix, algoritma deteksi, arsitektur non-UI-lockdown

---

## 📋 Konteks Proyek

Kamu bekerja pada codebase **GC Toxic Shield**, aplikasi PySide6 untuk deteksi kata kasar via Speech-to-Text di lingkungan warnet. Dokumen referensi arsitektur ada di `ENGINEERING_HANDOVER.md` — baca dulu sebelum mulai kerja, tapi **abaikan seluruh bagian yang membahas `overlay.py`, Win32 hook, dan lockdown OS**.

Kamu HANYA bekerja pada modul-modul berikut:
1. `app/detector.py` — akurasi deteksi toxic (regex, phonetic mapping, context exclusion)
2. `app/nlp_detector.py` — model NLP fallback
3. `app/penalty_manager.py` — state machine sanksi (level aplikasi, BUKAN OS lockdown)
4. `app/network_client.py` — sinkronisasi client-server
5. `app/audio_engine.py` — capture audio & STT
6. `app/auth_service.py` — auth & config persistence
7. `app/system_service.py` — HANYA bagian priority/DACL, bukan registry policy lockdown
8. `app/ui_manager.py` — dashboard admin (QSS/UI bugs)
9. `app/updater.py` — auto-updater
10. `app/overlay.py` — Bugfix keyboard & mouse hook

---

## 🔍 Bug & Perbaikan yang Harus Dikerjakan

### 1. `detector.py` — Akurasi Deteksi (PRIORITAS TINGGI)

**Bug #1 — AI detector bypass context_exclusions & allowed_words:**
Saat `self._ai_detector.is_loaded == True`, alur deteksi (baris ~141–162) LANGSUNG memakai hasil AI tanpa pernah menjalankan filter `_allowed_patterns` atau `_context_exclusions`. Ini artinya begitu model NLP aktif, seluruh whitelist dan context exclusion (`"kontrol"`, `"peler"` vs `"honda/yamaha/kentang"`, dll) jadi tidak berlaku. Perbaiki supaya jalur AI tetap melewati filter `allowed_words` dan `context_exclusions` yang sama seperti jalur regex biasa, sebelum keputusan akhir `is_toxic` ditentukan.

**Bug #2 — Context exclusion dicek di teks yang salah:**
Filter context exclusion (baris ~184–196) mengecek `cleaned_text` (hasil `_normalize_text` saja), padahal kata yang di-match sudah melalui `_apply_phonetic_mapping` (`mapped_text`). Kalau kata pemicu context exclusion sendiri butuh phonetic mapping untuk match, pengecekan jadi tidak akurat. Perbaiki agar konsisten memakai teks final (`mapped_text`) untuk pencarian context exclusion.

**Bug #3 — Phonetic mapping per-kata terlalu kaku:**
`_apply_phonetic_mapping` split by space dan cocokkan tiap token secara utuh. Ini gagal untuk kasus di mana STT menghasilkan tanda baca menempel (`"anjing,"`, `"goblok!"`) atau typo STT multi-kata. Tambahkan strip tanda baca ringan sebelum lookup mapping, atau gunakan regex substitution per-kata dengan boundary agar lebih robust.

**Bug #4 — Tidak ada logging/telemetry untuk near-miss:**
Tambahkan opsi logging (level DEBUG) untuk kasus di mana context exclusion MEMBATALKAN sebuah match — ini penting untuk audit "berapa banyak false-positive yang berhasil dicegah" vs "berapa yang lolos". Simpan ke `LoggerService` yang sudah ada (cek signature-nya di `app/` sebelum ubah).

**Test yang harus lulus setelah perbaikan** (tambahkan ke `test_detector.py` atau file test yang relevan):
```python
test_cases = [
    ("kontrol suhu ruangan", False),          # existing, harus tetap SAFE
    ("dia mengontrol semuanya", False),       # existing, harus tetap SAFE
    ("beli peeler buat kentang", False),      # context exclusion harus jalan walau AI aktif
    ("motor honda ada peler rusak", False),   # context exclusion harus jalan walau AI aktif
    ("kamu anjiiiing banget!", True),         # punctuation + repeated char
    ("goblok,", True),                        # trailing punctuation
]
```
Jalankan test ini dua kali: sekali dengan `nlp_model.pkl` di-mock sebagai loaded, sekali tanpa. Kedua mode harus menghasilkan hasil konsisten untuk context_exclusions dan allowed_words.

---

### 2. `penalty_manager.py` — Thread Safety Sanksi

Sesuai invariant di handover: reset timer pelanggaran harus thread-safe. Audit implementasi saat ini:
- Pastikan increment counter pelanggaran dan reset timer memakai `threading.Lock` yang sama (bukan lock terpisah yang bisa race).
- Pastikan callback ke `NetworkClient` untuk kirim event pelanggaran **tidak blocking** — kalau network lambat/putus, UI/state machine jangan ikut freeze. Gunakan queue atau fire-and-forget dengan retry di background thread `network_client.py`.
- Tambahkan unit test untuk race condition: simulasikan 2 pelanggaran nyaris bersamaan (multi-thread) dan pastikan counter akurat (tidak lompat atau double-count).

---

### 3. `network_client.py` — Reconnection Logic

- Audit reconnection logic: pastikan ada exponential backoff (bukan retry rapat setiap detik yang boros CPU/bandwidth), misal mulai 1s → 2s → 4s → maks 30s.
- Pastikan reconnect thread punya flag stop yang bersih saat aplikasi ditutup (hindari thread zombie/orphan).
- Cek race condition antara state "reconnecting" dan command masuk dari server (jangan sampai command diproses saat koneksi belum benar-benar stabil).

---

### 4. `audio_engine.py` — Graceful Error Handling

- Verifikasi `WinError 50` (mic disconnected) benar-benar tertangkap di semua jalur (device hot-unplug saat sedang recording, saat idle, saat baru start).
- Pastikan callback `on_transcription` yang jalan di background thread tidak pernah langsung memanggil widget PySide6 apa pun secara langsung — harus lewat Qt Signal. Audit ulang, karena ini rawan crash intermiten yang sulit direproduksi.

---

### 5. `ui_manager.py` — QSS f-string Escaping

Cari SEMUA tempat yang membangun stylesheet QSS memakai f-string dan pastikan `{{` `}}` sudah di-escape dengan benar. Ini bug kelas "muncul random di beberapa PC saja" — audit menyeluruh, bukan spot-check.

---

### 6. `overlay.py` — Bugfix keyboard hook

1. Audit penggunaan `ctypes.windll.user32.CallNextHookEx` di `KeyboardHookThread`. Pastikan ia dipanggil dengan argumen yang benar (0, nCode, wParam, lParam).
2. Verifikasi `_should_block_event` correctly mengecek `nCode`.
3. Perbaiki `KeyboardHookThread.stop` agar benar-benar melepaskan hook dengan memanggil `UnhookWindowsHookEx` menggunakan handle yang disimpan, dan set hook handle ke 0.
4. Tambahkan unit test untuk memastikan hook dilepas saat aplikasi ditutup atau saat thread berhenti secara normal/abnormal.

---

## 🧪 Deliverable yang Diharapkan

1. Diff/patch per file yang disebutkan di atas.
2. Ringkasan bug yang ditemukan + root cause + fix, dalam format tabel.
3. Test case baru (pytest) untuk tiap bug yang diperbaiki.
4. Daftar terpisah: "Catatan di luar scope"

---
*Prompt ini dibuat untuk eksekusi terbatas — pastikan agent mematuhi exclusion scope sebelum mulai commit apa pun.*
