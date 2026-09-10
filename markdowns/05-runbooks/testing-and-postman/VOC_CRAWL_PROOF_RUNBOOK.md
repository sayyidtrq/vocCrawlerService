# VOC Crawl Proof Runbook - X1 sampai X5

> Runbook verifikasi end-to-end Voice of Customer di environment Dev. Acuan: ADR-0001, ADR-0002, ADR-0003, `PLAN_KEY_PROCESS_DEMO.md`, dan `PROMPT_VOC_CRAWL_PROOF.md`.
> Status klaim: **[verified-local]**, **[verified-dev]**, **[assumption]**, atau **[blocked]**.

## 1. Target proof

Rantai yang harus terbukti:

~~~text
OneBox menambah Location
  -> Crawler menarik worklist
  -> OneBox enqueue crawl via service API
  -> worker Selenium mengambil review
  -> Crawler menyimpan dan deduplikasi review
  -> tahap AI mengisi sentiment, urgency, category, summary, action
  -> OneBox menarik delta review
  -> OneBox membuat Message/Ticket
  -> pengguna assign, tindak lanjut, dan eskalasi Ticket
~~~

AI sengaja tidak dijalankan otomatis oleh worker crawl. Pemisahan ini mengikuti ADR-0002 dan membuat kegagalan crawl, LLM, serta ingestion dapat di-retry secara independen.

## 2. Status implementasi

| Proses | Status | Bukti |
|---|---|---|
| Worklist OneBox -> Crawler | **[verified-dev]** | Sync pernah menghasilkan `status=synced` dan target masuk cache lokasi. |
| X5 enqueue non-blocking | **[verified-dev]** | Service token dengan scope crawl dapat enqueue batch, worker mengambil antrean, dan API tidak menunggu Selenium selesai. |
| Runtime Chromium di image | **[verified-dev]** | Chromium/chromedriver tersedia; worker berjalan headed melalui Xvfb dan memakai volume profile Google yang persisten. |
| X1 crawl Google real | **[verified-dev, partial target]** | Target 50 menghasilkan 40 review real, 0 gagal. Selisih 10 terjadi karena tidak ada kartu baru setelah 18 scroll. |
| X2 persistence + dedup | **[verified-dev]** | 40 review terikat ke company/lokasi/place yang benar, 40 hash unik; rerun menghasilkan `inserted=0` dan `duplicate=40`. |
| X3 analysis + token usage | **[in-progress-dev]** | `gemma3:1b` berhasil menganalisis satu review dengan 839 token. Batch penuh masih lambat karena eksekusi serial. |
| X4 service auth + delta | **[verified-dev, analysis pending]** | Delta mengembalikan 40 review, `location_id=8`, `has_more=false`, dan checkpoint terisi. Pull ulang setelah X3 selesai masih wajib untuk membuktikan field analysis. |
| Review -> Ticket -> eskalasi | **[blocked-by-X3/OneBox]** | Dilanjutkan setelah hasil analysis lengkap muncul pada delta dan consumer OneBox dijalankan. |

### 2.1 Rekap proof Dev aktual - 31 Juli 2026

| Item | Hasil |
|---|---|
| Target | RSU Hermina Depok |
| Company / lokasi Crawler / lokasi OneBox | `3 / 8 / 656` |
| Target review | 50 |
| Fetched / inserted / failed | `40 / 40 / 0` |
| Penyebab target tidak penuh | Tidak ada kartu review baru setelah 18 scroll |
| Login Google | Diperlukan satu kali untuk bootstrap profile persisten |
| Idempotency enqueue | Lulus; replay tidak membuat batch baru |
| Dedup crawl | Lulus; rerun `fetched=40`, `inserted=0`, `duplicate=40` |
| Delta sebelum analysis penuh | 40 item, final page, checkpoint tersedia |
| Model analysis terpilih | `gemma3:1b` |
| Bukti analysis minimum | 1 review sukses, total usage 839 token |

Keputusan sementara: **PASS WITH LIMITATION** untuk X1, X2, X4 raw, dan X5.
X3 belum boleh dinyatakan selesai sampai semua review target yang memiliki teks sudah
memiliki analysis atau kegagalannya tercatat. G5 tetap menunggu ingestion dan workflow
Ticket di OneBox.

### 2.2 Kendala AI dan estimasi 50 review

Kendala yang sudah ditemukan:

- model lama `qwen2.5:7b` tidak tersedia pada Ollama tujuan;
- `qwen3.5:9b` gagal dimuat, `qwen3:1.7b` mengembalikan JSON kosong, dan
  `gemma3:4b` tidak selesai dalam waktu proof;
- `gemma3:1b` menghasilkan response valid, tetapi inference berjalan di resource lokal
  dan masih lambat;
- implementasi `AnalysisService._analyze_items()` memanggil LLM **secara serial**.
  `ANALYSIS_BATCH_SIZE=20` hanya membagi iterasi menjadi kelompok, bukan menjalankan
  20 request secara paralel.

Estimasi kapasitas sementara untuk `gemma3:1b`:

| Komponen | Estimasi |
|---|---:|
| Warm inference per review | 30-90 detik |
| 50 review, inference serial | 25-75 menit |
| Cold start, tulis DB, validasi, dan kemungkinan retry | 5-15 menit |
| **Estimasi operasional 50 review** | **30-90 menit** |
| **Budget aman untuk jadwal/demo** | **maksimal 120 menit** |

Angka tersebut adalah **estimasi provisional**, bukan SLA. Setelah batch selesai, catat
`started_at`, `finished_at`, jumlah `success/failed/skipped`, dan hitung angka aktual:

~~~text
average_seconds_per_review = elapsed_seconds / attempted_reviews
estimated_50_minutes = average_seconds_per_review * 50 / 60
~~~

Untuk demo, analysis sebaiknya diproses sebelum sesi dimulai. Optimasi berikutnya adalah
worker analysis terpisah dengan concurrency kecil dan terukur, bukan menaikkan
`ANALYSIS_BATCH_SIZE` karena konfigurasi itu saat ini tidak menambah paralelisme.

## 3. Contract X5 yang sudah tersedia

| Endpoint | Scope | Fungsi |
|---|---|---|
| `POST /api/integration/v1/crawl-jobs` | `crawl:enqueue` | Membuat batch durable dan langsung merespons `202`. |
| `GET /api/integration/v1/crawl-jobs` | `crawl:read` | Menampilkan batch terbaru milik tenant token. |
| `GET /api/integration/v1/crawl-jobs/{batch_id}` | `crawl:read` | Menampilkan status dan hasil per `onebox_location_id`. |
| `GET /api/integration/v1/whoami` | service bearer | Memastikan token terikat ke company yang benar. |
| `GET /api/integration/v1/reviews` | `reviews:read` | Menarik review delta tanpa mengubah contract v1. |

Aturan penting:

- `company_id` selalu berasal dari service token, tidak diterima dari payload.
- Target POST memakai `onebox_location_id`, bukan primary key Crawler.
- Target harus ada di worklist cache dan masih `active + crawl_enabled + ingest_reviews`.
- `Idempotency-Key` wajib. Key sama dan payload sama mengembalikan batch lama; key sama dan payload berbeda menghasilkan `409 IDEMPOTENCY_CONFLICT`.
- Satu worker Selenium adalah baseline aman. Job memakai lease dan retry sehingga restart container tidak menghilangkan antrean.

## 4. Deployment Crawler System

P0 migrasi PostgreSQL ke MySQL sedang ditahan. Deploy proof ini tetap memakai database PostgreSQL yang aktif saat ini. Jangan menerapkan stash P0 bersama perubahan X1-X5.

### 4.1 Pre-deploy

~~~bash
cd ~/herminaCrawler
git status --short --branch
git fetch origin
git switch codex/key-process-x1-x5
git pull --ff-only
~~~

Berhenti bila server memiliki perubahan lokal yang tidak dikenal. Jangan melakukan reset atau overwrite.

### 4.2 Build, migration, dan start

~~~bash
docker compose up -d --build --force-recreate
docker compose ps
docker compose logs --tail=200 api crawl-worker
curl -fsS http://127.0.0.1:8000/api/health
~~~

Expected:

- service `api` healthy;
- service `crawl-worker` running;
- migration `20260729_0002` selesai;
- tidak ada loop crash Chromium/worker.

Verifikasi revision:

~~~bash
docker compose exec api python -m alembic current
~~~

## 5. G0 - refresh worklist

~~~bash
docker compose exec api python -m scripts.refresh_worklist --company-id 3 --json
~~~

Gate lulus bila `status=synced`, `fetched>0`, `upserted>=0`, dan `warning=null`. Jika `fetched=0`, periksa SiteId serta flag `active`, `crawl_enabled`, dan `ingest_reviews` di OneBox. Jangan membuat Location Crawler secara manual.

Catat `onebox_location_id` target tanpa menyimpan review text:

~~~bash
docker compose exec api python -c "from app.db.session import get_session_factory; from app.db.models import Location; from sqlalchemy import select; f=get_session_factory(); s=f(); print([(x.onebox_location_id,x.branch_name,x.crawl_enabled,x.ingest_reviews) for x in s.scalars(select(Location).where(Location.company_id==3,Location.is_active.is_(True)))])"
~~~

## 6. Issue service token proof

Perintah berikut otomatis menyertakan default `reviews:read`, lalu menambahkan dua scope crawl:

~~~bash
docker compose exec api python -m scripts.manage_api_client issue --company-id 3 --name onebox-crawl-dev --scope crawl:enqueue --scope crawl:read --expires-days 7
~~~

Raw token hanya tampil sekali. Simpan di secret/config OneBox dan shell sementara, bukan Git, screenshot, atau chat.

~~~bash
export VOC_API=http://127.0.0.1:8000
export VOC_SERVICE_TOKEN="<voc_staging_key.secret>"
curl -fsS "$VOC_API/api/integration/v1/whoami" -H "Authorization: Bearer $VOC_SERVICE_TOKEN"
~~~

Gate lulus bila `company_id=3` dan scopes berisi `reviews:read`, `crawl:enqueue`, serta `crawl:read`.

## 7. G0.5 - bootstrap profile Google untuk Selenium

Task ini dilakukan **satu kali per volume/profile Selenium**, lalu diulang hanya ketika sesi
Google habis, profile rusak, atau Google kembali menampilkan limited view. Login dilakukan
di Chromium normal yang berjalan di `ciptadra-svr`, bukan di Chrome laptop dan bukan melalui
WebDriver. Otomasi login Google sengaja tidak didukung.

### 7.1 Hentikan worker selama setup

Worker dihentikan agar retry job tidak habis sebelum profile siap:

~~~bash
cd ~/herminaCrawler
docker compose stop crawl-worker
docker volume inspect herminacrawler_selenium-profile
docker run --rm \
  -v herminacrawler_selenium-profile:/profile \
  alpine sh -lc 'chown -R 1000:1000 /profile'
~~~

### 7.2 Jalankan browser setup di loopback server

Browser setup memakai volume yang sama dengan mount
`/app/.selenium-profile` pada worker. Port hanya bind ke `127.0.0.1` server
dan tidak boleh diekspos ke LAN atau internet.

~~~bash
docker rm -f voc-chromium-profile-setup 2>/dev/null || true
docker run -d \
  --name voc-chromium-profile-setup \
  --shm-size=1g \
  --security-opt seccomp=unconfined \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Jakarta \
  -e CHROME_CLI="/config/.config/chromium https://www.google.com/maps" \
  -p 127.0.0.1:3000:3000 \
  -p 127.0.0.1:3001:3001 \
  -v herminacrawler_selenium-profile:/config/.config/chromium \
  lscr.io/linuxserver/chromium:version-b0ddd401

docker ps --filter name=voc-chromium-profile-setup
curl -fsSI http://127.0.0.1:3000/ | head
~~~

### 7.3 Login manual dari laptop

Di terminal **baru pada laptop developer**, buat SSH tunnel dan biarkan terminal terbuka:

~~~bash
ssh -L 3000:127.0.0.1:3000 ubuntu@192.168.1.3
~~~

Kemudian buka `http://127.0.0.1:3000` pada browser laptop. Halaman tersebut adalah
remote Chromium yang berjalan di server.

Checklist manual:

1. Login ke akun Google yang memang diizinkan untuk proof.
2. Buka Google Maps dan cari target proof, misalnya `Hermina Depok`.
3. Buka panel **Ulasan/Reviews** sampai kartu review terlihat.
4. Tutup tab sensitif lain; jangan mengunggah file atau menyalin secret ke browser ini.
5. Jangan mengirim password Google, cookie, atau screenshot token ke chat/evidence.

### 7.4 Simpan profile dan hidupkan kembali worker

Setelah daftar review terlihat:

~~~bash
docker stop voc-chromium-profile-setup

# Chromium setup berjalan sebagai UID 1000. Samakan ownership sebelum setup,
# dan hapus lock setelah setiap perpindahan antara browser setup dan worker.
docker run --rm \
  -v herminacrawler_selenium-profile:/profile \
  alpine sh -lc 'chown -R 1000:1000 /profile && rm -f /profile/SingletonLock /profile/SingletonCookie /profile/SingletonSocket'

docker rm voc-chromium-profile-setup

# Google dapat memberi limited view pada mode headless walaupun cookie login valid.
# Proof real dijalankan headed di virtual display Xvfb.
grep '^SELENIUM_HEADLESS=false$' .env
docker compose up -d --build --force-recreate crawl-worker
docker compose ps
docker compose logs --since=2m crawl-worker
~~~

Gate lulus bila:

- setup container sudah dihapus;
- `crawl-worker` berstatus running;
- volume `herminacrawler_selenium-profile` tetap ada;
- worker menjalankan `SELENIUM_HEADLESS=false` melalui Xvfb dan tidak mengalami error permission/profile lock;
- crawl berikutnya tidak lagi berhenti pada `limited view`.

> Catatan keamanan: profile berisi session cookie. Perlakukan volume sebagai secret,
> batasi akses Docker host, jangan backup ke Git/object storage umum, dan hapus/revoke
> session ketika proof selesai atau akun tidak lagi digunakan.

## 8. X1 dan X5 - enqueue crawl real

Gunakan target kecil agar proof terkendali. Nilai target aktual tetap berasal dari worklist Location.

~~~bash
export ONEBOX_LOCATION_ID="<id-dari-worklist>"
export RUN_ID="voc-proof-$(date -u +%Y%m%dT%H%M%SZ)"

curl -fsS -X POST "$VOC_API/api/integration/v1/crawl-jobs" \
  -H "Authorization: Bearer $VOC_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $RUN_ID" \
  -H "X-Request-ID: $RUN_ID" \
  -d "$(printf '{\"slot\":\"manual-proof\",\"targets\":[{\"onebox_location_id\":%s}]}' "$ONEBOX_LOCATION_ID")"
~~~

Response harus HTTP `202` dengan `batch_id`, status `queued`, dan job yang mengembalikan `onebox_location_id` yang sama. Simpan batch ID:

~~~bash
export BATCH_ID="<batch-id-response>"
curl -fsS "$VOC_API/api/integration/v1/crawl-jobs/$BATCH_ID" \
  -H "Authorization: Bearer $VOC_SERVICE_TOKEN"
docker compose logs --tail=200 crawl-worker
~~~

Gate X1/X5:

| Hasil | Keputusan |
|---|---|
| API cepat memberi `202`, job menjadi `succeeded`, dan `total_fetched>0` | Lulus; lanjut X2. |
| `succeeded` tetapi fetched 0 | Queue terbukti, crawl data belum terbukti; pilih target yang punya review. |
| `retry_wait` | Periksa error tersanitasi dan worker log; tunggu retry. |
| `failed` setelah max attempts | X1 gagal; cek Chromium, jaringan Google, profile, quota, atau selector. |
| `404 TARGET_NOT_FOUND` | Worklist target belum tersinkron atau dinonaktifkan. |

Jalankan POST yang sama dengan `Idempotency-Key` dan payload yang sama. Batch ID harus tetap sama dan job tidak boleh bertambah.

## 9. X2 - persistence dan dedup

Gunakan JWT user hanya untuk endpoint operasional lama selama belum tersedia read-only proof endpoint service. Jangan memasukkan token ke evidence.

~~~bash
export VOC_USER_TOKEN="<jwt-user-sementara>"
curl -fsS "$VOC_API/api/reviews?page=1&page_size=20&latest_first=true" \
  -H "Authorization: Bearer $VOC_USER_TOKEN"
~~~

Bukti X2:

- review terikat ke Location yang memiliki `onebox_location_id` target;
- `external_place_id` sama dengan worklist;
- `review_hash` terisi;
- run kedua tidak membuat duplikat dan menambah counter duplicate atau menghasilkan inserted 0.

Jika mapping lokasi salah, hentikan ingestion OneBox.

## 10. X3 - AI analysis

Tes konektivitas LLM dari container:

~~~bash
docker compose exec api sh -lc 'curl -fsS --connect-timeout 5 "$LOCAL_LLM_BASE_URL" >/dev/null && echo LLM_REACHABLE'
~~~

Jalankan tahap analysis terpisah:

~~~bash
curl -fsS -X POST "$VOC_API/api/analysis/pending" \
  -H "Authorization: Bearer $VOC_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{"location_id":<voc-location-id-internal>}"
~~~

Gate lulus bila success lebih dari 0, `tokens_used` dan `token_usage` tercatat, serta review memiliki sentiment, urgency, issue_category, summary, dan recommended_action.

## 11. X4 - delta pull

~~~bash
export UPDATED_SINCE="<UTC-sebelum-crawl>"
curl -fsS "$VOC_API/api/integration/v1/reviews?limit=100&updated_since=$UPDATED_SINCE" \
  -H "Authorization: Bearer $VOC_SERVICE_TOKEN" \
  -H "X-Request-ID: $RUN_ID-delta"
~~~

Gate lulus bila review X1 muncul dengan lokasi dan hasil analysis benar. Ikuti `next_cursor` ketika `has_more=true`; simpan `checkpoint_cursor` di OneBox hanya setelah seluruh page berhasil di-ingest.

## 12. Handoff ke OneBox

Claude/agen OneBox menjalankan receive pada Connection Dev:

~~~bash
docker exec <onebox-webapp-container> php app/bootstrap.php voice_of_customer_system receive <CONNECTION_ID>
~~~

Verifikasi di UI:

1. Review muncul di VOC Reviews.
2. Ticket Location menunjuk cabang benar, bukan Unknown.
3. Sentiment, urgency, category, summary, dan recommended action tampil.
4. Review negatif menjadi Ticket terbuka.
5. Ticket dapat di-assign, diberi action note, diubah status, dan dieskalasi.
6. Dashboard konsisten dengan jumlah data hasil proof.

## 13. Pembagian dua agen

### Codex - Crawler System

- deploy branch dan verifikasi migration/worker;
- refresh worklist;
- issue token proof dengan scope lengkap;
- menjalankan X1/X5, X2, X3, dan X4;
- menyerahkan evidence tanpa secret atau full review text;
- mencatat blocker Selenium/LLM/network berdasarkan stage yang tepat.

### Claude - OneBox

- memastikan PR OneBox sudah masuk `feature/voc` dan deployed;
- menyimpan service token di secret/config Connection;
- memanggil enqueue dengan `onebox_location_id` dan idempotency key;
- melakukan receive delta dan memajukan checkpoint hanya setelah sukses penuh;
- membuktikan mapping Message/Ticket, Location, assignment, dan escalation;
- menampilkan status batch pada Fetch Jobs tanpa menunggu Selenium di request web.

## 14. Decision gates

| Gate | Lulus bila |
|---|---|
| G0 | API healthy dan worklist synced. |
| G0.5 | Profile Google tersimpan, setup browser dihapus, dan worker kembali running tanpa limited view. |
| G1 | Enqueue memberi 202 dan worker mendapatkan review real. |
| G2 | Location/place/hash benar dan rerun tidak duplikat. |
| G3 | Analysis fields serta token usage terisi. |
| G4 | Service token tenant benar dan delta berisi review proof. |
| G5 | OneBox membuat Ticket yang dapat ditindaklanjuti. |

## 15. Prosedur test service end-to-end

Jalankan test berurutan. Jangan melewati gate yang gagal karena hasil tahap sesudahnya
tidak dapat dianggap valid.

| No. | Test | Aksi utama | Expected result | Evidence |
|---|---|---|---|---|
| T01 | Deployment | Build/recreate Compose dan cek migration | API healthy, worker running, Alembic head benar | metadata + status container |
| T02 | Service auth | Panggil `whoami` dengan token proof | company 3 dan tiga scope benar | response redacted |
| T03 | Tenant isolation | Gunakan target tenant lain/tidak terdaftar | request ditolak tanpa membocorkan data | status + error code |
| T04 | Worklist | Jalankan `refresh_worklist` company 3 | target aktif masuk cache dengan OneBox Location ID | counter + identity redacted |
| T05 | Profile Selenium | Selesaikan G0.5 | Google Maps menampilkan kartu review, worker memakai profile tanpa lock | status saja, tanpa cookie |
| T06 | Enqueue | POST crawl job dengan idempotency key baru | HTTP 202 dalam waktu singkat dan ada `batch_id` | enqueue response |
| T07 | Durable execution | Pantau batch dan restart worker sekali bila perlu | job tetap ada dan akhirnya terminal | batch history + log redacted |
| T08 | Crawl nyata | Tunggu job target 50 | `succeeded`, fetched mendekati target; selisih harus dijelaskan | final counters |
| T09 | Persistence | Query review hasil run | Location/place/hash benar dan jumlah DB bertambah | identity redacted |
| T10 | Idempotency API | Ulang POST dengan key dan payload sama | batch ID sama, tidak ada job tambahan | kedua response |
| T11 | Dedup crawler | Enqueue crawl baru untuk target sama | jumlah review stabil; inserted 0 atau duplicate bertambah | before/after counters |
| T12 | AI analysis | Jalankan pending analysis | analysis fields dan token usage terisi | aggregate analysis |
| T13 | Delta API | Pull contract v1 sejak sebelum crawl | review proof muncul dan cursor valid | payload redacted |
| T14 | OneBox ingestion | Jalankan consumer receive | Message/Ticket terbentuk satu kali | ingest counters |
| T15 | Workflow UI | Assign, beri tindak lanjut, ubah status, eskalasi | Ticket dapat dikelola end-to-end | screenshot redacted |

### 15.1 Ringkasan hasil wajib

Laporan proof minimal memuat:

~~~text
Environment:
Git commit/image:
Company ID / Site ID / OneBox Location ID:
Batch ID:
Target review: 50
Fetched:
Inserted:
Duplicate:
Failed:
Final status:
Google login required: yes/no
Analysis success/failed:
Delta returned:
Ticket created:
Idempotency verified: yes/no
Dedup verified: yes/no
Blocker/selisih:
~~~

Keputusan akhir:

- **PASS**: T01-T15 lulus dan tidak ada pelanggaran tenant/mapping.
- **PASS WITH LIMITATION**: rantai utama berhasil, tetapi fetched kurang dari 50 karena
  jumlah review yang memang tersedia atau pembatasan yang sudah dibuktikan dan dicatat.
- **FAIL**: review real tidak tersimpan, tenant isolation gagal, terjadi duplikasi,
  cursor tidak konsisten, atau Ticket tidak dapat ditindaklanjuti.

## 16. Evidence packet

~~~text
00_run_metadata.txt
01_worklist_redacted.json
02_enqueue_response.json
03_batch_final.json
04_worker_log_redacted.txt
05_selenium_profile_status.txt
06_review_identity_redacted.json
07_analysis_summary.json
08_whoami_redacted.json
09_delta_redacted.json
10_onebox_ingest_counters.txt
11_ticket_redacted.png
~~~

Jangan menyimpan password, raw token/JWT, Selenium cookies/profile, API key, cursor penuh, raw payload, atau full review text.

## 17. Known limitations setelah proof

- Scheduler tiga window masih pekerjaan terpisah; OneBox tetap control plane jadwal.
- Baseline worker hanya satu concurrency untuk menjaga stabilitas Selenium.
- P0 migrasi PostgreSQL ke MySQL ditahan dan harus direbase terhadap migration queue ini saat dilanjutkan.
- Production monitoring, secret rotation, retention, dan capacity test belum dibuktikan oleh proof ini.
