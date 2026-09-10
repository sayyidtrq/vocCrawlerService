# Field Mapping FINAL — Review VoC System → OneBox

> Deliverable RI-01 · disusun 2026-07-14 · status: **terverifikasi ke kode & DB dev**
> Sumber bukti: repo OneBox WSL `/var/www/html/onecloud/onecloud` (branch `feature/DNGO19-3346_Media-Crawler-Google-Business-Review`), MySQL dev `onecloud`, repo VoC (`app/db/models.py`, `apps/api/app_api/schemas.py`, `routers/reviews.py`).
> Penanda: `[verified]` = dicek langsung ke kode/DB · `[decision]` = butuh ACC Pak Agung (ada default) · `[gap]` = handoff Codex.

---

## 0. TL;DR — 5 perubahan besar vs draft RI-01

1. **Pola ingest BUKAN SonarTask.** Review di OneBox masuk lewat **Provider pattern** (`GbusinessProvider` → `messaging->ensureMessage()`); Ticket, Contact, dedup, dan notifikasi dibuat otomatis oleh pipeline. VoC tinggal bikin `VoiceOfCustomerSystemProvider`. `[verified]`
2. **MediaId `GBUSINESS` sudah ada** ("Google Business", Reference GroupId=Media) lengkap dengan UI existing (`dashboard/ReviewsController`, `AllReviewsController`) — **tidak perlu MediaId baru**. `[verified]`
3. **Rating punya rumah:** `MessageContent.Meta.star` → `Ticketing::addTicket()` otomatis set `Ticket.Sentiment = star (1–5)`. Untuk tiket review, kolom `Sentiment` = rating bintang, bukan skala -1/0/1 (itu konvensi news/Mediamonitoring). `[verified Ticketing.php:334–341]`
4. **Kode prioritas draft KEBALIK.** Verified dari `Reference`: `TP1=Low`, `TP2=Medium`, `TP3=High` → mapping urgency yang benar: **low→TP1, medium→TP2, high→TP3**. `[verified]`
5. **API VoC:** `review_hash` SUDAH ada di response ✅; `updated_since` param belum ada dan `updated_at` belum di-expose di response → dua-duanya `[gap]` Codex (prasyarat RI-08 delta sync).

---

## 1. Arsitektur Ingest Terverifikasi

```
Connection (ProviderId → Reference PVD*, MediaId, SiteId, Options JSON)
  → Messaging::getInstance()                        [Messaging.php:63 — "\Service\Provider\{Reference.Code}Provider"]
  → {Code}Provider::receive()                       [dipanggil receiveConnection, Messaging.php:1026]
  → susun objek message (stdClass) → ensureMessage() [Messaging.php:842]
       ├─ dedup: Message::findFirst("SiteId=… and MediaId=… and RemoteId=…")   ← kunci dedup 3-kolom
       ├─ prepareMessage + addMessage (tulis Message + MessageContent + MessageUser)
       └─ dispatch job background "process"
  → ProcessingService::processMessageById            [ProcessingService.php:59]
  → Ticketing::addTicket()                           [Ticketing.php:282]
       ├─ Contact find-or-create (dari MessageUser MSR1) → Requestor/ContactId
       ├─ TypeId = TT1 (atau TT3 kalau Setting messaging='Media'), StatusId = TS2
       ├─ MediaId = Message.MediaId
       ├─ Sentiment = MessageContent.Meta.star (kalau ada)
       └─ ruling->apply() (rules bisa set CategoryId/PriorityId/assignee)
```

**Konsekuensi penting:** Ticket dibuat **async** (job background). Provider tidak bisa set field analisa (`Description/Solution/CategoryId/PriorityId`) saat ingest → butuh **pass kedua** (lihat §4).

**Contoh hidup di DB dev:** Connection 805 (SiteId 169, `MediaId='GBUSINESS'`, `ProviderId='PVD49'` Code=Gbusiness) — 571 Message GBUSINESS, semua ter-link ke Ticket (`ObjectName='Ticket'`). `[verified]`

---

## 2. Mapping `Review` (VoC) → objek message Provider

Bentuk objek mengikuti `GbusinessProvider::rowReview()` + `map()` (file: `app/services/Provider/GbusinessProvider.php:76–176`).

| Field VoC (response `/api/reviews`) | Target | Transform / Catatan | Status |
|---|---|---|---|
| `id` | — | PK internal VoC, tidak dipetakan | [verified] |
| `company_id` | (implisit) `Connection.SiteId` | tidak ada di response (scoped JWT service user); mapping tenant = pilih Connection per site (RI-06) | [verified] |
| `location_id` + `location` | `To = {id: location_id, name: location}` → MessageUser MSR2 | pola Gbusiness: `To.id = TargetId` lokasi; `Connection.TargetId` diisi `location_id` VoC (1 Connection : 1 lokasi) ATAU 1 Connection multi-lokasi — lihat §7-K4 | [decision] K4 |
| `source` | — | MVP selalu Google Maps; channel diwakili `MediaId='GBUSINESS'` | [verified] |
| `review_hash` | **`Message.RemoteId`** | kunci dedup; ensureMessage scope `SiteId+MediaId+RemoteId` — unique global VoC aman | [verified] |
| `external_review_id` | `Meta.external_review_id` | nullable → jangan dipakai dedup | [verified] |
| `reviewer_name` | `From.name` → MessageUser MSR1 → Contact (find-or-create) → `Ticket.Requestor`/`ContactId` | otomatis via `getMessageContactId` | [verified] |
| (identitas reviewer) | `From.id` | pola Gbusiness pakai id level-review (`reviewId`); usul VoC: `external_review_id ?? review_hash` | [verified pola] |
| `reviewer_profile_url` | `Meta.reviewer_profile_url` | MVP di Meta (Contact.Url menyusul kalau perlu) | [decision] default Meta |
| `reviewer_photo_url` | `Meta.reviewer_photo_url` | | [verified] |
| `reviewer_local_guide_level` | `Meta.reviewer_local_guide_level` | | [verified] |
| `reviewer_total_reviews` | `Meta.reviewer_total_reviews` | | [verified] |
| `rating` (1–5) | **`Meta.star`** → otomatis `Ticket.Sentiment` | integer; konvensi existing review OneBox | [verified] |
| `review_text` | `Content.Body` (+`BodyText` auto strip_tags di `map()`) | teks publik tak terpercaya — escape di Volt saat render | [verified] |
| (subject) | `Message.Subject` → `Ticket.Subject` (trim 3899 di addTicket) | Gbusiness hardcode `"Google Business Review"`; usul: trim `review_text` ±120 char, fallback `"Google Review — {location}"` | [decision] K5 |
| `review_time` | `ReceiveDate` | ISO 8601 (+TZ) → `Y-m-d H:i:s` — normalisasi ke TZ site (WIB) | [verified] |
| `review_relative_time` | — | derivatif, tidak dipetakan | [verified] |
| `review_language` / `language` | `Meta.language` | | [verified] |
| `like_count` | `Meta.like_count` | | [verified] |
| `owner_response_text` / `owner_response_time` | `Meta.owner_response` (MVP) | fase lanjut: Message kedua `Incoming=0` + ParentId | [decision] default Meta |
| `scraped_at`, `raw_payload`, `created_at` | — | audit internal VoC | [verified] |
| (method) | `MethodId = 'COMMENT'` | pola Gbusiness | [verified] |

## 3. Mapping `ReviewAnalysis` (VoC) → OneBox

| Field VoC | Target | Transform / Catatan | Status |
|---|---|---|---|
| `sentiment` (`positive/neutral/negative/mixed`) | `Meta.ai_sentiment` (nilai asli) | **REVISI dari draft:** TIDAK ke `Ticket.Sentiment` — kolom itu dipakai rating utk tiket review. Skala -1/0/1 hanya konvensi news | [verified] |
| `sentiment_score` | `Meta.ai_sentiment_score` | | [verified] |
| `issue_category` | `Ticket.CategoryId` (pass kedua, RI-07) + `Meta.issue_category` saat ingest | butuh seed master Category per site (D7); Meta duluan biar data tidak hilang | [decision] D7 |
| `urgency` (`low/medium/high`) | `Ticket.PriorityId` (pass kedua) | **low→TP1 · medium→TP2 · high→TP3** (kode verified dari Reference) | [verified] |
| `summary` | `Ticket.Description` (pass kedua) | kolom kosong di semua pola existing — aman | [verified] |
| `recommended_action` | `Ticket.Solution` (pass kedua) | idem | [verified] |
| `keywords` (JSON) | `Meta.keywords` | tag Mediamonitoring = fase lanjut | [verified] |
| `is_potential_viral` | `Meta.is_potential_viral` | AlertRule = fase lanjut | [verified] |
| `is_patient_safety_issue` | `Meta.is_patient_safety_issue` | idem — flag penting, jangan hilang | [verified] |
| `model_name`, `prompt_version`, `raw_response` | — | audit internal VoC | [verified] |
| `analyzed`, `analysis_id` | (kontrol sync) | penanda apakah pass kedua perlu jalan | [verified] |

## 4. Mekanisme Apply Analisa (catatan desain untuk RI-05/RI-07)

Karena Ticket dibuat async oleh job `process`, field analisa di-apply lewat **pass kedua** dalam run sync yang sama (atau run berikutnya):

```
untuk tiap review yang analyzed=true:
  msg = Message::findFirst("SiteId=… and MediaId='GBUSINESS' and RemoteId='{review_hash}'")
  if msg && msg.ObjectId:                      # ticket sudah dibuat job process
      ticket = Ticket::findFirst(msg.ObjectId)
      ticket.Description = summary
      ticket.Solution    = recommended_action
      ticket.PriorityId  = mapUrgency(urgency)   # low→TP1, medium→TP2, high→TP3
      ticket.CategoryId  = mapCategory(issue_category)   # setelah D7
      ticket.update()
  else: tunda ke run berikutnya (ticket belum ke-link)
```

Idempotent: pass kedua boleh jalan berulang (nilai sama = no-op efektif).

## 5. Konstanta Terverifikasi

| Objek | Field | Nilai | Sumber |
|---|---|---|---|
| Message | `TypeId` | `MST2` (Inbound) | GbusinessProvider::map + Reference |
| Message | `StatusId` | `MSS1` (New) | idem |
| Message | `PriorityId` | `MSP1` | GbusinessProvider::map |
| Message | `Incoming` | `1` | idem |
| Message | `MediaId` | `GBUSINESS` | idem |
| Message | `MethodId` | `COMMENT` | GbusinessProvider::rowReview |
| Ticket (auto) | `TypeId` | `TT1` (atau `TT3` kalau `Setting messaging='Media'` — **cek nilai setting di site pilot**) | Ticketing::addTicket |
| Ticket (auto) | `StatusId` | `TS2` (New) | idem |
| Ticket (auto) | `MediaId` | = `Message.MediaId` | idem |
| Ticket (auto) | `Sentiment` | = `Meta.star` (1–5) | idem |
| Reference | `TP1/TP2/TP3` | Low / Medium / High | query DB dev |
| Reference | `TT1/TT3` | def / mediamonitoring | query DB dev |

⚠️ **Catatan data lama:** Ticket GBUSINESS lama di dev punya `MediaId='Gbusiness'` (Reference.Code) sementara Message pakai `'GBUSINESS'` (Reference.Id) — inkonsistensi historis. `addTicket` sekarang menyalin `Message.MediaId`, jadi data baru konsisten `GBUSINESS`. Filter UI harus sadar dua varian ini kalau menyentuh data lama.

## 6. Master Data / Seed yang Dibutuhkan (untuk RI-05/RI-06)

1. **Reference Provider baru:** `Id='PVDxx'` (lanjutan; terakhir terpakai PVD96), `GroupId='Provider'`, `Code='VoiceOfCustomerSystem'`, `Description='Voice of Customer System'` → class `app/services/Provider/VoiceOfCustomerSystemProvider.php`.
2. **Connection per site pilot:** `MediaId='GBUSINESS'`, `ProviderId=PVDxx`, `SiteId=<pilot>`, `Options` JSON = `{base_url, email/credential-ref, company_id, location_map}` — credential JANGAN hardcode (pola CiptalifeProvider yang hardcode = anti-contoh).
3. **Master Category per site** (nanti di RI-07, setelah D7 di-ACC).

## 7. Butuh Keputusan Pak Agung (sisa [blocked]/[decision])

| # | Keputusan | Default usulan |
|---|---|---|
| K1 | ACC **pola Provider** (ganti rencana pola SonarTask) — RI-04/RI-05 menyesuaikan | pakai Provider pattern |
| K2 | ACC **reuse MediaId `GBUSINESS`** (bukan MediaId baru) — dapat UI existing gratis | reuse |
| K3 | ACC `Ticket.Sentiment` = rating (1–5), AI sentiment ke Meta — revisi D8 | ikut konvensi existing |
| K4 | Topologi Connection: **1 Connection per lokasi** (pola Gbusiness, TargetId=location) vs 1 Connection per company (location map di Options) | 1 per lokasi (paling kompatibel pipeline) |
| K5 | Format `Subject` tiket review | trim `review_text` 120 char, fallback `"Google Review — {location}"` |
| K6 | `Ticket.LocationId`: tetap null di MVP atau isi master Location OneBox | null di MVP |
| K7 | `TypeId` tiket: ikut auto (TT1/TT3) atau TT baru khusus review | ikut auto (existing Gbusiness = TT1) |

## 8. API Gap — Handoff Codex (sisi VoC)

| # | Gap | Prioritas | Status |
|---|---|---|---|
| G1 | `GET /api/reviews` belum ada param `updated_since` (filter `Review.updated_at >= ?`; kolom sudah ada) | sebelum RI-08 | open |
| G2 | `updated_at` belum di-expose di `ReviewResponse` (hanya `created_at`) — dibutuhkan sbg cursor delta | sebelum RI-08 | open — **gap baru** |
| G3 | ~~konfirmasi `review_hash` di response~~ | — | ✅ closed: ada di `schemas.py:109` |
| G4 | Response tidak memuat `company_id` — OK untuk MVP (scoping via JWT service user per company); catat asumsi **1 service user = 1 company** | dokumentasi | acknowledged |
| G5 | `review_hash` unique **global** (bukan per company) — kalau 2 company crawl lokasi sama bisa bentrok di sisi VoC | backlog VoC | open (carry-over RI-01) |

## 9. Appendix — Bukti Query (DB dev `onecloud`, 2026-07-14)

```sql
-- kode prioritas/status/type (hasil: TP1=Low, TP2=Medium, TP3=High; TS2=New; TT1=def, TT3=mediamonitoring; MST2=Inbound; MSS1=New)
SELECT Id, GroupId, Code, Description FROM Reference
WHERE Id LIKE 'TP%' OR Id LIKE 'TT%' OR Id LIKE 'TS%' OR Id LIKE 'MST%' OR Id LIKE 'MSS%';

-- media & provider (hasil: GBUSINESS='Google Business' GroupId=Media; PVD49 Code=Gbusiness; PVD terakhir=PVD96 Ciptalife)
SELECT Id, GroupId, Code, Description FROM Reference WHERE GroupId IN ('Media','Provider');

-- contoh hidup (hasil: Connection 805 SiteId 169 GBUSINESS/PVD49; 571 message; semua ObjectName='Ticket')
SELECT Id, SiteId, MediaId, ProviderId, TargetId FROM Connection WHERE Id=805;
SELECT MediaId, COUNT(*) FROM Message GROUP BY MediaId;  -- GBUSINESS = 571
SELECT m.Id, m.ObjectName, t.TypeId, t.StatusId, t.MediaId
FROM Message m JOIN Ticket t ON t.Id=m.ObjectId WHERE m.MediaId='GBUSINESS' LIMIT 5;
```

Referensi kode: `Messaging.php:842` (ensureMessage/dedup), `Messaging.php:63` (provider factory), `ProcessingService.php:59+` (process→addTicket), `Ticketing.php:282` (addTicket, Meta.star→Sentiment di :334–341), `GbusinessProvider.php:76–176` (rowReview/map).
