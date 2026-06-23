# GC Toxic Shield — Features

## 🎚 Dynamic Multi-Zone Proximity Filter

### Konsep
Fitur ini memfilter *audio chunk* berdasarkan **energi suara (RMS — Root Mean Square)** sebelum dikirim ke Speech-to-Text engine. Setiap chunk dievaluasi energinya dan dicocokkan dengan zona yang ditentukan pengguna. Zona bertipe `PROCESS` meneruskan chunk ke antrean STT, sedangkan `IGNORE` langsung membuangnya.

### Zona Default

| Zona | Min RMS | Max RMS | Action | Keterangan |
|------|---------|---------|--------|------------|
| Background Noise | 0.00 | 0.05 | IGNORE | Suara latar / kipas AC |
| User Voice | 0.06 | 0.30 | PROCESS | Suara percakapan normal |
| Distant Yell | 0.31 | 0.45 | IGNORE | Teriakan dari kejauhan |
| User Yell | 0.46 | 1.00 | PROCESS | Teriakan langsung ke mic |

### Catatan Teknis
- **Perhitungan RMS** dilakukan dengan NumPy vectorized operation (~3μs per chunk). Tidak ada operasi file I/O di dalam loop audio.
- **Sinkronisasi zona** menggunakan Python GIL untuk atomic reference assignment — tidak diperlukan lock tambahan.
- **Fallback rule**: Jika RMS chunk tidak cocok dengan zona manapun, default action adalah `IGNORE`.

---

## 🚨 Extended Penalty System (15-Level Cascade)
Sistem ganda peringatan dan lockdown dengan eskalasi hingga 20 menit. Dilengkapi form kata sandi admin yang tersinkronisasi secara real-time dengan server.

---

## 🛡️ InstallerGuard & Settings Blocker (Process-Level Security)
Mengunci OS tanpa memanipulasi Windows Registry:
- **Block Windows Settings & Control Panel**: Memantau dan menghentikan secara instan `systemsettings.exe` dan `control.exe` saat diaktifkan oleh admin.
- **Smart Installer Blocker**:
  - **Specific Keywords**: Menghentikan aplikasi terlarang (seperti *TikTok Live Studio*) secara instan.
  - **Generic Keywords**: Membatasi `setup.exe` atau penginstal lainnya hanya ketika dijalankan di folder rawan seperti `Downloads` atau `Desktop`. Folder `Program Files` dikecualikan agar aplikasi legal tetap bisa terinstal.
- **Browser Whitelist**: Menghindari pemblokiran browser agar user tetap bisa berselancar dengan bebas tanpa penutupan paksa yang tidak sengaja.

---

## 📡 Non-Stop Cloud Detection
Speech-to-Text via Google Cloud dengan auto-recovery driver audio dan filter pengecualian konteks (*Context Exclusions*).

---

## 🔄 Silent Auto-Updater
Pembaruan aplikasi klien senyap tanpa jendela console hitam yang mengganggu pemain game, memanfaatkan skrip batch tersembunyi dan loop retry penyalinan berkas.
