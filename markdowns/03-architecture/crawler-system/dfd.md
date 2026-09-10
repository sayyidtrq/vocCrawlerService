> ⚠️ **SUPERSEDED oleh `decisions/ADR-0001-ownership-inversion.md` (2026-07-21).**
> **JANGAN dipakai sebagai acuan kerja baru.** DFD di bawah menampilkan "User/Admin VoC" sebagai aktor dengan UI, dan proses User/Auth Management + Competitor Monitoring di sisi VoC — itu **sudah tidak berlaku**. VoC kini headless (hanya proses Akuisisi Review); sisanya di OneBox. Disimpan sebagai histori.

# Voice of Customer System — DFD (Draft v1)

> **Status:** draf high-level, belum di-detailing.
> **Grounding:** proses dipetakan dari struktur nyata `app/services/*` dan `app/integrations/*` ✅.
> **Konvensi:** mengikuti gaya [onebox_system/dfd.md](../onebox_system/dfd.md) — lingkaran = proses, kotak = external entity, silinder = data store.
> **Companion:** [erd.md](erd.md) (rancangan struktur data target).

---

## DFD Level 0 — Context Diagram

Satu proses tunggal: **Voice of Customer System**. Empat external entity.

```mermaid
flowchart LR
    G["Google Maps / Google Places<br/>(sumber review publik)"]
    LLM["AI Provider<br/>(Gemini / OpenRouter / local LLM)"]
    U["User / Admin VoC<br/>(via FE dashboard / terminal)"]
    OB["OneBox / OneCloud<br/>(consumer utama)"]

    VOC(("Voice of Customer<br/>System"))

    G -->|"raw review + place data"| VOC
    VOC -->|"teks review untuk dianalisa"| LLM
    LLM -->|"hasil analisa (sentiment, urgency, dll)"| VOC
    U -->|"kelola lokasi, trigger fetch, lihat dashboard"| VOC
    VOC -->|"info review, dashboard, export"| U
    OB -->|"auth service + pull request (GET /api/reviews)"| VOC
    VOC -->|"JSON: reviews + analysis + dashboard"| OB
```

**Interpretasi:** VoC System duduk di tengah 4 dunia — narik dari Google, minjem otak AI provider, dikelola user internal, dan **menyuplai OneBox** (arah integrasi utama sesuai MUST_READ: OneBox = consumer, pull via REST).

---

## DFD Level 1 — Dekomposisi

Lima proses inti (dipetakan dari `app/services/`) + 1 proses usulan fase lanjut:

| # | Proses | Sumber kode | Data store yang disentuh |
|---|--------|-------------|--------------------------|
| 1 | **Akuisisi Review** (fetch/crawl) | `fetch_service`, `selenium_fetch_service`, `google_places_client`, `selenium_google_maps_client` | Source, Location, FetchSchedule, Review, FetchLog |
| 2 | **AI Analysis** | `analysis_service`, `gemini_client` / `openrouter_client` / `local_llm_client` | Review, ReviewAnalysis |
| 3 | **Data Provider API** (integrasi keluar) | FastAPI routes: `/api/reviews`, `/api/dashboard/*` | Review, ReviewAnalysis, Location |
| 4 | **User & Auth Management** | JWT auth, `entitlement_service`, `settings_service` | User, Company, ApiClient |
| 5 | **Competitor Monitoring** | `competitor_service` | Competitor, CompetitorReview |
| 6 | **Alert / Notification** ⚠️ *(usulan fase lanjut)* | belum ada | AlertRule, AlertEvent |

```mermaid
flowchart LR
    %% External entities
    G["Google Maps / Places"]
    LLM["AI Provider"]
    U["User / Admin VoC"]
    OB["OneBox"]

    %% Processes
    P1(("1<br/>Akuisisi<br/>Review"))
    P2(("2<br/>AI<br/>Analysis"))
    P3(("3<br/>Data Provider<br/>API"))
    P4(("4<br/>User & Auth<br/>Management"))
    P5(("5<br/>Competitor<br/>Monitoring"))

    %% Data stores
    DLoc[("Location")]
    DRev[("Review")]
    DAna[("ReviewAnalysis")]
    DLog[("FetchLog")]
    DUsr[("User")]
    DCom[("Company")]
    DCli[("ApiClient ⚠️")]
    DCpt[("Competitor")]
    DCRev[("CompetitorReview")]

    %% Flow proses 1
    U -->|"kelola lokasi, trigger fetch"| P1
    G -->|"raw review"| P1
    P1 -->|"data lokasi"| DLoc
    P1 -->|"review baru (dedup review_hash)"| DRev
    P1 -->|"log hasil fetch"| DLog

    %% Flow proses 2
    DRev -->|"review belum dianalisa"| P2
    P2 <-->|"prompt / hasil"| LLM
    P2 -->|"sentiment, urgency, issue category,<br/>summary, recommended action"| DAna

    %% Flow proses 3
    OB -->|"auth + GET /api/reviews<br/>(delta: updated_since)"| P3
    DRev --> P3
    DAna --> P3
    DLoc --> P3
    P3 -->|"JSON paginated"| OB

    %% Flow proses 4
    U -->|"login / register"| P4
    P4 --> DUsr
    P4 --> DCom
    P4 -->|"credential service-to-service"| DCli
    P4 -.->|"token & tenant scope (company_id)<br/>untuk semua proses"| P3

    %% Flow proses 5
    U -->|"daftarkan kompetitor"| P5
    G -->|"review kompetitor"| P5
    P5 --> DCpt
    P5 --> DCRev
```

**Catatan draf:**
- Proses 3 = **satu-satunya pintu untuk OneBox**. Dua penyesuaian target di pintu ini: (a) auth service-to-service via `ApiClient` ⚠️ (bukan JWT user), (b) dukungan **delta sync** `updated_since` — dua-duanya tercatat sebagai API gap, owner: Codex.
- Proses 4 memberi *scope tenant* (`company_id`) ke semua proses lain — mirror `SiteId` di OneBox.
- Proses 6 (Alert) belum digambar di diagram — diusulkan setelah MVP; polanya meniru grup Notification Onebox (lihat [erd.md](erd.md)).
- Dekomposisi Level 2 per proses menyusul setelah draf direview.
