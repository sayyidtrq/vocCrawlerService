# OneBox Upstream and Local Feature Route Configuration

This document describes the repository's supported OneBox upstream modes,
their security boundaries, and the local development workflow. Keep it updated
when OneBox routing or worklist configuration changes.

## 1. Problem statement

Hermina Crawler currently consumes the OneBox worklist from one configured
OneBox deployment. A deployed development instance can use a base URL such as:

```dotenv
ONEBOX_BASE_URL=https://dev.onebox.co.id/feature/voc
```

Local OneBox development uses a route prefix per Jira PBI, for example:

```text
https://localhost.onebox.co.id/feature/DNGO19-3471/
https://localhost.onebox.co.id/feature/DNGO19-3388/
```

The goal is to let a local Hermina Crawler instance select one of these local
feature routes safely, without changing the behavior of the deployed dev
configuration.

Credentials are intentionally omitted from this document. Service-account
credentials must remain in an untracked `.env` or secret store and must never be
committed. Any credential pasted into chat, tickets, or logs should be rotated.

## 2. Important terminology

This requirement is not primarily a CORS requirement.

- The origin of every example local URL is
  `https://localhost.onebox.co.id`.
- `/feature/DNGO19-3471` is a path prefix, not a host or browser origin.
- Hermina Crawler calls OneBox from Python as a server-to-server request. CORS
  does not restrict this request.
- CORS matters only if JavaScript running in a browser calls the Hermina API or
  OneBox API directly across origins.

The existing `CORS_ALLOWED_ORIGINS` setting therefore remains a separate
concern. A feature path must never be added to a CORS origin entry.

## 3. Current behavior

The current client builds OneBox endpoints by keeping the configured base path:

```text
{ONEBOX_BASE_URL without trailing slash}/{endpoint without leading slash}
```

Examples:

| Base URL | Endpoint | Effective request URL |
|---|---|---|
| `https://dev.onebox.co.id/feature/voc` | `/api/Authenticate` | `https://dev.onebox.co.id/feature/voc/api/Authenticate` |
| `https://localhost.onebox.co.id/feature/DNGO19-3471` | `/api/VocWorklist` | `https://localhost.onebox.co.id/feature/DNGO19-3471/api/VocWorklist` |

Consequently, local feature routing already works at URL-composition level when
the complete local feature base URL is supplied explicitly. The remaining risks
are configuration mistakes, Docker name resolution, TLS trust, and accidental
mixing of worklists from multiple feature branches.

## 4. Configuration contract

### 4.1 Existing explicit mode

`ONEBOX_BASE_URL` remains the authoritative configuration for deployed
environments:

```dotenv
APP_ENV=development
ONEBOX_BASE_URL=https://dev.onebox.co.id/feature/voc
ONEBOX_WORKLIST_PATH=/api/VocWorklist
```

It also remains valid for a local developer who prefers an explicit URL:

```dotenv
APP_ENV=local
ONEBOX_BASE_URL=https://localhost.onebox.co.id/feature/DNGO19-3471
ONEBOX_WORKLIST_PATH=/api/VocWorklist
```

### 4.2 Local feature-key mode

To make switching Jira feature routes less error-prone, the repository supports
an optional local feature-key mode:

```dotenv
APP_ENV=local
ONEBOX_LOCAL_ORIGIN=https://localhost.onebox.co.id
ONEBOX_LOCAL_FEATURE_KEY=DNGO19-3471
ONEBOX_WORKLIST_PATH=/api/VocWorklist
```

The application derives:

```text
https://localhost.onebox.co.id/feature/DNGO19-3471
```

Rules:

1. `ONEBOX_LOCAL_FEATURE_KEY` is accepted only when `APP_ENV=local`.
2. Its value must match `^DNGO19-[0-9]+$`, case-insensitively, and is normalized
   to uppercase.
3. `ONEBOX_LOCAL_ORIGIN` must contain only an `http` or `https` scheme, host,
   and optional port. User info, path, query, and fragment are rejected.
4. The default local origin is `https://localhost.onebox.co.id`.
5. Setting both `ONEBOX_BASE_URL` and `ONEBOX_LOCAL_FEATURE_KEY` is an error.
   The application must fail at startup rather than silently choosing one.
6. Feature keys must come from process configuration only. They must not be
   accepted from a browser request, query parameter, or arbitrary API payload.

This is deliberately a constrained template, not a general-purpose URL
wildcard. It prevents an operator-controlled feature selector from becoming an
SSRF mechanism.

## 5. One active OneBox route per crawler instance

A Hermina Crawler process has one OneBox service account, site, company mapping,
worklist cache, and worker queue. It must therefore target exactly one OneBox
base route at a time.

Switching from `DNGO19-3471` to another PBI requires:

1. stop or pause the local API and worker;
2. change `ONEBOX_LOCAL_FEATURE_KEY`;
3. restart both processes;
4. refresh the worklist;
5. verify the returned `site_id` before running crawl jobs.

Supporting multiple OneBox feature branches concurrently is out of scope. That
would require isolated crawler instances and isolated cache/database state, not
a wildcard that selects an upstream per request.

## 6. Docker and local hostname handling

When Hermina Crawler runs directly on the Windows host, the hosts-file mapping
for `localhost.onebox.co.id` may be available normally.

When it runs in Docker, `localhost` refers to the container itself. The API and
crawl-worker containers must be able to resolve `localhost.onebox.co.id` to the
host gateway or to the network address that exposes the OneBox reverse proxy.
The Compose services contain the following hostname mapping:

```yaml
extra_hosts:
  - "localhost.onebox.co.id:host-gateway"
```

This mapping must be applied to every container that creates the OneBox client,
including both `api` and `crawl-worker`.

The mapping still needs runtime verification for each Docker Desktop/WSL
topology. If the OneBox reverse proxy is reachable only through a shared Docker
network, an explicit network alias is preferable to the host gateway.

## 7. Local HTTPS trust

The crawler must continue verifying TLS certificates. Implementation must not
set `verify=False` globally or disable certificate checks to make local routing
work.

If the certificate for `localhost.onebox.co.id` is signed by a local CA, that CA
must be trusted by the Python process and by both Docker containers. The
recommended approach is to mount/install the development CA certificate into
the container trust store. The requested hostname must remain
`localhost.onebox.co.id` so certificate hostname verification still succeeds.

## 8. URL construction requirements

Authentication and worklist requests must use the same resolved base route:

```text
POST <resolved-base>/api/Authenticate
GET  <resolved-base><ONEBOX_WORKLIST_PATH>
```

The URL builder must:

- preserve `/feature/<key>`;
- normalize one boundary slash;
- reject base URLs with query strings, fragments, or user info;
- require `http` or `https`, with `https` preferred;
- avoid standard URL-join behavior that discards the feature prefix when the
  endpoint begins with `/`;
- never log service-account passwords or bearer tokens.

## 9. Repository implementation

The behavior is implemented in these locations:

| File | Responsibility |
|---|---|
| `app/config.py` | Reads both modes, validates URLs and feature keys, and resolves one effective base URL at startup |
| `app/integrations/onebox_worklist_client.py` | Uses the resolved base URL for authentication and worklist requests |
| `app/services/worklist_sync_service.py` | Treats either a valid explicit URL or local feature key as configured |
| `.env.example` | Documents both mutually exclusive modes without credentials |
| `docker-compose.yml` | Maps `localhost.onebox.co.id` to the host gateway for both API and worker |
| `tests/test_worklist_sync.py` | Covers route derivation, validation, prefix preservation, and client requests |

Configuration validation runs while application settings are loaded. Invalid
or conflicting configuration therefore stops startup before the worker can use
an unintended upstream.

## 10. Acceptance criteria

### Configuration

- Existing deployed configuration using
  `https://dev.onebox.co.id/feature/voc` behaves unchanged.
- Local `DNGO19-3471` configuration resolves to
  `https://localhost.onebox.co.id/feature/DNGO19-3471`.
- A different valid PBI key can be selected by changing only
  `ONEBOX_LOCAL_FEATURE_KEY` and restarting the local processes.
- Invalid or ambiguous settings fail fast with a safe, actionable error.

### Connectivity

- Both the API and crawl worker resolve `localhost.onebox.co.id` correctly.
- TLS verification remains enabled and succeeds with the trusted local CA.
- Authentication reaches the feature-prefixed `/api/Authenticate` route.
- Worklist sync reaches the feature-prefixed `/api/VocWorklist` route.

### Isolation and security

- One crawler instance cannot switch upstream based on untrusted request data.
- Service-account password and JWT never appear in logs or diagnostic output.
- Worklist `site_id` must match `ONEBOX_SITE_ID` before data is accepted.
- No CORS wildcard is introduced as part of this work.

## 11. Manual verification

1. Configure a local feature key without placing credentials in shell history.
2. Start/recreate both Hermina services.
3. Verify hostname resolution from both containers.
4. Run the worklist refresh through the normal Hermina UI or scheduler flow.
5. Confirm that the UI reports a successful sync for the expected site.
6. Confirm in sanitized logs that requests use
   `/feature/DNGO19-<number>/api/...`.
7. Switch to a second PBI key, restart, and repeat.
8. Restore the original configuration and verify the dev base URL remains
   unchanged.

## 12. Troubleshooting notes

- A connection refusal or timeout is a routing, bind-address, firewall, or
  Docker-network problem—not CORS.
- A browser CORS failure is unrelated to the crawler's outbound worklist call.
- An HTTPS certificate error must be fixed by trusting the local CA; do not
  disable TLS verification.
- A 404 on `/api/Authenticate` or `/api/VocWorklist` usually means the feature
  prefix was omitted or the selected OneBox feature route is not running.
- A startup error mentioning both URL modes means `ONEBOX_BASE_URL` and
  `ONEBOX_LOCAL_FEATURE_KEY` were both set. Clear one of them.
- The `.env` assignment must not have indentation or trailing punctuation. Use
  `ONEBOX_TIMEOUT_SECONDS=30`, not an indented value ending in a period.
