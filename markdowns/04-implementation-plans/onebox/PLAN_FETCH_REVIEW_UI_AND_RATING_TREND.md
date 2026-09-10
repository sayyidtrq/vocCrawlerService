# Plan - Fetch Review UI and Rating Trend

Status: Draft implementation plan
Owner utama: OneBox
Pairing: Crawler untuk contract, counters, dan snapshot

## Goal

Menyederhanakan UI Fetch Review agar sesuai kemampuan teknis crawler dan tidak menyesatkan user. UI harus menjelaskan bahwa sistem menyisir review berdasarkan lokasi dan rentang waktu, sementara jumlah review adalah batas pengambilan.

## Prinsip UX

1. User memilih apa yang ingin dicapai, bukan parameter teknis Selenium.
2. Sistem harus jujur jika hasil baru kurang dari batas pengambilan.
3. Duplicate dan out-of-range ditampilkan sebagai hasil scan normal.
4. Progress job harus terlihat tanpa refresh manual.
5. Manual fetch tidak boleh diam-diam overlap dengan scheduler.

## Mode Fetch

### Update Terbaru

Default untuk operasional harian.

Field:

- Lokasi
- Rentang otomatis dari `last_seen_review_time` sampai hari ini
- Batas pengambilan, default 50

Copy UI:

- "Ambil ulasan terbaru sejak penarikan terakhir."
- "Jumlah adalah batas pengambilan, bukan jaminan ulasan baru."

### Backfill Awal

Untuk lokasi baru atau data historis belum lengkap.

Field:

- Lokasi
- Rentang awal
- Batch size: 300 sampai 500, bisa disembunyikan sebagai advanced setting

Copy UI:

- "Ambil riwayat ulasan bertahap. Jika data banyak, sistem akan membuat batch lanjutan."

### Rentang Khusus

Untuk audit atau recovery.

Field:

- Lokasi
- Dari tanggal
- Sampai tanggal
- Batas pengambilan
- Rating filter jika dibutuhkan

Copy UI:

- "Crawler tetap menyisir dari ulasan terbaru Google. Rentang lama mungkin membutuhkan scan lebih panjang."

## Layout Fetch Review

### Section Form

Urutan field:

1. Mode fetch
2. Lokasi
3. Rentang tanggal
4. Batas pengambilan
5. Filter rating
6. Action `Mulai`

Action sekunder:

- `Tambah ke antrean`
- `Dry run` hanya untuk admin/dev jika dibutuhkan

### Status Lokasi

Saat lokasi dipilih, tampilkan:

| Informasi | Sumber |
| --- | --- |
| Place ID | Master lokasi/Connection |
| Last successful crawl | Crawler state |
| Last seen review date | Crawler state |
| First run status | Crawler state |
| Scheduler aktif | OneBox scheduler |

### Riwayat Fetch

Kolom wajib:

| Kolom | Tujuan |
| --- | --- |
| Waktu | Kapan job dibuat |
| Cabang | Target bisnis |
| Mode | Update terbaru, Backfill, Rentang khusus |
| Batch | Trace ke crawler batch |
| Status | Queued/running/succeeded/partial/failed |
| Scan | Total disisir |
| Cocok / Batas | Review masuk filter dibanding batas |
| Baru | Inserted ke DB Crawler |
| Duplikat | Review sudah ada |
| Di luar rentang | Review tidak masuk window |
| Stop reason | Kenapa job berhenti |
| Aksi | Detail, ulangi, cancel jika running |

### Detail Job

Detail job perlu menampilkan:

- Request payload yang dikirim OneBox.
- Response Crawler.
- Timeline status.
- Counter lengkap.
- Error message asli jika ada.
- Link ke review yang berhasil masuk jika tersedia.

## Progress Bar

Progress tidak boleh hanya spinner.

Tampilkan:

- Status: Mengantre, Berjalan, Menyimpan, Selesai, Sebagian gagal, Gagal.
- Current counters: scanned, matched, inserted, duplicate.
- Estimasi sederhana: `scanned / scan_limit`.
- Jika scan limit tidak diketahui, gunakan indeterminate progress plus counter live.

## Rating Trend

Kebutuhan stakeholder:

- Melihat rating cabang minggu lalu vs minggu ini.
- Melihat perubahan rating bulanan, kuartalan, tahunan.

Masalah:

- Rating Google saat ini tidak bisa direkonstruksi akurat hanya dari review yang masuk.
- Average rating review internal bukan hal yang sama dengan rating Google official.

Solusi:

Crawler mengirim rating snapshot setiap job:

```json
{
  "target_id": "169:LOC-001",
  "source": "google_maps",
  "google_rating": 4.5,
  "google_review_count": 9422,
  "snapshot_at": "2026-09-01T08:00:00+07:00",
  "crawl_job_id": "uuid"
}
```

OneBox menyimpan snapshot dan menampilkan trend:

| Tab | Isi |
| --- | --- |
| Mingguan | Rating snapshot per minggu, delta dari minggu sebelumnya |
| Bulanan | Rating snapshot per bulan, delta dari bulan sebelumnya |
| Kuartalan | Ringkasan per kuartal |
| Tahunan | Trend high-level per tahun |

## Empty/Error State

Gunakan pesan yang actionable:

- "Belum ada baseline. Jalankan Backfill Awal untuk lokasi ini."
- "Job sedang berjalan untuk lokasi ini. Buka detail job atau tunggu selesai."
- "Tidak ada review baru. Crawler menyisir X review dan menemukan Y duplikat."
- "Google meminta login. Perbarui Selenium profile lalu jalankan ulang."
- "Worklist belum segar. Refresh worklist setelah menambah lokasi."

## Validation Rules

- Lokasi wajib punya `external_place_id` atau resolvable name.
- Date from tidak boleh lebih besar dari date to.
- Batas pengambilan maksimal 300 untuk manual regular/custom.
- Backfill memakai batch size maksimal 500.
- Jika ada job running target/window sama, tombol `Mulai` disabled atau diarahkan ke job existing.

## Definition of Done

- User paham kenapa hasil baru bisa kurang dari batas pengambilan.
- Duplicate tidak terlihat sebagai error.
- Job progress bisa dipantau.
- Rating trend memakai snapshot.
- Fetch Review tetap mengarah ke flow final: Crawler raw DB -> OneBox pull -> Kelola Review -> AI async.

---

# SPESIFIK: FIELD, AUTOFILL, VALIDASI, DoD

> Menjawab catatan: *"definition of done ini masih terlalu general, make it
> specific — validasi detailnya berupa apa, autofill saat apa, field form
> berubah jadi apa saja."*
>
> Semua `id` di bawah adalah **field yang benar-benar ada hari ini** di
> `app/views/Voc/fetchjobs.volt`, bukan nama karangan. Yang belum ada ditandai
> **BARU**.

## F.1 Inventaris field hari ini

| id | Label sekarang | Tipe | Nilai awal |
| --- | --- | --- | --- |
| `fj-loc-sel` | Cabang | select | kosong |
| `fj-single-target` | **Jumlah review** | number 1–300 | 50 |
| `fj-date-preset` | Rentang tanggal | select | Semua tanggal / 7 / 14 / 21 / 30 / Rentang sendiri |
| `fj-date-from`, `fj-date-to` | (tanpa label, aria saja) | date | kosong |
| `fj-sort` | Urutan pengambilan | select | Terbaru |
| `fj-single-status` | panel status lokasi | teks | "Belum ada cabang dipilih" |
| `fj-run` / `fj-queue-add` | Mulai / Tambah ke antrean | button | aktif |
| **`fj-mode`** | **Mode fetch** | **select** | **BARU** — Update Terbaru / Backfill Awal / Rentang Khusus |

**Keputusan istilah.** `fj-single-target` berganti label menjadi
**"Batas pengambilan"** dengan keterangan *"Batas biaya penyisiran, bukan
jumlah ulasan baru yang dijanjikan."* Alasannya: nilainya memang diteruskan
sebagai `max_reviews_to_collect`, dan kata "Jumlah review" membuat orang
membaca hasil "10/50" sebagai kegagalan padahal justru penyaringnya bekerja.
Field-nya **tidak dihapus** — menghapusnya menghilangkan satu-satunya rem biaya
yang dipegang operator.

## F.2 Field berubah jadi apa, per mode

`—` = tidak ditampilkan. **kunci** = terlihat tapi tidak bisa diubah, dengan
alasan tertulis di bawah field.

| Field | Update Terbaru (default) | Backfill Awal | Rentang Khusus |
| --- | --- | --- | --- |
| `fj-loc-sel` | wajib | wajib | wajib |
| `fj-date-preset` | **kunci** ke "Sejak penarikan terakhir" | **kunci** ke "Semua tanggal" | bebas, default "Rentang sendiri" |
| `fj-date-from` | terisi otomatis dari watermark, **kunci** | — | wajib diisi |
| `fj-date-to` | — (selalu "sampai sekarang") | — | opsional |
| `fj-single-target` | autofill **50**, bisa diubah | autofill **300**, bisa diubah | autofill **50**, bisa diubah |
| `fj-sort` | **kunci** ke "Terbaru" | **kunci** ke "Terbaru" | **kunci** ke "Terbaru" bila ada rentang; bebas bila "Semua tanggal" |
| `fj-run` | aktif bila lolos V1–V7 | aktif bila lolos V1–V7 | aktif bila lolos V1–V7 |

Alasan yang WAJIB tampil di bawah field terkunci — dikunci diam-diam adalah
cacat, bukan kerapian:

- `fj-sort` → *"Google Maps tidak punya penyaring tanggal. Rentang hanya bisa dikerjakan lewat urutan Terbaru."* (**sudah berlaku hari ini** lewat `fj-sort-hint`)
- `fj-date-from` pada Update Terbaru → *"Dimulai dari ulasan terbaru yang sudah masuk, dikurangi 1 hari sebagai jaga-jaga."*

## F.3 Autofill: kapan tepatnya, dari mana

Tiga pemicu, tidak lebih. Autofill yang berjalan di waktu lain akan menimpa
ketikan orang.

**A1 — saat `fj-loc-sel` berubah** (satu panggilan ke endpoint status lokasi):

| Yang diisi | Sumbernya | Kalau sumbernya kosong |
| --- | --- | --- |
| `fj-date-from` | watermark OneBox: ulasan terbaru cabang itu − 1 hari | mode dipaksa **Backfill Awal** (A2) |
| `fj-single-target` | 50 (Update Terbaru) / 300 (Backfill Awal) | — |
| `fj-single-status` | Place ID, tanggal ulasan terbaru, status jadwal | "Belum pernah ditarik" |

**A2 — saat cabang ternyata belum punya ulasan sama sekali:** mode otomatis
pindah ke **Backfill Awal** disertai pemberitahuan:
*"Cabang ini belum punya ulasan di OneBox. Mulai dengan Backfill Awal supaya penarikan berikutnya bisa lanjut dari titik yang jelas."*
Mode tetap boleh diubah manual — ini pemberitahuan, bukan larangan.

**A3 — saat `fj-mode` diubah:** field disusun ulang mengikuti F.2. Nilai yang
**pernah diketik sendiri** pada `fj-single-target` tidak ditimpa; yang ditimpa
hanya nilai yang masih berupa hasil autofill.

> **Yang belum bisa di-autofill hari ini.** `place_review_count` baru tersedia
> SESUDAH satu crawl berhasil, dan cursor durable di Crawler (P2) belum dibuat.
> Jadi jumlah batch backfill belum bisa dihitung di muka — lihat F.6.

## F.4 Validasi: kondisi, kapan diperiksa, pesan persis

Pesan tampil **di bawah field terkait**, bukan alert global. Alert global hanya
untuk V5 dan V6 karena penyebabnya di luar form.

| # | Kondisi | Diperiksa saat | Pesan | Efek |
| --- | --- | --- | --- | --- |
| V1 | `fj-loc-sel` kosong | submit | "Pilih cabang dulu." | `fj-run` disabled |
| V2 | Cabang tanpa Place ID | saat cabang dipilih | "Cabang ini belum punya Google Place ID. Lengkapi di layar Lokasi sebelum menarik ulasan." | `fj-run` disabled |
| V3 | `fj-date-from` > `fj-date-to` | saat salah satu berubah | "Tanggal awal melewati tanggal akhir." | `fj-run` disabled |
| V4 | Rentang Khusus, `fj-date-from` kosong | submit | "Rentang Khusus butuh tanggal awal. Kalau ingin semua tanggal, pakai mode Backfill Awal." | `fj-run` disabled |
| V5 | Ada jadwal berjalan untuk cabang sama | saat cabang dipilih **dan** submit | "Jadwal *nama* sedang menarik ulasan untuk cabang ini sejak *jam*. Menariknya bersamaan akan menyisir ulasan yang sama dua kali." | `fj-run` disabled + tautan ke Riwayat Fetch |
| V6 | Kuota harian `VOC_SCRAPE` habis | submit | "Kuota crawl harian sudah habis. Coba lagi besok atau tambah kuota di Pengaturan > Setup Parameter." | `fj-run` disabled |
| V7 | `fj-single-target` di luar 1–300 | saat diubah | "Batas pengambilan antara 1 dan 300." | `fj-run` disabled |
| V8 | Rentang > 365 hari (Rentang Khusus) | saat diubah | "Rentang lebih dari setahun akan menyisir sangat lama. Pertimbangkan Backfill Awal." | **peringatan saja**, `fj-run` tetap aktif |

V5 dan V6 **sudah berlaku di backend** (`jadwalSedangBerjalan()` dan penjaga
benefit). Yang belum ada: pemeriksaannya **sebelum** submit — hari ini orang
baru tahu setelah menekan tombol.

## F.5 Definition of Done — dapat diuji satu per satu

Tiap baris harus bisa dijawab ya/tidak oleh orang yang membuka layar, bukan
oleh yang membaca kodenya.

**Form**

1. Mode fetch jadi field pertama, default **Update Terbaru**.
2. Pilih cabang yang pernah ditarik → `fj-date-from` terisi sendiri dan terkunci, alasannya tertulis di bawahnya.
3. Pilih cabang tanpa ulasan → mode pindah sendiri ke Backfill Awal disertai pemberitahuan.
4. Ganti mode → susunan field berubah sesuai F.2 tanpa reload.
5. Label `fj-single-target` berbunyi "Batas pengambilan", bukan "Jumlah review".
6. Tidak ada field terkunci tanpa kalimat alasan di bawahnya.

**Validasi**

7. V1–V8 berperilaku persis seperti F.4.
8. V5 muncul **saat cabang dipilih**, bukan sesudah menekan Mulai.
9. Pesan muncul di bawah field terkait; hanya V5/V6 yang jadi alert.

**Hasil & keterbacaan**

10. Sesudah job selesai, layar menyebut angka: disisir, cocok, baru, sudah ada, di luar rentang.
11. Hasil "0 baru" dengan duplikat tinggi **tidak** memakai warna/kata kegagalan.
12. Alasan berhenti tampil sebagai kalimat, warnanya beda antara "sudah selesai" dan "masih ada sisanya". ✅ **sudah jalan di dev**
13. Batch banyak cabang dengan alasan berbeda menyebut jumlahnya ("1 dari 5 cabang …"). ✅ **kode siap, belum ada kasusnya di dev**

**Rating trend**

14. Snapshot tercatat dari penarikan **terjadwal**, bukan hanya manual.
15. Grafik tren menampilkan rating sendiri dan rating Google berdampingan. ✅ **kode siap**
16. Tooltip menyebut selisih cakupan dalam angka ("Belum tertarik: N ulasan"). ✅ **kode siap**
17. Cabang tanpa data Google tidak menampilkan legenda kosong. ✅ **kode siap**

## F.6 Yang sengaja ditunda, dan alasannya

| Item | Kenapa ditunda |
| --- | --- |
| Rencana batch backfill otomatis | Butuh `place_review_count` per cabang, baru ada sesudah satu crawl berhasil. Sebelum itu angkanya tebakan. |
| "Last seen review date" dari Crawler | P2 (cursor durable) belum dibuat. OneBox sementara memakai watermark dari datanya sendiri. |
| Tab Kuartalan & Tahunan pada tren | Perlu bucket per periode, dan titik snapshot harus rapat dulu. Tidak ada gunanya tab kuartal saat titiknya baru dua. |

## F.7 Findings UI yang digabung ke sini

Dipindahkan dari `crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md` karena
lingkupnya UI/UX:

| Finding asli | Dijawab di |
| --- | --- |
| DoD UI/UX belum ada | F.5 |
| "ulasan sepertinya dihilangkan aja" | F.1 — label diganti, field dipertahankan sebagai rem biaya |
| Pemberitahuan first run & scheduler | A2 dan V5 |
| Autofill form berdasarkan aturan | F.3 |
| Validasi form saat kurang | F.4 |

Aturan tambahan : 
- No ai slop , jangan gunakan 