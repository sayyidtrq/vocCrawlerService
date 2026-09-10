# Prompt: Implementasi Key Process VoC OneBox — Demo Phase 1

> Paste blok `txt` di bawah ke Claude Code yang dibuka di project ini.
> Tujuan: implementasi 5 key process VoC, diprioritaskan untuk **demo Phase 1**.

---

## Temuan Kunci yang Mendasari Prompt Ini

**UI review sudah ada di OneBox.** Phase 1 bukan pekerjaan UI — melainkan **ingest data**. Begitu Ticket ber-`MediaId='Gbusiness'` masuk, dashboard existing langsung hidup.

| Key Process | Status di OneBox | Kerjaan Phase 1 |
|---|---|---|
| 1. Ambil review (crawler) | VoC Python ✅ selesai · sisi OneBox ❌ | **BUILD** — `VoiceOfCustomerSystemProvider` |
| 2. Tampilkan data review | ✅ `dashboard/ReviewsController` + `AllReviewsController` | **REUSE** — verifikasi + poles |
| 3. Filter review | ✅ filter per Connection/account + tanggal di `AllReviewsController` | **REUSE** — cek cakupan filter |
| 4. AI analysis | VoC ✅ · sisi OneBox: simpan ke Meta + rules | **BUILD kecil** — pass kedua + rules |
| 5. Kelola review | ✅ lifecycle Ticket (assign/resolve/note) | **REUSE** — verifikasi jalan utk tiket review |

---

```txt
Kamu adalah senior engineer yang mengimplementasikan fitur Voice of Customer (VoC) di OneBox untuk DEMO PHASE 1. Prioritaskan yang membuat demo hidup paling cepat, bukan kelengkapan fitur.

## BACA DULU (urut, wajib)
1. markdowns/00-start-here/MUST_READ.md — naming & boundary rules (yang menang kalau konflik)
2. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-02_keputusan-arsitektur.md — keputusan D1–D11
3. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/LABELING_rule-first-strategy.md — strategi labeling (D11)
4. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/DECISION_ui-placement-voc-menu.md — penempatan UI
5. markdowns/08-agent-prompts-and-handoffs/two_agents_workflow.md — pembagian peran Claude/Codex

## FAKTA TERVERIFIKASI (jangan diasumsikan ulang, jangan dilanggar)

Lokasi kode:
- OneBox (PHP): \\wsl.localhost\Ubuntu22.04-Swoole\var\www\html\onecloud\onecloud
- VoC System (Python/FastAPI): C:\Users\sayyi\Documents\project\hermina_crawler — API di http://localhost:8000, prefix /api

TEMUAN TERPENTING — pipeline review Gbusiness SUDAH ADA di OneBox:
- app/services/Provider/GbusinessProvider.php — TEMPLATE UTAMA. Struktur: __construct($di,$options,$messaging) baca Connection.Options JSON → receive() → listReviews($account,$location) → rowReview($row) → ensure($row) → messaging->ensureMessage($message). map() men-set $message->MediaId='GBUSINESS'.
- app/controllers/dashboard/ReviewsController.php — dashboard review SUDAH ADA: partialAction, categoryAction, priorityAction, statusAction, trendAction, reviewsSlaAction, getSumRatingAction, getAvgRatingAction, getDataRatingAction. Semua query: Ticket.SiteId=? AND Ticket.MediaId='Gbusiness' AND Ticket.Sentiment > 0.
- app/controllers/dashboard/AllReviewsController.php — list + report review, filter Connection MediaId='GBUSINESS'.
- CATATAN CASE: Ticket.MediaId dipakai sebagai 'Gbusiness', Connection.MediaId sebagai 'GBUSINESS'. Verifikasi nilai persis di DB dev sebelum menulis query — jangan menebak.

Mekanisme yang dapat dipakai gratis:
- app/services/Ticketing.php:263 → memanggil $this->ruling->apply($ticket,$message) otomatis saat addTicket. Jadi rules labeling jalan tanpa kode tambahan.
- app/services/Ruling.php — rule engine: model Rule (Conditions JSON, Actions JSON, Enabled, Priority, Terminal, RuleType='RLS1', SiteId). Kondisi: field Body|Channel|Category|kolom Message, type Contain|Equals|Not Contain, digabung And|Or. Aksi: set kolom Ticket apa pun (CategoryId, PriorityId, dll) + AgentId/OrganizationId.
- Ticketing::addTicket men-set Ticket.Sentiment dari Meta.star (rating bintang 1–5) — untuk tiket review, Sentiment BUKAN -1/0/1.

Keputusan yang mengikat (dari RI-02):
- D9: pakai Provider pattern (VoiceOfCustomerSystemProvider extends Provider + messaging->ensureMessage), BUKAN task manual ala SonarTask.
- D5: reuse MediaId Gbusiness/GBUSINESS, JANGAN bikin media baru.
- D1: dedup lewat Message.RemoteId = review_hash.
- D4: summary→Ticket.Description, recommended_action→Ticket.Solution, urgency→Ticket.PriorityId (TP1=Low,TP2=Medium,TP3=High), rating→Meta.star, sisanya→MessageContent.Meta.
- D8: sentiment AI (string+score) ke Meta.ai_sentiment / Meta.ai_sentiment_score — JANGAN sentuh Ticket.Sentiment.
- D10: feature flag di Connection.Enabled + Connection.Options JSON (ai_analysis_enabled, competitor_enabled, review_quota).
- D11: labeling rule-first (CategoryId/PriorityId via Rule), AI hanya untuk summary & recommended_action.

## SCOPE DEMO PHASE 1 (kerjakan HANYA ini)

Target demo: "review Google masuk otomatis ke OneBox, terklasifikasi, tampil di dashboard, dan bisa di-assign ke tim."

P1 (wajib, tanpa ini demo tidak jalan):
1. VoiceOfCustomerSystemProvider — tarik dari VoC API, dedup, jadi Ticket+Message via ensureMessage.
2. Seed data: Reference ProviderId baru + 1 row Connection pilot (Options berisi base_url, credential, company_id, location map, feature flags D10).
3. Pass kedua: apply field analisa (Description/Solution/PriorityId/Meta) sesuai D4/D8.
4. Verifikasi dashboard existing (dashboard/Reviews + AllReviews) menampilkan data hasil ingest.

P2 (kalau P1 selesai & masih ada waktu):
5. Rules labeling: seed master Category + 5–8 row Rule untuk kategori isu terbesar (LABELING doc Step 1–4).
6. Verifikasi aksi kelola review (assign/resolve/note) bekerja pada tiket review.

JANGAN dikerjakan di Phase 1:
- Jangan bikin VocController/menu/view baru dulu — pakai dashboard existing (DECISION doc menunggu ratifikasi Agung).
- Jangan bikin scheduler otomatis (manual trigger dulu).
- Jangan migration/kolom baru.
- Jangan refactor MediamonitoringController atau controller dashboard existing.
- Jangan pindahkan logic crawling/Selenium ke OneBox.

## CARA KERJA
1. VERIFIKASI DULU sebelum menulis kode: baca file pattern yang relevan, konfirmasi nama kolom/nilai Reference/MediaId di DB dev. Tandai klaim dengan [verified] / [assumption] / [blocked].
2. Kerjakan SATU item P1 dalam satu waktu. Setelah satu item selesai + terverifikasi jalan, BERHENTI dan laporkan sebelum lanjut.
3. Sebelum mengubah/membuat file, sebutkan dulu: path file, alasan, dan ringkasan perubahan.
4. Kalau menemukan fakta yang bertentangan dengan dokumen, JANGAN diam-diam menyesuaikan — laporkan sebagai "Temuan & Deviasi".
5. Kalau butuh endpoint/param VoC yang belum ada, catat sebagai "API Gap (handoff Codex)" — jangan tambal di OneBox.

## GUARDRAIL
- Semua query/insert WAJIB scoped SiteId.
- Jangan commit .env, .env.local, app/config/development.php, app/config/local.php.
- Jangan hardcode credential (CiptalifeProvider yang hardcode = anti-contoh; taruh di Connection.Options).
- Branch: feature/DNGO19-3346_Media-Crawler-Google-Business-Review. Jangan kerja di develop/hotfix/release.
- Teks review = konten publik tak terpercaya → escape di view, jangan raw.

## OUTPUT PERTAMA YANG DIMINTA
Jangan langsung menulis kode. Mulai dengan:
1. Ringkasan hasil verifikasi: nilai persis MediaId di Ticket vs Connection, ProviderId yang tersedia di Reference, struktur Connection.Options milik Connection Gbusiness existing (ID 805) sebagai contoh.
2. Rencana file: daftar path yang akan dibuat/diubah untuk P1 item 1–2, dengan alasan tiap file.
3. Baru setelah saya setujui, tulis kodenya.
```

---

## Catatan Pemakaian
- Jalankan di Claude Code yang dibuka di folder project ini (butuh akses WSL + repo VoC).
- Satu item P1 → review → lanjut. Jangan minta semua sekaligus.
- Kalau Agung meratifikasi/override D1–D11, update RI-02 dulu sebelum lanjut generate.
