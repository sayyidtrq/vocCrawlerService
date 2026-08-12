# Insiden: Fetch Jobs ditolak `TARGET_NOT_FOUND` di dev

**Tanggal:** 11–12 Agustus 2026
**Dampak:** seluruh 13 cabang VoC di dev tidak bisa ditarik reviewnya
**Status:** selesai. Data dibereskan, dua perbaikan kode masuk (`1ae5f8a5ba`)

---

## 1. Ringkasan

Layar Fetch Jobs menolak penarikan dengan:

> Cabang ini belum dikenal Crawler System. Daftar target di Crawler perlu
> disegarkan dari Worklist OneBox lebih dulu.

Kalimat itu **salah menuduh**, dan saran yang dikandungnya justru memperburuk.
Cabangnya dikenal Crawler. Yang terjadi: cabangnya berstatus **nonaktif** di
mata Crawler, karena OneBox mengirimkan status itu sendiri lewat worklist.

Penyebab akhirnya bukan bug pada kode fetch jobs, bukan pula akibat merge mana
pun. Yang tertinggal adalah **bangkai dari masalah yang sudah selesai**: koneksi
tersuspend karena service token lama, tokennya lalu diperbaiki, tetapi status
suspend-nya tidak pernah dibersihkan. Sinkronisasi worklist berikutnya
memindahkan bangkai itu ke Crawler.

---

## 2. Garis waktu (UTC)

| Waktu | Kejadian |
|---|---|
| 11 Agu 03:14:25 | 13 koneksi `PVD99` tersuspend `CNS2`, `Error` 12–19, `Remarks` = `HTTP error 401: INVALID_SERVICE_TOKEN` |
| 11 Agu ~03:2x | service token dirotasi ke yang baru (sidik SHA-256 `8d1c293b9f86`) |
| 11 Agu 03:27 | batch `beb57fcf` Five Coffee Forest **berhasil 10/10** |
| — | `StatusId=CNS2` tidak pernah dibersihkan; tidak ada yang membersihkannya |
| 12 Agu 06:07 | `refresh_worklist --company-id 3` dijalankan → 14 fetched, 14 upserted |
| 12 Agu | penarikan mulai ditolak `TARGET_NOT_FOUND` |
| 12 Agu 06:55 | SQL unblock dijalankan → 13 cabang kembali `CNS1`, `Error` 0 |
| 12 Agu | `refresh_worklist` diulang → penarikan normal kembali |

Baris ketiga adalah kunci pembacaannya: **crawl berhasil 13 menit sesudah error
401 tercatat.** Itu membuktikan tokennya sudah benar saat itu, dan `Remarks` yang
terbaca hari ini hanyalah catatan lama.

---

## 3. Rantai sebab

1. Service token lama ditolak Crawler (`401 INVALID_SERVICE_TOKEN`).
2. Tiap kegagalan menaikkan `Connection.Error`. Lewat tiga kali,
   `Messaging.php` menyuspend koneksinya:
   ```php
   if ($conn->Error > 2) { $conn->StatusId = 'CNS2'; }
   ```
3. Token diperbaiki. Penarikan **manual** jalan lagi — `crawlStart` memakai
   koneksinya langsung dan tidak pernah melihat `StatusId`.
4. `StatusId=CNS2` tertinggal. Tidak ada proses yang membersihkannya.
5. Worklist memetakan `crawl_enabled` dari `StatusId`:
   ```php
   'crawl_enabled' => ((string) $conn->StatusId === 'CNS1'),   // versi lama
   ```
6. `refresh_worklist` mengirim `crawl_enabled=false` untuk 13 cabang.
7. Crawler menandai lokasinya disabled → enqueue ditolak.

Selama langkah 4 dan 5 belum tersentuh, keadaan ini bisa tidur berhari-hari lalu
meledak pada sinkronisasi berikutnya — jauh dari perubahan apa pun yang
menyebabkannya.

### Kenapa pesan errornya menyesatkan

Crawler menjawab dengan **tiga** kemungkinan sekaligus:

```
"One or more crawl targets are absent, disabled, or outside this tenant."
```

OneBox hanya menerjemahkan yang pertama, lalu menyarankan menyegarkan worklist.
Pada penyebab kedua — `disabled` — menyegarkan justru **memantapkan**
keadaannya, karena yang tersinkron adalah status nonaktifnya. Saran itu
mengarahkan orang menjauh dari sebabnya, dan pada kasus ini justru yang memicu
kerusakannya.

---

## 4. Perbaikan kode

Commit `1ae5f8a5ba`, di branch **`feature/DNGO19-3420_VOC-Fetch-Jobs-Crawl`**.

**Belum masuk `feature/voc`, jadi belum ada di dev.** Yang memulihkan dev pada
insiden ini adalah perbaikan DATA (langkah 4–5 di runbook), bukan perbaikan kode
ini. Selama commit ini belum ter-merge, jebakannya masih hidup: suspensi
berikutnya akan mematikan crawl dengan cara yang sama.

**`crawl_enabled` lepas dari `StatusId`.**
```php
'crawl_enabled' => ((int) $conn->Enabled === 1 && $kind === self::KIND_LOCATION),
```
`StatusId` menjawab "boleh disapu penjadwal Messaging?" — pertanyaan yang tidak
ada hubungannya dengan "boleh di-crawl?". Kompetitor tetap dikecualikan lewat
`kind`, bukan lewat efek samping status.

**Pesan `TARGET_NOT_FOUND` menyebut ketiga kemungkinan** berurut dengan
tindakannya masing-masing, dan menyatakan terang bahwa menyegarkan worklist
tidak menolong kalau sebabnya cabang nonaktif.

---

## 5. Runbook: kalau ini terjadi lagi

### Langkah 1 — BACA dulu, jangan bertindak

Jalankan di DB environment yang bermasalah (dev = `onecloud_rel`):

```sql
SELECT Id, Enabled, StatusId, Error,
       JSON_UNQUOTE(JSON_EXTRACT(Options,'$.location.branch_name')) AS Cabang,
       JSON_UNQUOTE(JSON_EXTRACT(Options,'$.company_id'))           AS CompanyId,
       JSON_UNQUOTE(JSON_EXTRACT(Options,'$.onebox_location_id'))   AS LocationId,
       JSON_UNQUOTE(JSON_EXTRACT(Options,'$.kind'))                 AS Kind,
       ModifyDate, Remarks
  FROM Connection
 WHERE ProviderId = 'PVD99' AND SiteId = 169
 ORDER BY Id;
```

`Remarks` menyebut sebabnya sendiri. **Jangan menjalankan perbaikan apa pun
sebelum membacanya** — sebab yang berbeda butuh perbaikan yang berbeda, dan
perbaikan yang salah memperpanjang gangguannya.

### Langkah 2 — Cocokkan gejala dengan sebab

| Yang terbaca | Sebab | Tindakan |
|---|---|---|
| `Remarks` = `401 INVALID_SERVICE_TOKEN`, `ModifyDate` **baru** | service token tidak sah | periksa sidik token (di bawah), rotasi kalau lama |
| `Remarks` = `401`, `ModifyDate` **lama**, token sudah benar | bangkai — sebabnya sudah beres | cukup unsuspend |
| `Remarks` = `TENANT MISMATCH ... company_id=N` | `Options.company_id` salah | setel ke company yang benar (site 169 → company 3) |
| `StatusId=CNS2`, `Remarks` kosong | disuspend dari luar VoC | telusuri, lalu unsuspend |
| Semua `CNS1` tapi tetap ditolak | bukan soal status | periksa `onebox_location_id` terisi, dan cabang pernah tersinkron |
| `Kind=competitor`, `CNS3` | **normal, jangan diubah** | kompetitor memang tidak di-crawl lewat jalur ini |

Periksa sidik token tanpa memaparkan nilainya:

```sql
SELECT LEFT(SHA2(JSON_UNQUOTE(JSON_EXTRACT(Options,'$.service_token')),256),12) AS sidik,
       COUNT(*) AS jumlah
  FROM Connection
 WHERE ProviderId='PVD99' AND SiteId=169
 GROUP BY sidik;
```

Satu baris hasil = semua koneksi seragam. Lebih dari satu baris = ada yang
tertinggal saat rotasi terakhir, dan itu sendiri sudah menjadi masalah.

### Langkah 3 — Betulkan sebabnya lebih dulu

Membebaskan tanpa membereskan sebab hanya menunda: tiga kegagalan berikutnya
akan menyuspend lagi.

- Token salah → jalankan skrip rotasi token
- `company_id` salah → `JSON_SET(Options,'$.company_id', 3)`
- Bangkai → langsung ke langkah 4

### Langkah 4 — Bebaskan yang tersuspend

```sql
UPDATE Connection
   SET StatusId = 'CNS1', Error = 0,
       Remarks = 'unsuspend manual: crawl VoC diblokir CNS2',
       ModifyDate = NOW()
 WHERE ProviderId = 'PVD99'
   AND SiteId     = 169
   AND StatusId   = 'CNS2'
   AND JSON_EXTRACT(Options, '$.kind') IS NULL;
```

`kind IS NULL` **wajib**: kompetitor sengaja `CNS3`, dan menghidupkannya membuat
review kompetitor ikut masuk antrean tiket kita.

`Error = 0` juga bukan hiasan — penghitungnya kumulatif, jadi kalau ditinggal di
angka 3, satu kegagalan berikutnya langsung mengembalikannya ke `CNS2`.

### Langkah 5 — Kirim keadaan barunya ke Crawler

Membetulkan OneBox saja **tidak cukup**. Crawler masih memegang
`crawl_enabled=false` dari sinkronisasi sebelumnya:

```bash
docker compose exec api \
  python -m scripts.refresh_worklist --company-id 3 --json
```

### Langkah 6 — Buktikan

Tarik satu cabang dari layar Fetch Jobs. Berhasil berarti selesai; masih ditolak
berarti sebabnya lain — kembali ke langkah 1 dan baca `Remarks` yang baru.

---

## 6. Pelajaran

**`Remarks` bercerita tentang masa lalu, bukan masa kini.** Ia berisi pesan
kegagalan **terakhir**, bukan keadaan sekarang. Selalu bandingkan `ModifyDate`
dengan kapan sebabnya diperbaiki. Pada insiden ini `Remarks` menunjuk token yang
sudah diganti sepuluh menit kemudian — nyaris membuat orang merotasi token yang
sebenarnya sudah benar.

**Lokal bukan dev.** Sepanjang penelusuran ini keduanya berbeda tiga kali:
versi MySQL (8.0 vs 5.7), id master lokasi (1703–1711 vs 656–684), dan sebab
suspensi (`TENANT MISMATCH` di lokal, `401` di dev). Diagnosis dari lokal harus
selalu dikonfirmasi ulang di environment yang bergejala sebelum dipercaya.
Pada insiden ini diagnosis dari lokal sempat disodorkan untuk dev dan ternyata
salah; yang menyelamatkan hanyalah karena langkah "baca `Remarks` dulu"
ditempatkan sebagai keharusan sebelum tindakan apa pun.

**Pesan error yang menyebut satu sebab dari tiga bukan penyederhanaan.** Ia
mengarahkan orang ke tindakan yang salah, dan di sini tindakan itu justru yang
memicu kerusakannya.

**Status yang dipinjam dari domain lain akan menggigit.** `StatusId` milik
messaging dipakai untuk memutuskan hal crawl. Selama dua urusan berbeda berbagi
satu bendera, kegagalan di satu sisi akan diam-diam mematikan sisi lainnya.

---

## 7. Yang masih terbuka

**Tidak ada yang membersihkan `CNS2` setelah sebabnya beres.**
`WorkerTask::unsuspendAction` melakukan tepat itu:

```sql
UPDATE Connection SET StatusId='CNS1', Error=0, Remarks='unsuspend'
 WHERE StatusId='CNS2' AND Enabled=1
```

tetapi baris cron-nya dikomentari di `crontab.txt`. Selama mati, setiap gangguan
sesaat meninggalkan bangkai permanen yang baru menggigit entah kapan.
Menyalakannya menyentuh seluruh koneksi, bukan hanya VoC — **keputusan senior
dev**.

**Koneksi VoC ikut disapu penjadwal Messaging.** `Messaging::getConnections`
menyapu `Enabled=1 AND StatusId='CNS1'`, termasuk koneksi VoC yang tidak pernah
dipakai untuk messaging. Setiap kegagalan di sana dihitung sebagai error koneksi
dan bisa menyuspendnya. Perbaikan `1ae5f8a5ba` memutus akibatnya terhadap crawl,
tetapi akarnya masih ada. **Keputusan senior dev** — menyentuh service bersama.

**Crawler masih bisa membakar sepuluh menit tanpa hasil.** Terpisah dari
insiden ini, tetapi relevan saat crawl dijadwalkan otomatis. Rinciannya di
`prompt-crawler-target-vs-scan.md`.
