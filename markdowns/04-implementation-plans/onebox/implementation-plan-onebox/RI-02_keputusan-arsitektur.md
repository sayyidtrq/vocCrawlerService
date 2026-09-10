> ⚠️ **SEBAGIAN SUPERSEDED oleh `../../decisions/ADR-0001-ownership-inversion.md` + `ADR-0002-ai-execution-split.md` (2026-07-21).**
> Yang **TIDAK berlaku lagi**: **D2** & **D6** (`Connection.TargetId` = location_id milik VoC; mapping lokasi berbasis config VoC) — sekarang lokasi dikelola di OneBox + auto-provisioning ke VoC. **D10** direvisi: parameter/kuota pakai `Benefit`/`SiteBenefit` (bukan hanya `Connection.Options`).
> Yang **masih berlaku**: D1, D3, D4, D5, D7, D8, D9, D11. Baca ADR dulu sebelum memakai dokumen ini.

# RI-02 — Keputusan Arsitektur (Decision Log) (≤2 MD)

> Status: **keputusan sementara sudah diambil & direvisi 2026-07-14** berdasarkan verifikasi langsung ke repo OneBox WSL + DB dev (temuan besar: pipeline review Gbusiness sudah ada — lihat RI-01 §7 dan `../implementation-plan/field-mapping-final.md`). Peran task ini: **minta ratifikasi lead** — tiap keputusan tinggal di-ACC atau dioverride Pak Agung. Semua keputusan reversible.

## Daftar Keputusan (D1–D11)

| # | Keputusan | Pilihan (default) | Alasan | Bukti |
|---|---|---|---|---|
| D1 | Kunci dedup | `Message.RemoteId = review_hash` — dedup efektif `SiteId+MediaId+RemoteId` (scope bawaan `ensureMessage`) | NOT NULL + unique di VoC; `external_review_id` nullable | [verified] models.py + Messaging.php:842 |
| D2 | Identitas koneksi per site | **1 row `Connection`** per site pilot: `ProviderId=PVDxx baru` (Reference `Code='VoiceOfCustomerSystem'`), `MediaId='GBUSINESS'`, dibuat manual (SQL); topologi per-lokasi vs per-company = K4 di dokumen final | pola persis Connection 805 existing (Gbusiness/PVD49); `Message.ConnectionId` valid untuk join UI | [verified] DB dev Connection 805 + Messaging.php:63 (provider factory) |
| D3 | Auth service-to-service (MVP) | **service user khusus di VoC + JWT login** (`/api/auth/login`) — credential disimpan di config per-env OneBox, **JANGAN hardcode di provider** (CiptalifeProvider yang hardcode = anti-contoh) | jalan hari ini tanpa perubahan VoC; API key/`ApiClient` = fase 2 (handoff Codex); asumsi 1 service user = 1 company (G4) | [verified] auth existing |
| D4 | Rumah field analisa | `summary`→`Ticket.Description` · `recommended_action`→`Ticket.Solution` · `urgency`→`Ticket.PriorityId` (**low=TP1, medium=TP2, high=TP3** — REVISI: usul awal kebalik) · `rating`→**`Meta.star`** (otomatis jadi `Ticket.Sentiment` via addTicket) · sisanya→`MessageContent.Meta` (JSON) · di-apply via **pass kedua** (Ticket dibuat async) | tanpa migration — sesuai guardrail; Meta.star = konvensi existing review | [verified] Reference DB dev (TP1=Low/TP2=Medium/TP3=High); Ticketing.php:334–341 |
| D5 | Channel/MediaId | **REVISI: reuse MediaId `GBUSINESS`** ("Google Business") — TIDAK bikin MediaId baru | media sudah ada di Reference (GroupId=Media) + UI existing (`dashboard/ReviewsController`, `AllReviewsController`) langsung jalan; data review tetap terpisah dari news via MediaId ini | [verified] DB dev Reference + 571 message GBUSINESS |
| D6 | Mapping tenant & lokasi (MVP) | mapping `company_id`/`location_id` VoC → `SiteId`/lokasi OneBox via **row Connection per site** (`Options` JSON menyimpan base_url/company_id/location map), 1 pilot site dulu; upgrade ke UI-managed nanti | konsisten dengan pola provider existing; tanpa migration | [verified] pola Connection.Options (GbusinessProvider) |
| D7 | `issue_category` | `Ticket.CategoryId` + **seed master Category** per site (kategori dari AI itu set kecil & tetap); saat ingest simpan juga `Meta.issue_category` biar tidak hilang sebelum seed siap | dashboard butuh agregasi per kategori — JSON Meta tidak bisa di-GROUP BY dengan wajar | [assumption] model Category — verifikasi di RI-07; contoh dev: ada Ticket GBUSINESS dgn CategoryId terisi (714) via rules |
| D8 | Sentiment AI (termasuk `mixed`) | **REVISI: seluruh AI sentiment (string asli 4 nilai + score) ke `Meta.ai_sentiment`/`Meta.ai_sentiment_score`** — TIDAK menyentuh `Ticket.Sentiment`, karena untuk tiket review kolom itu = rating bintang 1–5 (di-set otomatis dari `Meta.star`) | skala -1/0/1 hanya konvensi news/Mediamonitoring; konvensi review existing = star; tidak ada data hilang | [verified] Ticketing.php:334–341 + query Mediamonitoring |
| D9 | **(BARU)** Pola ingest | **Provider pattern**: class `VoiceOfCustomerSystemProvider extends Provider` + `messaging->ensureMessage()` — BUKAN task manual pola SonarTask | dapat gratis: dedup, pembuatan Ticket+Contact, rules, notifikasi, UI; pola yang sama dipakai review existing (Gbusiness, GooglePlay, Bukalapak) | [verified] GbusinessProvider.php + ProcessingService.php + Ticketing::addTicket |
| D10 | **(BARU)** Feature flag & entitlement | **Bertingkat, MVP paling murah:** (1) `Connection.Enabled` = master on/off per site; (2) flag granular di **`Connection.Options` JSON**, mirror entitlement VoC: `ai_analysis_enabled`, `competitor_enabled`, `review_quota`/`scrape_limit`; (3) `Menu`+`RoleMenu` = siapa yang lihat. **BELUM** pakai `Benefit`/`SiteBenefit` — baru dipakai kalau fitur ini dijual per-paket | konsisten dgn D2/D6 yang sudah menaruh config di `Connection.Options` → nol tabel baru, nol migration; VoC sudah punya padanannya di sisi sana (`require_ai_enabled`, `require_competitor_enabled`, `review_quota`) sehingga flag dua sisi bisa disamakan namanya | [verified] `app/services/entitlement_service.py` (VoC) + pola `Connection.Options` (GbusinessProvider) + `BenefitService::hasBenefit` |
| D11 | **(BARU)** Klasifikasi/labeling | **Rule-first, AI-secondary.** Label deterministik (issue category, prioritas, routing/assign) pakai **rule engine `Service\Ruling` yang sudah ada** (`Rule.Conditions`/`Actions` JSON per `SiteId`). AI VoC **hanya** untuk yang rules tak bisa: `summary`, `recommended_action`, nuansa sentiment | hemat token drastis (rules = 0 token, instan, deterministik, bisa diaudit); **gratis kalau D9 di-ACC** — `Ticketing::addTicket` sudah otomatis manggil `ruling->apply()`, jadi tanpa kode tambahan | [verified] `Ruling.php` (evaluateConditions/executeActions), `Ticketing.php:263`, `Rule.php`; bukti nyata: Ticket GBUSINESS dev CategoryId terisi via rules |

## Langkah Eksekusi
1. Bawa tabel D1–D11 + K1–K7 (dokumen final §7) ke Pak Agung (chat/meeting singkat) — format "ini default saya, mohon koreksi kalau ada yang keliru". (0.5 MD)
2. Update dokumen ini dengan hasil (ACC/override per baris) + tanggal. (0.5 MD)
3. Kalau ada override → propagasi ke plan RI terkait (tiap plan menyebut nomor D yang dipakainya).

## Hasil Ratifikasi
_(diisi setelah dibawa ke Pak Agung)_

| # | Hasil | Tanggal | Catatan |
|---|---|---|---|
| D1–D11 | pending | — | — |

## Definition of Done
Semua baris D1–D11 berstatus ACC/override, tercatat di sini, dan plan turunannya sudah disesuaikan.

## Risiko
- Lead override D4/D7 jadi "kolom baru di Ticket" → butuh migration; dampaknya ke RI-05/07/12 (sudah dirancang mudah beralih — lihat bagian Meta di RI-07).
- Lead override D9 (tetap pola SonarTask) → RI-04/RI-05 balik ke rencana awal; kehilangan otomatisasi Ticket/Contact/dedup — perlu ±3–5 MD ekstra.

## Dampak D9 ke Plan Turunan (kalau di-ACC)
- **RI-04** (`VoiceOfCustomerSystemClient`): tetap dibuat, tapi sebagai HTTP client yang dipakai provider (pola `Library\CiptalifeApi` dipanggil dari `CiptalifeProvider`) — bukan standalone.
- **RI-05** (`VoiceOfCustomerSystemTask`): berubah jadi `VoiceOfCustomerSystemProvider extends Provider` (`receive()` + pass kedua apply analisa) + seed Reference PVDxx + Connection pilot. Tidak nulis Ticket/Message manual.
- **RI-08** (scheduler): pakai mekanisme `receiveConnection` existing — perlu cek cara Connection dijadwalkan (cron/queue) saat eksekusi RI-08.
- **RI-10/11/12** (UI): evaluasi reuse `dashboard/ReviewsController` + `AllReviewsController` yang sudah filter GBUSINESS sebelum bikin controller baru.
