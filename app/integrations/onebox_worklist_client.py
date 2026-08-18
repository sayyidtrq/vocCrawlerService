from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx

from app.config import Settings, get_settings
from app.utils.date_parser import parse_datetime

logger = logging.getLogger(__name__)


class OneBoxWorklistError(RuntimeError):
    """Base error for the outbound OneBox worklist client."""


class OneBoxAuthenticationError(OneBoxWorklistError):
    """OneBox rejected authentication or the configured service account."""


class OneBoxUnavailableError(OneBoxWorklistError):
    """OneBox could not be reached after the configured retries."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class OneBoxWorklistClient:
    """Small, in-memory JWT client for OneBox's read-only worklist."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._http = http_client or httpx.Client(
            timeout=self.settings.onebox_timeout_seconds
        )
        self._owns_http = http_client is None
        self._sleep = sleep
        self._token: str | None = None
        self._valid_until: datetime | None = None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "OneBoxWorklistClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_worklist(self) -> dict[str, Any]:
        self._require_configuration()
        response = self._request(
            "GET",
            self._path(self.settings.onebox_worklist_path),
            headers={"Authorization": f"Bearer {self._get_token()}"},
        )
        if response.status_code == 401:
            self._invalidate_token()
            response = self._request(
                "GET",
                self._path(self.settings.onebox_worklist_path),
                headers={"Authorization": f"Bearer {self._get_token()}"},
            )
        if response.status_code == 401:
            raise OneBoxAuthenticationError("OneBox worklist authentication failed.")
        if response.status_code == 403:
            raise OneBoxAuthenticationError("OneBox worklist access was forbidden.")
        if response.status_code >= 400:
            raise OneBoxWorklistError(
                f"OneBox worklist returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OneBoxWorklistError("OneBox worklist returned invalid JSON.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise OneBoxWorklistError("OneBox worklist response is missing data[].")
        return payload

    def _get_token(self) -> str:
        if self._token and self._token_is_valid():
            return self._token
        return self._login()

    def _login(self) -> str:
        response = self._request(
            "POST",
            self._path("/api/Authenticate"),
            data={
                "email": self.settings.onebox_service_email,
                "password": self.settings.onebox_service_password,
                "siteId": str(self.settings.onebox_site_id),
            },
        )
        if response.status_code in {401, 403}:
            raise OneBoxAuthenticationError("OneBox service account was rejected.")
        if response.status_code >= 400:
            raise OneBoxWorklistError(
                f"OneBox authentication returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OneBoxAuthenticationError(
                "OneBox authentication returned invalid JSON."
            ) from exc
        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise OneBoxAuthenticationError(
                "OneBox authentication response did not contain a token."
            )
        self._token = token
        self._valid_until = _as_utc(
            parse_datetime(payload.get("valid_until"))
            if isinstance(payload, dict)
            else None
        )
        if self._valid_until is None:
            self._valid_until = _utc_now() + timedelta(minutes=5)
        return token

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempts = self.settings.onebox_max_retry + 1
        for attempt in range(attempts):
            try:
                response = self._http.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt == attempts - 1:
                    raise OneBoxUnavailableError(
                        "OneBox request timed out after retries."
                    ) from exc
                self._backoff(attempt)
                continue
            except httpx.RequestError as exc:
                if attempt == attempts - 1:
                    raise OneBoxUnavailableError(
                        "OneBox request could not be completed."
                    ) from exc
                self._backoff(attempt)
                continue

            if response.status_code >= 500 and attempt < attempts - 1:
                self._backoff(attempt)
                continue
            return response
        raise OneBoxUnavailableError("OneBox request could not be completed.")

    def _backoff(self, attempt: int) -> None:
        delay = min(8.0, 0.5 * (2**attempt))
        self._sleep(delay)

    def _token_is_valid(self) -> bool:
        if self._valid_until is None:
            return False
        return self._valid_until > _utc_now() + timedelta(seconds=30)

    def _invalidate_token(self) -> None:
        self._token = None
        self._valid_until = None

    def _require_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("ONEBOX_BASE_URL", self.settings.onebox_base_url),
                ("ONEBOX_SVC_EMAIL", self.settings.onebox_service_email),
                ("ONEBOX_SVC_PASSWORD", self.settings.onebox_service_password),
                ("ONEBOX_SITE_ID", self.settings.onebox_site_id),
            )
            if value is None or (isinstance(value, str) and not value.strip())
        ]
        if missing:
            raise OneBoxWorklistError(
                "OneBox worklist integration is not configured: "
                + ", ".join(missing)
            )

    def _path(self, path: str) -> str:
        return f"{self.settings.onebox_base_url.rstrip('/')}/{path.lstrip('/')}"
