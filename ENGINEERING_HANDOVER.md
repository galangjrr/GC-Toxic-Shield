# 🛠️ Engineering Handover & Complete Architecture Specification
**GC Toxic Shield — PySide6 Client Application (v2.1.0 Obsidian Cyberpunk Edition)**

Dokumen ini ditulis secara komprehensif untuk seluruh perekayasa (*engineers*) dan pengembang (*developers*) yang akan melakukan pemeliharaan, pembaruan (*updates*), atau perbaikan (*bug fixes*) pada codebase **GC Toxic Shield**.

---

## 📌 Executive Summary & Core Objective

**GC Toxic Shield** adalah sistem pengawasan dan proteksi desktop real-time untuk lingkungan komputer (khususnya Warnet / PC Gaming Renting) yang berfungsi:
1. Mendeteksi kata-kata toksik/kasar via mikrofon secara otomatis menggunakan Cloud Speech-to-Text (STT) + Regex Phonetic Exclusions + NLP.
2. Memberikan sanksi berjenjang (Warning Overlay hingga Full OS Lockdown).
3. Mencegah manipulasi sistem oleh pengguna (*Anti-Tampering* & *Installer Blocking*).
4. Menyinkronkan konfigurasi dan status secara real-time dengan server pusat (**GC Toxic Shield Center**).

---

## 🏗️ 1. Architecture & Execution Flow

Aplikasi berbasis **Event-Driven Architecture** dengan kombinasi **PySide6 Qt Signal/Slot** dan **Multi-threading (Python threading)** untuk menjaga GUI tetap responsif di PC spesifikasi rendah (*low-end PC*).

### High-Level Data Flow:
```
[Microphone Audio Input]
         │
         ▼
 ┌────────────────┐
 │  AudioEngine   │  (PyAudio chunking + Google STT async thread)
 └───────┬────────┘
         │ emits on_transcription(text)
         ▼
 ┌────────────────┐
 │ ToxicDetector  │  (Phonetic Mappings + Context Exclusions + NLP fallback)
 └───────┬────────┘
         │ returns is_toxic, matched_words
         ▼
 ┌────────────────┐     ┌─────────────────┐
 │ LoggerService  ├────►│  Local CSV Log  │
 └───────┬────────┘     └─────────────────┘
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
 ┌────────────────┐                       ┌────────────────┐
 │ PenaltyManager │                       │ NetworkClient  │
 └───────┬────────┘                       └───────┬────────┘
         │                                         │
         ├──► [WARNING: Floating Dialog]           ▼
         └──► [LOCKDOWN: Topmost Win32 Hook]  [GC Toxic Shield Server]
```

---

## 🧩 2. Detailed Module Breakdown & Invariants

Berikut adalah rincian fungsional tiap file dalam proyek ini beserta **aturan kritis (invariants)** yang **TIDAK BOLEH DIRUSAK**:

### 1. `main.py` (Entry Point & Application Bootstrap)
- **Fungsi Utama**:
  - Privilege Elevation Check (`check_admin()`): Meminta ulang hak akses Administrator via `ShellExecuteW` (`runas`).
  - Global Mutex: Mencegah *multiple instances* aplikasi berjalan bersamaan di Windows.
  - Initializer Services: Memuat `AuthService`, `LoggerService`, `ToxicDetector`, `PenaltyManager`, `LockdownOverlay`, `AdminDashboard`, `NetworkClient`, dan `InstallerGuard`.
  - System Tray Integration: Menjalankan `pystray` icon di background thread yang dikaitkan dengan `PySide6` melalui `TrayCommunicator` Qt Signals.
  - Maintenance Mode Handler: Mengizinkan admin toggle mode perawatan untuk mematikan proteksi OS & audio engine secara sementara tanpa keluar dari aplikasi.
- ⚠️ **Aturan Kritis**:
  - `QApplication` **MUST** dibuat sebelum instansiasi widget PySide6 (`AdminDashboard`, `LockdownOverlay`).
  - Komunikasi antara `pystray` thread (background thread) dan PySide6 UI **MUST** menggunakan Qt Signals (`TrayCommunicator`). Jangan panggil fungsi GUI Qt langsung dari listener pystray!

---

### 2. `app/audio_engine.py` (Audio Capture & STT Engine)
- **Fungsi Utama**:
  - Merekam sampel audio mikrofon secara *chunked* menggunakan `PyAudio`.
  - Menerjemahkan sampel suara ke string teks bahasa Indonesia (`id-ID`) menggunakan Google Speech API via modul `speech_recognition`.
  - Menghitung RMS audio secara real-time untuk visualisasi **VU Meter** di UI Admin.
  - Fitur autosave & noise calibration peak reset.
- ⚠️ **Aturan Kritis**:
  - Menangani error `WinError 50` (Microphone Disconnected / Device Not Found) secara gracefully tanpa melempar unhandled exception yang bisa membuat app crash.
  - Thread audio berjalan asinkronus; callback `on_transcription` dieksekusi di luar thread GUI, pastikan thread-safe saat memicu pemrosesan selanjutnya.

---

### 3. `app/detector.py` & `app/nlp_detector.py` (Toxic Analysis & Context Exclusions)
- **Fungsi Utama**:
  - `ToxicDetector`:
    - Pencocokan Regex boundary `(\bword\b)` untuk mencegah matching parsial.
    - **Phonetic Mappings**: Mengoreksi plesetan/kesalahan dengar STT (misal: `"anjing"` terdeteksi `"anting"`).
    - **Context Exclusions**: Menghindari false positive pada kata berkonteks aman (contoh kata `"peler"` dikecualikan jika ada kata pendamping seperti `"honda"`, `"yamaha"`, `"kentang"`, `"peeler"`).
    - **Allowed Words / Whitelist**: Kata yang eksplisit diizinkan (`"kontrol"`, `"mengontrol"`, `"kumpul"`, dll).
  - `nlp_detector.py`:
    - Memuat model Scikit-Learn (TF-IDF + LinearSVC) `nlp_model.pkl` jika tersedia untuk klarifikasi konteks sekunder.
- ⚠️ **Aturan Kritis**:
  - Perubahan pada `assets/word_list.json` harus mempertahankan struktur key: `main`, `mappings`, `context_exclusions`, dan `allowed_words`.

---

### 4. `app/penalty_manager.py` (Sanction State Machine)
- **Fungsi Utama**:
  - Mengatur tahapan sanksi pengguna berdasarkan histori pelanggaran dalam sesi aktif (`WARNING` -> `LOCKDOWN`).
  - Mengelola reset timer pelanggaran (`PenaltyResetMinutes`).
  - Mengirim payload event pelanggaran ke server via `NetworkClient`.
  - Memanggil `LockdownOverlay` atau `WarningBox`.
- ⚠️ **Aturan Kritis**:
  - Reset timer pelanggaran harus thread-safe dan tidak menghapus hitungan sanksi aktif sebelum rentang waktu reset tercapai.

---

### 5. `app/overlay.py` (OS Lockout & Warning UI)
- **Fungsi Utama**:
  - `LockdownOverlay`: Window PySide6 Frameless Fullscreen `Qt.WindowStaysOnTopHint`.
  - Low-Level Win32 Hooks (`SetWindowsHookExW` untuk `WH_KEYBOARD_LL` & `WH_MOUSE_LL`): Memblokir kombinasi tombol OS seperti `Alt+Tab`, `Alt+F4`, `Ctrl+Alt+Del`, `Win Key`, dan klik mouse di luar layar lockdown.
  - `WarningBox`: Window peringatan melayang non-blocking.
  - `InstallerBlockDialog`: Dialog override password admin saat pengguna mencoba membuka installer terlarang.
- ⚠️ **Aturan Kritis**:
  - Penggunaan hook Win32 harus selalu di-unhook (`UnhookWindowsHookEx`) saat overlay ditutup agar OS pengguna tidak terkunci selamanya.
  - Operasi PySide6 GUI dalam overlay harus dieksekusi di Main Thread.

---

### 6. `app/installer_guard.py` (Real-Time Process Blocking & Protection)
- **Fungsi Utama**:
  - Memantau proses Windows secara kontinu menggunakan `psutil`.
  - **System Settings Blocker**: Membunuh `systemsettings.exe` (Windows Settings) & `control.exe` (Control Panel) secara instan jika opsi diaktifkan.
  - **Smart Triangulation Engine**:
    - *Specific Keywords*: Blokir langsung (contoh: `tiktok live studio`, `bytedance`).
    - *Generic Keywords*: Hanya diblokir jika proses berjalan di lokasi berisiko (folder `Downloads`, `Desktop`, `Temp`).
  - **Browser Whitelist**: Pengecualian untuk `chrome.exe`, `msedge.exe`, `firefox.exe` agar penelusuran web biasa tidak menutup browser.
  - **Admin Override Callback**: Memanggil `InstallerBlockDialog` saat installer teridentifikasi.
- ⚠️ **Aturan Kritis**:
  - Pengecekan proses harus ringan (<0.1% CPU). Gunakan sleep interval (misal 0.5s - 1.0s) pada loop background thread installer guard.

---

### 7. `app/network_client.py` (Client-Server Network Sync)
- **Fungsi Utama**:
  - Menghubungkan client ke server **GC Toxic Shield Center** via TCP Sockets.
  - Registrasi berbasis MAC Address lokal yang valid.
  - Menyinkronkan perubahan konfigurasi server secara real-time (ganti password admin, saklar installer guard, dsb).
  - Menerima remote lockdown command & WOL (Wake-On-LAN) relaying.
- ⚠️ **Aturan Kritis**:
  - Penanganan keterputusan koneksi (reconnection logic) harus otomatis mencoba terhubung kembali di background tanpa membekukan UI client.

---

### 8. `app/auth_service.py` (Authentication & Persistence)
- **Fungsi Utama**:
  - Membaca & menulis `assets/config.json`.
  - Hashing password admin dengan SHA-256.
  - Verifikasi kredensial login admin.
- ⚠️ **Aturan Kritis**:
  - Password admin tersimpan sebagai hash SHA-256, jangan simpan plaintext password dalam file konfigurasi.

---

### 9. `app/system_service.py` (OS Hardening & Priority Management)
- **Fungsi Utama**:
  - `set_high_priority()`: Mengatur prioritas proses client ke HIGH_PRIORITY_CLASS di Windows.
  - `harden_app_directory()`: Mengatur DACL/ICACLS folder instalasi agar pengguna biasa tidak dapat memodifikasi/menghapus file biner client.
  - Registry policy toggles untuk membatasi akses kontrol Windows jika diaktifkan.

---

### 10. `app/ui_manager.py` (PySide6 Admin Dashboard)
- **Fungsi Utama**:
  - Interface visual admin dengan styling Obsidian Cyberpunk QSS.
  - Tab navigasi:
    1. Status & VU Meter (Audio Monitoring)
    2. Wordlist & Mappings Manager
    3. Sanction Configuration
    4. Network Status & Server Pairing
    5. Microphone Calibration Wizard
    6. System Security & Settings
- ⚠️ **Aturan Kritis**:
  - Ketika memperbarui stylesheet / QSS dengan `f-string`, **Wajib meng-escape kurung kurawal ganda (`{{` dan `}}`)** agar PySide6 / Python tidak melempar `KeyError` atau `NameError`.

---

### 11. `app/updater.py` (Silent Background Auto-Updater)
- **Fungsi Utama**:
  - Memeriksa update dari GitHub Release API.
  - Mengunduh zip rilis di background, membuat launcher `.bat` dengan flag `CREATE_NO_WINDOW | DETACHED_PROCESS`.
  - Loop penyalinan (`xcopy` retry loop 5 kali) untuk menimpa executable yang sedang aktif tanpa memicu command prompt hitam yang mengganggu pengguna.

---

## 🗃️ 3. Configuration & Data Structures

### `assets/config.json` Schema Reference
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

## 🛠️ 4. Build, Packaging & Deployment Standard

1. **PyInstaller Command**:
   - Gunakan skrip spec `main.spec` atau `GC Toxic Shield.spec`.
   - Mode kompilasi: `--onedir --windowed`.
   - *Sebab*: `--onedir` lebih cepat pada PC warnet dengan DeepFreeze / ShadowDefender. `--windowed` mencegah jendela CMD hitam terbuka saat aplikasi berjalan.
   - Pengecualian modul: Exclude `tkinter` / `customtkinter` untuk menghemat ukuran file biner.

2. **Antivirus Exception Rules**:
   - Skrip `install.ps1` menambahkan folder instalasi ke Windows Defender Exclusion secara otomatis.
   - **Avast Antivirus**: Aplikasi menolak diinstal jika Avast aktif karena Avast Kernel Self-Defense merusak hook Win32 & killing process client.

---

## 🧪 5. Testing & Verification Checklist Before Release

Sebelum melakukan release / commit baru, engineer **WAJIB** menjalankan pengujian berikut:

1. **E2E UI & Event Test**:
   ```bash
   python test_e2e_pyside.py
   ```
   *Ekspektasi*: Aplikasi dapat menginisialisasi Qt, berpindah 6 tab tanpa error QSS, memicu warning box, dan keluar secara bersih.

2. **Installer Guard Test**:
   - Buka `control.exe` atau jalankan setup `.exe` dari folder `Downloads`.
   - *Ekspektasi*: Proses terdeteksi dan dihentikan instan (atau dialog override muncul).

3. **Lockdown Overlay Test**:
   ```bash
   python test_lockdown.py
   ```
   *Ekspektasi*: Screen terkunci, input keyboard/mouse terblokir, unlock via password admin berhasil unhook Win32 API.

---
*- Document created for Engineering Handover & Maintenance Safety.*
