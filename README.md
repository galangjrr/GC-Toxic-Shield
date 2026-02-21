# 🛡️ GC Toxic Shield
**Brand:** GC Net Security Suite  
**Version:** 1.0 (Google Speech Edition)  
**Target OS:** Windows 10/11 x64  
**Hardware Profile:** Optimized for maximum CPU efficiency (Integrated Graphics friendly)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg" alt="CustomTkinter">
  <img src="https://img.shields.io/badge/License-Proprietary-red.svg" alt="License">
</p>

## 📌 Project Overview
**GC Toxic Shield** adalah aplikasi sistem moderasi suara *real-time* yang dirancang khusus untuk lingkungan Internet Cafe (GC Net). Aplikasi ini memutar audio mikrofon pengguna di latar belakang dan mendeteksi penggunaan kata-kata kotor/toxic secara langsung.

Jika pelanggaran terdeteksi, sistem akan mengaktifkan mekanisme peringatan visual agresif atau mengunci layar (Lockdown Overlay) untuk menegakkan disiplin bermain secara preventif, memastikan lingkungan warnet tetap nyaman dan ramah.

### 🚀 Apa yang baru di Edisi 1.0?
*GC Toxic Shield* kini telah sepenuhnya bertransisi ke **Cloud-Based Online Engine (Google Speech Recognition)**.
- **⚡ Ultra-ringan:** Ukuran aplikasi dipangkas drastis dari `~500MB` menjadi `~65MB`.
- **💻 Performa Maksimal:** Beban statis memori dan CPU ditekan, tidak mengganggu *Frame Rate (FPS)* PC *client*.
- **🎙️ Smart Digital Gain:** Manajemen volume ganda untuk mic *low-sensitivity* langsung dari Admin Dashboard.

---

## 🛠️ Key Features

### 1. 🚨 Extended Penalty System (15-Level Cascade)
Sistem memiliki rekam jejak jumlah pelanggaran untuk setiap komputer (hingga riwayatnya diputihkan):
- **Sistem Ganda (2 Warning + 1 Lockdown):** Tiap kelipatan 3, layar pengguna akan dikunci penuh untuk melumpuhkan fungsi PC dalam rentang durasi 1 Menit hingga kemuncaknya di **20 Menit**. (Level 3, 6, 9, 12, 15).
- **Hardened Admin Override:** *Lockdown Overlay* memiliki *password form* tersembunyi. Admin dapat memencet tombol rahasia untuk membypass hukuman, _namun_ ini tidak akan mereset hitungan "dosa" anak tersebut kembali ke nol kecuali Admin memutihkannya sengaja ke panel Dashboard.
- **Auto-Forgive:** Pelanggaran akan diriset otomatis ke nol jika pengguna bersih dan bersikap baik selama 60 menit.

### 2. 🛡️ Surgical Desktop Guard & Settings Block
Mengunci OS tanpa menghancurkan UX Explorer:
- **Block Editing (Anti-Iseng):** Pengguna dapat me-*refresh* desktop tanpa *bug* ikon lenyap, namun dilarang keras membuat folder, menghapus, ataupun mengutip data asing ke layar Desktop (otomatis dihapus dalam hitungan ms oleh *Watchdog Engine* lalu dtegur visual).
- **Settings Lock:** Memutus akses ke App *Settings* Windows & *Control Panel* untuk melumpuhkan upaya *tampering*.

### 3. 📡 Non-Stop Cloud Detection
- **Cloud STT id-ID:** Sensor *Speech-to-Text* langsung melalui Google Cloud dan Regex Exact Word Boundary.
- **Auto-Recover:** Secara agresif merecover dan mereset port jika Audio Driver tiba-tiba mati/tercabut secara iseng (*WinError 50* handling).
- **Hot-Reload Wordlist:** Perbarui daftar "Kata Utama" dan "Kata Alias/Typo" dari antarmuka Admin secara instan.

### 4. 🔄 GitHub Auto-Updater & One-Click Deploy
- **1-Liner PowerShell Installer:** Cukup pastekan *script* pendek di PowerShell Administrator masing-masing PC klien, dan GC Toxic Shield akan mengunduh otomatis dari rilis repositori GitHub Anda dan menaruh pintasan di Desktop.
- **In-App Updater:** Terdapat tombol *Update* di dalam *Dashboard Admin*. Ia membaca _latest release_ dari GitHub dan dengan mulus me-rekonstruksi *executable* tanpa merusak konfigurasi JSON lokal dari Warnet.

---

## 💻 Instalasi Instan (Client PC)

Pemasangan ke komputer Klien warnet sangat mudah, tidak perlu *Copy-Paste* manual! Langkah-langkahnya:
1. Buka **PowerShell** pada PC Klien *(Wajib pilih "Run as Administrator")*.
2. Salin (*Copy*) dan Jalankan (*Paste*) baris perintah sakti di bawah ini:
   ```powershell
   iex (irm "https://raw.githubusercontent.com/galangjrr/GC-Toxic-Shield/main/install.ps1")
   ```
3. Tekan **Enter**. Aplikasi akan langsung terunduh, terbingkai di `C:\GC Net\`, dan memicu ikon mendarat lurus ke *Desktop* Klien secara ajaib dalam 5 detik!

---

## ⚙️ Architecture & Build
Modul `build.py` telah dikonfigurasi secara manual. Cukup jalankan perintah ini di VSCode/Terminal utama:
```bash
python build_tools/build.py
```
Aplikasi akan dibungkus sebagai `GCToxicShield.exe` tanpa bloatware sistem ke dalam folder `dist/GCToxicShield`.

---

## 🎮 Windows Defender & Anti-Cheat Compatibility
Aplikasi ini memanfaatkan pelacakan UI paksa yang menggunakan **Win32 API Global Keyboard Hooks** untuk memblokir aksi *Alt+Tab* dan tombol *Windows* saat hukuman *Lockdown* jatuh.

- **Windows Defender:** Tambahkan jalur instalasi (`C:\GC Net\GC Toxic Shield`) ke daftar pengecualian/whitelist Defender agar fitur Desktop Guard tidak teridentifikasi sebagai *Trojan* atau pembatasan sistem iseng.
- **Game Anti-Cheat (Vanguard):** Dirancang se-*pasif* mungkin (hanya meng-*hook* saat *lockdown* terjadi). Matikan *hooking* dan blokir manual dengan izin akses jika *Client* memainkan Valorant.

---

## 🔒 Security
- **UAC Manifest:** Memerlukan akses *Administrator* wajib.
- **Anti-Brute Force:** Pemasukan *Password* palsu di menu Lockdown akan berbuah hukuman penguncian paksa hingga 30 menit.
- **Dashboard Authentication:** Hanya dapat diakses dan ditutup total melalui *Password Admin* terotentikasi SHA256 (Default `admin123`).

---
*Developed for GC Net.*
