> **Language:**  Indonesia | [ English](README.en.md)

# GC Toxic Shield
**Brand:** GC Net Security Suite  
**Version:** 2.0.0 (PySide6 Edition)  
**Target OS:** Windows 10/11 x64  
**Hardware Profile:** Optimized for maximum CPU efficiency (Integrated Graphics friendly)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/GUI-PySide6-green.svg" alt="PySide6">
  <img src="https://img.shields.io/badge/License-Proprietary-red.svg" alt="License">
</p>

## Project Overview
**GC Toxic Shield** adalah aplikasi sistem moderasi suara *real-time* yang dirancang khusus untuk lingkungan Internet Cafe (GC Net). Aplikasi ini memutar audio mikrofon pengguna di latar belakang dan mendeteksi penggunaan kata-kata kotor/toxic secara langsung.

Jika pelanggaran terdeteksi, sistem akan mengaktifkan mekanisme peringatan visual agresif atau mengunci layar (Lockdown Overlay) untuk menegakkan disiplin bermain secara preventif, memastikan lingkungan warnet tetap nyaman dan ramah.

### Apa yang baru di Edisi 2.0.0?
*GC Toxic Shield* kini telah sepenuhnya bermigrasi ke **PySide6** untuk Client & Server, serta membawa pembaharuan arsitektur audio dan keamanan:
- **7-Stage Deterministic Audio Pipeline (>95% Akurasi):** Perombakan total alur tangkapan suara mic warnet. Dilengkapi *Noise Floor Auto-Calibration* (`adjust_for_ambient_noise`), *Proximity RMS Gate* penyaring teriakan tetangga sebelah meja (>1m), *Controlled Soft-Limiter (tanh)* batas 3x anti-clipping kotak, serta *Character Deduplication* untuk menangkap teriakan vokal panjang (misal: `kontooool`).
- **Windows Microphone Privacy Guard (Anti-Sabotase):** Menutup celah bypass anak-anak lewat ikon mic biru taskbar. Menutup paksa `systemsettings.exe` dalam 10ms dan mengunci saklar toggle *Microphone Access* via Windows Group Policy (`LetAppsAccessMicrophone = 1`) menjadi abu-abu permanen tanpa merusak registry (reversibel 100%).
- **Modern PySide6 UI:** Migrasi total dari CustomTkinter ke PySide6 dengan akselerasi GPU, rendering halus, dan QSS style yang konsisten.
- **InstallerGuard (Process-Level Blocker):** Pemblokiran Settings, Control Panel, dan program berbahaya dilakukan di level proses secara *real-time* tanpa merusak registry OS.
- **Browser Whitelist & Smart Triangulation:** Mengeliminasi *false positives* dengan mengecualikan browser utama (Chrome, Edge, Firefox, dll) dari pendeteksian judul jendela, serta memisahkan deteksi installer spesifik (e.g. *TikTok Live Studio*) dari installer umum berdasarkan lokasi aman (`Program Files`).
- **GC Toxic Shield Center Persistence:** Manajemen PC grid di server kini persisten berbasis database MAC Address & IP dalam `server_config.json`. Menghindari daftar PC acak dengan pengurutan nama alami (*natural sorting*), serta mendukung CRUD PC langsung dari GUI Dashboard.
- **Silent Auto-Update:** Klien memperbarui diri secara asinkron lewat skrip batch tersembunyi (`CREATE_NO_WINDOW`) dengan mekanisme retry `xcopy`. Bebas dari kedipan command prompt hitam yang mengganggu permainan user.
- **Multi-Adapter Wake-On-Lan (WOL):** Sinyal bangun dikirim ke seluruh adapter jaringan aktif (multi-broadcast IP) pada port 7 & 9 menggunakan pustaka `psutil` untuk keandalan maksimal.

---

## Key Features

### 1. Extended Penalty System (15-Level Cascade)
Sistem memiliki rekam jejak jumlah pelanggaran untuk setiap komputer (hingga riwayatnya diputihkan):
- **Sistem Ganda (2 Warning + 1 Lockdown):** Tiap kelipatan 3, layar pengguna akan dikunci penuh untuk melumpuhkan fungsi PC dalam rentang durasi 1 Menit hingga kemuncaknya di **20 Menit**. (Level 3, 6, 9, 12, 15).
- **Hardened Admin Override & Password Sync:** *Lockdown Overlay* memiliki *password form* tersembunyi. Admin dapat menggunakan kata sandi admin yang tersinkronisasi secara *real-time* dari Server untuk membuka kunci.
- **Auto-Forgive:** Pelanggaran akan diriset otomatis ke nol jika pengguna bersih dan bersikap baik selama 60 menit.

### 2. Process-Level InstallerGuard & Windows Anti-Sabotage
Perlindungan sistem tingkat tinggi tanpa merusak integritas sistem operasi:
- **Lock Windows Settings & Control Panel:** Mematikan instan `systemsettings.exe` dan `control.exe` saat fitur aktif, mencegah pengunjung iseng mengotak-atik setelan Windows.
- **Microphone Privacy Lock:** Kunci saklar toggle *Microphone Access* di menu Settings Windows jadi abu-abu permanen (*"Managed by your organization"*). Klik pada ikon mic biru di taskbar mental instan dalam hitungan milidetik.
- **Smart Installer Blocker:**
  - **Kata Kunci Spesifik:** Menutup langsung aplikasi terlarang (e.g. *TikTok Live Studio*, *Bytedance*, *TikTok*) di manapun lokasinya.
  - **Kata Kunci Umum:** Memblokir `setup.exe` atau installer lainnya hanya jika dijalankan di folder rawan seperti `Downloads` atau `Desktop`. Jika dijalankan di `Program Files`, installer dibiarkan berjalan normal.
- **Browser Whitelist:** Membiarkan semua browser populer berjalan bebas, mencegah penutupan browser secara tidak sengaja saat pengguna mencari konten terkait kata kunci di web.

### 3. 7-Stage Audio Detection Pipeline (>95% Accuracy)
- **Acoustic Auto-Tune:** Mengukur kebisingan dasar ruangan (AC, kipas, keyboard mekanik) secara mandiri saat mic pertama kali dibuka.
- **Hardware-Level Noise Gate:** Evaluasi energi RMS linear langsung di memori; membuang desis lantai (<0.05) dan suara bocor PC sebelah (0.301–0.450) sebelum dikirim ke internet.
- **Controlled Soft-Limiter (tanh):** Pembatasan gain maksimal 3x dengan lengkungan gelombang sinus alami untuk mencegah *square-wave clipping* yang merusak akurasi Google STT.
- **Plafon Durasi Adaptif (8s):** Memotong kalimat per 8 detik untuk mencegah rekaman gantung di lingkungan berisik warnet.
- **Vocal Deduplication:** Reduksi karakter berulang otomatis (`anjinggg` → `anjing`, `kontooool` → `kontol`).
- **Zero False-Positive Context Guard:** Konteks aman (`player`, `dealer honda`, `peeler kentang`) dievaluasi pada teks asli tanpa mutasi string.
- **Auto-Recover:** Merecover dan mereset port jika Audio Driver tiba-tiba mati/tercabut secara fisik (*WinError 50* handling).

### 4. Silent Auto-Updater
- **1-Liner PowerShell Installer:** Cukup pastekan *script* pendek di PowerShell Administrator masing-masing PC klien untuk instalasi instan.
- **Silent In-App Updater:** Klik tombol update di Admin Center untuk mengunduh, mengekstrak, dan menyalin berkas pembaruan klien secara senyap di latar belakang. Klien akan melakukan auto-restart tanpa mengganggu game yang sedang berjalan.

### 5. Dynamic Multi-Zone Proximity Filter
Mengevaluasi energi (RMS) setiap *audio chunk* secara *real-time* dan memfilter berdasarkan zona energi yang ditentukan pengguna:
- **Zone Builder UI:** Buat beberapa zona batas energi (misal: *Background Noise* → IGNORE, *User Voice* → PROCESS).
- **Real-time VU Meter:** Lihat representasi visual tingkat RMS saat berbicara, lengkap dengan indikator warna zona (hijau = PROCESS, merah = IGNORE).
- **Zero-Latency Sync:** Perubahan zona langsung diterapkan ke engine audio tanpa *restart* — tanpa operasi I/O di *hot path*.

### 6. GC Toxic Shield Center (Server GUI)
Pusat kendali modern berbasis PySide6 untuk mengontrol semua PC Klien:
- **CRUD PC Grid:** Tambah, edit (Ubah nama, IP, MAC), atau hapus PC secara manual melalui dialog UI yang elegan.
- **Remote Lock Custom Message:** Admin dapat mengunci PC tertentu secara remote dan menyisipkan pesan kustom langsung ke layar klien (misal: "Harap tenang saat bermain").
- **Natural Sorting:** Grid PC tersusun rapi secara numerik (`PC-1`, `PC-2`, `PC-10`).
- **Analisis & Ekspor Data:** Catatan pelanggaran dapat diekspor langsung ke format **CSV** atau **Markdown** dengan sekali klik.
- **Sanction JSON Sync & Blocker Control:** Sunting konfigurasi sanksi secara visual dan kontrol saklar fitur InstallerGuard langsung secara terpusat.

---

## Instalasi Instan (Client PC)

Pemasangan ke komputer Klien warnet sangat mudah, tidak perlu *Copy-Paste* manual! Langkah-langkahnya:
1. Buka **PowerShell** pada PC Klien *(Wajib pilih "Run as Administrator")*.
2. Salin (*Copy*) dan Jalankan (*Paste*) baris perintah sakti di bawah ini:
   ```powershell
   iex (irm "https://raw.githubusercontent.com/galangjrr/GC-Toxic-Shield/main/install.ps1")
   ```
3. Tekan **Enter**. Aplikasi akan langsung terunduh, terbingkai di `C:\GC Net\`, dan memicu ikon mendarat lurus ke *Desktop* Klien secara ajaib dalam 5 detik!

---

## Project Structure

```text
GC-Toxic-Shield/
├── app/             # Application core modules
├── assets/          # Icons, word_list.json, config.json, sanksi_custom.json
├── build_tools/     # PyInstaller build.py & UAC manifest
├── docs/            # Handover, PRD, diagrams & calibration/
├── scripts/         # Dev utilities & emergency_repair.ps1
├── tests/           # All test suites + conftest.py
├── install.ps1      # Client one-liner installer
├── main.py          # Main entry point
├── README.md        # Project documentation
├── requirements.txt # Dependencies
└── .gitignore       # Build/binary ignore rules
```

---

## Architecture & Build

Modul `build.py` telah dikonfigurasi menggunakan PyInstaller. Cukup jalankan perintah ini di VSCode/Terminal utama:
```bash
python build_tools/build.py
```
Aplikasi akan dibungkus sebagai `GCToxicShield.exe` tanpa bloatware sistem ke dalam folder `dist/GCToxicShield`.

---

## Windows Defender & Anti-Cheat Compatibility
Aplikasi ini memanfaatkan pelacakan UI paksa yang menggunakan **Win32 API Global Keyboard Hooks** untuk memblokir aksi *Alt+Tab* dan tombol *Windows* saat hukuman *Lockdown* jatuh.

- **Windows Defender:** Tambahkan jalur instalasi (`C:\GC Net\GC Toxic Shield`) ke daftar pengecualian/whitelist Defender agar fitur-fitur pemantauan proses tidak teridentifikasi sebagai *false positive*.
- **Game Anti-Cheat (Vanguard):** Dirancang se-*pasif* mungkin (hanya meng-*hook* saat *lockdown* terjadi). Matikan *hooking* dan blokir manual dengan izin akses jika *Client* memainkan Valorant.

---

## Security
- **UAC Manifest:** Memerlukan akses *Administrator* wajib.
- **Anti-Brute Force:** Pemasukan *Password* palsu di menu Lockdown akan berbuah hukuman penguncian paksa hingga 30 menit.
- **Dashboard Authentication:** Hanya dapat diakses dan ditutup total melalui *Password Admin* terotentikasi SHA256 (Default `admin123`).

---
*Developed for GC Net.*
