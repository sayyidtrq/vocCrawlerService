from __future__ import annotations

import time
from collections.abc import Iterator
from urllib.parse import quote, urlsplit

import requests

from app.config import Settings
from app.integrations.review_source_client import ReviewSourceError


class ApifyAccountExhaustedError(RuntimeError):
    """Signals that the current Apify account cannot spend more credits."""

    def __init__(self, message: str, *, request: dict | None = None,
                 response: dict | None = None):
        super().__init__(message)
        self.request = request or {}
        self.response = response or {}


class ApifyClient:
    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        settings: Settings,
        http_session: requests.Session | None = None,
        *,
        max_rate_limit_retries: int = 4,
    ):
        self.settings = settings
        self.http_session = http_session or requests.Session()
        self.max_rate_limit_retries = max_rate_limit_retries

    def start_run(self, actor_id: str, input: dict, *, token: str) -> tuple[str, str]:
        response = self._request(
            "post",
            f"{self.base_url}/actors/{quote(actor_id, safe='')}/runs",
            token=token,
            json=input,
        )
        data = self._json_data(response)
        run_id = data.get("id")
        dataset_id = data.get("defaultDatasetId")
        if not run_id or not dataset_id:
            raise ReviewSourceError(
                "Apify start-run response omitted the run or dataset id.",
                retriable=True,
                code="APIFY_INVALID_RESPONSE",
            )
        return str(run_id), str(dataset_id)

    def get_run_status(self, run_id: str, *, token: str) -> str:
        deadline = time.monotonic() + self.settings.apify_run_timeout_seconds
        terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        while True:
            response = self._request(
                "get",
                f"{self.base_url}/actor-runs/{quote(run_id, safe='')}",
                token=token,
            )
            status = str(self._json_data(response).get("status") or "").upper()
            if status in terminal:
                return status
            if time.monotonic() >= deadline:
                # Not a hard failure: Apify pushes dataset items incrementally
                # as the actor scrapes, so whatever's already in the dataset
                # is real, usable data even though the run itself hasn't
                # confirmed SUCCEEDED yet. The caller reads the dataset
                # either way and decides what to do with a non-SUCCEEDED
                # status - raising here would only cost it that data plus a
                # full-price retry for reviews it may have already paid for.
                return "POLL_TIMEOUT"
            time.sleep(self.settings.apify_poll_interval_seconds)

    def get_run_status_once(self, run_id: str, *, token: str) -> str:
        """Satu kali cek status, tanpa menunggu - untuk run yang diparkir."""
        response = self._request(
            "get",
            f"{self.base_url}/actor-runs/{quote(run_id, safe='')}",
            token=token,
        )
        return str(self._json_data(response).get("status") or "").upper()

    def dataset_item_count(self, dataset_id: str, *, token: str) -> int | None:
        response = self._request(
            "get",
            f"{self.base_url}/datasets/{quote(dataset_id, safe='')}",
            token=token,
        )
        count = self._json_data(response).get("itemCount")
        return int(count) if count is not None else None

    def abort_run(self, run_id: str, *, token: str) -> None:
        # Menghentikan tagihan untuk run yang melewati tenggat.
        self._request(
            "post",
            f"{self.base_url}/actor-runs/{quote(run_id, safe='')}/abort",
            token=token,
        )

    def iter_dataset_items(self, dataset_id: str, *, token: str) -> Iterator[dict]:
        offset = 0
        page_size = 1000
        while True:
            response = self._request(
                "get",
                f"{self.base_url}/datasets/{quote(dataset_id, safe='')}/items",
                token=token,
                params={"format": "json", "limit": page_size, "offset": offset},
            )
            try:
                items = response.json()
            except ValueError as exc:
                raise ReviewSourceError(
                    "Apify dataset returned invalid JSON.",
                    retriable=True,
                    code="APIFY_INVALID_RESPONSE",
                ) from exc
            if not isinstance(items, list):
                raise ReviewSourceError(
                    "Apify dataset response was not a list.",
                    retriable=True,
                    code="APIFY_INVALID_RESPONSE",
                )
            if not items:
                return
            yield from items
            offset += len(items)

    def _request(self, method: str, url: str, *, token: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        for attempt in range(self.max_rate_limit_retries + 1):
            try:
                response = self.http_session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.settings.fetch_timeout_seconds,
                    **kwargs,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                raise ReviewSourceError(
                    f"Apify request failed: {exc}",
                    retriable=True,
                    code="APIFY_REQUEST_FAILED",
                ) from exc
            except requests.RequestException as exc:
                raise ReviewSourceError(
                    f"Apify request failed: {exc}",
                    code="APIFY_REQUEST_FAILED",
                ) from exc
            if response.status_code == 429:
                if attempt < self.max_rate_limit_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise ReviewSourceError(
                    self._error_message(response),
                    retriable=True,
                    code="APIFY_RATE_LIMITED",
                )
            if response.status_code == 402 or self._is_credit_exhaustion(response):
                raise ApifyAccountExhaustedError(
                    self._error_message(response),
                    request={
                        "method": method.upper(),
                        "path": urlsplit(url).path,
                        "params": kwargs.get("params"),
                        "json": kwargs.get("json"),
                    },
                    response={
                        "status_code": response.status_code,
                        "error": self._error_payload(response),
                    },
                )
            if not response.ok:
                raise ReviewSourceError(
                    self._error_message(response),
                    retriable=response.status_code in {408, 429, 500, 502, 503, 504},
                    code="APIFY_HTTP_ERROR",
                )
            return response
        raise AssertionError("rate-limit retry loop did not return")

    @staticmethod
    def _json_data(response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ReviewSourceError(
                "Apify returned invalid JSON.",
                retriable=True,
                code="APIFY_INVALID_RESPONSE",
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ReviewSourceError(
                "Apify response omitted its data object.",
                retriable=True,
                code="APIFY_INVALID_RESPONSE",
            )
        return data

    @staticmethod
    def _is_credit_exhaustion(response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            return False
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return False
        haystack = " ".join(
            str(error.get(key) or "") for key in ("type", "message", "code")
        ).lower()
        return any(word in haystack for word in ("credit", "payment required", "quota"))

    @staticmethod
    def _error_message(response) -> str:
        default = f"Apify API error (HTTP {response.status_code})."
        try:
            payload = response.json()
        except ValueError:
            return default
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            return str(error.get("message") or error.get("type") or default)
        return default

    @staticmethod
    def _error_payload(response) -> dict:
        try:
            payload = response.json()
        except ValueError:
            return {}
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return {}
        return {
            key: error[key]
            for key in ("type", "code", "message")
            if error.get(key) is not None
        }
