# TASK: Full Implementation of Dynamic Multi-Zone Proximity Filter

## 1. Context & Objective
Sistem kalibrasi statis (mic calibration) sebelumnya telah bersih dihapus dari `GC Toxic Shield`. Tugas Anda sekarang adalah membangun fitur baru: "Dynamic Multi-Zone Proximity Filter" yang berbasis pada amplitudo/energi suara (RMS - Root Mean Square).

Sistem harus mengevaluasi energi dari setiap *audio chunk* yang masuk secara *real-time*. Pengguna dapat membuat beberapa "zona" batas energi secara dinamis melalui UI. Jika energi *chunk* masuk ke zona yang ditandai "PROCESS", teruskan audio tersebut ke antrean STT/Detector. Jika masuk ke zona "IGNORE", *chunk* tersebut langsung dibuang (*dropped*).

## 2. Target Files
- `config.py` atau file settings terkait (Untuk menyimpan dan menginisialisasi state/konfigurasi default).
- `audio_engine.py` (Kalkulasi RMS secara efisien dan pemfilteran *chunk* audio).
- `ui_manager.py` (Membangun tab UI baru, VU Meter real-time, dan manajemen daftar zona dinamis).

## 3. Data Architecture
Gunakan struktur `List of Dictionaries` berikut sebagai *state* awal. Tambahkan ini ke sistem memori/konfigurasi aplikasi agar nilainya persisten:

```python
ZONES = [
    {"id": "zone_1", "name": "Background Noise", "min_rms": 0.00, "max_rms": 0.05, "action": "IGNORE"},
    {"id": "zone_2", "name": "User Voice", "min_rms": 0.06, "max_rms": 0.30, "action": "PROCESS"},
    {"id": "zone_3", "name": "Distant Yell", "min_rms": 0.31, "max_rms": 0.45, "action": "IGNORE"},
    {"id": "zone_4", "name": "User Yell", "min_rms": 0.46, "max_rms": 1.00, "action": "PROCESS"}
]
```

## 4. Execution Steps
Kerjakan langkah-langkah di bawah ini secara sekuensial. Pastikan setiap langkah berjalan tanpa error sebelum melanjutkan ke langkah berikutnya.

### Step 1: Engine RMS Calculation (`audio_engine.py`)
1. Buat private method `_calculate_rms(audio_chunk)` di dalam class audio engine yang mengembalikan nilai RMS float dari chunk audio (bytes/numpy array) saat ini.
2. Pastikan variabel/state `ZONES` dapat diakses langsung oleh audio engine secara in-memory.

### Step 2: Engine Gate Logic (`audio_engine.py`)
    1. Di dalam loop perekaman utama, tepat sebelum chunk dikirim ke antrean (queue) STT atau Detector, sisipkan logika filter.
    2. Hitung `current_rms` dari chunk tersebut.
    3. Iterasi melalui `ZONES`:
    - Jika `current_rms >= min_rms` DAN `current_rms <= max_rms`:
        - Jika `action == "PROCESS"`, izinkan chunk masuk antrean.
        - Jika `action == "IGNORE"`, drop/continue (jangan masukkan antrean).
        - Hentikan iterasi (break) jika zona sudah ditemukan.
    4. Fallback Rule: Jika `current_rms` tidak memenuhi kriteria di zona manapun, set action default menjadi `"IGNORE"`.

### Step 3: Visual Calibration UI (`ui_manager.py`)
1. Buat tab baru di UI manager dengan judul "Proximity Filter".
2. Tambahkan widget Real-time VU Meter (bisa berupa progress bar horizontal).
3. Hubungkan VU Meter ini agar membaca nilai `current_rms` terbaru dari `audio_engine.py`. Update UI ini secara responsif (misal: 10-30 fps) agar pengguna dapat melihat representasi visual dari suara mereka secara presisi saat berbicara.

### Step 4: Dynamic Zone Builder UI (`ui_manager.py`)
1. Di bawah VU Meter, render daftar form berdasarkan state `ZONES`.
2. Setiap baris mewakili satu zona dan harus berisi:
   - Input/Entry untuk "Nama Zona".
   - SpinBox/Slider untuk "Min RMS" (0.00 - 1.00).
   - SpinBox/Slider untuk "Max RMS" (0.00 - 1.00).
   - ComboBox/Dropdown untuk "Action" (`PROCESS` atau `IGNORE`).
   - Tombol "Hapus" untuk menghapus baris tersebut.
3. Tambahkan satu tombol utama "Add New Zone" di bawah daftar untuk membuat baris/zona baru dengan nilai default yang aman.

### Step 5: State Synchronization
1. Setiap kali pengguna melakukan interaksi di UI (mengubah nilai spinbox, mengetik nama, menambah/menghapus zona), perubahan tersebut HARUS langsung tersinkronisasi ke variabel in-memory `ZONES` yang digunakan oleh `audio_engine.py`.
2. Jangan menunda sinkronisasi, filter engine harus menggunakan nilai terbaru saat itu juga.

## 5. Strict Constraints & Rules
1. Performance is Critical: Logika iterasi di `audio_engine.py` berada di hot path (berjalan puluhan/ratusan kali per detik). Dilarang keras melakukan operasi I/O (seperti membaca/menulis file `.json` atau `.txt`) di dalam loop audio. Selalu baca state `ZONES` dari RAM/Memory.
2. UI Validation: Berikan validasi otomatis di UI. Nilai input `min_rms` tidak boleh lebih besar dari `max_rms` pada baris zona yang sama.
3. No Redundant Libraries: Gunakan library pemrosesan array atau matematika yang sudah di-import di project ini. Jangan menambahkan dependency baru yang tidak krusial.
4. Clean Code: Jangan merusak fungsi STT, Detector, atau Logging yang sudah berjalan stabil.

## 6. Update Documentation
1. Update `README.md` dengan fitur baru.
2. Update `docs/features.md` dengan fitur baru.
3. Update `docs/user_guide.md` dengan fitur baru.

