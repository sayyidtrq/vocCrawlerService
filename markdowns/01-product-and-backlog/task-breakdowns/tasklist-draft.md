# Review Intelligence — Feature Tasklist (Draft v1)

> **Untuk:** basis pembuatan tiket Jira (permintaan Pak Agung: tiap task maksimal 5 hari kerja / 5MD).
> **Konteks keputusan (terkunci):** data review disimpan ke tabel **`Ticket`** existing, lewat/menyerupai modul **`Mediamonitoring`**; UI = dashboard **VOC**; pola ingest meniru **`SonarTask`** (narik dari API eksternal → dedup → `new Ticket()` → dashboard).
> **Status:** DRAFT untuk direview bareng + sebagian task nunggu keputusan Agung (ditandai ⚠️). Estimasi MD masih kasar; bisa berubah setelah spike (Epic A).
> **Legend:** `MD` = man-day (hari kerja). `⚠️` = butuh keputusan/konfirmasi lead. `→` = depends on.

---

## Ringkasan Epic

| Epic | Fokus | Total kasar |
|------|-------|-------------|
| A | Discovery & Keputusan | 7 MD |
| B | Ingestion (CrawlerSystemTask) | 15 MD |
| C | Scheduling & Reliability | 7 MD |
| D | UI / VOC Dashboard | 16 MD |
| E | Management + Akses | 6 MD |
| F | Hardening | 5 MD |
| | **Total kasar** | **± 56 MD** (~11 minggu solo) |

> ⚠️ Total ini besar untuk dikerjakan sekaligus. Lihat **Garis MVP** di bawah — disarankan potong scope untuk rilis pertama.

---

## Epic A — Discovery & Keputusan *(kerjakan paling awal)*

**RI-01 · Field mapping: review Crawler System → Ticket** — 3MD
Petakan tiap field response Crawler System (`/api/reviews`) ke kolom `Ticket` (atau `Message`/`Contact`/`Reference`). Tandai field yang belum ada rumahnya.
*Selesai kalau:* tabel mapping lengkap + daftar field tanpa kolom padanan.

**RI-02 · Konfirmasi keputusan arsitektur ke lead** ⚠️ — 2MD → RI-01
Minta keputusan Agung: (a) field analisa ekstra (urgency/issue_category/summary/recommended_action) ditaruh di kolom `Ticket` baru vs `Reference`/`Data`; (b) auth service-to-service OneBox<->Crawler System; (c) Google review = `MediaId`/channel baru?; (d) mapping site/tenant Onebox ↔ location/provider location di Crawler System.
*Selesai kalau:* semua keputusan tercatat & di-ACC.

**RI-03 · Kesiapan API Crawler System + run lokal** — 2MD
Jalankan Crawler System lokal; verifikasi `/api/health`, `/api/auth/login`, `/api/reviews`; catat contoh payload. Tambah param delta (`updated_since`) kalau belum ada.
*Selesai kalau:* bisa narik sample review dari lokal + kontrak API terdokumentasi.

---

## Epic B — Ingestion (CrawlerSystemTask, meniru SonarTask)

**RI-04 · Library `CrawlerSystemClient`** — 4MD → RI-03
Bikin `app/library/CrawlerSystemClient.php` (contek pola `CiptalifeApi.php`): `health()`, `login()`/auth, `getReviews($params)`. Config per-environment, timeout eksplisit, logging via `Library\Logger`, mock fixture untuk dev.
*Selesai kalau:* bisa dipanggil & mengembalikan data terparse dari live + mock.

**RI-05 · Job ingest `CrawlerSystemTask`** — 5MD → RI-04, RI-01
Clone pola `SonarTask`: narik review → cek duplikat (dedup key `review_hash`/`external_review_id` + `SiteId`) → `new Ticket()` isi field ter-mapping → bungkus DB transaction. Bisa dijalankan manual dulu (dev).
*Selesai kalau:* dijalankan → muncul Ticket review; dijalankan ulang → tidak dobel.

**RI-06 · Mapping Site ↔ lokasi RS** ⚠️ — 3MD → RI-02
Petakan site/tenant Onebox ke `location_id` Crawler System (tabel/config + resolver). Pastikan Ticket hasil ingest ber-`SiteId`/`LocationId` benar.
*Selesai kalau:* Ticket masuk ke site yang tepat.

**RI-07 · Simpan field analisa ekstra** ⚠️ — 3MD → RI-02
Simpan urgency/issue_category/summary/recommended_action/flag sesuai keputusan RI-02 (migration kalau perlu kolom baru).
*Selesai kalau:* field bisa di-query di Ticket review.

---

## Epic C — Scheduling & Reliability

**RI-08 · Scheduler + delta sync + trigger manual** — 4MD → RI-05
Daftarkan `CrawlerSystemTask` ke scheduler; sync inkremental (`updated_since` atau `latest_first` + stop saat ketemu yang sudah ada); tombol "Sync Now".
*Selesai kalau:* jalan terjadwal, tidak narik ulang semua tiap kali.

**RI-09 · Error handling & observability** — 3MD → RI-05
Timeout, re-auth saat 401, retry/backoff terbatas, log terstruktur, surface kegagalan. Jangan log credential.
*Selesai kalau:* kegagalan tercatat & job tidak crash; tidak ada secret di log.

---

## Epic D — UI / VOC Dashboard *(reuse Mediamonitoring)*

**RI-10 · Sumber "Review" di nav Mediamonitoring** — 4MD → RI-05
Tambah filter/sumber "Review/VOC" di Mediamonitoring; list view meniru pola `listNews` di-scope ke channel review.
*Selesai kalau:* Ticket review tampil di list.

**RI-11 · Halaman detail review** — 4MD → RI-10
Detail meniru pola `detail.volt` Mediamonitoring: reviewer, rating, sentiment, urgency, summary, recommended action, link sumber.
*Selesai kalau:* detail render lengkap.

**RI-12 · Dashboard VOC (sentiment/urgency/trend/mapping)** — 5MD → RI-10, RI-07
Reuse pola dashboard/report Mediamonitoring: breakdown sentiment, urgency, mapping issue-category, trend.
*Selesai kalau:* dashboard menampilkan agregat live.

**RI-13 · Poles visual vs benchmark Next.js** — 3MD → RI-12
Samakan tampilan ke FE benchmark Crawler System, dalam batas template/`global.css` Onebox.
*Selesai kalau:* di-ACC mendekati benchmark.

---

## Epic E — Management ("dikelola") + Akses

**RI-14 · Aksi manajemen review** — 4MD → RI-10
Assign / tandai handled / resolve / tambah note — reuse lifecycle `Ticket`.
*Selesai kalau:* satu review bisa di-assign + resolve + diberi note.

**RI-15 · Registrasi menu + role/permission** — 2MD → RI-10
Daftarkan menu + `RoleMenu`; scope siapa yang boleh lihat VOC.
*Selesai kalau:* role yang benar bisa lihat, lainnya tidak.

---

## Epic F — Hardening

**RI-16 · Integration test + verifikasi staging** — 3MD → RI-08, RI-12
**RI-17 · Dokumentasi + runbook** — 2MD → sebagian besar task

---

## Garis MVP (rekomendasi rilis pertama)

Untuk membuktikan alur end-to-end secepatnya tanpa mengerjakan semua:

**MVP = RI-01→RI-07 (ingest) + RI-10→RI-12 (lihat + dashboard) + RI-15 (akses)**
→ review Google masuk ke Ticket, tampil, ada dashboard, ter-scope role. (~± 34 MD)

**Fast-follow:** RI-08/09 (scheduler & reliability), RI-13 (poles), RI-14 (management), RI-16/17 (hardening).

---

## Catatan & Asumsi

- Estimasi kasar; **wajib direvisi setelah Epic A (spike)** — beberapa task bisa mengecil/membesar.
- **RI-02 adalah gerbang**: RI-06, RI-07, dan sebagian D bergantung pada keputusan Agung. Kerjakan Epic A dulu.
- Crawler System tetap microservice eksternal (kerjaan FastAPI/Selenium tidak dibuang); Onebox hanya narik + simpan ke Ticket — konsisten dengan pola `SonarTask` existing.
- Semua query & data **wajib scoped `SiteId`** (multi-tenant).
- Credential Crawler System/OneBox lewat config per-env, **jangan hardcode / commit**.
