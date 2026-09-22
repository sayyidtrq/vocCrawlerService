from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
_REDIS_ERROR = object()


class ApifyAllAccountsExhaustedError(RuntimeError):
    """Raised when no configured Apify account remains usable."""


class ApifyTokenPool:
    def __init__(
        self,
        tokens: list[str],
        *,
        redis_url: str | None = None,
        exhausted_ttl_seconds: int = 86400,
        redis_client=None,
    ):
        self._tokens = [token.strip() for token in tokens if token.strip()]
        self._index = 0
        self._redis = redis_client
        self._redis_errors: tuple[type[BaseException], ...] = ()
        self._exhausted_ttl_seconds = exhausted_ttl_seconds
        self.last_switch: dict | None = None
        signature = hashlib.sha256(
            "\0".join(self._tokens).encode()
        ).hexdigest()[:16]
        self._key = f"apify:account-pool:{signature}"
        if self._redis is None and redis_url:
            import redis

            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis_errors = (redis.RedisError,)
        self._sync()

    @property
    def current_index(self) -> int:
        return self._index

    def current(self) -> str:
        self._sync()
        if self._index >= len(self._tokens):
            raise ApifyAllAccountsExhaustedError(
                "All configured Apify accounts are exhausted."
            )
        return self._tokens[self._index]

    def token_at(self, index: int) -> str:
        """Token akun tertentu - run yang diparkir harus dilanjutkan dengan akun
        yang memulainya."""
        if not 0 <= index < len(self._tokens):
            raise ApifyAllAccountsExhaustedError(
                f"Apify account #{index} is not configured."
            )
        return self._tokens[index]

    def rotate(self, marker: dict | None = None) -> str | None:
        self._sync()
        previous = self._index
        if self._redis is None:
            self._index += 1
            next_index = self._index if self._index < len(self._tokens) else None
        else:
            marked = self._redis_call(
                "set",
                f"{self._key}:exhausted:{previous}",
                "1",
                ex=self._exhausted_ttl_seconds,
            )
            next_index = (
                self._next_available(previous)
                if marked is not _REDIS_ERROR
                else previous + 1
            )
            if next_index is not None and next_index >= len(self._tokens):
                next_index = None
            self._index = next_index if next_index is not None else len(self._tokens)
            if next_index is not None:
                self._redis_call("set", f"{self._key}:current", next_index)

        event = {
            "switched_at": datetime.now(timezone.utc).isoformat(),
            "from_account_index": previous,
            "to_account_index": next_index,
            **(marker or {}),
        }
        self.last_switch = event
        if self._redis is not None:
            self._redis_call("set", f"{self._key}:last_switch", json.dumps(event))
        return self._tokens[next_index] if next_index is not None else None

    def _sync(self) -> None:
        if self._redis is None or not self._tokens:
            return
        value = self._redis_call("get", f"{self._key}:current")
        if value is _REDIS_ERROR:
            return
        try:
            index = int(value)
        except (TypeError, ValueError):
            index = self._index
        candidate = self._next_available(index - 1)
        if candidate is not None:
            self._index = candidate
            self._redis_call("set", f"{self._key}:current", candidate)
        elif self._redis is not None:
            self._index = len(self._tokens)

    def _next_available(self, previous: int) -> int | None:
        for step in range(1, len(self._tokens) + 1):
            candidate = (previous + step) % len(self._tokens)
            exhausted = self._redis_call(
                "exists", f"{self._key}:exhausted:{candidate}"
            )
            if exhausted is _REDIS_ERROR:
                return candidate
            if not exhausted:
                return candidate
        return None

    def _redis_call(self, method: str, *args, **kwargs):
        try:
            return getattr(self._redis, method)(*args, **kwargs)
        except self._redis_errors as exc:
            # Redis coordinates workers but must not turn a cache outage into a
            # crawler outage. This process continues with its in-memory index.
            logger.warning("Redis Apify account state unavailable: %s", exc)
            return _REDIS_ERROR
