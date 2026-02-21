# 🛡️ GC Toxic Shield V2
**Brand:** GC Net Security Suite  
**Version:** 2.1.0 (Google Speech Edition)  
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

### 🚀 Apa yang baru di V2?
Pada versi 2.1.0, *GC Toxic Shield* telah sepenuhnya bertransisi dari *offline engine* yang berat menjadi **Cloud-Based Online Engine (Google Speech Recognition)**.
- **⚡ Ultra-ringan:** Ukuran aplikasi turun drastis dari `~500MB` menjadi `~65MB`.
- **💻 Performa Maksimal:** Beban memori dan CPU ditekan hingga angka terkecil, memastikan perlindungan tidak mengganggu *Frame Rate (FPS)* game berat PC *client*.
- **🎙️ Smart Digital Gain:** Otomatis menyesuaikan volume dari mic *low-sensitivity* (misal: Fantech HQ 53).
- **📝 Pemetaan Fonetik Cerdas:** Otomatis menerjemahkan misheard words/plesetan (seperti *peeler* -> *peler*) menjadi deteksi akurat.

---

## 🛠️ Key Features

### 1. 📡 Real-time Non-Stop Engine
- **Cloud STT:** Mentranskripsi suara langsung dari mikrofon melalui Google Speech (id-ID).
- **Auto-Recover:** Secara agresif merecover koneksi *Audio Driver* jika terjadi *WinError 50* atau *disconnect*.
- **Overlap Protection:** Tidak mencatat pelanggaran bertumpuk saat jendela *Lockdown* sedang aktif.

### 2. 🛡️ Strict Wordlist Matching
- **Regex Boundaries:** Mencocokkan kata menggunakan *whole-word regex* (`\b`), mencegah *false positive* (contoh: "kontrol" tidak akan terdeteksi sebagai "kontol").
- **Hot-Reload:** Administrator dapat menambah/menghapus daftar kata melalui UI Dashboard, dan sistem *detector* akan diperbarui saat itu juga tanpa *restart*.

### 3. 🚨 Tiered Intervention System (Sanksi 3 Tingkat)
Sistem memiliki memori jumlah pelanggaran dan bereskalasi otomatis:
- **Pelanggaran 1-2:** Memunculkan *Warning Box* di tengah layar.
- **Pelanggaran 3:** Memicu *Lockdown Overlay* (Layar dihitamkan dengan pesan kutipan, blokir input *keyboard* sementara).
- **Admin Override:** *Lockdown Overlay* memiliki *password form* rahasia agar operator dapat membuka PC sewaktu-waktu secara manual.
- **Auto-Forgive:** Penghitungan pelanggaran akan direset kembali ke nol jika *user* berkelakuan baik (tidak melanggar) selama durasi tertentu (*default*: 60 menit).

### 4. 🧹 Self-Cleaning Logs & Privacy
- **Volatile Live Monitor:** Menampilkan teks transkripsi ke Admin Dashboard untuk dipantau secara langsung, lalu dibersihkan total setelah beberapa waktu (T3). 
- **Incident Storage:** Hanya kalimat yang secara positif *terbukti* mengeluarkan kata toxic yang akan diabadikan di `logs/toxic_incidents.csv`. *Privacy first!*

---

## ⚙️ Architecture & Build

Karena peralihan dari *offline* ke *online*, pastikan PC *Client* **memiliki akses internet stabil**.

**Kompilasi ke Executable:**
Modul `build.py` telah dikonfigurasi secara manual. Cukup jalankan:
```bash
python build_tools/build.py
```
Aplikasi akan dibungkus sebagai `GCToxicShield.exe` satu folder (*one-dir*) untuk startup sistem operasi yang lebih cepat.

---

## 🎮 Windows Defender & Anti-Cheat Compatibility
GC Toxic Shield menggunakan teknik **Win32 API Global Keyboard Hooks** untuk memblokir input *Alt+Tab* dan *Windows Key* saat *Lockdown Overlay* aktif. Teknik ini diwajikan untuk mencegah pengguna mencurangi sistem sanksi warnet.

Namun, meng-hook input secara global sering kali dicurigai oleh sistem keamanan:
1. **Windows Defender / Antivirus:** Karena aplikasi ini di-*build* dengan PyInstaller dan tidak memiliki sertifikat *Digital Signature* (Code Signing Certificate) berbayar, AV mungkin mendeteksinya sebagai *False Positive* (misal: `Trojan:Win32/Wacatac` atau serupa).
   - **Solusi:** Tambahkan folder `dist/GCToxicShield/` ke dalam **Exclusion / Pengecualian** Windows Defender di tiap PC Client.
   - *Architecture note:* Build versi *Production* menggunakan mode `--windowed` (tanpa console) dan `--onedir` (tanpa temp extraction) untuk meminimalkan deteksi heuristik sejauh mungkin.
2. **Game Anti-Cheat (Vanguard, XignCode, HackShield, dll):** Anti-cheat tingkat *Kernel (Ring-0)* seperti *Valorant Vanguard* sangat agresif terhadap *overlay* atau *hook* dari aplikasi pihak ketiga yang tidak tersertifikasi. 
   - Aplikasi ini didesain se-*pasif* mungkin (hanya meng-*hook* saat *lockdown* terjadi). 
   - **Solusi:** Pastikan folder aplikasi dimasukkan ke *whitelist* Anti-Cheat jika memungkinkan, atau jika masih terjadi konflik saat *lockdown*, pertimbangkan mematikan fitur *Lockdown Overlay* dan cukup gunakan *WarningBox* saja.


---

## 🔒 Security
- **UAC Manifest:** `.exe` secara inheren akan selalu meminta akses *Administrator* agar *Keyboard Hook* *Overlay System* dapan berjalan di atas game *Full-Screen*.
- **Dashboard Authentication:** UI Admin disembunyikan total di latar belakang. Saat aplikasi pertama berjalan/saat dibuka lewat tray, perlu *Password Authentication* untuk membukanya.
- **Secure Exit:** Menutup (*Exit*) aplikasi juga memerlukan *Password Administrator*.

---
*Developed for GC Net.*
