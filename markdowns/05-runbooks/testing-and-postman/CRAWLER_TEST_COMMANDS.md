# Runbook - Crawler test and script commands

Status: Current (2026-10-26, branch `feature/multitenant-readiness`)
Purpose: one place to find which command to run, what it needs, and what it costs.

Legend: **verified** = run on 2026-10-26 on this branch. **docstring** = read from the script's own docstring, not run.

All commands run from the repo root `hermina-crawler/` with the repo virtualenv. Inside Docker the same scripts run as `docker compose exec -T api python -m scripts.<name>`.

## 1. Which command do I run?

| I changed or want to check | Run | Needs | Time |
|---|---|---|---|
| Anything, before a merge | `.venv/bin/python -m pytest -q` | nothing | ~26 s |
| The whole multi-tenant flow, watched by eye | `.venv/bin/python scripts/simulate_multitenant.py` | nothing | ~2 s |
| Reply suggestion, try_* scripts, scoring scripts | section 3, "Reply suggestion and AI helpers" | nothing | <1 s |
| Reply suggestion against the real Jev model | `scripts/try_replies.py` (section 5) | Jev key, a database | seconds, trivial cost |
| Tenant provisioning, weight, usage counters | section 3, "Tenants" | nothing | <3 s |
| Job queue, fairness, deactivation | section 3, "Queue and worker" | nothing | <3 s |
| A migration or anything that locks rows | section 7 (throwaway PostgreSQL) | Homebrew PostgreSQL | ~1 min |

Known result today: **598 passed, 4 failed, 2 skipped**. The 4 failures are all in `tests/test_tenant_mode_config.py` (see section 8) and fail the same way without any of the multi-tenant changes.

## 2. Setup

```bash
cd hermina-crawler
.venv/bin/python -m pytest --version     # the project virtualenv is .venv
```

- Tests use in-memory SQLite and fakes. They never call Apify, OpenAI, Jev or OneBox, and they never touch the database in `.env`.
- Only `tests/test_postgres_concurrency.py` needs a real PostgreSQL (`TEST_DATABASE_URL`); it is skipped otherwise.

## 3. Tests by area (all offline, **verified**)

### Everything

```bash
.venv/bin/python -m pytest -q
```

### Tenants (provisioning, weight, usage counters, deactivation)

```bash
.venv/bin/python -m pytest tests/test_tenant_provisioning.py tests/test_tenant_weight.py tests/test_tenant_usage.py tests/test_tenant_deactivation.py tests/test_tenant_isolation.py tests/test_tenant_registry_schema.py -q
```

### Worklist push

```bash
.venv/bin/python -m pytest tests/test_worklist_push_api.py tests/test_worklist_snapshot.py tests/test_worklist_sync.py tests/test_worklist_taxonomy_ingest.py -q
```

### Queue and worker (claiming, fairness, caps, crawl jobs)

```bash
.venv/bin/python -m pytest tests/test_weighted_claim.py tests/test_integration_crawl_jobs.py tests/test_apify_fetch_service.py tests/test_parked_source_runs.py -q
```

### Reply suggestion and AI helpers (124 tests together)

```bash
.venv/bin/python -m pytest tests/test_reply_suggestion_modes.py tests/test_try_replies.py tests/test_try_examples.py tests/test_try_reviews.py tests/test_eval_scripts.py tests/test_analysis_with_taxonomy.py tests/test_jev_dynamic_questions.py tests/test_provider_taxonomy.py -q
```

| File | What it proves |
|---|---|
| `test_reply_suggestion_modes.py` (14) | Decision rules with a fake provider: a confident preset is returned, a critical flag escalates, below the threshold gives none, an id that was never offered gives none, another tenant's review is not found. The endpoint checks the analysis scope, the AI flag, 400 on bad input, 502 on a provider failure. |
| `test_try_replies.py` (13), `test_try_reviews.py` (17) | The judging logic of `try_replies.py` and `try_reviews.py`. |
| `test_try_examples.py` (8) | The example reviews still name slugs, flags and presets that OneBox's catalog has. |
| `test_eval_scripts.py` (9) | The scoring math of `eval_reply.py` and `eval_taxonomy.py`. |
| `test_analysis_with_taxonomy.py`, `test_jev_dynamic_questions.py`, `test_provider_taxonomy.py` | Analysis with a taxonomy, Jev prompt building, provider taxonomy. |

### Integration API contract

```bash
.venv/bin/python -m pytest tests/test_integration_api_contract.py tests/test_contract_v3.py tests/test_integration_delta_sync.py tests/test_service_auth.py -q
```

### Stateless v2 API (317 tests, offline)

```bash
.venv/bin/python -m pytest tests/test_v2_crawls.py tests/test_v2_ai.py tests/test_v2_audit.py -q
```

How to call the v2 API by hand (curl examples, setup, error codes): [../STATELESS_V2_API.md](../STATELESS_V2_API.md). Design: ADR-0006.

### Migrations

```bash
.venv/bin/python -m pytest tests/test_alembic_single_head.py -q
.venv/bin/python -m alembic heads        # must print exactly one head (today: 20261026_0014)
```

### The simulation's own test

```bash
.venv/bin/python -m pytest tests/test_simulate_multitenant.py -q
```

## 4. Multi-tenant simulation (**verified**)

`scripts/simulate_multitenant.py` plays OneBox against the real API and the real worker, with a fake fetch service. It uses its own temporary SQLite file, ignores the `.env`, and blocks network access at the socket level. Nothing outside the temp file is touched. Full flag and scenario reference: [MULTITENANT_SIMULATION.md](MULTITENANT_SIMULATION.md).

```bash
.venv/bin/python scripts/simulate_multitenant.py                          # all 7 scenarios, exit 0 when every check passes
.venv/bin/python scripts/simulate_multitenant.py --list                   # names only
.venv/bin/python scripts/simulate_multitenant.py --scenario fairness      # one scenario
.venv/bin/python scripts/simulate_multitenant.py --scenario quota --verbose
.venv/bin/python scripts/simulate_multitenant.py --seed 7 --keep-db       # print the temp database path and keep it
```

| Scenario | Shows |
|---|---|
| `provisioning` | Three tenants register, one-time tokens, weights, rotation, platform-only access |
| `worklist` | Versioned snapshots: applied, stale, malformed, scope-less |
| `isolation` | An access matrix of tenant tokens against foreign resources |
| `crawl` | Backfill and delta batches drained by the real worker, usage reconciled |
| `deactivation` | Waiting jobs cancelled, running job kept, 409 for enqueue and push, other tenants untouched |
| `fairness` | Weights 1/2/3 get 10/20/30 of 60 claims, delta before backfill, cap of 2, a 300-job backfill next to a small tenant |
| `quota` | The Q-41 caps and Q-43 Jev budget at normal, alert and pause levels, plus `review_quota_remaining` honoured by the worker |

Today's run: 7/7 scenarios, 71 checks passed, about 2 seconds.

## 5. Scripts that call a real AI (**docstring**, not run)

They spend tokens. Jev costs $0.042 per million input tokens, so Jev runs cost fractions of a cent; the OpenAI script uses your OpenAI key. Use `--list` first, it makes no AI call.

| Command | What it does | Needs |
|---|---|---|
| `python -m scripts.try_replies --list` | Names of the example reviews, no AI call | database |
| `python -m scripts.try_replies --industry kesehatan` | Real reply suggestion on that industry's examples; exit 1 if an expectation fails; a few hundred tokens each | `ANALYSIS_PROVIDER=jev` (or `--provider jev`), `TYPESAFE_API_KEY` |
| `python -m scripts.try_replies --all-industries` | Same, every industry | same |
| `python -m scripts.try_replies --text "Antre lama sekali" --threshold 0.6` | One review of your own | same |
| `python -m scripts.try_reviews --list` / `--industry spbu` / `--only campuran` | Real analysis on positive, negative and mixed examples; a few thousand tokens each | the server's analysis provider |
| `python -m scripts.eval_reply labelled.csv --taxonomy snapshot.json --presets presets.json --threshold 0.75` | Precision and safety recall on a labelled CSV. Targets: precision >= 0.90 and safety recall = 1.0 | Jev |
| `python -m scripts.eval_taxonomy labelled.csv --taxonomy snapshot.json --provider jev` | Per-aspect precision and recall of a taxonomy | the chosen provider |
| `python scripts/test_jev_ai.py` | One real Jev request. Not a pytest test despite the name. | `TYPESAFE_API_KEY` |
| `python scripts/test_openai_ai.py` | One real OpenAI request | `OPENAI_API_KEY` |

Run them in Docker as `docker compose exec -T api python -m scripts.try_replies --industry kesehatan`. Options shared by `try_*`: `--company-id N`, `--key kesehatan:0e20266e`, `--provider jev|absa|openai`, `--only NAME`.

## 6. Operator and heavy scripts (**docstring**, not run)

| Script | What it does | Careful |
|---|---|---|
| `scripts/generate_provisioning_key.py` | Prints the key OneBox uses to register tenants and the hash for `ONEBOX_PROVISIONING_KEY_HASH` | Set the real `SERVICE_TOKEN_PEPPER` first; the key is shown once |
| `scripts/manage_company.py`, `scripts/manage_api_client.py` | Create and list companies and API clients | Writes to the configured database |
| `scripts/refresh_worklist.py` | Pull the worklist from OneBox (old pull path) | Needs OneBox credentials; goes away with MT-22 |
| `scripts/run_crawl_worker.py` / `.sh` | Start a real crawl worker | **Calls Apify and costs money** |
| `scripts/simulate_fetch_jobs_pipeline.py`, `scripts/simulate_onebox_to_ai.py`, `scripts/live_crawler_test_demo.py` | Older end-to-end simulations | Use the configured database, and the live demo may call real services |
| `scripts/stress_test_ai_service.py`, `scripts/stress_test_fetch_reviews.py`, `scripts/benchmark_fetch_and_db.py`, `scripts/stress-absa-10.sh` | Load and performance tests | The fetch ones may call Apify; heavy on the database |
| `scripts/export_*_pdf.py` | Build PDF reports from results | Read-only |
| `scripts/deploy*.sh`, `scripts/check_deploy_branch.sh` | Deploy | Changes the target environment |

Rule of thumb: do not run anything in this table against the dev database or a real Apify account unless you meant to.

## 7. Real PostgreSQL check (throwaway, **verified**)

SQLite cannot test row locking or the PostgreSQL migration. This recipe uses Homebrew PostgreSQL in a temporary directory and leaves nothing behind. TCP only, port 54329.

```bash
PGDIR="$(mktemp -d)"
initdb -D "$PGDIR/data" -U postgres --auth=trust -E UTF8
pg_ctl -D "$PGDIR/data" -o "-p 54329 -c unix_socket_directories=''" -l "$PGDIR/pg.log" -w start
psql -h localhost -p 54329 -U postgres -c "create database mt"
```

Run all migrations from scratch (checks the whole chain, including the weight column and index):

```bash
DATABASE_URL="postgresql+psycopg2://postgres@localhost:54329/mt" APP_ENV=local .venv/bin/python -m alembic upgrade head
```

Run the repo's PostgreSQL test (use a separate empty database, the test creates and drops its own schema):

```bash
psql -h localhost -p 54329 -U postgres -c "create database mt_test"
TEST_DATABASE_URL="postgresql+psycopg2://postgres@localhost:54329/mt_test" .venv/bin/python -m pytest tests/test_postgres_concurrency.py -q
```

Stop and clean up:

```bash
pg_ctl -D "$PGDIR/data" stop -m fast
rm -rf "$PGDIR"
```

Known: `test_concurrent_analysis_writes_do_not_corrupt_or_deadlock` fails with a `KeyError: 'is_safety_issue'` on this branch and on the code from before the multi-tenant changes. It is an analysis issue, not a queue one. `test_claim_next_never_double_claims_under_concurrent_workers` passes.

## 8. Known failing tests (not code bugs)

`tests/test_tenant_mode_config.py` fails 4 tests (`test_mode_is_normalised[managed-managed]`, `test_mode_is_normalised[ Managed -managed]`, `test_managed_mode_needs_no_onebox_values`, `test_managed_mode_only_warns_about_leftover_onebox_credentials`). The cause is the local `.env`: it sets `ONEBOX_SITE_ID` and `ONEBOX_COMPANY_ID`, and `ONEBOX_TENANT_MODE=managed` rejects them on purpose. The same four fail on `dev` without any multi-tenant code. CI uses its own environment.

## 9. Before merging to `dev`

```bash
.venv/bin/python -m pytest -q                                  # only the 4 known failures allowed
.venv/bin/python scripts/simulate_multitenant.py               # 7/7 scenarios
.venv/bin/python -m alembic heads                              # exactly one head
git fetch origin && git log --oneline HEAD..origin/dev | wc -l # how far dev moved
```

After merging, run the same four commands on `dev`, then (on a deployed dev) call `GET /api/integration/v1/tenants/<site_id>` and check that `usage` and `weight` are present.
