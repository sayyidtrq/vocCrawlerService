# MUST_READ - Voice of Customer  System x OneBox Integration

Instruksi wajib untuk Claude Code, Codex, dan engineer sebelum lanjut integrasi OneBox.

---

## ðŸš¨ BACA PALING AWAL â€” Architecture Decision Records (ADR)

ADR adalah **otoritas tertinggi**. Kalau ADR bertentangan dengan dokumen lain, **ADR yang menang**.

| ADR | Isi | Status |
|---|---|---|
| `../decisions/ADR-0001-ownership-inversion.md` | **OneBox = System of Record.** Seluruh modul VoC (dashboard, review mgmt, location, competitor, reports, insights, parameter/benefit) dikelola di OneBox. VoC = crawler engine **headless**, hanya scraping. | Accepted Â· diratifikasi internal 2026-07-22 Â· **mekanisme provisioning di-amandemen ADR-0003** |
| `../decisions/ADR-0002-ai-execution-split.md` | AI: **parameter & kuota di OneBox, eksekusi di VoC.** VoC wajib mengembalikan `tokens_used`. | Accepted |
| `../decisions/ADR-0003-crawl-execution-pull-queue.md` | **Eksekusi crawl.** Provisioning **push sinkron â†’ pull worklist** (VoC menarik daftar target dari OneBox; simpan lokasi jadi instan). VoC pakai **antrean crawl durable + worker** (bukan fetch blocking), crawl **inkremental** (cursor). Scheduler tiga-window RI-08 tetap, trigger jadi **non-blocking**. | Accepted |
| `../decisions/ADR-0004-fast-ingestion-labeling-on-demand-ai.md` | **Review fast path.** Raw review masuk OneBox tanpa menunggu AI; sentiment labeling memakai program existing OneBox; AI analysis dipicu user untuk single/bulk dan berjalan asynchronous. | Accepted |

### Daftar modul NON-NEGOTIABLE (ditetapkan 2026-07-22)

Semua ini **dikelola di OneBox**, tanpa kecuali:
setup lokasi Â· setup competitor Â· dashboard Â· review management Â· location management Â·
competitor management Â· reports Â· AI analysis Â· insights Â· setup parameter/benefit.

**Scraping tetap milik VoC** â€” jangan pindahkan Selenium/crawling ke OneBox.

Cakupan **AI analysis** dan **insights** masih akan dikaji ulang; kepemilikannya tidak.
Status implementasi per modul + konsekuensi teknis: lihat bagian "Ratifikasi internal" di ADR-0001.

âš ï¸ Ratifikasi ini **internal dev, belum disetujui Pak Agung.**

## â›” DOKUMEN YANG SUDAH TIDAK BERLAKU (jangan jadikan acuan kerja baru)

Semua sudah diberi banner di bagian atas file. Disimpan hanya sebagai histori.

1. `../crawler_system/erd.md` â€” ERD lama: VoC memiliki Location/Competitor/Company/User
2. `../crawler_system/dfd.md` â€” DFD lama: VoC punya aktor User/Admin + UI
3. `architecture_diagram.md` + `voc_onebox_architecture.drawio` â€” VoC digambar punya FE sendiri
4. `implementation-plan-onebox/RI-06_tenant-mapping.md` â€” mapping lokasi arah terbalik
5. `implementation-plan-onebox/RI-02_keputusan-arsitektur.md` â€” **sebagian**: D2, D6 batal; D10 direvisi. D1/D3/D4/D5/D7/D8/D9/D11 masih berlaku.

**Aturan menulis dokumen baru:** kalau sebuah keputusan arsitektur berubah, buat ADR baru di `markdowns/02-meetings-and-decisions/` (format `ADR-####-nama.md`), tandai dokumen lama dengan banner SUPERSEDED **di 5 baris pertama**, lalu daftarkan di sini.

---

## Canonical Naming

Mulai sekarang gunakan nama **Voice of Customer  System** untuk sistem Voice of Customer  + analysis ini.

Jangan gunakan nama lama untuk dokumen baru, task baru, class baru, prompt baru, atau komunikasi implementasi baru.
Nama lama hanya boleh muncul saat membahas dokumen historis, repo/deployment lama, path existing, atau kutipan chat lama.

Naming baru yang dipakai: Voice of Customer SystemClient, Voice of Customer SystemTask, Voice of Customer SystemSync.

## System Boundary

Voice of Customer  System adalah external microservice untuk crawling, review retrieval, analysis, dan data provider API.
OneBox adalah consumer. Untuk fase ini OneBox pull data dari Voice of Customer  System.

Flow utama: Voice of Customer  System API -> OneBox client -> sync task -> Ticket / Message / MessageContent -> Mediamonitoring / VOC UI.

Jangan pindahkan logic Selenium/crawling ke OneBox.

## Agent Ownership

Claude Code fokus pada OneBox: baca struktur, cari pattern existing, implement client/sync task, mapping model, dan validasi UI.
Codex fokus pada Voice of Customer  System: API contract, contoh request/response, docs handoff, API gap, tasklist, dan progress report.

## Peta kerja aktif

**[VOC_DEV_TASKLIST.md](../01-product-and-backlog/task-breakdowns/VOC_DEV_TASKLIST.md)** â€” tasklist development per modul (M0â€“M9) berikut
prasyarat, owner, dependensi, dan status. Ini yang menentukan **urutan & status** pekerjaan.
Dokumen `RI-xx` dan `VOC-CS-xx` tetap dipakai sebagai **detail teknis** tiap task.

## Required Reading Order

1. markdowns/00-start-here/MUST_READ.md
2. markdowns/02-meetings-and-decisions/adr/ADR-0004-fast-ingestion-labeling-on-demand-ai.md
3. markdowns/04-implementation-plans/key-process/PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md
4. markdowns/01-product-and-backlog/task-breakdowns/VOC_DEV_TASKLIST.md
3. markdowns/08-agent-prompts-and-handoffs/two_agents_workflow.md
3. markdowns/01-product-and-backlog/task-breakdowns/tasklist-draft.md
4. markdowns/99-legacy-reference/developer_guide.md
5. markdowns/08-agent-prompts-and-handoffs/superprompt.md
6. markdowns/00-start-here/link-docs.md
7. markdowns/04-implementation-plans/crawler-system/implementation-plan-crawler-system/VOC-CS-08_consumer-worklist.md

Dokumen lama boleh belum dimigrasi. Untuk pekerjaan baru, file ini yang menang.

## Rules For New Work

- Jangan hardcode credential API, DB, atau token.
- Jangan commit perubahan config lokal seperti .env, .env.local, atau config development pribadi.
- Jangan coding besar sebelum field mapping OneBox jelas.
- Kalau OneBox butuh parameter yang belum ada, catat sebagai API gap Voice of Customer  System.
- Handoff antar agent wajib menandai status: verified, assumption, atau blocked.
- Worklist consumer wajib memakai ONEBOX_COMPANY_ID yang eksplisit; tenant tidak boleh ditebak.
- OneBox adalah scheduler dan master data; Crawler System hanya me-refresh cache target lalu menjalankan crawling.

## Current Integration Assumption

- Voice of Customer  System berjalan sebagai 3rd party service.
- Deployment Voice of Customer  System memakai Docker.
- **Dua arah pull (lihat [ADR-0003](../02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md)):**
  - VoC **pull worklist** dari OneBox (`GET /api/VocWorklist (configurable)`) untuk tahu target crawl â€” menggantikan push `POST /api/locations`.
  - OneBox **pull review delta** dari VoC (`GET /api/integration/v1/reviews`) untuk masuk Ticket.
- Trigger crawl dari OneBox bersifat **non-blocking** (enqueue), bukan fetch sinkron menunggu Selenium.
- Auth/access API dari sisi OneBox masih perlu dikonfirmasi.
- Parameter final dari OneBox masih perlu dikonfirmasi.
## Urgent demo contract - Fetch Jobs end-to-end

Sebelum mengubah flow Fetch Jobs, wajib baca:

- `FETCH_JOBS_E2E_CONTRACT.md` - kontrak satu klik crawl sampai Kelola Review;
- `PROMPT_FETCH_JOBS_E2E_CLAUDE.md` - task implementasi OneBox untuk Claude;
- `PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md` - flow raw ingestion dan AI on-demand.

Untuk demo, source dikunci ke Selenium dan date range dinonaktifkan sampai durable crawl API
mendukung keduanya. Tombol `Tarik Review Sekarang` tidak boleh menjadi langkah wajib.
