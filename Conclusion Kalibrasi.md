# Analisis Potensi Bug & Failure pada "Dual-Criteria Calibration"

Berdasarkan rancangan `implementation_plan.md` terbaru (Kelulusan via **Akurasi 80%** ATAU **Word Count Limit 15 Kata**), berikut adalah evaluasi dan proyeksi **Bug, Error, dan Failure** yang sangat mungkin terjadi di lapangan (kondisi warnet sebenarnya).

---

## 1. Kegagalan Logika Kriteria B (False Positive Word Count)
**Deskripsi Masalah:**
Fitur ini mengandalkan *akumulasi 15 kata STT bebas* untuk menetapkan "Max Leakage RMS" pada Jarak 1/2 Meja. Namun STT Google terkadang berhalusinasi (menerjemahkan suara ketikan keyboard keras, suara tembakan game, atau derit kursi sebagai serpihan kata/gumaman). 
**Dampak:**
Jika lingkungan warnet sangat berisik oleh game (bukan suara mulut), STT bisa saja mengumpulkan 15 kata *halusinasi*. Saat itu tercapai, sistem akan LULUS dan mengambil sampel RMS dari ledakan game, bukan dari suara bocor vokal user sebelah. Ambang batas *Noise Gate* akan terekam salah (terlalu tinggi).
**Fakta di lapangan** 
Case Nomor 1, tidak valid. Karena selama sistem berjalan, tidak pernah mengalami hal seperti ini. hanya murni suara user PC lain dan penonton yang masuk ke mikrofon. Tidak ada halusinasi yang terjadi.

## 2. Bug Sinkronisasi Waktu Pengambilan RMS (Desync Metrics)
**Deskripsi Masalah:**
Wizard memanggil fungsi `audio_engine.get_last_metrics()` SECARA INSTAN tepat saat callback transkripsi (STT) mencapai kata ke-15.
**Dampak:**
Sistem STT Google memiliki _delay/latency_ sekitar 1-2 detik sejak user selesai bicara hingga teks dikembalikan ke layar. Jika user membaca ke-15 kata tersebut dan lalu **diam/berhenti berbicara** selama 2 detik menunggu STT merespons, maka `get_last_metrics()` akan menangkap RMS audio dari *detik keheningan/diam* tersebut!
Akibatnya, batas maksimum suara bocoran yang terekam adalah 0.001 (diam), sehingga saat user main sungguhan, filter STT akan selamanya tertutup.

## 3. Kegagalan Skalabilitas Perangkat (Premium Headset Infinite Loop)
**Deskripsi Masalah:**
Headset *gaming* premium modern (misal: Razer Kraken, HyperX dengan *active noise suppression* internal) dirancang sedemikian rupa agar mic-nya **benar-benar tuli** terhadap suara dari jarak 1-2 meter. 
**Dampak:**
Saat pengujian Stage 1 (Jarak 2 meja), pembicara berteriak secerdas apapun dari jauh TIDAK AKAN ditangkap STT (karena terblokir oleh hardware mic itu sendiri). Maka, **Akurasi akan selalu 0%** dan **Word Count akan selalu 0/15**. 
Kalibrasi Stage 1 tidak akan pernah lulus dan *stuck* di status "Mendengarkan..." selamanya, menghentikan seluruh proses kalibrasi aplikasi.
**Fakta di lapangan** 
Case Nomor 3, tidak valid. Karena headset yang digunakan adalah headset gaming biasa, bukan headset premium.

## 4. Kegagalan Stage 3 (Salah Tangkap Kriteria)
**Deskripsi Masalah:**
Stage 3 (Primary User) mewajibkan pengguna duduk tepat di depan Mic dan membaca frasa agar sistem mendapatkan *Baseline RMS Min* dan *Cetak Biru Frekuensi (Hz)*.
**Dampak:**
Jika aturan `IF (Akurasi >= 80%) OR (Word Count >= 15)` diaplikasikan pukul rata ke semua Stage, maka User Utama yang sengaja membaca asal-asalan (atau cadel) bisa memicu kelulusan lewat jalur Word Count (Kriteria B). Hal ini fatal, karena Stage 3 HARUS menggunakan Frasa Valid (Kriteria A) agar filter frekuensinya (*Frequency Fingerprint*) tidak terkontaminasi oleh noise yang asal bunyi.
**Klarifikasi**
Hal ini tidak akan terjadi, karena pada saat melakukan kalibrasi, yang melakukan kalibrasi adalah operator warnet, bukan user utama. Operator warnet akan membaca frasa yang sudah ditentukan dan akan mendapatkan akurasi yang tinggi karena duduk tepat di depan mikrofon.

---

---

### Kesimpulan Re-Evaluasi Lapangan:
Berdasarkan klarifikasi dan fakta lapangan yang telah Anda berikan, berikut adalah konfirmasi akhir mitigasinya:

1. **Case 1 (False Positive Word Count): OK.** Sistem tidak pernah berhalusinasi di warnet Anda. Kriteria B dijamin murni menangkap suara bocor (valid).
2. **Case 3 (Headset Premium): OK.** Penggunaan headset gaming biasa memastikan suara dari 1-2 meter masih akan masuk secara wajar, sehingga `Word Count` pasti akan bertambah.
3. **Case 4 (Stage 3 False-Pass): OK.** Operator yang melakukan kalibrasi secara profesional di depan mic utama memastikan Kriteria A (Akurasi 80%) pasti selalu mendominasi Tahap 3.

**SATU-SATUNYA MASALAH ESENSIAL: Case 2 (Bug Delay RMS / Desync).**
*Jeda waktu / latency* antara selesainya suara fisik dan kembalinya teks STT ke layar (sekitar 1-2 detik) menyebabkan fungsi pengambilan *"Instant RMS"* merekam *keheningan/ruangan sepi*, bukannya *teriakan user*. 

*Solusi yang akan dikerjakan ke dalam Sistem:*
Aplikasi akan diberikan memori sementara (Tracking History Array) saat mode kalibrasi/mendengarkan aktif. Memori ini akan *terus-menerus memantau* RMS yang masuk ke telinga mic. Saat `Word Count = 15` tercapai, sistem tidak akan mengecek RMS di detik itu, melainkan akan **mengeluarkan nilai Peak Tertinggi yang pernah terekam selama periode bicara tersebut**.
