# ADR-0006 - Stateless REST crawler with an audit-only database

- **Status:** Proposed (2026-10-26)
- **Decision maker:** Sayyid (dev). Not ratified by Pak Agung.
- **Replaces:** the planned ADR-0006 "multi-tenant package provisioning + push worklist" (never written) and the "opsi D" design in `markdowns/multitenant-readiness/`. The code for it (tenant registry, `PUT /worklist`, weighted queue, usage counters) is already on `dev`, switched off by default (`ONEBOX_TENANT_MODE=single`).
- **Related:** [ADR-0001](ADR-0001-ownership-inversion.md) (OneBox is the system of record, kept), [ADR-0003](ADR-0003-crawl-execution-pull-queue.md) (pull worklist and durable queue, replaced for v2), [ADR-0005](ADR-0005-separate-review-tables-shared-columns.md).

## Context

The multi-tenant work moved tenant management into the crawler: a registry, tokens, a worklist, a weighted queue, quotas and deactivation. It works (see the simulation), but the crawler now carries a lot of configuration and business state that OneBox already owns: who is a customer, what they bought, what to crawl and when, how much they may use.

The wish is a crawler that is a plain REST service: OneBox sends everything a call needs and gets the result back. The crawler keeps a database, but only as a **backup and audit trail** to check for stale or missing data, never to decide anything.

## Decision

### 1. The crawler is a stateless REST service (API v2)

Every call carries its own inputs. The crawler never reads its database to answer a request.

| Call | Purpose |
|---|---|
| `POST /api/integration/v2/crawls` | Targets (place id or URL), mode (`backfill`, `delta`, `range`), `date_from`/`date_to`, `max_reviews`. Starts one Apify run per target and returns the run ids. Optional `Idempotency-Key`. |
| `GET /api/integration/v2/crawls/{run_id}?cursor=&limit=` | Run status and a page of normalized reviews (with `review_hash`) read from the Apify dataset, plus a `next_cursor`. |
| `POST /api/integration/v2/analysis` | Review texts, ratings and the taxonomy in the body; returns the analysis. |
| `POST /api/integration/v2/reply-suggestion` | Text, presets and taxonomy in the body; returns the decision (the service is already pure). |
| `GET /api/integration/v2/audit/summary` | Per `site_id` and `place_id`: stored review count, newest and oldest review time, last crawl, last analysis. |
| `POST /api/integration/v2/audit/reconcile` | The caller sends the review hashes it holds for a place; the crawler returns what the backup has that the caller lacks, and what the caller has that the backup lacks. |
| `GET /api/health` | As today. |

A long crawl is identified by its **Apify run id**. There is no job queue and no crawl worker process. When Apify's concurrency limit is full the crawler answers `429` with `Retry-After` (the code already tells that apart from out-of-credit).

### 2. OneBox owns everything about tenants and scheduling

Who a tenant is, what they bought, quotas and their alerts, what to crawl and when, fairness between customers, review storage as the record, delta cursors (OneBox sends `date_from`), and Jev budgets. The crawler has **no** tenant registry, no per-tenant tokens, no worklist, no weights, no quotas, no usage counters, no deactivation.

### 3. The database is a write-mostly audit store

Separate new tables, with no foreign keys to the old `companies` or `locations`:

- `audit_crawl_runs`: Apify run id, `site_id`, place id, mode, request parameters (JSON), status, fetched count, timestamps, optional idempotency key.
- `audit_reviews`: `site_id`, place id, `review_hash`, normalized payload (JSON), review time, `first_seen_at`, `last_seen_at`, `seen_count`, `first_run_id`. Unique on (`site_id`, `review_hash`).
- `audit_analyses`: `site_id`, `review_hash`, provider, model, taxonomy key, result (JSON), tokens in and out, timestamp.

`site_id` is a plain label sent by the caller. It is not looked up, validated against a registry, or used for access control.

Rules:
1. **Best-effort writes.** A failed audit write is logged and counted; it never fails or slows the request.
2. **No read dependency.** Responses are built from the request and from Apify. The one allowed read is the optional replay protection: if `Idempotency-Key` is already in `audit_crawl_runs`, return the stored run ids (it saves a duplicate, paid Apify run). If the database is down, it fails open.
3. **Retention** is configurable, default keep everything.
4. The existing v1 tables stay untouched until v1 is retired.

### 4. Minimal configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | the audit database |
| `CRAWLER_API_TOKEN` | one shared bearer token (constant-time compare, no database lookup) |
| `APIFY_API_TOKENS` | Apify account(s) |
| `TYPESAFE_API_KEY` / `OPENAI_API_KEY` | analysis providers |
| `AUDIT_RETENTION_DAYS` | optional, `0` = keep (default) |

Not needed in v2: `ONEBOX_*`, `SERVICE_TOKEN_PEPPER`, `CRAWL_WORKER_*`, the provisioning key, tenant mode, fairness and cap settings. Redis stays optional (Apify token pool only).

## Consequences

- Less to run: no crawl-worker container, no queue, no provisioning flow, fewer settings, fewer failure modes.
- OneBox must implement what it used to get from the crawler: storing every review from `GET /crawls/{run_id}`, dedup by `review_hash`, delta cursors, scheduling, quotas, fairness, retries, and collecting a run's data before Apify's dataset retention expires.
- A repeated `POST /crawls` without an idempotency key (or with the audit database down) can start a second, paid Apify run.
- The multi-tenant code on `dev` becomes dead weight for v2. It stays until OneBox switches; then a cleanup change removes the tenant registry, worklist, weighted queue, usage counters and their tests, and retires `scripts/simulate_multitenant.py` in favour of a v2 contract simulation.
- The audit database makes stale-data checks possible without the crawler being the source of truth.

## Migration

1. Ship v2 beside v1 (new router, new tables, new migration). v1 and the HGA flow are unchanged.
2. Optional one-off script copies existing `reviews`/`review_analysis` into the audit tables (`site_id` from `companies.onebox_site_id`).
3. OneBox switches to v2 per feature (crawl first, then analysis and reply).
4. When OneBox no longer calls v1, remove v1 and the multi-tenant code in one cleanup change.

## Open questions

1. Idempotency: is the optional replay protection enough, or should runs also be tagged on the Apify side so a replay is detected without the database?
2. How long should OneBox keep collecting from `GET /crawls/{run_id}` before the Apify dataset expires, and who alerts on a run that was never collected?
3. Should `analysis` write to `audit_analyses` when `site_id` is absent (use a null label) or skip the write?
4. Does the audit store need the raw Apify payload, or only the normalized review?
