# VOC-CS-08 - Consumer Worklist OneBox

Status: **Implemented in VoC; OneBox endpoint must be available in the target environment.**

This increment implements the ADR-0003 pull direction: **OneBox owns the worklist and the
Crawler System consumes it as a crawl-target cache.** The sync does not create Ticket,
Message, or analysis records and does not change review cursors.

## Contract

The Crawler System logs in to `POST {ONEBOX_BASE_URL}/api/Authenticate` with form fields
`email`, `password`, and `siteId`. It then calls the configurable worklist path, whose
default is `GET {ONEBOX_BASE_URL}/api/VocWorklist`, with `Authorization: Bearer <JWT>`.

Expected response shape:

```json
{
  "data": [
    {
      "onebox_connection_id": 1039,
      "onebox_location_id": 12,
      "kind": "location",
      "external_place_id": "ChIJ...",
      "branch_name": "Hospital Depok",
      "hospital_name": "Hospital",
      "city": "Depok",
      "target_review_count": 100,
      "google_maps_url": "https://maps.google.com/...",
      "active": true,
      "crawl_enabled": true,
      "ingest_reviews": true,
      "mock": false
    }
  ],
  "meta": { "site_id": 169, "count": 1 }
}
```

`data[].kind` is `location` or `competitor`. `external_place_id` is the stable identity
used for idempotent upsert. `active` controls visibility/activation, `crawl_enabled`
controls whether the target enters a crawl run, `ingest_reviews` controls review ingestion,
and `mock` selects mock fetch behavior for a managed location.

## Configuration

Copy the following values into the deployment secret store. Do not commit them to Git or
print them in logs:

```dotenv
ONEBOX_BASE_URL=https://onebox.example.internal
ONEBOX_SVC_EMAIL=voc-service@example.internal
ONEBOX_SVC_PASSWORD=<secret>
ONEBOX_SITE_ID=169
ONEBOX_COMPANY_ID=<explicit VoC company id>
ONEBOX_WORKLIST_PATH=/api/VocWorklist
ONEBOX_TIMEOUT_SECONDS=30
ONEBOX_MAX_RETRY=3
ONEBOX_WORKLIST_CACHE_STALE_AFTER_SECONDS=86400
```

`ONEBOX_COMPANY_ID` is mandatory for the consumer even though the JWT scopes the OneBox
request. It prevents a deployment from guessing which VoC tenant should receive the data.

### Test without OneBox using Postman Mock Server

1. Import `postman/onebox-worklist-mock.postman_collection.json` into Postman.
2. Create a **public** mock server from that collection and copy its
   `https://<id>.mock.pstmn.io` URL.
3. Copy `.env.example` to `.env`, then replace its OneBox block with
   `.env.postman-mock.example` and set `ONEBOX_BASE_URL` to the copied URL.
4. Ensure `ONEBOX_COMPANY_ID` points to an existing company in the crawler database.
5. Run:

```bash
alembic upgrade head
python -m scripts.refresh_worklist --json
```

The collection mocks both authentication and worklist responses, so the existing production
client path is exercised unchanged. A successful run reports `status: synced`, `fetched: 2`,
and `upserted: 2`. The sample location has `mock: true`, so a later review fetch uses the
crawler's local mock review client instead of Google Maps or Selenium.

## Data behavior

1. The entire response is validated before any database mutation.
2. Location and competitor rows are upserted by `company_id + external_place_id`.
3. Existing review, analysis, deduplication, and crawl-cursor data is preserved.
4. Rows previously managed by OneBox but absent from a successful response are soft-disabled;
   they are not deleted.
5. A successful pull writes `worklist_sync_states` with last attempt, last success, item count,
   site ID, and cleared error.
6. On a network outage, the last successful cache is retained and returned with a warning.
   If no successful cache exists, the crawl run stops rather than using an unknown target list.
7. Authentication and malformed-payload errors stop the run and must be fixed; they are not
   silently converted into a stale crawl.

## Migration and commands

Run the migration in the VoC environment before starting the application:

```bash
alembic upgrade head
```

Refresh manually and inspect the result:

```bash
python -m scripts.refresh_worklist --company-id <VOC_COMPANY_ID>
python -m scripts.refresh_worklist --company-id <VOC_COMPANY_ID> --json
```

The normal `FetchService.fetch_location()` and
`FetchService.fetch_all_active_locations()` paths refresh the worklist at the beginning of
the crawl run. The all-location path refreshes once, then fetches only active targets with
`crawl_enabled=true`. OneBox remains responsible for scheduling; the Crawler System does not
create a second scheduler.

## Verification checklist

- [verified] `app/integrations/onebox_worklist_client.py` caches JWT in memory, refreshes on
  expiry/401, retries timeout/network/5xx, and does not log credentials or tokens.
- [verified] `app/services/worklist_sync_service.py` validates, upserts, soft-disables, and
  records cache health in one transaction.
- [verified] migration `20260724_0001_add_onebox_worklist_cache.py` creates the required
  columns and sync-state table.
- [verified] tests cover upsert, idempotency, soft-disable, outage fallback, explicit tenant,
  and JWT reuse.
- [blocked] Final URL, service-account permission, and exact `siteId`/`company_id` values are
  environment facts that must be supplied by OneBox/Infra.

## Operational notes

The cache is a read-through target registry, not a second master-data UI. If the endpoint
returns an empty list successfully, that is treated as an authoritative empty worklist and
managed targets are disabled. Therefore OneBox must not publish an empty list during a
partial deploy; use a health/readiness gate or return a non-2xx response until the list is
complete.
