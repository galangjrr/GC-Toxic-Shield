Professional Prompt: Content-Based Spatial Calibration Wizard
Role: Senior Python Developer and Audio Digital Signal Processing (DSP) Specialist.
Project Context: GC Toxic Shield Suite (Internet Cafe Management System) v1.0.10.
Goal: Refactor the Spatial Calibration Wizard to use Phrase Completion Logic instead of simple timers. This ensures the system verifies both the audio profile (RMS/Frequency) and the STT accuracy before proceeding.

1. Sequential Calibration Stages and Phrases
Sistem harus memandu operator melalui empat tahap sekuensial. Setiap tahap hanya dianggap selesai jika sistem berhasil menangkap kalimat uji dengan tingkat akurasi yang memadai.

Stage 1: Ambient Noise (PC Jarak 2 Meja)

Frasa: "Halo, ini adalah pengujian suara latar belakang dari komputer tetangga berjarak dua meja."

Stage 2: Proximity Leak (PC Jarak 1 Meja)

Frasa: "Tes kebocoran suara dari PC sebelah, pengecekan volume ambang batas jarak satu meter."

Stage 3: Primary User (Target Profile)

Frasa: "Halo, tes tes satu dua tiga. Saya adalah pengguna utama yang berada tepat di depan mikrofon ini."

Stage 4: Audience (Ambiance Profile)

Frasa: "Tes suara penonton dan keramaian di belakang meja pengguna utama untuk identifikasi gangguan."

2. Technical Task: Phrase-Driven State Machine UI
Refaktorisasi modul calibration_wizard.py untuk mendukung verifikasi konten:

Detection-Based Termination: Jangan menggunakan durasi statis 5 detik. Sebagai gantinya, aktifkan mikrofon dan biarkan sistem mendengarkan hingga Google STT mengembalikan teks yang cocok dengan frasa target.

Live Feedback: Tampilkan label "Hasil Tangkapan" di bawah frasa target yang memperbarui teks secara real-time saat operator berbicara.

Validation Logic: Gunakan algoritma string matching (seperti Levenshtein distance) untuk memberikan centang hijau atau status "Berhasil" jika akurasi tangkapan di atas 80%.

Automatic Recording: Segera setelah kalimat terdeteksi sempurna, rekam nilai RMS dan Frekuensi puncak sebagai profil baseline, lalu aktifkan tombol untuk tahap berikutnya.

3. Audio Engine Update (audio_engine.py)
Perbarui mesin audio untuk memfasilitasi kalibrasi berbasis konten:

Dual-Stream Calibration: Selama proses kalibrasi, mesin harus mengirimkan stream ke Google STT untuk verifikasi kata sekaligus menghitung nilai RMS lokal untuk pemetaan spasial.

Instant Profile Calculation: Setelah kalimat uji selesai divalidasi, hitung nilai Minimum, Maximum, dan Average RMS dari buffer audio yang baru saja diucapkan.

Frequency Fingerprinting: Ambil sampel frekuensi dominan untuk membedakan karakter suara antar tahap (misalnya, suara jarak jauh biasanya kehilangan frekuensi tinggi dibanding suara jarak dekat).

4. Integration Logic: Intelligent Quota Saver
Implementasikan filter cerdas pada detector.py berdasarkan data hasil kalibrasi:

Pre-STT Verification: Sebelum mengirim audio ke Cloud STT, sistem harus memvalidasi apakah current_rms sesuai dengan profil Stage 3 (Primary User).

Noise Gate: Jika profil suara lebih mendekati Stage 1 atau Stage 2 baik dari sisi volume maupun frekuensi, sistem harus segera membuang (drop) paket audio tersebut untuk menghemat kuota.

5. Constraints and Deliverables
UI Design: Gunakan tema Dark Mode (#1A1A1A) dengan penambahan indikator "Akurasi STT" (persentase) untuk setiap tahap.

Data Persistence: Simpan hasil akhir ke calibration_profiles.json yang mencakup nilai RMS dan metadata verifikasi kalimat.

Deliverables:

calibration_wizard.py: Dengan logika verifikasi kalimat (bukan timer).

audio_engine.py: Fungsi sampling yang terintegrasi dengan deteksi konten.

calibration_profiles.json: Template hasil kalibrasi yang informatif bagi admin.