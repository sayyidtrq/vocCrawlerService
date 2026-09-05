# vocCrawlerService — hermina-crawler

Headless Google Maps review crawler for OneBox's Voice-of-Customer module.
OneBox is the system of record (ADR-0001); this service scrapes reviews,
runs AI analysis, and exposes them over `/api/integration/*`.

## Repo layout: `app/` vs `apps/`

- **`app/`** — the library: domain models (`app/db`), services (`app/services`),
  external clients (`app/integrations`), config, utils. No web framework here.
  Imported by everything else.
- **`apps/api/`** — the FastAPI deployable. Routers, request/response schemas,
  dependency wiring. Depends on `app/`, never the reverse.
- **`scripts/`** — operator CLI entry points (company/api-client management).
- **`main.py`** — kept only as a console entry point for local inspection.

## Language convention (new code)

- **Code is strictly English** — identifiers, symbols, function/class names,
  API names, enum values, config keys.
- **Comments may be Indonesian.** The dense "why" comments already in
  `config.py`, `crawl_job_service.py`, and `selenium_google_maps_client.py`
  are deliberate; keep writing rationale in whichever language expresses it
  best. Don't translate existing comments.
- **Keep docstrings short.** One line is usually enough. Explain *why*, not
  *what*, and don't pad it into a multi-paragraph docblock.

## Other

- Timestamps: `datetime.now(timezone.utc)`, never `datetime.utcnow()`.
- The living refactor plan is
  `markdowns/04-implementation-plans/crawler-system/PLAN_MAJOR_REFACTOR.md`.
- `markdowns/PROJECT_STATUS.md` predates the major refactor — treat git history
  and the refactor plan as the current source of truth.
