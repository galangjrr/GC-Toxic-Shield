Sequential Spatial Calibration Wizard
Role: Senior Python Developer and Audio Digital Signal Processing (DSP) Specialist.
Project Context: GC Toxic Shield Suite (Internet Cafe Management System) v1.0.9.
Goal: Implement Spatial Sound Fingerprinting via a Sequential Calibration Wizard to eliminate false positives and optimize API Quota.

1. Calibration Phrases and Stages
AI Agent harus mengintegrasikan frasa spesifik berikut ke dalam logika antarmuka pengguna untuk setiap tahap pengujian:

Stage 1: Ambient Noise (PC Jarak 2 Meja)

Instruksi: Tangkap profil suara latar belakang.

Frasa: "Halo, ini adalah pengujian suara latar belakang dari komputer tetangga berjarak dua meja."

Stage 2: Proximity Leak (PC Jarak 1 Meja)

Instruksi: Tangkap ambang batas kebocoran suara jarak dekat.

Frasa: "Tes kebocoran suara dari PC sebelah, pengecekan volume ambang batas jarak satu meter."

Stage 3: Primary User (Target Profile)

Instruksi: Tangkap profil suara pengguna utama sebagai target penindakan.

Frasa: "Halo, tes tes satu dua tiga. Saya adalah pengguna utama yang berada tepat di depan mikrofon ini."

Stage 4: Audience (Ambiance Profile)

Instruksi: Tangkap gangguan suara dari area belakang pengguna.

Frasa: "Tes suara penonton dan keramaian di belakang meja pengguna utama untuk identifikasi gangguan."

2. Technical Task: Sequential State Machine UI
Lakukan refaktorisasi pada modul kalibrasi yang ada menjadi Step-by-Step Wizard menggunakan CustomTkinter:

Sequential Logic: Tampilkan instruksi frasa secara bergantian sesuai tahap yang aktif.

UI Control: Gunakan tombol dinamis "Mulai Tahap Ini" yang berubah menjadi "Selesai dan Rekam" saat proses sampling berjalan.

Visualisasi: Tampilkan VU Meter (Progress Bar) secara real-time untuk memvisualisasikan RMS (volume) yang sedang ditangkap agar operator mengetahui keaktifan mikrofon.

3. Audio Engine Enhancement (audio_engine.py)
Perbarui mesin audio untuk mendukung Short-Burst RMS dan Frequency Sampling:

Sampling: Buat fungsi untuk menangkap nilai Minimum, Maximum, dan Average RMS selama durasi 5 detik.

Frequency Analysis: Identifikasi peak frequencies selama pengucapan frasa untuk membedakan karakter suara user utama dengan suara latar belakang.

Threading: Pastikan proses penangkapan audio berjalan pada daemon thread agar antarmuka pengguna tidak mengalami pembekuan (freezing).

4. Integration Logic: Quota Saver
Implementasikan filter spasial pada detector.py sebelum mengirimkan data ke Google Cloud STT:

Volume Filter: Jika current_rms berada di bawah nilai leaking_baseline_max_rms (hasil Stage 2), sistem harus menghentikan proses transmisi data ke Cloud.

Frequency Match: Hanya kirim audio ke Cloud jika profil frekuensi cocok dengan target_user_profile (hasil Stage 3).

Objective: Mengurangi penggunaan kuota API pada suara yang teridentifikasi sebagai kebocoran suara atau noise dari PC lain.

5. Constraints and Standards
Data Persistence: Simpan hasil kalibrasi ke dalam file calibration_profiles.json dengan struktur data yang mencakup min_rms, max_rms, avg_rms, dan freq_peak untuk setiap tahap.

Error Handling: Implementasikan try-except untuk menangani kegagalan perangkat keras mikrofon (seperti WinError 50) guna memastikan sistem tetap stabil.

Visual Style: Gunakan tema Dark Mode yang konsisten dengan desain GC Toxic Shield Center v1.0.9 (Latar belakang: #1A1A1A).

Expected Deliverables
calibration_wizard.py: Class lengkap dengan sistem State Machine UI.

audio_engine.py (Update): Fungsi sampling RMS dan frekuensi baru.

detector.py (Logic Update): Logika filter spasial untuk efisiensi kuota.