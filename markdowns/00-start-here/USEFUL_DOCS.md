# Useful Documents Index

Index ini menandai dokumen yang paling berguna untuk pekerjaan VoC. Label dipakai untuk membantu prioritas baca, bukan untuk menghapus dokumen lain.

## Label

| Label | Arti |
| --- | --- |
| UTAMA | Dibaca pertama untuk memahami proyek |
| BERGUNA | Dipakai langsung untuk development, UAT, runbook, atau grooming |
| REFERENSI | Dipakai saat butuh konteks spesifik |
| SENSITIVE | Berisi akses/credential atau informasi operasional terbatas |
| ARSIP | Historis; validitasnya perlu dibandingkan dengan dokumen terbaru |

## Start Here

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `MUST_READ.md` | Konteks minimum sebelum mengerjakan VoC |
| UTAMA | `PROJECT_STATUS.md` | Status terakhir proyek |
| UTAMA | `VOC_FETCH_LOGIC_TOP_DOWN.md` | Kajian top-down refactor Fetch Review: window, cursor, duplicate, rating snapshot |
| UTAMA | `VOC_STAKEHOLDER_OVERVIEW.md` | Narasi high-level untuk stakeholder |
| REFERENSI | `fe-profile-progress-report.md` | Progress frontend/profile |
| REFERENSI | `link-docs.md` | Link eksternal dan dokumen terkait |

## Product And Backlog

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `../01-product-and-backlog/grooming/2026-08-25-voc-grooming-sprint.md` | Grooming terbaru dari hasil meeting |
| UTAMA | `../01-product-and-backlog/JIRA_TICKETS_CORRECTED.md` | Daftar tiket yang sudah dikoreksi |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3388_ai-analysis-setup-regrooming.md` | Detail scope AI Analysis Setup |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3420_fetch-jobs-crawl-dev-spec.md` | Detail scope Fetch Jobs Crawl |
| BERGUNA | `../01-product-and-backlog/jira-specs/DNGO19-3515_ticket-routing-PEMAHAMAN.md` | Pemahaman Ticket Routing |
| BERGUNA | `../01-product-and-backlog/task-breakdowns/SAYYID_TASK_BREAKDOWN.md` | Breakdown task Sayyid |
| BERGUNA | `../01-product-and-backlog/VOC_TEAM_PRODUCT_BACKLOG.md` | Backlog product/team |
| REFERENSI | `../01-product-and-backlog/VOC_HOSPITAL_STAKEHOLDER_USER_STORIES.md` | User story stakeholder rumah sakit |

## Architecture

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `../03-architecture/integration/api-contract-v1.md` | Kontrak API integrasi |
| UTAMA | `../03-architecture/integration/FETCH_JOBS_E2E_CONTRACT.md` | Kontrak Fetch Jobs E2E |
| BERGUNA | `../03-architecture/integration/architecture_diagram.md` | Diagram integrasi OneBox dan Crawler |
| BERGUNA | `../03-architecture/crawler-system/erd.md` | ERD Crawler |
| BERGUNA | `../03-architecture/crawler-system/dfd.md` | DFD Crawler |
| BERGUNA | `../03-architecture/onebox-system/erd.md` | ERD OneBox terkait VoC |
| BERGUNA | `../03-architecture/onebox-system/dfd.md` | DFD OneBox terkait VoC |

## Implementation Plans

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `../04-implementation-plans/key-process/PLAN_KEY_PROCESS_DEMO.md` | Plan demo key process |
| UTAMA | `../04-implementation-plans/key-process/PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md` | Plan final fast ingest dan AI on demand |
| UTAMA | `../04-implementation-plans/crawler-system/PLAN_REVIEW_FETCH_LOGIC_REFACTOR.md` | Plan refactor crawler dari count-first ke window/cursor-aware |
| BERGUNA | `../04-implementation-plans/onebox/PLAN_FETCH_REVIEW_UI_AND_RATING_TREND.md` | Plan UI Fetch Review dan rating trend berbasis snapshot |
| BERGUNA | `../04-implementation-plans/crawler-system/implementation-plan-crawler-system/00_INDEX.md` | Index work package Crawler |
| BERGUNA | `../04-implementation-plans/onebox/implementation-plan-onebox/00_INDEX.md` | Index work package OneBox |
| BERGUNA | `../04-implementation-plans/scheduler/SCHEDULER_CRAWLING_DESIGN.md` | Desain scheduler |
| BERGUNA | `../04-implementation-plans/scheduler/SCHEDULER_IMPLEMENTATION_TASKLIST.md` | Tasklist implementasi scheduler |

## Runbooks

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `../05-runbooks/testing-and-postman/VOC_CRAWL_PROOF_RUNBOOK.md` | Pembuktian crawler end-to-end |
| UTAMA | `../05-runbooks/testing-and-postman/VOC_FETCH_LOGIC_E2E_TEST_PLAN.md` | Skenario E2E untuk validasi fetch window/cursor dan duplicate-heavy |
| BERGUNA | `../05-runbooks/testing-and-postman/POSTMAN_AI_ANALYSIS_ENDPOINTS.md` | Endpoint AI Analysis untuk Postman |
| BERGUNA | `../05-runbooks/testing-and-postman/SCHEDULER_DEV_UAT_RUNBOOK.md` | UAT scheduler |
| BERGUNA | `../05-runbooks/tenant-onboarding/VOC_TENANT_ONBOARDING_RUNBOOK.md` | Setup tenant baru |
| BERGUNA | `../05-runbooks/service-auth/VOC_SERVICE_AUTH_RUNBOOK.md` | Token dan scope service-to-service |
| BERGUNA | `../05-runbooks/deployment/VOC_CRAWLER_PULL_FLOW_DEPLOYMENT.md` | Deploy pull-flow crawler |
| REFERENSI | `../05-runbooks/setup-and-local-dev/local-dev-setup-guide.md` | Setup lokal |

## Troubleshooting

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| UTAMA | `../06-troubleshooting/incidents/VOC_WORKLIST_REFRESH_DUPLICATE_RESOLUTION.md` | Resolusi duplicate worklist setelah seeding |
| BERGUNA | `../06-troubleshooting/incidents/INCIDENT_CRAWL_TARGET_NOT_FOUND.md` | Debug target tidak dikenal |
| BERGUNA | `../06-troubleshooting/incidents/INSIDEN_SELENIUM_CRAWLER_MATI.md` | Debug Selenium/worker mati |
| BERGUNA | `../06-troubleshooting/incidents/VOC_SCHEDULER_TIDAK_JALAN.md` | Debug scheduler tidak jalan |
| BERGUNA | `../06-troubleshooting/diagnostics/NETWORK_WIREGUARD_CORS_ONEBOX.md` | Debug koneksi WireGuard/CORS |

## Data And Seeding

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| BERGUNA | `../07-data-and-seeding/field-mapping/implementation-plan/field-mapping-final.md` | Mapping field Crawler ke OneBox dan Ticket |
| BERGUNA | `../07-data-and-seeding/VOC_DBEAVER_SEEDING.md` | Panduan seeding via DB tool |
| REFERENSI | `../07-data-and-seeding/sql/VOC_SEED_PUSKESMAS_SITE169_DEV.sql` | SQL seed Puskesmas site 169 dev |
| REFERENSI | `../07-data-and-seeding/workbooks/VOC_EPIC_BACKLOG_1-3.xlsx` | Workbook backlog lama |

## Agent Prompts

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| BERGUNA | `../08-agent-prompts-and-handoffs/PROMPT_FETCH_JOBS_E2E_CLAUDE.md` | Prompt handoff Fetch Jobs ke Claude |
| BERGUNA | `../08-agent-prompts-and-handoffs/CODEX_TODO_REVIEW_FETCH_LOGIC_REFACTOR.md` | Todo scope Codex untuk refactor Fetch Review |
| BERGUNA | `../08-agent-prompts-and-handoffs/PROMPT_REVIEW_FETCH_LOGIC_REFACTOR.md` | Prompt agent untuk refactor Fetch Review window/cursor-aware |
| BERGUNA | `../08-agent-prompts-and-handoffs/PROMPT_VOC_CRAWL_PROOF.md` | Prompt pembuktian crawl |
| BERGUNA | `../08-agent-prompts-and-handoffs/two_agents_workflow.md` | Pembagian kerja Codex dan Claude |
| REFERENSI | `../08-agent-prompts-and-handoffs/superprompt.md` | Prompt besar historis |

## Design UX And Research

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| BERGUNA | `../09-design-ux-and-research/VOC_UI_ONEBOX.md` | Catatan UI OneBox VoC |
| BERGUNA | `../09-design-ux-and-research/VOC_SETTINGS_REDESIGN_STITCH.md` | Redesign settings |
| BERGUNA | `../09-design-ux-and-research/VOC_PERSONA_WORKSPACE.md` | Persona/workspace design |
| REFERENSI | `../09-design-ux-and-research/VoC-Riset-Review-Google.md` | Riset review Google |

## Sensitive And Legacy

| Label | Dokumen | Kegunaan |
| --- | --- | --- |
| SENSITIVE | `../98-sensitive-access/VOC_CREDENTIALS.md` | Akses dan credential terbatas |
| ARSIP | `../99-legacy-reference/hermina-crawler-original/markdown-hc/README.md` | Arsip dokumentasi Hermina Crawler awal |
| ARSIP | `../99-legacy-reference/developer_guide.md` | Developer guide lama/reference |
