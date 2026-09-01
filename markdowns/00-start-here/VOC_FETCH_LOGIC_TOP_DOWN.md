# VoC Fetch Logic - Top Down Review

Status: Draft untuk validasi product, architect, dan engineering.
Sumber awal: `C:\Users\sayyi\Downloads\VoC System Document Design.md`

## Executive Summary

Masalah utama Fetch Review saat ini bukan hanya bug teknis, tetapi salah model kerja: sistem terlalu berpusat pada "ambil N review". Untuk Google Maps, pendekatan count-first rawan duplikat, sulit mengambil review historis, dan membuat ekspektasi user keliru.

Model yang lebih sehat:

1. OneBox tetap menjadi control plane dan satu-satunya entry point user.
2. Crawler tetap menjadi execution plane untuk scrape Google Maps.
3. Fetch review harus window-first: lokasi, rentang tanggal, dan cursor menjadi dasar kerja.
4. Target jumlah review tetap ada, tetapi menjadi batas keamanan atau chunk size, bukan janji bahwa sistem pasti mendapat angka itu.
5. Duplikat adalah kondisi normal dalam crawling Google newest-first, bukan otomatis kegagalan.
6. Rating trend weekly, monthly, quarterly, yearly butuh snapshot rating berkala, bukan hanya kumpulan review.

## Kenapa Count-First Bermasalah

Contoh user meminta:

- Lokasi: Hermina Depok
- Rentang tanggal: 1 Agustus sampai hari ini
- Urutan: terbaru
- Jumlah: 50 review

Crawler Google Maps biasanya menyisir review dari yang terbaru. Kalau sistem berhenti saat item ke-50, beberapa hal bisa terjadi:

- Review dalam rentang tanggal ternyata kurang dari 50.
- Sebagian besar review sudah pernah masuk dari scheduler atau crawl manual sebelumnya.
- User mengira "50 review baru" akan masuk, padahal crawler hanya menyisir 50 item dan banyak yang duplicate.
- Untuk mengambil review lama, sistem harus melewati review baru yang sudah pernah disisir.

Kesimpulannya: count hanya membatasi biaya scan, bukan representasi kebutuhan bisnis.

## Mental Model Baru

### First Run atau Backfill

Dipakai saat lokasi baru pertama kali didaftarkan atau history belum lengkap.

Tujuan:

- Mengambil review historis sebanyak mungkin dalam rentang yang disepakati.
- Memecah kerja menjadi batch 300 sampai 500 review supaya worker tidak terlalu lama.
- Menyimpan progress dan continuation state supaya bisa dilanjutkan.

### Regular Delta

Dipakai setelah lokasi sudah punya baseline data.

Tujuan:

- Menangkap review baru sejak crawl terakhir.
- Menghindari overlap manual dan scheduler untuk target yang sama.
- Selesai cepat dan aman dipakai sebagai job rutin.

### Custom Date Range

Dipakai untuk audit, recovery, atau permintaan khusus.

Tujuan:

- Menyisir review pada rentang tanggal tertentu.
- Tetap transparan jika sistem harus melewati banyak duplicate atau review di luar rentang.

## Flow Top Down

1. Admin menambahkan master lokasi di OneBox.
2. OneBox menyimpan lokasi dan konfigurasi Connection.
3. OneBox mengirim worklist ke Crawler.
4. Crawler menyimpan target aktif beserta `external_place_id`, nama lokasi, tenant, dan cursor.
5. Admin atau scheduler membuat crawl job.
6. Crawler menyisir Google Maps berdasarkan mode, window, dan cursor.
7. Review mentah cepat masuk DB Crawler.
8. OneBox menarik raw review delta dari Crawler.
9. OneBox menyimpan review ke DB OneBox.
10. OneBox menjalankan labeling sentiment native.
11. Kelola Review langsung bisa dipakai.
12. User memilih single atau bulk review untuk AI analysis asynchronous.
13. Hasil AI mengupdate review atau Ticket existing.
14. Rating snapshot disimpan untuk trend mingguan, bulanan, kuartalan, dan tahunan.

## Boundary Crawler dan OneBox

| Area | Pemilik Utama | Catatan |
| --- | --- | --- |
| UI Fetch Review | OneBox | Form, validasi user, status history |
| Scheduler config | OneBox | OneBox menentukan jadwal dan target bisnis |
| Worklist target | OneBox -> Crawler | OneBox mengirim lokasi aktif dan konfigurasi |
| Scraping Google Maps | Crawler | Selenium, dedupe source, cursor, raw metadata |
| Raw review store | Crawler | Staging cepat sebelum OneBox pull |
| Review business model | OneBox | Kelola Review, RUD, ticket, permission |
| Sentiment native | OneBox | Rule/service existing diprioritaskan |
| AI analysis | Crawler/AI service async | Dipicu dari OneBox, hasil balik ke OneBox |
| Rating trend | OneBox, data dari Crawler | Butuh rating snapshot dari crawl |

## Field State Yang Perlu Dipahami

Jangan hanya pakai satu `last_fetched_at`. Minimal butuh pemisahan makna:

| Field | Arti |
| --- | --- |
| `last_successful_crawl_at` | Waktu job crawler selesai sukses |
| `last_seen_review_time` | Tanggal review terbaru yang ditemukan di source |
| `oldest_scanned_review_time` | Tanggal review terlama yang berhasil disisir pada job |
| `first_run_completed_at` | Penanda baseline historis pernah selesai |
| `cursor_source_review_id` | Identitas review terakhir untuk continuation/dedupe |
| `google_rating_snapshot` | Rating Google saat crawl berjalan |
| `google_review_count_snapshot` | Total review Google saat crawl berjalan |

## Risiko Kalau Tidak Direfactor

- Demo key process terlihat gagal karena hasil 0/target padahal crawler sebenarnya bekerja.
- Scheduler dan manual fetch saling overlap.
- Data historical sulit dilengkapi.
- Rating trend tidak akurat.
- User menganggap duplikat sebagai error sistem.
- Worker dipaksa scanning panjang tanpa progress yang bisa dijelaskan.

## Keputusan Yang Perlu Disepakati

1. Apakah istilah UI tetap "Jumlah ulasan" atau diganti menjadi "Batas pengambilan"? UI jumlah ulasan tidak perlu ditampilkan atau sebenernya bisaa ditampilkan jadi batas pengambilan, tapi pengambilannya dilakukan dari last fetched at jadi dari bawah (latest) ke atas . supaya tidak ada ulasan yang di tengah - tengah initial run dan manual crawler
2. Apakah first run wajib untuk setiap lokasi baru sebelum scheduler aktif? Ya wajib
3. Berapa batch size aman untuk backfill: 300, 400, atau 500? 400an aman
4. Di mana rating snapshot disimpan: Crawler saja, OneBox saja, atau keduanya? keduanya, SNAPSHOT sangat penting untuk TREN pada dashboard maupun grafik ulasan
5. Apakah manual fetch boleh memotong antrian scheduler untuk target yang sama? tidak boleh

## Rekomendasi Singkat

Untuk urgent demo, jangan rombak semua sekaligus. Lakukan refactor bertahap:

1. Ubah bahasa UI dan status supaya count tidak terlihat seperti janji hasil.
2. Tambahkan state cursor dan snapshot rating.
3. Terapkan lock per target agar manual dan scheduler tidak overlap.
4. Tambahkan mode `backfill`, `regular_delta`, dan `custom_range`.
5. Setelah itu baru optimasi scheduler dan trend KPI.
