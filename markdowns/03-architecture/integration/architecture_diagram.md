> ⚠️ **SUPERSEDED oleh `../decisions/ADR-0001-ownership-inversion.md` (2026-07-21).**
> **JANGAN dipakai sebagai acuan kerja baru.** Diagram di bawah menggambarkan VoC punya FE/dashboard sendiri dan memiliki master data — itu **sudah tidak berlaku**. VoC kini headless (hanya scraping); dashboard/lokasi/kompetitor/report semua di OneBox. Berlaku juga untuk `voc_onebox_architecture.drawio`. Disimpan sebagai histori.

# Voice of Customer System × OneBox — Architecture Diagram

> Versi Mermaid (render otomatis di Obsidian & GitHub). Versi editable/presentasi: [voc_onebox_architecture.drawio](voc_onebox_architecture.drawio) — buka di app.diagrams.net / draw.io desktop / plugin VS Code / plugin Obsidian "Diagrams".
> Konvensi yang dipakai (Microsoft/AWS style): system boundary sebagai container, alur data bernomor kiri→kanan, warna konsisten per sistem, garis putus-putus = lintas boundary, ⚠️ = keputusan belum final.

## Diagram Konteks (Mermaid)

```mermaid
flowchart LR
    subgraph EXT["🌐 Sumber Eksternal"]
        R(["👤 Publik / Reviewer"])
        G["Google Maps / Google Reviews"]
        R -->|tulis review| G
    end

    subgraph VOC["🟨 Voice of Customer System — Docker · FastAPI · Python (owner: Codex)"]
        CR["Crawler Worker (Selenium)"]
        AI["AI Analysis<br/>sentiment · urgency · issue category<br/>summary · recommended action"]
        VDB[("VoC DB<br/>reviews + analysis")]
        API["REST API<br/>POST /api/auth/login · GET /api/reviews<br/>GET /api/dashboard/* ⚠️ auth S2S TBD"]
        CR -->|"2 · analisa AI"| AI
        AI -->|"3 · simpan"| VDB
        VDB --> API
    end

    subgraph OB["🟩 OneBox / OneCloud — Phalcon 5 + Swoole · multi-tenant SiteId (owner: Claude Code)"]
        subgraph INTG["Integration Layer (baru)"]
            TASK["VoiceOfCustomerSystemTask<br/>app/tasks · manual → scheduled<br/><i>pola: SonarTask</i>"]
            CLI["VoiceOfCustomerSystemClient<br/>app/library<br/><i>pola: CiptalifeApi</i>"]
        end
        DB[("MySQL<br/>Ticket · Message · MessageContent · Contact<br/><i>selalu scoped SiteId</i>")]
        UI["Mediamonitoring / VOC Dashboard<br/>Volt UI · menu + role permission"]
        TASK -->|"4 · trigger pull per SiteId"| CLI
        TASK -->|"6 · dedup (SiteId + review_hash)<br/>→ mapping → new Ticket/Message"| DB
        DB -->|"7 · query VOC:<br/>sentiment · urgency · trend"| UI
    end

    U(["👥 Pimpinan Pusat<br/>Reviewer · Kontributor"])

    G -->|"1 · scrape terjadwal"| CR
    CLI -.->|"5 · HTTPS: login + GET /api/reviews (Bearer)"| API
    UI -->|"8 · dashboard per role"| U

    style EXT fill:#f5f5f5,stroke:#666
    style VOC fill:#fff2cc,stroke:#d6b656
    style OB fill:#d5e8d4,stroke:#82b366
    style INTG fill:#ffffff,stroke:#82b366,stroke-dasharray: 5 5
    style DB fill:#dae8fc,stroke:#6c8ebf
    style VDB fill:#dae8fc,stroke:#6c8ebf
    style UI fill:#e1d5e7,stroke:#9673a6
```

## Narasi Alur (untuk presentasi)

1. **Scrape** — Crawler VoC System (Selenium) mengambil review publik dari Google Maps secara terjadwal.
2. **Analisa** — AI menganalisa tiap review: sentiment, urgency, issue category, summary, recommended action.
3. **Simpan** — Review + hasil analisa disimpan di DB VoC System (dedup internal via `review_hash`).
4. **Trigger** — Di OneBox, `VoiceOfCustomerSystemTask` (pola SonarTask) jalan manual dulu, nanti terjadwal — iterasi per `SiteId`.
5. **Pull** — Task memanggil `VoiceOfCustomerSystemClient` (pola CiptalifeApi): login → `GET /api/reviews` lintas boundary via HTTPS + Bearer. ⚠️ auth service-to-service belum final.
6. **Ingest** — Dedup (`SiteId` + `review_hash`/`external_review_id`) → mapping field → `new Ticket()` + `Message` + `MessageContent` (+ `Contact` reviewer). Semua ber-`SiteId`.
7. **Query** — Dashboard VOC membaca tabel internal (bukan call API realtime) — konsisten keputusan "persist, bukan proxy".
8. **Akses** — User melihat dashboard sesuai role (menu + role permission existing).

## Catatan Desain (kenapa begini)

- **Persist ke `Ticket` existing, bukan tabel baru** — keputusan lead; mengikuti pola yang sudah berjalan (SonarTask → Ticket → Mediamonitoring).
- **VoC System tetap microservice terpisah** — Selenium/crawling tidak boleh pindah ke OneBox (boundary rule di MUST_READ).
- **Dashboard baca DB internal, bukan proxy API** — UI tetap hidup walau VoC System down; bisa di-scope SiteId native; reuse reporting existing.
- **Titik rawan yang digambar eksplisit**: (a) garis 5 = satu-satunya dependency runtime antar sistem; (b) ⚠️ auth S2S; (c) mapping SiteId ↔ location.

## Cara pakai / edit

| Kebutuhan | Cara |
|---|---|
| Lihat cepat | Buka file ini di **Obsidian** (Mermaid render otomatis) |
| Edit visual / presentasi | Buka `.drawio` di **app.diagrams.net** atau draw.io desktop |
| Edit .drawio di Obsidian | Install community plugin **"Diagrams"** |
| Import Mermaid ke draw.io | draw.io → Arrange → Insert → Advanced → Mermaid → paste blok di atas |
| Export gambar | draw.io → File → Export as → PNG/SVG (untuk Google Docs / slide report) |
