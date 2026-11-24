# Offline multi-tenant crawler simulation

Run from the repository root with its existing virtual environment:

```bash
.venv/bin/python scripts/simulate_multitenant.py
.venv/bin/python scripts/simulate_multitenant.py --list
.venv/bin/python scripts/simulate_multitenant.py --scenario fairness --seed 7 --verbose
.venv/bin/python scripts/simulate_multitenant.py --scenario provisioning worklist --keep-db
```

The script plays OneBox through the real FastAPI `create_app()` and in-process
`TestClient`, with real service-token authentication, queue and `CrawlWorker`.
A deterministic fake replaces fetching; automatic analysis is disabled. There
are no network calls, external services, sleeps or charges, and no dependencies
to install. Exit code is **0 only when every check passes**; failures print
`[FAIL]` and return a nonzero exit code.

## Isolation and retained data

The script imports no application modules until it has installed an isolated
environment and disabled `dotenv.load_dotenv`. This matters because
`app/config.py` loads the repo `.env` at import time; merely unsetting
`ONEBOX_SITE_ID` and `ONEBOX_COMPANY_ID` would let that file reintroduce them.
`_EnvSettings` does not configure a separate env file. The simulation clears
settings/engine/session-factory caches and supplies its own local managed-mode
settings, fixed throwaway pepper, and provisioning hash computed by the real
`provisioning_key_hash` function. Inherited credentials and configuration are
excluded. Environment values and patched functions are restored on exit.

It creates a file using `tempfile.mkdtemp()`, verifies that the engine URL points
to that exact SQLite file **before** `Base.metadata.create_all`, and guards every
SQL connection and statement against using another database. Socket connection,
DNS and datagram-send guards reject accidental network use. The configured
database is never opened and `.env` is neither read nor changed by this script.
Verbose logging prints only selected HTTP fields; it never prints authorization
headers, tokens, hashes, or inherited secrets. The tenants table shows public
token key IDs.

Each scenario starts with fresh tables in the same disposable file. By default
the directory is removed even when a scenario fails. `--keep-db` retains the
directory and prints the absolute file path; it contains **only the last selected
scenario's data**. Remove that printed directory when finished. Within fairness
and quota, independent experiments also reset explicitly labeled synthetic data.
Run this utility by itself: its temporary environment and guards are process-wide.

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--scenario NAME ...` | All seven in order | Select one or more; the flag may also be repeated. Each scenario runs independently. |
| `--list` | Off | Print scenario names/descriptions without loading the app or creating a database. |
| `--tenants N` | `3` | Provision at least three tenants. Extra tenants participate in fairness with weights `1..N`; other scenarios focus on the first two or three. Use small values for an interactive demonstration. |
| `--seed N` | `42` | Seed fake review content and ratings. API-generated credential IDs and batch UUIDs still vary. |
| `--keep-db` | Off | Keep the temporary database and print its path. |
| `--verbose` | Off | Show HTTP method, path, status, and selected request/response fields. |

The importable entry point is `scripts.simulate_multitenant.run(argv=None)`.
Pass `[]` for defaults without reading the caller's command line. It returns a
`Report` with scenario outcomes, passed/failed checks, `database_path`, observed
`engine_paths`, and `database_removed`. Its optional `reviews_per_location=8`
keyword configures fake source availability per call (minimum five for these
scenarios). The fake respects target, budget and the worker's remaining quota,
writes unique nonempty reviews, and uses `FetchLogService` for coverage and counts.

## What each scenario proves

| Scenario | Checks and printed evidence |
| --- | --- |
| `provisioning` | Sites 169, 177, 201 register with names; repeat registration issues no second token. GET omits secrets and shows active/default weight/zero usage/empty worklist. PATCH stores Default/Plus weights 1/2. Rotation allows both credentials during overlap, then rejects the old credential after a labeled expiry setup. Tenant tokens cannot call provisioning endpoints. Prints tenants and key IDs. |
| `worklist` | A full `{snapshot_version, items, taxonomies}` snapshot has two branches and a competitor; replay is stale; v2 disables the removed branch. An invalid snapshot returns `400 INVALID_SNAPSHOT` atomically. Another tenant's snapshots and a token lacking `worklist:write` cannot change T1. Prints sent versions, outcomes and item counts. |
| `isolation` | Seeded reviews and batches make foreign access attempts meaningful. Both tenants can use owned locations/reviews/batches; foreign resolution, review filtering, enqueue and batch reads return 404 without foreign resource IDs in response fields or text. Unfiltered review pulls contain owned locations only. Prints the access matrix. |
| `crawl` | HTTP backfill then delta batches progress through queued/running/completed using the real worker. Replay returns the same batch. Usage equals fake fetched totals by coverage and only T1 receives reviews. Prints job timelines and before/after usage. |
| `deactivation` | One real claim remains running while labeled setup creates `retry_wait` and `awaiting_source` siblings. PATCH cancels all waiting states, preserves the running job and data, and leaves T1 untouched. A waiting-only batch becomes cancelled; a mixed batch stays running until completion, then cancelled. New enqueue/push returns `409 TENANT_INACTIVE`; reads still work. Reactivation permits new jobs without reviving cancelled jobs. Prints state counts and batch transitions. |
| `fairness` | Weights 1/2/3 receive 10/20/30 of 60 claims. Three newer T1 deltas precede its older backfills. A settings copy with tenant concurrency cap two leaves jobs running and serves every tenant without exceeding two. With equal weights, all five small-tenant deltas finish claiming by position ten beside a 300-job backfill queue. Prints sequences, expected/actual shares, priority positions and live counts. |
| `quota` | Aggregate fetch-log setup represents purchased location counts 10/100/310 without hundreds of review rows. HTTP usage drives normal/alert/pause decisions, includes lifetime backfill and current-month delta/date-window, and excludes dry runs, legacy coverage and earlier-month operating usage. A final three-job batch gets remaining quotas 7/2/0 and fetches 5/2/0. Prints usage/caps/states, estimated Jev dollars, Jev policy boundaries and per-job quota consumption. |

Quota rules follow [Q-41 and Q-43](../../multitenant-readiness/04-OPEN-QUESTIONS.md):

- Backfill lifetime cap: `max(100000, 2500 * purchased_locations)` fetched reviews;
  alert at 80%, pause new backfills at 100%.
- Operating monthly cap: `2000 * purchased_locations`; alert at 50%, pause new
  operating crawls at 100%.
- Proposed monthly Jev budget: `max(10, 0.25 * purchased_locations)` dollars;
  alert at 80%, pause analysis at 100%, keep ingestion enabled.
- Estimated Jev cost: `(backfill_fetched + operating_fetched) * 1000 / 1000000 * 0.042`.
  This is a hypothetical month in which all shown fetched reviews are analyzed,
  including historical backfill. It is not measured AI usage. Q-43 remains a
  proposal in the source document.

Caps and policy decisions are simulated on the OneBox side. The crawler reports
usage and enforces the supplied per-batch `review_quota_remaining`. These
experiments use a single worker process and fresh unique reviews; they do not
prove parallel-worker locking or duplicate-fetch accounting. See the
[OneBox HTTP handoff](../../multitenant-readiness/05-ONEBOX-HANDOFF.md) for the contract.

## Example output

```text
=== fairness: Measure weighted claims, delta priority, live caps and a large-queue neighbour. ===
  Claims: T1 T2 T3 T3 T2 T3 ...
  [PASS] Claim shares follow tenant weights (within one claim)

  tenant | weight | claims | expected | actual share | expected share
  ------ | ------ | ------ | -------- | ------------ | --------------
  T1     | 1      | 10     | 10       | 16.7%        | 16.7%
  T2     | 2      | 20     | 20       | 33.3%        | 33.3%
  T3     | 3      | 30     | 30       | 50.0%        | 50.0%
  ...
Summary: 7/7 scenarios passed; 71 checks passed / 0 failed.
Temporary database removed.
```

The single regression test runs every scenario quietly and asserts that all
observed SQL paths equal the temporary file, an inherited configured-database
sentinel was never created, cleanup completed, secrets were not printed, and the
run finishes in under 60 seconds:

```bash
.venv/bin/python -m pytest -q tests/test_simulate_multitenant.py
```
