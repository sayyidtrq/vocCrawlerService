# VoC × OneBox — Epic Backlog & User Stories

> Dibuat 2026-07-2X hasil sprint grooming. **Otoritas teknis tetap [ADR-0001..0004](../02-meetings-and-decisions/adr/) + [VOC_DEV_TASKLIST.md](task-breakdowns/VOC_DEV_TASKLIST.md)** — dokumen ini menambahkan lapisan Epic/Story di atasnya, tidak menggantikan.
> Setiap story mengacu ke task ID (`M#-##`) di `VOC_DEV_TASKLIST.md` untuk traceability. Status story = status task-nya di sana per tanggal dokumen ini.

---

## Prinsip grooming yang disepakati

1. **Epic → Story → Task**, bukan langsung Task. Epic = nilai bisnis; Story = kebutuhan peran; Task = unit kerja teknis (sudah ada di `VOC_DEV_TASKLIST.md`).
2. **M0 (fondasi teknis) dan "Demo Readiness/Proof X1-X5" BUKAN Epic** — diperlakukan sebagai **Gate** (prasyarat) dan **Release DoD** lintas-epic. Alasan: tidak ada "user story" natural untuk "ratifikasi ADR" atau "buktikan rantai nyambung" — itu prasyarat kerja / definisi selesai, bukan kebutuhan pengguna.
3. **E4 (Benefit) dipisah dari E1 (Master Data)** walau dua-duanya "config" — stakeholder beda: E1 untuk admin tenant (apa yang dipantau), E4 untuk komersial (berapa kuota, siapa bayar).
4. **E7 (Multi-Tenant) adalah generalisasi E1** — sengaja diurutkan setelah E1+E2 terbukti untuk 1 tenant.

---

## Daftar Epic (urutan prioritas)

| # | Epic | Status ringkas |
|---|---|---|
| E1 | Master Data & Config/Setup | Hampir selesai |
| E2 | Ingest & Ticketing | Jalur kritis, risiko tertinggi (belum terbukti di Dev) |
| E3 | Scheduling & Reliability | Belum mulai, nunggu E2 |
| E4 | Entitlement & Benefit | Sebagian (bug-fix selesai, registrasi belum) |
| E5 | AI Analysis & Insights | Kode ada, ada bug aktif (kategori tidak diskriminatif) |
| E6 | Review Management UI | Sebagian besar selesai |
| E7 | Multi-Tenant Onboarding (Opsi C) | Spec disetujui, kode belum ada |

---

## Gate lintas-epic (bukan Epic — prasyarat wajib)

| Gate | Isi | Wajib sebelum |
|---|---|---|
| G-ADR | Ratifikasi ADR-0001/0002/0003 ke Pak Agung | Kerja besar lanjut dianggap resmi |
| G-DEVENV | Seeding DB dev seragam antar dev (M0-06, **blocked**, dieskalasi) | Onboarding dev baru ke E1/E2 |
| G-ROLE | Perbaikan `getUserAllRole` (M0-07, **blocked**, butuh izin senior) | E6 story menu/role (M8-07) |
| G-NET | Jaringan WireGuard OneBox⇄Crawler terbukti 2 arah (bukan cuma asumsi) | E2 story delta pull |
| G-DBMIG | Migrasi Postgres→MySQL (ADR-0004) — **sedang ditahan**, jangan digabung dengan perubahan E2 | Rilis produksi Crawler |

---

# EPIC 1 — Master Data & Config/Setup

**Nilai bisnis:** admin tenant bisa mengatur apa yang dipantau (lokasi, kompetitor) tanpa bantuan developer, dan konfigurasi itu otomatis tersalur ke Crawler.
**Definition of Done Epic:** tambah/ubah/nonaktifkan lokasi & kompetitor di OneBox → otomatis muncul/hilang di worklist Crawler, tanpa langkah manual di sisi Crawler.

| ID                     | User Story                                                                                                                                                                          | Acceptance Criteria                                                                                            | Task terkait | Status                                             |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------ | -------------------------------------------------- |
| E1-S1                  | Sebagai **admin tenant**, saya ingin menambah/mengubah/menonaktifkan cabang (lokasi) yang dipantau, supaya saya bisa mengatur cakupan tanpa developer.                              | Form simpan berfungsi; toggle aktif/nonaktif; hapus hanya jika belum ada review; Place ID tidak boleh duplikat | M1-01        | ✅ Done                                             |
| E1-S2                  | Sebagai **admin tenant**, saya ingin mendaftarkan kompetitor yang ingin dipantau, supaya bisa membandingkan performa.                                                               | Pola sama seperti lokasi; `StatusId=CNS3` agar tak tersapu penjadwal                                           | M1-02        | ✅ Done                                             |
| E1-S3                  | Sebagai **sistem**, begitu lokasi/kompetitor disimpan di OneBox, target itu harus otomatis tersedia untuk ditarik Crawler, supaya tidak ada sinkronisasi ganda.                     | `GET /api/VocWorklist` ter-scope `sid` dari JWT                                                                | M1-03        | ✅ Done [verified]                                  |
| E1-S4                  | Sebagai **Crawler**, saya ingin menarik worklist dari OneBox dan menyimpannya ke cache lokal, supaya crawl tahu target tanpa OneBox mendorong data.                                 | Sync menghasilkan `status=synced`, target masuk cache                                                          | M1-05        | 🟡 WIP — [verified-dev] sebagian, belum penuh      |
| E1-S5                  | Sebagai **admin tenant**, saat saya menghapus/nonaktifkan lokasi, saya ingin crawl-nya berhenti **tanpa kehilangan data historis**, supaya review lama tetap ada untuk audit.       | Ditandai nonaktif, bukan dihapus fisik (selaras ADR-0001)                                                      | M1-04        | ✅ Done                                             |
| E1-S6                  | Sebagai **developer**, saya ingin jembatan transisi (push sync lama di tombol resync/toggle) dihapus setelah E1-S4 terbukti stabil, supaya tidak ada dual-write yang membingungkan. | Tombol resync/toggle OneBox tidak lagi memanggil endpoint tulis lama                                           | M1-06        | ⬜ Todo (nunggu E1-S4 terbukti)                     |
| E1-S7                  | Sebagai **sistem**, endpoint tulis Location/Competitor lama di Crawler harus jadi read-only bagi manusia, supaya OneBox benar-benar satu-satunya tempat edit.                       | Endpoint lama menolak write manual, hanya menerima dari sync internal                                          | M1-07        | ⬜ Todo                                             |
| — *(bug, bukan story)* | Connection dev 1039 (Hermina Depok) `StatusId` salah, ikut tersapu penjadwal                                                                                                        | Perbaiki `StatusId` jadi kode yang benar                                                                       | M1-08        | ⬜ Todo [verified] — **quick fix, kerjakan duluan** |

**Catatan risiko E1:** B2 di `PLAN_KEY_PROCESS_DEMO.md` — Connection dev mewarisi kredensial dari koneksi lama yang menunjuk alamat salah (`space.datakelola.com`, bukan API VoC). Ini **blocker nyata** buat E1-S4/E2, bukan cuma housekeeping — cek & perbaiki sebelum lanjut proof.

---

# EPIC 2 — Ingest & Ticketing

**Nilai bisnis:** review yang tercrawl otomatis masuk sebagai Ticket yang bisa ditindaklanjuti — tanpa duplikat, tanpa request yang nge-hang.
**Definition of Done Epic:** satu siklus penuh terbukti di Dev (bukan cuma lokal): tambah lokasi → crawl → review tersimpan+dianalisa → tertarik ke OneBox → jadi Ticket → bisa di-assign/resolve.

| ID | User Story | Acceptance Criteria | Task terkait | Status |
|---|---|---|---|---|
| E2-S1 | Sebagai **OneBox**, saya ingin memicu crawl satu target secara non-blocking, supaya UI tidak menunggu Selenium selesai. | `POST /api/integration/v1/crawl-jobs` balas `202`+`batch_id` <1 detik | M2-03 | ✅ [verified-dev] enqueue non-blocking dan crawl real terbukti; target 50 menghasilkan 40 review, 0 gagal |
| E2-S2 | Sebagai **sistem**, job yang gagal harus di-retry sesuai jenis error (429 backoff, 404 tidak diulang, timeout diulang singkat), supaya crawl tangguh. | Retry differentiated per kelas error | M2-04 | 🟡 [verified-local] |
| E2-S3 | Sebagai **sistem**, crawl antar-target harus diberi jeda, supaya tidak memicu blokir Google. | Rate limit + stagger dalam window | M2-05 | 🟡 [verified-local] |
| E2-S4 | Sebagai **ops**, saya ingin melihat status batch crawl (queued/succeeded/failed), supaya saya tahu progres tanpa membaca log mentah. | `GET /api/integration/v1/crawl-jobs/{batch_id}` | M2-07 | 🟡 [verified-local] |
| E2-S5 | Sebagai **OneBox**, saya ingin menarik review baru secara delta (bukan tarik ulang semua), supaya sinkron harian cepat dan tidak dobel. | Cursor `checkpoint_cursor` disimpan hanya setelah seluruh halaman sukses | M3-01, M3-03 | ⬜ Todo |
| E2-S6 | Sebagai **OneBox**, saat lokasi baru ditambahkan yang sudah punya histori lama di Crawler, saya ingin backfill penuh dulu sebelum masuk aliran delta, supaya tidak ada review lama yang terlewat. | `?location_id=&updated_since=<jauh>` dipanggil sebelum digabung ke delta | M3-04 | ⬜ Todo — **jebakan teridentifikasi, jangan skip** |
| E2-S7 | Sebagai **manajemen/agent**, saya ingin review otomatis menjadi Ticket yang bisa langsung ditindaklanjuti (assign/reply/resolve), supaya tidak perlu UI kelola terpisah. | Baris review di UI VoC bisa buka `Ticket/showTicketDetail` | (dari Key Process Demo P0) | ✅ Done 2026-07-21 — reuse `openTabTicketDetail` |
| E2-S8 | Sebagai **manajemen**, saya ingin review kompetitor tersedia untuk perbandingan, supaya bisa insight tanpa jadi Ticket. | Endpoint `competitor_reviews` di Crawler + consume di OneBox | M3-06 (API gap), M3-07 | 🔴 Blocked — endpoint belum ada sama sekali di Crawler |
| E2-S9 | Sebagai **OneBox**, saya ingin lokasi lama yang sudah sempat di-crawl tapi belum jadi Ticket direkonsiliasi, supaya tidak ada data "hilang" di tengah jalan. | Kasus Bekasi — item spesifik yang sudah ditemukan | M3-05 | ⬜ Todo |

**Release Gate E2 (update 31 Juli 2026):** X1 crawl Google real dan X5 enqueue sudah **[verified-dev]**. X1 berstatus PASS WITH LIMITATION karena target 50 menghasilkan 40 review tanpa kegagalan. Jalur kritis berpindah ke X3 analysis penuh, X4 delta enriched, lalu ingestion/Ticket OneBox. Jangan lompat ke E3 sebelum G3-G5 di runbook lulus.

---

## Placeholder Epic (di-groom sesi berikutnya)

Struktur di bawah **sengaja belum ditulis story-nya** — dikerjakan setelah E1+E2 selesai groom & mulai jalan, biar kualitas breakdown-nya sama detail, bukan buru-buru:

- **E3 — Scheduling & Reliability** (M4, M5)
- **E4 — Entitlement & Benefit** (M6) — bisa mulai groom lebih awal karena independen, tanya kalau mau dimajukan
- **E5 — AI Analysis & Insights** (M7) — **prioritas naik**: bug kategori (`doctor_service` 73/75) perlu story terpisah bertanda urgent, tidak menunggu urutan epic
- **E6 — Review Management UI** (M8 sisa)
- **E7 — Multi-Tenant Onboarding** (spec sudah ada di `SPEC-multi-tenant-opsi-c.md` §10 — tinggal dipecah jadi story)
