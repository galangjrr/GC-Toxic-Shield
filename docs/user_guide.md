# GC Toxic Shield — User Guide

## 🎚 Proximity Filter

### Membuka Tab
Klik **"🎚 Proximity Filter"** di sidebar kiri untuk membuka halaman konfigurasi filter.

### Membaca VU Meter
- **VU Meter** di bagian atas menampilkan tingkat energi suara (RMS) secara *real-time* saat Anda berbicara ke mikrofon.
- Nilai RMS ditampilkan secara numerik di sebelah kanan meter (misal: `RMS: 0.0342`).
- **Warna indikator:**
  - 🟢 **Hijau** = Suara Anda masuk zona `PROCESS` (diteruskan ke deteksi).
  - 🔴 **Merah** = Suara Anda masuk zona `IGNORE` (dibuang).
  - ⚪ **Abu-abu** = Suara tidak masuk zona manapun (default: dibuang).

### Mengatur Zona

#### Mengedit Zona
Setiap baris zona memiliki 4 kolom yang dapat diedit langsung:
1. **Nama Zona** — Nama deskriptif (misal: "Background Noise").
2. **Min RMS** — Batas bawah energi (0.00–1.00).
3. **Max RMS** — Batas atas energi (0.00–1.00).
4. **Action** — Pilih `PROCESS` (proses) atau `IGNORE` (abaikan).

> **Validasi Otomatis:** Jika Anda mengatur Min RMS lebih besar dari Max RMS, sistem akan otomatis mengoreksi Max RMS agar sama dengan Min RMS.

#### Menambah Zona Baru
Klik tombol **"➕ Add New Zone"** di pojok kanan atas area zona. Zona baru akan ditambahkan dengan nilai default yang aman.

#### Menghapus Zona
Klik tombol **🗑** di sebelah kanan baris zona. Zona akan langsung dihapus.

### Tips Kalibrasi
1. Buka tab **Proximity Filter** dan perhatikan VU Meter.
2. Diam sejenak — catat nilai RMS saat diam (biasanya 0.00–0.03).
3. Bicara normal — catat nilai RMS (biasanya 0.05–0.15).
4. Atur zona `Background Noise` (IGNORE) untuk menutupi nilai RMS saat diam.
5. Atur zona `User Voice` (PROCESS) untuk menutupi nilai RMS saat bicara normal.
6. Cek tab **Live Monitor** — pastikan transkripsi hanya muncul saat Anda berbicara.

### Persistensi
Semua perubahan zona **langsung tersimpan** ke `config.json` dan aktif tanpa restart. Konfigurasi akan otomatis dimuat kembali saat aplikasi dibuka.
