# Apify migration — execution report

Branch: `apify-migration` (local only, not pushed). Implemented by Codex
(`codex exec`) under supervision, per `CLAUDE.md`'s delegation policy, then
independently reviewed and verified before committing.

## What was implemented, vs. the spec

Everything in `MIGRATION_APIFY_REVIEW_SOURCE.md` was built, including the
decommission checklist. Six new modules, exactly as specced:

- [app/integrations/apify_client.py](../../app/integrations/apify_client.py)
  — thin REST wrapper: `start_run`, `get_run_status` (polls to a terminal
  state or times out), `iter_dataset_items` (offset/limit pagination until
  an empty page). 429s get exponential backoff on the same token (never
  trigger rotation); a 402 or a body containing
  credit/quota/"payment required" language raises `ApifyAccountExhaustedError`
  for the caller to rotate on. The 429 branch returns before the
  credit-exhaustion check ever runs, so a rate-limited response can't be
  misread as account exhaustion.
- [app/integrations/apify_token_pool.py](../../app/integrations/apify_token_pool.py)
  — `ApifyTokenPool.current()`/`rotate()`, in-memory, one instance per
  `ApifyFetchService` (shared across jobs in the same worker process).
  `rotate()` returns `None` once every token is exhausted;
  `ApifyAllAccountsExhaustedError` on `current()` after that point.
- [app/integrations/apify_review_parser.py](../../app/integrations/apify_review_parser.py)
  — pure mapping, matches the spec's column table field-for-field, including
  the `reviewer_photo_url`→`reviewer_photo` fallback and the
  `is_local_guide` bool → `"Local Guide"`/`None` string collapse.
- [app/integrations/apify_review_client.py](../../app/integrations/apify_review_client.py)
  — orchestrates checkpoint resolution → actor call → pagination → parse →
  the exhaustion-continuation loop. On `ApifyAccountExhaustedError` mid-run
  it rotates and re-issues the same request with `newerThan` advanced to
  the last successfully parsed item, not a fresh restart. Defines the
  `SORT_BY_MAP` used by both this module and the checkpoint store.
- [app/services/apify_checkpoint_store.py](../../app/services/apify_checkpoint_store.py)
  — `load`/`save`/`clear`/`resolve_effective_lower_bound` with the exact
  three-way logic from the spec (no checkpoint / same sort_by takes the more
  restrictive lower bound / different sort_by logs a warning, discards, and
  restarts from the originally requested `date_from`).
- [app/services/apify_fetch_service.py](../../app/services/apify_fetch_service.py)
  — `SeleniumFetchService` renamed in place to `ApifyFetchService`; the
  `keep_check`/`scan_limit`/`time_limit_seconds` live-scrolling contract is
  gone. `stopped_reason == "apify_accounts_exhausted"` maps to
  `status = "partial_success"` (an existing, already-terminal status —
  `CrawlWorker._is_permanent_source_failure`/`_refresh_batch_status` handle
  it unchanged) with `stop_reason` surfaced through the existing
  `crawl_result.stop_reason()` helper.

DB: `apify_resume_checkpoint` JSON column added to both `Location` and
`Competitor` ([models.py](../../app/db/models.py)), with Alembic migration
[20260915_0008_add_apify_resume_checkpoint.py](../../alembic/versions/20260915_0008_add_apify_resume_checkpoint.py)
following the `20260826_0007` naming/structure convention. Verified
`alembic heads` resolves to a single head (`20260915_0008`).

Call sites swapped: `crawl_worker.py`'s `fetch_service_factory`,
`fetch_jobs.py`, `pipeline.py`, `integration_crawl_jobs.py` (the summary
string — this router never branched on source), `terminal/fetch_menu.py`.
Config: `apify_api_tokens` (comma-separated `APIFY_API_TOKENS`),
`apify_actor_id`, `apify_run_timeout_seconds`, `apify_poll_interval_seconds`
added; `selenium_max_target_reviews` renamed to `crawl_max_target_reviews`
with the same default (300) and clamp behavior.

`rg -n "SeleniumFetchService|SeleniumGoogleMapsReviewClient|selenium_google_maps" --type py`
returns zero matches — verified independently, not just taken on Codex's
word.

## Decommission — fully completed, not deferred

Tests were green before any deletion happened (confirmed independently).
Deleted: `selenium_google_maps_client.py`, its now-orphaned
`google_maps_review_parser.py` helper (was only ever imported by the
Selenium client — verified via `git show HEAD:... | grep`),
`test_selenium_scraping.py`, `test_google_maps_review_parser.py`,
`scripts/setup_selenium_profile.py`, `scripts/diagnose_google_maps_runtime.py`,
and the dead `generate_selenium_review_hash` hash helper. Trimmed: the
Chromium/xvfb/xauth install block from the `Dockerfile`, the Selenium
profile volume from `docker-compose.yml`, the `selenium`/
`undetected-chromedriver` lines from `requirements.txt`, all `selenium_*`
settings and the `"selenium"` `REVIEW_SOURCE_MODE` from `app/config.py`
(and its exposure in `settings_service.py`/the settings router).
`INCIDENT_P0_GOOGLE_MAPS_ONLY_5_REVIEWS.md` is marked
resolved/historical with a pointer to the migration spec, not deleted.

Two extensions beyond the literal decommission checklist, both verified
correct rather than assumed: `google_maps_review_parser.py` (dead once its
only caller was deleted) and `generate_selenium_review_hash` (dead once the
only branch that selected it was deleted).

## Deliberately deferred / skipped

- **The live smoke test against Hermina Bogor** — no real `APIFY_API_TOKENS`
  exist in this environment, so this could not run. Everything else in the
  spec's testing plan ran as unit/mocked coverage instead.
- **Live confirmation of the exact 402 error shape** — the spec doc itself
  flagged this as unconfirmed against a real response. `apify_client.py`'s
  credit-exhaustion detection (402 status, or an `error.type`/`message`/`code`
  containing "credit"/"payment required"/"quota") is implemented against
  Apify's documented shape but not verified live. **This is the one thing
  that could misbehave against a real account** — see the checklist below.
- **`requirements.txt` lock regeneration** — `selenium`/
  `undetected-chromedriver` lines were removed by hand rather than via
  `pip-compile`/equivalent, because that needs network access this
  environment doesn't have. A human should regenerate the lock properly
  (there could be now-orphaned transitive dependencies still pinned).
- **`.env` (local, gitignored, not part of any commit)** — Codex changed
  `REVIEW_SOURCE_MODE=seLenium` to `apify` in the local `.env` file so the
  app doesn't fail Pydantic validation immediately (`"selenium"` was
  removed from `REVIEW_SOURCE_MODES`). This is a local file edit only, not
  part of the branch. Worth double-checking this repo's staging/deploy
  `.env` gets the same update — it's not tracked by git so this change
  doesn't travel with the branch.

## Deviations from the spec doc, and why

None architectural. The two dead-code extensions above (parser helper,
selenium hash function) are natural consequences of the decommission
checklist's own logic, not new decisions.

## Test results

Independently re-run after every commit, not just taken from Codex's
self-report:

```
139 passed, 2 skipped, 0 failed
```

(`python -m pytest tests/ -q --ignore=tests/test_real_integrations.py`, run
twice — once mid-review, once after the final commit on `apify-migration`.)
Also independently verified: `alembic heads` → single head `20260915_0008`;
`ruff check` on every new Apify file → clean; the Selenium-reference grep
sweep → zero matches; no `apify_api_tokens` leak in the settings endpoints.

## What a human needs to do before merging

- [ ] Set real `APIFY_API_TOKENS` (comma-separated if more than one account)
      in every environment's actual `.env`/secret store — this repo's local
      `.env` was patched for `REVIEW_SOURCE_MODE` only, and `.env` isn't
      tracked by git so no environment picks this up automatically.
- [ ] Run one real smoke test against a known place (e.g. Hermina Bogor)
      with a small `maxReviewsPerPlace` end to end, and specifically confirm
      the exact 402/credit-exhaustion response shape against a real
      exhausted-or-near-exhausted account — `apify_client.py`'s detection
      logic is implemented from documentation, not a live response.
- [ ] Regenerate `requirements.txt`'s lock properly (network access needed)
      instead of the by-hand line removal done here.
- [ ] Review and apply the `20260915_0008_add_apify_resume_checkpoint`
      Alembic migration on the dev DB.
- [ ] Review the 5-commit diff on `apify-migration`
      (`docs → feat → refactor → test → chore`).
- [ ] Decide when to merge — the branch is local only, not pushed, not a PR.
