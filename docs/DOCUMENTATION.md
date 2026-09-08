# 📚 Technical Documentation - GC Toxic Shield

Dokumen ini berisi panduan teknis mendalam mengenai arsitektur, modularitas kode, struktur data, dan rekayasa OS level yang diterapkan pada **GC Toxic Shield** edisi 2.0.0 (PySide6 Edition).

---

## 🏗️ 1. Architecture Overview

Aplikasi ini menggunakan pola **Publisher-Subscriber (Callback driven)** antar lapisan modul untuk meminimalisasi *blocking* *Thread* UI dan memastikan *Event Loop* tetap responsif di mesin yang lambat (*low-end PC*).

Aliran data (*Data Flow*):
1. **Mikrofon Desktop** menangkap suara dan dialirkan secara *chunked* ke `AudioEngine`.
2. `AudioEngine` mengirimkan data ke Google Speech API secara asinkron. Setelah kalimat terbentuk, *engine* memicu *callback* `on_transcription(text)`.
3. String transkripsi diserahkan ke `ToxicDetector`.
4. `ToxicDetector` memproses teks dengan pencocokan kata kotor (termasuk pemetaan fonetik) dan menyaring hasil menggunakan **Context Exclusions** (pengecualian konteks) untuk meminimalkan *false positive*.
5. Jika `ToxicDetector` mendeteksi adanya pelanggaran (`is_toxic=True`), `LoggerService` akan mencatat pelanggaran tersebut ke `.csv`, lalu meneruskannya ke `PenaltyManager` dan dikirimkan secara real-time ke **GC Toxic Shield Center** via `NetworkClient`.
6. `PenaltyManager` melihat histori *(state)* sesi komputer klien dan memutuskan tingkat sanksi (Warning atau Lockdown).
7. Modul `Overlay` dan `InstallerGuard` menerima sinyal untuk membekukan UI/UX OS menggunakan Win32 global hooks atau secara aktif menghentikan pengeksekusi program terlarang.

---

## 🧩 2. Module Breakdown

### `main.py`
Titik masuk (*Entry Point*) aplikasi klien. Menginisialisasi seluruh layanan (*Services*), menjalankan aplikasi dalam *System Tray* (Pystray), mencegah aplikasi hidup ganda (Global Mutex), serta menghubungkan fungsi Callback antar-modul.

### `app/audio_engine.py` (Cloud STT)
Menjalankan utas (`Thread`) pendengar mikrofon. 
- **`PyAudio`**: Merekam suara *frame-by-frame*.
- **`speech_recognition` (Google Speech)**: Menerjemahkan *ambient frame* menjadi teks secara asinkronus dengan bahasa `id-ID` (Indonesia).
- Memiliki resiliensi mandiri (menangkap *WinError 50 Device Not Found*) jika mikrofon dicabut secara mendadak.

### `app/detector.py` (Toxic Matching & Context Exclusion)
Menerima string hasil transkripsi dan mencocokkannya dengan *Wordlist*.
- Menggunakan Regex Boundary `(\bword\b)` untuk menghindari *false positive*.
- **Pemetaan Fonetik**: Mengkoreksi tipografi/plesetan *on-the-fly* (misal: "anjing" sering salah dengar menjadi "anting", "peler" menjadi "peeler").
- **Context Exclusions**: Menghindari pemblokiran pada frasa normal. Kata-kata seperti "kentang peeler" atau "dealer honda" tidak akan memicu pendeteksian toxic meskipun mengandung kata dasar yang masuk dalam daftar hitam.

### `app/installer_guard.py` (Process-Level Blocker)
Menggantikan sistem blokir berbasis registry lama yang tidak stabil.
- **Top-Level Settings Blocker**: Memantau instan kemunculan proses `systemsettings.exe` (Windows Settings) dan `control.exe` (Control Panel). Jika terdeteksi, proses akan dihentikan secara paksa menggunakan `psutil` dalam waktu milidetik.
- **Smart Triangulation Engine**: Pemblokiran file eksekusi berbahaya dipisah menjadi dua level:
  - **Specific Keywords** (e.g. `tiktok live studio`, `bytedance`): Langsung dihentikan di manapun lokasi eksekusinya.
  - **Generic Keywords** (e.g. `setup`, `installer`, `wizard`): Hanya dihentikan jika dijalankan dari lokasi tidak aman seperti folder `Downloads` atau `Desktop`. Jika dijalankan dari `Program Files`, installer dibiarkan berjalan normal.
- **Browser Whitelist**: Browser utama (Chrome, Edge, Firefox, dll) dimasukkan ke dalam daftar putih agar tidak terpengaruh oleh pelacakan judul jendela (mencegah browser ditutup secara tidak sengaja saat pengguna mencari kata kunci tersebut di internet).

### `app/network_client.py` (Network Synchronizer)
Mengatur komunikasi asinkron dua arah antara Klien dan Server.
- **MAC-Based Registration**: Mengirimkan daftar MAC Address lokal yang valid (menyaring multicast/fake MAC) beserta IP address ke Server pada fase registrasi awal.
- **Real-time Configuration Sync**: Menyinkronkan perubahan pengaturan dari server secara instan, termasuk penyelarasan kata sandi administrator (`change_password`) dan penyesuaian saklar `InstallerGuard`.
- **WOL Relayer & Remote Lock Receiver**: Menangani permintaan lockdown jarak jauh dari server (mendukung parameter pesan kustom) serta mampu merelay paket Wake-On-Lan (WOL) lewat semua adapter jaringan aktif menggunakan pustaka `psutil`.

### `app/ui_manager.py` (PySide6 Dashboard)
Dashboard visual admin klien yang telah sepenuhnya bermigrasi ke **PySide6**.
- Dilengkapi dengan *QSS (Qt Style Sheets)* modern bertema gelap.
- Menyediakan visualisasi VU Meter audio secara *real-time* berbasis RMS (Root Mean Square).
- Sinkronisasi asinkron penuh dengan konfigurasi filter zona (Proximity Filter).

### `app/updater.py` (Silent Auto-Updater)
Mengatur pembaruan otomatis aplikasi klien lewat API rilis GitHub.
- Pembaruan berjalan secara **senyap (Silent)** di latar belakang.
- Utas pembaruan mengekstrak arsip zip rilis terbaru menggunakan modul `zipfile` bawaan Python ke dalam direktori temporal, lalu membuat file batch (`.bat`) peluncur.
- File batch dieksekusi dengan bendera `CREATE_NO_WINDOW | DETACHED_PROCESS` agar command prompt hitam tidak berkedip di layar pengguna (tidak mengganggu game).
- Mengimplementasikan perulangan penyalinan (`xcopy` retry loop) sebanyak 5 kali untuk mengatasi kendala file terkunci saat overwrite exe.

---

## 🗃️ 3. Data Structures

Segala *setting* atau rekam histori klien akan disimpan secara luring (offline) di direktori `%APPDATA%` atau folder utama instalasi, khusus pada di direktori `assets/` dan `logs/`.

### A. `assets/word_list.json`
Menggunakan struktur *Dictionary* untuk kemudahan *lookup*.
```json
{
  "main": [
    "anjing",
    "babi",
    "peler"
  ],
  "mappings": {
    "anjing": ["anjir", "anj", "anting"],
    "peler": ["peeler"]
  },
  "context_exclusions": {
    "peler": ["honda", "yamaha", "dealer", "diler", "peeler", "kentang", "buah"]
  },
  "allowed_words": ["kontrol", "mengontrol"]
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
  "AdminPasswordHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "BlockInstaller": true,
  "BlockSettings": true
}
```

---

## 🛠️ 4. Build & Deployment Rules

1. Konfigurasi `build.py` menggunakan argumen kompilasi **PyInstaller** `["--onedir", "--windowed"]`. 
   - `--onedir` lebih unggul dari `--onefile` untuk PC warnet yang *caching*-nya dihapus setiap PC direstart (DeepFreeze/ShadowDefender). Mode *One-Dir* mencegah OS mengekstrak 60MB *library* temporal ke `%TEMP%` setiap *startup*, yang berisiko memperlambat komputasi.
   - `--windowed` mematikan *Command Prompt Console*, mencegah *hook* memori terekspos sehingga heuristik *Antivirus* lebih senyap.
   - Modul `customtkinter` dan `tkinter` dikecualikan secara keras (`--exclude-module`), sedangkan `PySide6` beserta submodul QtWidgets/QtCore/QtGui disertakan dalam hidden imports.

2. Skrip Instalasi menggunakan perintah unduhan asinkronus via PowerShell tanpa menyela *thread* operasi OS, me-restart diri sendiri menggunakan metode *Batch Script Suicide* pasca-ekstrak.

---

## 🛡️ 5. Security & Antivirus Handling (Warnet Non-Diskless)

GC Toxic Shield dirancang untuk berjalan di lingkungan warnet dengan tingkat intervensi pengguna yang tinggi.

### A. Penanganan Antivirus Pihak Ketiga (Avast, dsb)
Aplikasi ini menggunakan teknik *API Hooking* (Global Keyboard Hook) dan kompilasi *PyInstaller* yang perilakunya sering dianggap sebagai anomali (False Positive) oleh antivirus pihak ketiga yang ketat seperti Avast Antivirus.
- **Dilarang Keras Menggunakan Avast**: Instalasi GC Toxic Shield `install.ps1` akan otomatis dibatalkan secara keras jika mendeteksi *Service/Proses* Avast berjalan di latar belakang. Avast memiliki kemampuan "Self-Defense" level kernel yang akan senantiasa membunuh GC Toxic Shield.
- **Windows Defender (Bawaan)**: `install.ps1` sudah otomatis menambahkan _Exclusion_ (Pengecualian) Folder dan Proses ke dalam _Windows Defender_ untuk mengatasi proteksi bawaan OS tanpa masalah.

### B. Blokade Eksekusi Installer & Control Panel (Anti-Adware & Anti-Tampering)
Karena pengunjung warnet membutuhkan *Hak Akses Administrator* penuh untuk memainkan game tertentu (seperti *Point Blank*), mereka rentan mengunduh dan menginstal program *Adware* berisi Avast yang merusak stabilitas Warnet.
- **Blokir Proses (Installer & Settings)**: Opsi saklar **"Blokir Instalasi Program"** dan **"Kunci Pengaturan Windows"** di server dikirim secara real-time ke klien.
- Dibandingkan memanipulasi registry policies (`DisableMSI=2` atau `DisallowRun`) yang sering rusak/tidak presisi, klien menjalankan `InstallerGuard` secara asinkron dengan konsumsi CPU <0.1% untuk mendeteksi tanda tangan biner dan nama file instalan terlarang, membunuh prosesnya instan, dan memunculkan pop-up dialog peringatan di layar.

---
*- Author: Galang (GC Net Suite Developer).*
