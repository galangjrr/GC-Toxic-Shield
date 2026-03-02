# 📚 Technical Documentation - GC Toxic Shield

Dokumen ini berisi panduan teknis mendalam mengenai arsitektur, modularitas kode, struktur data, dan rekayasa OS level yang diterapkan pada **GC Toxic Shield** edisi 1.0.

---

## 🏗️ 1. Architecture Overview

Aplikasi ini menggunakan pola **Publisher-Subscriber (Callback driven)** antar lapisan modul untuk meminimalisasi *blocking* *Thread* UI dan memastikan *Event Loop* tetap responsif di mesin yang lambat (*low-end PC*).

Aliran data (*Data Flow*):
1. **Mikrofon Desktop** menangkap suara dan dialirkan secara *chunked* ke `AudioEngine`.
2. `AudioEngine` mengirimkan data ke Google Speech API. Setelah kalimat terbentuk, *engine* memicu *callback* `on_transcription(text)`.
3. String transkripsi diserahkan ke `ToxicDetector`.
4. Jika `ToxicDetector` mengembalikan hasil `is_toxic=True`, maka `LoggerService` akan mencatat pelanggaran tersebut ke `.csv`, lalu meneruskannya ke `PenaltyManager`.
5. `PenaltyManager` melihat histori *(state)* komputer ini (apakah sudah melanggar ke-3, 6, 9 kali?) dan memutuskan sanksi (Warning atau Lockdown).
6. Modul `Overlay` dan `InstallerGuard` menerima sinyal dari `PenaltyManager` untuk membekukan UI/UX OS menggunakan Win32 global hooks atau membunuh pengeksekusi installer terlarang.

---

## 🧩 2. Module Breakdown

### `main.py`
Titik masuk (*Entry Point*) aplikasi. Bertugas menginisialisasi seluruh layanan (*Services*), menjalankan aplikasi dalam *System Tray* (Pystray), mencegah aplikasi hidup dua kali (Global Mutex), dan menggabungkan tautan fungsi Callback antar-modul.

### `app/audio_engine.py` (Cloud STT)
Menjalankan utas (`Thread`) pendengar mikrofon. 
- **`PyAudio`**: Merekam suara *frame-by-frame*.
- **`speech_recognition` (Google Speech)**: Menerjemahkan *ambient frame* menjadi teks secara asinkronus dengan bahasa `id-ID` (Indonesia).
- Memiliki resiliensi mandiri (menangkap *WinError 50 Device Not Found*) jika mikrofon dicabut secara mendadak.

### `app/detector.py` (Toxic Matching)
Menerima string hasil transkripsi dan mencocokkannya dengan *Wordlist*.
- Menggunakan Regex Boundary `(\bword\b)` untuk menghindari *false positive*.
- Mengimplementasikan Pemetaan Fonetik (Pembenaran Tipografi/Kekerabatan Suasana), cth: `anjing` sering salah dengar menjadi `anting` / `peler` sering diterjemahkan `peeler`. Modul ini mengkoreksi tipografi ini *on-the-fly* sebelum mencocokkannya.

### `app/penalty_manager.py` (The Punisher)
Manajer durasi dan hitungan (*Stateful*).
- Menyimpan jumlah dosis pelanggaran setiap sesi.
- Membaca level hukuman secara dinamis dari file JSON `config.json`.
- Menerapkan sistem *Auto-Forgive* (Mereset dosis dosa ke 0 jika anak tersebut diam dan tidak melanggar selama *X* menit berturut-turut).

### `app/overlay.py` & `app/desktop_guard.py` (OS Integrations)
Lapisan *Enforcement* terberat.
- `LockdownOverlay`: Memanggil *TopMost Fullscreen Window* berlatar hitam untuk menutupi game tanpa izin.
- `InstallerGuard`: Pemantauan secara *Real-Time* menggunakan WMI (low-priority thread). Memindai Metadata (Version Info/File Description) dari semua file eksekusi baru menggunakan `pefile`. Jika cocok dengan keyword terlarang (seperti 'setup', 'installer'), eksekusi pelakunya segera dibunuh dengan `psutil` lalu peringatan dikirimkan ke Center.

### `app/ui_manager.py`
*Dashboard* Visual berteknologi `CustomTkinter`. Tersinkronisasi secara asinkron dengan mesin (contoh: Membaca level volume *digital gain audio* dalam pola *Polling* 50ms untuk *progress-bar* VU Meter).

### `app/updater.py` & `install.ps1`
Sistem instalasi skala massal dan pendorong versi otomatis (*Continuous Deployment*). Berkomunikasi dengan parameter `/repos/{user}/{repo}/releases/latest` pada GitHub API.

---

## 🗃️ 3. Data Structures

Segala *setting* atau rekam histori klien akan disimpan secara luring (offline) di direktori `%APPDATA%` atau folder utama instalasi, khusus pada di direktori `assets/` dan `logs/`.

### A. `assets/word_list.json`
Menggunakan struktur *Dictionary* untuk kemudahan *lookup*.
```json
{
  "main": [
    "anjing",
    "babi"
  ],
  "mappings": {
    "anjing": ["anjir", "anj", "anting"],
    "babi": ["bawa", "bab"]
  }
}
```

### B. `assets/config.json`
Berisi variabel statis yang tidak disarankan terhapus pasca unduhan versi terbaru GitHub.
```json
{
  "sanction_list": [
    {
      "type": "WARNING",
      "message": "Kata kasar terdeteksi! (Peringatan 1/3)",
      "duration": 0,
      "warning_delay": 5
    },
    {
      "type": "LOCKDOWN",
      "message": "KOMPUTER TERKUNCI KARENA KATA KASAR!",
      "duration": 60,
      "warning_delay": 0
    }
  ],
  "PenaltyResetMinutes": 60,
  "AdminPasswordHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

---

## 🛠️ 4. Build & Deployment Rules
1. Konfigurasi `build.py` menggunakan argumen kompilasi **PyInstaller** `["--onedir", "--windowed"]`. 
   - `--onedir` lebih unggul dari `--onefile` untuk PC warnet yang *caching*-nya dihapus setiap PC direstart (DeepFreeze/ShadowDefender). Mode *One-Dir* mencegah OS mengekstrak 60MB *library* temporal ke `%TEMP%` setiap *startup*, yang berisiko memperlambat komputasi.
   - `--windowed` mematikan *Command Prompt Console*, mencegah *hook* memori terekspos sehingga heuristik *Antivirus* lebih senyap.

2. Skrip Instalasi menggunakan perintah unduhan asinkronus via PowerShell tanpa menyela *thread* operasi OS, me-restart diri sendiri menggunakan metode *Batch Script Suicide* pasca-ekstrak.

## 🛡️ 5. Security & Antivirus Handling (Warnet Non-Diskless)

GC Toxic Shield dirancang untuk berjalan di lingkungan warnet dengan tingkat intervensi pengguna yang tinggi.

### A. Penanganan Antivirus Pihak Ketiga (Avast, dsb)
Aplikasi ini menggunakan teknik *API Hooking* (Global Keyboard Hook) dan kompilasi *PyInstaller* yang perilakunya sering dianggap sebagai anomali (False Positive) oleh antivirus pihak ketiga yang ketat seperti Avast Antivirus.
- **Dilarang Keras Menggunakan Avast**: Instalasi GC Toxic Shield `install.ps1` akan otomatis dibatalkan secara keras jika mendeteksi *Service/Proses* Avast berjalan di latar belakang. Avast memiliki kemampuan "Self-Defense" level kernel yang akan senantiasa membunuh GC Toxic Shield.
- **SOP Pembersihan**: Mengingat sistem PC di tempat Anda *bukan* komputer Diskless (tidak di-*Deep Freeze*), maka jika peringatan Avast muncul saat instalasi, Anda diwajibkan melakukan uninstalasi penuh atas Avast dari menu *Control Panel -> Programs and Features*, kemudian _restart_ PC sebelum mencoba kembali.
- **Windows Defender (Bawaan)**: `install.ps1` sudah otomatis menambahkan _Exclusion_ (Pengecualian) Folder dan Proses ke dalam _Windows Defender_ untuk mengatasi proteksi bawaan OS tanpa masalah.

### B. Blokade Eksekusi Installer (Anti-Adware)
Karena pengunjung warnet membutuhkan *Hak Akses Administrator* penuh untuk memainkan game tertentu (seperti *Point Blank*), mereka rentan mengunduh dan menginstal program *Adware* berisi Avast yang merusak stabilitas Warnet.
- **Fitur Kunci Instalasi**: Terdapat opsi saklar (Toggle) **"Blokir Instalasi Program (MSI & EXE)"** di dalam tab GUI `Admin`.
- Menyalakan fitur ini akan menulis kunci ke *Registry Policies* (`DisableMSI=2` dan Explorer `DisallowRun`), mencegah *executable* dengan nama umum `setup.exe` atau `.msi` dijalankan oleh siapapun agar PC warnet aman dari program sampah, sembari tetap memanjakan pemain game berat.

---
*- Author: Galang (GC Net Suite Developer).*
