# OneBox Local Feature CORS

This document explains how OneBox feature pages are allowed to call the Hermina
Crawler API from a browser during local development.

## Browser origin behavior

Local OneBox feature pages use URLs such as:

```text
https://localhost.onebox.co.id/feature/DNGO19-3388/
https://localhost.onebox.co.id/feature/DNGO19-3471/
```

For CORS, both pages have exactly the same origin:

```text
https://localhost.onebox.co.id
```

An origin contains only scheme, hostname, and optional port. It never contains
the `/feature/...` path. Consequently, CORS does not support or require an entry
such as `https://localhost.onebox.co.id/feature/*`.

Allowing `https://localhost.onebox.co.id` permits browser requests from every
path on that origin, including every current and future `DNGO19-*` feature key.

## Hermina Crawler configuration

The local/default browser allowlist is documented in `.env.example`:

```dotenv
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://localhost.onebox.co.id
```

The value is comma-separated and must not contain paths or trailing slashes.
FastAPI reads it through `app/config.py` and applies it through
`CORSMiddleware` in `apps/api/main.py`.

After changing `.env`, restart the Hermina API process or recreate its API
container. The crawl worker does not serve browser requests and does not need a
CORS restart for this change.

## Separate OneBox outbound configuration

The following variables configure Hermina Crawler's server-to-server worklist
connection to OneBox:

```dotenv
ONEBOX_BASE_URL=https://dev.onebox.co.id/feature/voc
ONEBOX_WORKLIST_PATH=/api/VocWorklist
```

They do not control which browser pages may call Hermina and must not be used as
a CORS allowlist. Server-to-server requests are not restricted by browser CORS.

## Verification

Send a browser-style preflight request:

```bash
curl -i -X OPTIONS http://localhost:8000/api/health \
  -H 'Origin: https://localhost.onebox.co.id' \
  -H 'Access-Control-Request-Method: GET'
```

The response must include:

```text
access-control-allow-origin: https://localhost.onebox.co.id
```

The same result applies regardless of whether the calling page is under
`/feature/DNGO19-3388/`, `/feature/DNGO19-3471/`, or another path on the same
origin.

## Security boundary

This configuration allows all browser pages served by
`https://localhost.onebox.co.id`, not only paths matching `/feature/DNGO19-*`.
Browsers do not provide a trustworthy path-level origin for CORS enforcement.
Authentication and authorization remain mandatory on protected Hermina API
endpoints.
