# Voice of Customer (VoC) × OneBox — Project Status

> ⚠️ **BASI per 2026-09 — jangan dijadikan sumber kebenaran.** Dokumen ini
> bertanggal 2026-07-24, sebelum major refactor (R1–R11). Bagian "Belum/parsial"
> dan "Blockers" sudah tidak akurat: FE Next.js + user-auth sudah dipensiun,
> CRUD locations/competitors sudah di-drop, config sudah pindah ke
> pydantic-settings, dsb. Sumber terbaru: riwayat git dan
> `markdowns/04-implementation-plans/crawler-system/PLAN_MAJOR_REFACTOR.md`.
> Segarkan dokumen ini sebelum dipakai untuk handoff.
>
> Update asli: 2026-07-24 · Diverifikasi langsung ke kode hari itu.
> Otoritas keputusan: `markdowns/02-meetings-and-decisions/adr/ADR-*`. Semua ADR **belum diratifikasi Pak Agung**.

---

## 1. Di mana kita sekarang (1 paragraf)

Backend integrasi **sudah matang**: crawler VoC (headless) menarik review → masuk `Ticket` OneBox → tampil di dashboard & review UI yang berfungsi. Location & Competitor management punya CRUD backend lengkap. Yang tertinggal ada di **lapisan frontend (beberapa form masih mock/belum persist)**, **modul turunan (reports/insights/benefit masih stub)**, dan **hal infrastruktur/keputusan** (DB masih Supabase free tier, semua ADR belum diratifikasi lead). Fase saat ini: merapikan agar **demo Phase 1 solid**.

---

## 2. Vision

**Produk:** Fitur di dalam OneBox yang membuat manajemen Hermina bisa mengambil keputusan berbasis *suara pelanggan* — menarik review Google (nanti + sosmed) secara otomatis, dianalisa AI (sentiment, urgensi, kategori isu, rekomendasi), diklasifikasi, ditampilkan di dashboard VOC, dan **dikelola** lewat modul Ticket OneBox (assign/resolve/follow-up) — tanpa baca review satu per satu.

**Arsitektur:** OneBox = **System of Record** untuk semua modul (ADR-0001). VoC = **crawler engine headless** (scraping + AI eksekusi). Data VoC = cache, bukan sumber kebenaran.

---

## 3. Sudah diimplement ✅ (verified hari ini)

**Backend ingest (inti):**
- `VocProvider` — pull worklist (ADR-0003), dedup `review_hash`→`Message.RemoteId`, bikin Ticket+Message.
- `VoiceOfCustomerSystemClient` — health/login/getReviews/getIntegrationReviews/fetchPage.
- `syncnowAction` — tarik manual, idempotent.
- Labeling rule-first (`Service\Ruling`) auto-apply saat `addTicket` (D11) — klasifikasi tanpa token AI.

**Location management:**
- CRUD backend lengkap: `locationSave/Import/Toggle/Resync/Delete`.
- **PIC/penanggung jawab (nama/WA/email/id onebox)** — backend ditambahkan hari ini (write+read round-trip verified).

**Competitor management:**
- CRUD backend lengkap: `competitorSave/Create/Update/Toggle/Resync/Delete/Import/Detail`.
- Frontend `competitors.volt` **sudah wired ke backend** (13 panggilan).

**UI yang berfungsi (baca dari `Ticket` MediaId Gbusiness):**
- Dashboard VOC (`dashboardData`), Reviews (`reviewsData`) — tarik data nyata.
- Menu VoC + 9 submenu + permission (seed `voc_setup_all.sql`).

**Lain-lain:**
- `BenefitService` — 3 bug diperbaiki (lookup site jwt→session→config, addUsage, guard null).
- Seed user & menu (idempotent). Runbook akses menu untuk tim.
- ADR-0001..0004 terdokumentasi.

---

## 4. Belum / parsial ⏳

| Item | Status | Catatan |
|---|---|---|
| **Save frontend Location** | ❌ mock | `locations.volt` save/toggle/delete cuma update array JS, **tidak POST** ke backend → tidak persist. Blocker demo location mgmt |
| Reports | ⏳ stub | view ada, isi belum |
| Insights | ⏳ stub | cakupan masih dikaji |
| Setup parameter/benefit (screen client) | ❌ belum | butuh brainstorm (audience, editable/read-only) |
| AI param control (ADR-0002 split) | ❌ belum | parameter AI masih di VoC, token metering belum jalan |
| Migrasi DB Postgres→MySQL (ADR-0004) | ❌ belum | diputuskan, runbook siap, nunggu kredensial infra |
| FE Next.js VoC dipensiun (ADR-0001 #5) | ❌ belum | masih hidup |
| VoC auth → service account (ADR-0001 #6) | ❌ belum | masih user-based |
| Scheduler crawl kontinu | ❌ belum | sekarang manual (syncnow) |

---

## 5. Blockers (urut dampak)

1. **DB Supabase free tier** — lambat, tidur saat idle → 500 intermiten. Genting menuju produksi. *Aksi: ADR-0004, butuh kredensial server MySQL dari Nabil/Ridho.*
2. **Save frontend Location masih mock** — perubahan cabang (termasuk PIC) tidak persist. *Aksi: wire `locations.volt` save ke `Voc/locationSave` (snippet sudah disiapkan untuk Cello).*
3. **Semua ADR (0001–0004) belum diratifikasi Agung** — membangun di atas keputusan yang bisa berubah. *Aksi: bawa ADR ke lead.*
4. **Reproducibility dev env** — seed menu/role beda antar-dev kalau base DB beda. *Aksi: runbook ada; butuh base DB standar (keputusan Agung).*
5. **Benefit screen butuh desain** — audience & editable/read-only belum diputuskan. *Aksi: brainstorm.*
6. **Dua engine (Gbusiness resmi vs Selenium)** — pemilihan engine per-lokasi & dedup lintas-engine belum diputuskan. *Aksi: keputusan + tanya positioning ke Agung.*

---

## 6. Plan ke depan (prioritized)

### Sprint sekarang — solidkan demo Phase 1
1. **Wire save Location** (hilangkan mock) — blocker paling murah-berdampak.
2. **Brainstorm + build benefit screen** (mulai read-only).
3. **Reports & Insights** — dari stub jadi minimal berisi.

### Paralel — infrastruktur
4. **Eksekusi migrasi DB** (ADR-0004) begitu kredensial infra siap — ½–1 hari.
5. **Bawa ADR 0001–0004 ke Agung** untuk ratifikasi.

### Berikutnya — pasca-MVP
6. AI param split (ADR-0002) + token metering via Benefit.
7. Scheduler crawl kontinu (via media gateway existing).
8. Pensiunkan FE Next.js + VoC auth → service account.
9. Keputusan strategi dua-engine + dedup lintas-engine.

---

## 7. Keputusan yang menunggu Agung

| # | Keputusan | Dampak kalau berubah |
|---|---|---|
| ADR-0001 | OneBox = System of Record | fondasi seluruh rework |
| ADR-0004 | DB → MySQL di server OneBox | butuh kapasitas server + kredensial |
| Engine | Gbusiness resmi vs Selenium, per-lokasi | positioning VoC vs modul existing |
| Benefit screen | audience & editable | menentukan lokasi menu + kompleksitas |
| Base DB dev standar | dump canonical | keseragaman env tim |

*Dokumen ini living — perbarui tiap ada perubahan status.*
