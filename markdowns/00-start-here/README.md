# VoC Markdown Knowledge Base

Folder ini adalah pusat dokumentasi enhancement Voice of Customer OneBox dan Crawler Service.

Struktur disusun berdasarkan satu dimensi utama: tujuan dokumen. Jika mencari sesuatu, mulai dari kategori tujuan kerja, bukan dari nama modul atau nama pembuat dokumen.

## Struktur Folder

| Folder | Tujuan | Kapan dibaca |
| --- | --- | --- |
| `00-start-here` | Orientasi, status proyek, dan dokumen lintas modul | Saat onboarding, handoff, atau mencari konteks cepat |
| `01-product-and-backlog` | Grooming, backlog, Jira spec, user story, task breakdown | Saat menyusun scope, sprint, atau copy task ke Jira |
| `02-meetings-and-decisions` | Notulen, revisi stakeholder, ADR, opsi arsitektur | Saat butuh alasan keputusan atau perubahan arah |
| `03-architecture` | ERD, DFD, kontrak integrasi, diagram sistem | Saat memahami boundary OneBox, Crawler, DB, queue, API |
| `04-implementation-plans` | Plan teknis per modul dan work package | Saat mulai development paralel Codex/Claude |
| `05-runbooks` | Prosedur setup, deployment, UAT, Postman, tenant onboarding | Saat menjalankan sistem, demo, testing, atau deploy |
| `06-troubleshooting` | Insiden, diagnosa, dan resolusi masalah berulang | Saat error muncul di UI/log/server |
| `07-data-and-seeding` | SQL seed, mapping field, workbook referensi | Saat setup master data, tenant, atau migrasi data |
| `08-agent-prompts-and-handoffs` | Prompt Claude/Codex dan pembagian kerja agent | Saat delegasi task ke agent lain |
| `09-design-ux-and-research` | Riset, UX, persona, redesign notes | Saat merapikan UI atau validasi pengalaman user |
| `98-sensitive-access` | Dokumen akses/credential lokal | Hanya untuk operator yang berwenang |
| `99-legacy-reference` | Arsip dokumen lama Hermina Crawler | Saat butuh referensi historis, bukan sumber utama |

## Dokumen Utama

Dokumen yang paling berguna untuk memahami state terbaru:

| Status | Dokumen | Alasan |
| --- | --- | --- |
| UTAMA | `MUST_READ.md` | Gerbang konteks sebelum mengerjakan VoC |
| UTAMA | `PROJECT_STATUS.md` | Snapshot status dan arah proyek |
| UTAMA | `VOC_FETCH_LOGIC_TOP_DOWN.md` | Kajian refactor Fetch Review: date window, cursor, duplicate, rating snapshot |
| UTAMA | `VOC_STAKEHOLDER_OVERVIEW.md` | Penjelasan high-level untuk stakeholder |
| BERGUNA | `../04-implementation-plans/key-process/PLAN_KEY_PROCESS_DEMO.md` | Target demo key process |
| BERGUNA | `../04-implementation-plans/key-process/PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md` | Flow final ingest cepat, labeling, dan AI async |
| BERGUNA | `../04-implementation-plans/crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md` | Plan teknis refactor fetch crawler |
| BERGUNA | `../04-implementation-plans/onebox/PLAN_FETCH_REVIEW_UI_AND_RATING_TREND.md` | Plan UI Fetch Review dan rating trend |
| BERGUNA | `../03-architecture/integration/FETCH_JOBS_E2E_CONTRACT.md` | Kontrak Fetch Jobs end-to-end |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3420_fetch-jobs-crawl-dev-spec.md` | Dev specification Fetch Jobs Crawl |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3388_ai-analysis-setup-regrooming.md` | Re-grooming AI Analysis Setup |
| BERGUNA | `../05-runbooks/testing-and-postman/VOC_CRAWL_PROOF_RUNBOOK.md` | Runbook pembuktian crawler |
| BERGUNA | `../06-troubleshooting/incidents/VOC_WORKLIST_REFRESH_DUPLICATE_RESOLUTION.md` | Resolusi worklist stale/duplicate setelah seeding |

## Aturan Penempatan Dokumen Baru

- Backlog atau Jira detail masuk ke `01-product-and-backlog`.
- Keputusan yang sudah disepakati masuk ke `02-meetings-and-decisions/adr`.
- Diagram dan kontrak sistem masuk ke `03-architecture`.
- Rencana implementasi masuk ke `04-implementation-plans`.
- Prosedur yang bisa dijalankan operator masuk ke `05-runbooks`.
- Error, root cause, dan resolusi masuk ke `06-troubleshooting`.
- SQL seed, mapping, dan workbook masuk ke `07-data-and-seeding`.
- Prompt untuk agent masuk ke `08-agent-prompts-and-handoffs`.
- UX, riset, dan design review masuk ke `09-design-ux-and-research`.
- Credential atau akses masuk ke `98-sensitive-access`.
- Dokumen lama yang belum dipercaya sebagai sumber terbaru masuk ke `99-legacy-reference`.

## Catatan

Dokumen di `99-legacy-reference` boleh berguna sebagai sejarah, tetapi jangan dijadikan sumber kebenaran tanpa dibandingkan dengan `00-start-here`, `02-meetings-and-decisions/adr`, dan plan terbaru.
