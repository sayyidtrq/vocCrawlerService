# Voice of Customer System - Team Assignment & Product Backlog

> Status: draft operasional untuk tim 4 orang
> Konteks: integrasi Voice of Customer System ke OneBox sedang berjalan di W2.
> Tujuan dokumen: membagi pekerjaan secara rata untuk 3 developer, mendefinisikan tanggung jawab lead dev/solution engineer, dan menyediakan product backlog yang bisa langsung dipakai untuk tracking.

---

## 1. Ringkasan Tim

| Role | Kapabilitas | Fokus Utama | Prinsip Pembagian |
|---|---|---|---|
| Lead Dev + Solution Engineer | Arsitektur, integrasi, review, deployment, koordinasi stakeholder | Decision, unblocker, quality gate, integration owner | Tidak menjadi bottleneck coding harian; fokus ke desain, review, dan end-to-end demo |
| Dev A - Backend | Backend utama | OneBox ingestion, task, provider, mapping Ticket/Message/Contact | Memegang jalur data masuk ke OneBox |
| Dev B - Backend half + FE | Fullstack ringan | VoC API/client, data validation, support dashboard data, testing | Menjadi jembatan backend Crawler System dan UI data |
| Dev C - FE | Frontend | UI VoC di OneBox: list, detail, dashboard polish, empty/error state | Memegang pengalaman pengguna dan tampilan demo |

---

## 2. Target MVP

MVP dianggap siap demo jika alur berikut berjalan:

```text
Review real dari Voice of Customer System
-> dipull oleh OneBox
-> dedup tidak membuat duplikat
-> reviewer dibuat/dicari sebagai Contact
-> review masuk sebagai Ticket + Message + MessageContent
-> review tampil di list/detail VoC
-> dashboard menampilkan sentimen, urgency, trend, kategori isu, dan lokasi prioritas
```

---

## 3. Pembagian Tugas Utama

### Lead Dev + Solution Engineer

| Area | Task | Output |
|---|---|---|
| Architecture | Finalisasi keputusan integrasi: pull model, endpoint, auth mode, field mapping, dedup key | Decision log yang jelas dan disetujui tim |
| Coordination | Sinkronisasi scope dengan OneBox, Infra, dan stakeholder | Daily direction + blocker list |
| Deployment | Pastikan VoC backend dapat diakses dari jaringan OneBox dan env live benar | Base URL, credential, health check, smoke evidence |
| Code Review | Review PR Dev A/B/C sebelum merge | PR aman, tidak bocor credential, tidak breaking flow existing |
| Integration Test | Menjalankan skenario end-to-end dari fetch real data sampai tampil di UI OneBox | Evidence demo dan daftar bug prioritas |
| Risk Management | Mitigasi Selenium, fallback official API, dan reliability plan | Risk register + fallback decision |

Lead tidak mengambil banyak story implementasi UI/backend rutin, kecuali task high-risk yang perlu keputusan cepat.

### Dev A - Backend OneBox

| Area | Task | Output |
|---|---|---|
| Client | Rapikan `VoiceOfCustomerSystemClient` untuk login/pull data live, timeout, retry, dan error envelope | Client stabil untuk mock dan live mode |
| Ingestion | Rapikan `VoiceOfCustomerSystemTask` untuk receive, analysis, processpending | Command task bisa dijalankan ulang tanpa duplikasi |
| Mapping | Implement mapping Review -> Contact -> Ticket -> Message -> MessageContent | Data OneBox konsisten dan scoped SiteId |
| Dedup | Pastikan `RemoteId` / `review_hash` mencegah duplikat | Rerun task menghasilkan 0 duplicate ticket |
| Observability | Tambah log ringkasan run: total fetched, inserted, duplicate, failed | Debug lebih cepat saat demo/staging |

### Dev B - Backend Half + FE

| Area | Task | Output |
|---|---|---|
| VoC API Support | Verifikasi endpoint `/api/reviews`, auth JWT, pagination, filter, latest_first | Contract praktis untuk OneBox live pull |
| Real Data Fetch | Bantu setup real fetch dari Google Places/Selenium sesuai env | Review real masuk ke DB VoC |
| Data Shape | Validasi field sentiment, urgency, issue_category, summary, recommended_action | Payload siap dimapping ke OneBox |
| Test Fixture | Maintain fixture/sample untuk local dev dan regression | Dev bisa test tanpa service live |
| Dashboard Data | Bantu endpoint/query `dashboardData` agar FE dapat data siap render | FE tidak perlu hitung logic berat di browser |

### Dev C - Frontend

| Area | Task | Output |
|---|---|---|
| Route & Menu | Pastikan menu VoC di Media Monitoring stabil dan role-based | Menu muncul di tempat benar |
| Review List | Rapikan tabel reviews: filter, search, pagination, status, empty state | List review enak dipakai dan demo-ready |
| Detail Page | Buat detail review: teks review, reviewer, rating, sentiment, urgency, recommended action | User bisa memahami satu kasus review |
| Dashboard | Polish dashboard KPI, sentimen, top issue, negative reviews, lokasi prioritas | Dashboard ringkas dan informatif |
| UI State | Loading, error, no data, partial data, retry | UI tidak terlihat rusak saat API/data bermasalah |

---

## 4. Roadmap Kerja

| Week | Fokus | Output Utama | Owner Dominan |
|---|---|---|---|
| W1 | Pengembangan VoC System dan fix feedback | API, dashboard awal, data model, crawler/fetch feedback | Lead + Dev B |
| W2 | Kickoff dan integrasi OneBox | Branch, client/task, menu route, fixture ingest, akses service | Lead + Dev A + Dev C |
| W3 | Prototype dan real data | Real review dari VoC masuk ke Ticket/Message, list/detail/dashboard membaca data real | Dev A + Dev B + Dev C |
| W4 | Stabilization, UAT, handoff | Scheduler/delta, reliability, bugfix, runbook, demo final | Semua, dipimpin Lead |

Status saat ini: W2 sedang berjalan.

---

## 5. Product Backlog

### Epic 1 - Integration Foundation

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-001 | Sebagai tim, saya perlu keputusan final field mapping Review ke entity OneBox agar implementasi tidak berubah-ubah | P0 | Lead | 1 MD | - | Mapping Review -> Ticket/Message/Contact terdokumentasi dan dipakai semua dev |
| VOC-002 | Sebagai engineer OneBox, saya perlu client yang bisa login dan pull data dari VoC API | P0 | Dev A | 2 MD | VOC-001 | Client bisa mock dan live, timeout jelas, error terbaca |
| VOC-003 | Sebagai engineer, saya perlu konfigurasi Connection per SiteId/location agar pull data bisa diarahkan per tenant | P0 | Dev A | 1.5 MD | VOC-001 | Connection 1039/1040 atau env target bisa run sesuai SiteId |
| VOC-004 | Sebagai lead, saya perlu smoke test dari OneBox ke VoC backend agar akses network tervalidasi | P0 | Lead | 1 MD | VOC-002 | `curl /api/health`, login, dan pull reviews sukses dari container OneBox |

### Epic 2 - Data Ingestion to OneBox

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-010 | Sebagai user OneBox, saya ingin review masuk sebagai Ticket agar dapat ditindaklanjuti | P0 | Dev A | 2 MD | VOC-002 | Review menghasilkan Ticket scoped SiteId dengan ProviderId VoC |
| VOC-011 | Sebagai user OneBox, saya ingin isi review tersimpan sebagai Message/MessageContent agar konteks review tidak hilang | P0 | Dev A | 1.5 MD | VOC-010 | Message dan MessageContent terisi teks review dan metadata penting |
| VOC-012 | Sebagai sistem, saya perlu find-or-create Contact reviewer agar reviewer tidak dibuat dobel | P0 | Dev A | 1.5 MD | VOC-010 | Reviewer yang sama reuse Contact sesuai aturan matching |
| VOC-013 | Sebagai sistem, saya perlu dedup agar rerun task tidak membuat Ticket duplikat | P0 | Dev A | 1 MD | VOC-011 | Rerun receive menghasilkan duplicate count, bukan insert baru |
| VOC-014 | Sebagai operator, saya perlu log ingestion yang jelas agar error bisa dilacak | P1 | Dev A | 1 MD | VOC-010 | Log mencatat fetched/inserted/duplicate/failed dan request context |

### Epic 3 - Real Data from VoC System

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-020 | Sebagai tim, saya perlu VoC backend mengambil review real agar demo tidak hanya fixture | P0 | Dev B | 2 MD | akses API/source | Review real masuk DB VoC dan terlihat di `/api/reviews` |
| VOC-021 | Sebagai OneBox, saya perlu payload review punya field analisis yang stabil | P0 | Dev B | 1.5 MD | VOC-020 | Payload punya rating, review_text, review_hash, sentiment/urgency jika analyzed |
| VOC-022 | Sebagai developer, saya perlu fixture tetap tersedia untuk regression saat service live down | P1 | Dev B | 1 MD | VOC-021 | Mock mode tetap bisa menjalankan 10+ sample tanpa internet |
| VOC-023 | Sebagai tim, saya perlu dokumentasi cara switch mock ke live | P1 | Dev B | 0.5 MD | VOC-020 | Connection/env menjelaskan `mock=false`, base URL, user/pass/token |

### Epic 4 - VoC UI in OneBox

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-030 | Sebagai user, saya ingin menu VoC muncul di Media Monitoring sesuai role | P0 | Dev C | 1 MD | seed menu | Menu VoC muncul dan route `#/voc/*` membuka tab benar |
| VOC-031 | Sebagai user, saya ingin melihat list review dengan filter dasar | P0 | Dev C | 2 MD | VOC-010 | Tabel menampilkan review real dari Ticket/Message |
| VOC-032 | Sebagai user, saya ingin membuka detail review agar bisa melihat konteks dan rekomendasi aksi | P0 | Dev C | 2 MD | VOC-031 | Detail menampilkan review, rating, contact, sentiment, urgency, summary |
| VOC-033 | Sebagai manager, saya ingin dashboard ringkas untuk melihat kondisi VoC | P0 | Dev C | 2 MD | VOC-031, VOC-021 | KPI, sentiment distribution, top issue, negative review tampil |
| VOC-034 | Sebagai user, saya butuh loading/error/empty state agar UI tidak membingungkan | P1 | Dev C | 1 MD | VOC-031 | Semua state utama punya tampilan jelas |

### Epic 5 - Scheduler, Delta, and Reliability

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-040 | Sebagai sistem, saya perlu scheduler agar pull tidak manual terus | P1 | Dev A | 2 MD | VOC-014 | Task bisa dijalankan scheduled tanpa duplikasi |
| VOC-041 | Sebagai sistem, saya perlu checkpoint/delta sync agar hanya data baru/berubah yang ditarik | P1 | Dev A + Dev B | 2 MD | VOC-013, VOC-021 | Pull berikutnya tidak mengambil semua data lagi |
| VOC-042 | Sebagai lead, saya perlu runbook deploy dan rollback agar demo/staging aman | P1 | Lead | 1 MD | VOC-004 | Runbook berisi deploy, smoke, rollback, dan known issue |
| VOC-043 | Sebagai tim, saya perlu risk mitigation Selenium agar crawler tidak menjadi single point of failure | P1 | Lead + Dev B | 1 MD | VOC-020 | Risk register dan fallback source tersedia |

### Epic 6 - QA, UAT, and Demo Readiness

| ID | Story | Priority | Owner | Size | Dependency | Acceptance Criteria |
|---|---|---:|---|---:|---|---|
| VOC-050 | Sebagai lead, saya perlu test scenario end-to-end untuk memastikan alur lengkap | P0 | Lead | 1 MD | VOC-030..033 | Checklist E2E lulus: fetch, ingest, list, detail, dashboard |
| VOC-051 | Sebagai developer, saya perlu bug bash W3/W4 agar prototype stabil | P1 | Semua | 2 MD | MVP UI | Bug P0/P1 ditutup sebelum demo |
| VOC-052 | Sebagai stakeholder, saya perlu demo story yang jelas | P1 | Lead | 0.5 MD | VOC-050 | Script demo menjelaskan problem, flow, output, dan next step |

---

## 6. Workload Balance

| Person | Estimasi MD MVP | Fokus Beban | Catatan |
|---|---:|---|---|
| Lead | 6-8 MD | Decision, deployment, review, E2E, demo | Jangan ambil terlalu banyak coding agar bisa unblock semua orang |
| Dev A - Backend | 11-13 MD | Client, ingestion, mapping, dedup, scheduler | Beban backend paling kritis, tapi scope jelas |
| Dev B - Backend/FE | 8-10 MD | Real data, API shape, fixture, dashboard data | Cocok sebagai bridge antara VoC backend dan UI |
| Dev C - FE | 8-10 MD | Menu, list, detail, dashboard polish, states | Scope UI cukup besar tapi tidak perlu masuk ingestion |

Pembagian ini sengaja membuat Dev A memegang critical backend path, Dev C memegang demo surface, Dev B menjadi integrator data, dan Lead menjaga arah serta kualitas.

---

## 7. Suggested Daily Workflow

1. Pagi: 15 menit sync blocker.
2. Siang: tiap dev push small commit/PR.
3. Sore: Lead review PR dan update blocker.
4. Setiap selesai story: isi evidence singkat.
5. Setiap bug P0: hentikan feature baru sampai alur utama kembali hijau.

Evidence minimal:

```text
Story:
Branch/commit:
Command/test:
Screenshot/log:
Known issue:
Next action:
```

---

## 8. Definition of Done MVP

- Real review berhasil masuk dari VoC System.
- OneBox berhasil pull data tanpa fixture.
- Review menjadi Ticket + Message + MessageContent.
- Dedup berhasil saat task dijalankan ulang.
- List review menampilkan data real.
- Detail review menampilkan konteks review dan hasil analisis.
- Dashboard menampilkan KPI utama.
- Menu dan permission dasar aktif.
- Ada runbook deploy, smoke test, dan rollback sederhana.
- Ada daftar risiko Selenium dan fallback source.

