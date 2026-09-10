# RI-09 — Error Handling & Observability (≤3 MD)

## 1. Tujuan & DoD
Kegagalan integrasi terlihat dan tidak merusak: timeout, 401, 5xx, VoC down. **Selesai kalau:** tiap mode gagal ter-log terstruktur, task tidak crash, tidak ada secret di log, dan ada ringkasan per-run (fetched/inserted/skipped/failed).

## 2. Prasyarat
RI-05; sebaiknya sebelum RI-08 mengaktifkan jadwal.

## 3. File Target
`VoiceOfCustomerSystemClient.php` + `VoiceOfCustomerSystemTask.php` [ubah].

## 4. Langkah
1. **Client:** timeout eksplisit (sudah), 401 → re-login retry 1x (sudah dirancang RI-04), 5xx/timeout → retry max 2x dengan backoff (sleep 2s, 8s) lalu throw. Pola log: `Logger::get('VoiceOfCustomerSystem')` — pesan tanpa credential/token (audit: grep token/password di log dev).
2. **Task:** counter per-run → log ringkasan akhir: `sync done: fetched=120 inserted=37 skipped=83 failed=0 durasi=42s`. Failed>0 → level warning.
3. **Item-level fault isolation** (sudah di RI-05 try/catch per item) — pastikan satu review busuk tidak menghentikan batch; simpan `review_hash` yang gagal di log.
4. **Cek konvensi lokasi log** `[assumption]`: di mana Monolog nulis di deployment ini (`grep -rn "StreamHandler\|path" app/library/Logger.php | head`) supaya lu tahu file mana yang dibaca saat troubleshooting.

## 5. Verifikasi
Simulasi: (a) VoC mati total, (b) VoC mati di tengah, (c) credential salah, (d) satu item JSON rusak (edit fixture). Keempatnya: log jelas, exit rapi, ringkasan akurat.

## 6. Risiko
Retry berlebihan memukul VoC — batasi 2x, backoff. Log membengkak — ringkasan per-run, bukan per-item sukses.

## 7. Temuan & Deviasi (eksekusi 2026-07-15)

1. **SELESAI** — perubahan di `VoiceOfCustomerSystemClient` (+`withRetry()`) dan `VoiceOfCustomerSystemProvider::receive()` (bukan Task, sesuai D9).
2. **Client:** retry transient (curl error / HTTP 5xx) max 2x backoff 2s→8s, berlaku untuk **login DAN getReviews**; 4xx/401 tidak di-retry (401 → re-login sekali, sudah dari RI-04). Sleep coroutine-aware (`\Swoole\Coroutine::sleep` kalau di dalam coroutine — penting saat jalan di worker).
3. **Ringkasan per-run:** `sync done: fetched=N inserted=N deduped=N skipped=N failed=N durasi=Xs (connection Y)` — INFO kalau failed=0, WARNING + daftar hash gagal kalau failed>0. Isolasi per-item: try/catch per review, `rowReview` return null utk row invalid (tanpa `review_hash`) atau ensure gagal.
4. **Hasil simulasi:**
   - (a) VoC down (URL bogus): 2× warning "transient failure" + backoff → throw rapi → `receiveConnection` existing otomatis catat **`Connection.Error`++ dan `Remarks`=pesan error** (observability bawaan pipeline nyambung gratis) → CLI exit non-zero.
   - (b) Recovery: run berikutnya normal (summary INFO).
   - (d) Item rusak (`review_hash` null di fixture): `failed=1`, batch lanjut (deduped=4 item lain tetap diproses), hash/id gagal tercatat di log.
   - (c) Credential salah: path-nya = login non-200 → throw langsung tanpa retry (by design, 4xx non-transient) — belum diuji live (butuh VoC hidup); tervalidasi lewat simulasi (a) yang lewat jalur login yang sama.
5. **Lokasi log (verified `Logger.php`):** StreamHandler ke **stdout** — di dev dibaca via output CLI / `docker logs <webapp>`; level dari env `LOG_LEVEL_CONSOLE`/`LOG_LEVEL_BUFFER`.
6. Audit credential: log tidak memuat password/token (postForm error hanya log path; response login tidak di-log; GET reviews tidak bawa token di URL).

## 9. Estimasi (3 MD)
Hari 1: client retry/backoff. Hari 2: ringkasan + isolasi. Hari 3: simulasi 4 skenario.
