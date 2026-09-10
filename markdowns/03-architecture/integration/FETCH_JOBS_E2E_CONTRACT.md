# Fetch Jobs End-to-End Contract

> Status: implementation contract untuk demo key process.
> Acuan: ADR-0003 dan ADR-0004.

## 1. Outcome wajib

Satu klik `Mulai Crawl` di OneBox harus menyelesaikan alur berikut tanpa tombol tarik review kedua:

```text
OneBox enqueue crawl
  -> Crawler scrape + persist raw review
  -> OneBox memantau batch
  -> OneBox otomatis menarik discovery delta
  -> OneBox upsert raw review
  -> labeling sentiment native OneBox
  -> Kelola Review langsung dapat digunakan
```

AI analysis tidak berada pada critical path ini. AI hanya dipicu kemudian oleh user untuk
single/bulk review dan berjalan asynchronous.

## 2. Kontrak enqueue Crawler

```http
POST /api/integration/v1/crawl-jobs
Authorization: Bearer <service-token>
Idempotency-Key: onebox-<site>-<location>-<unique-run>
Content-Type: application/json
```

```json
{
  "slot": "manual",
  "targets": [
    {
      "onebox_location_id": 656,
      "target_review_count": 10
    }
  ]
}
```

`target_review_count` bersifat optional dan backward-compatible. Jika tidak dikirim, Crawler
memakai target dari cache Worklist. Jika dikirim, nilainya 1-300 dan menjadi target job itu.
Nilai target ikut fingerprint idempotency, sehingga key yang sama dengan target berbeda
menghasilkan `409 IDEMPOTENCY_CONFLICT`.

Response status batch memuat target per job dan agregat review:

```json
{
  "data": {
    "batch_id": "uuid",
    "status": "completed",
    "counts": {
      "queued": 0,
      "running": 0,
      "retry_wait": 0,
      "succeeded": 1,
      "skipped": 0,
      "failed": 0
    },
    "review_counts": {
      "target": 10,
      "fetched": 10,
      "inserted": 3,
      "duplicate": 7,
      "failed": 0
    },
    "jobs": []
  }
}
```

`fetched` bukan jumlah review baru. Jumlah review baru adalah `inserted`; review yang sudah
pernah tersimpan masuk `duplicate`.

## 3. Orkestrasi wajib di OneBox

### Phase A - Enqueue

`VocController::crawlStartAction` harus menerima dan memvalidasi:

- Connection/lokasi;
- target review 1-300;
- source yang benar-benar didukung;
- CSRF dan permission user.

OneBox backend, bukan browser, menambahkan service token. Payload ke Crawler wajib membawa
`target_review_count`.

### Phase B - Poll crawl

Browser polling `Voc/crawlStatus?batch_id=...` sekitar setiap 3-5 detik.

- `queued`: tampilkan `Menunggu worker`;
- `running`: tampilkan `Mengambil review dari Google`;
- `retry_wait`: tampilkan percobaan dan jadwal retry;
- `completed`: lanjut otomatis ke Phase C;
- `partial_failed`: lanjut Phase C untuk hasil sukses, lalu tampilkan warning;
- `failed`: berhenti, tampilkan error tersanitasi dan tombol retry.

Selama Selenium `running`, progress bar harus indeterminate karena Crawler belum mengirim
jumlah kartu secara live. Jangan membuat persen review palsu. Setelah terminal, tampilkan
`review_counts` aktual.

### Phase C - Auto import

Setelah `completed` atau `partial_failed`, JavaScript otomatis memanggil controller OneBox
baru, misalnya `POST Voc/crawlImport`, dengan `batch_id` dan Connection yang sama.
Controller menjalankan pipeline delta yang saat ini dipakai `syncnowAction`.

Syarat:

- tidak meminta user menekan `Tarik Review Sekarang`;
- cursor hanya disimpan setelah seluruh page sukses;
- upsert tetap memakai SiteId + provider + `review_hash`/RemoteId;
- pemanggilan ulang aman dan tidak membuat Message/Ticket ganda;
- import mengembalikan angka pulled, inserted, updated, duplicate, failed;
- `analysis=null` tidak boleh menggagalkan raw ingestion.

### Phase D - Native labeling dan selesai

Setelah raw review tersimpan, OneBox menjalankan program labeling sentiment existing. Claude
wajib membuktikan class/service dan field output existing sebelum membuat logic baru.

Jika import dan labeling selesai:

- progress menjadi 100%;
- tampilkan ringkasan crawl + import;
- sediakan tombol `Buka Kelola Review`;
- refresh data Kelola Review tanpa menunggu AI.

## 4. Progress UI yang jujur

Progress terdiri dari state, bukan perkiraan waktu:

| State | Mode bar | Label |
|---|---|---|
| enqueue | determinate awal | Menyiapkan crawl |
| queued | indeterminate | Menunggu worker |
| running | indeterminate | Mengambil review dari Google |
| importing | indeterminate | Menyimpan review ke OneBox |
| labeling | indeterminate | Memberi label sentiment |
| completed | 100% | Review siap dikelola |
| failed | stop | Tampilkan sebab dan retry |

Di bawah bar tampilkan counter aktual saat tersedia:

```text
Target 10 | Terbaca 10 | Baru 3 | Duplikat 7 | Gagal 0
```

## 5. Idempotency dan recovery

- Klik ganda tidak membuat batch baru karena `Idempotency-Key`.
- Refresh browser dapat melanjutkan polling jika `batch_id` disimpan di state/session OneBox.
- Auto-import boleh dipanggil ulang; delta cursor dan dedup harus membuatnya idempotent.
- `partial_failed` tetap mengimpor review dari job sukses.
- Kegagalan labeling tidak boleh menghapus raw review; simpan status labeling gagal untuk retry.
- Kegagalan AI tidak berpengaruh pada Fetch Jobs.

## 6. Acceptance test demo

1. Pilih RS Hermina Depok dan target 10.
2. Pastikan POST Crawler memperlihatkan `target_review_count=10`.
3. Progress berpindah queued/running ke importing tanpa tombol kedua.
4. Crawler menunjukkan target/fetched/inserted/duplicate/failed aktual.
5. Review raw terlihat di Kelola Review segera setelah import.
6. Label positive/neutral/negative terisi lewat program native OneBox.
7. Rerun tidak membuat review, Message, atau Ticket ganda.
8. Ollama dimatikan: langkah 1-7 tetap berhasil.
9. User memilih single/bulk review untuk AI pada flow terpisah.
10. Hasil AI hanya meng-update Ticket existing.
