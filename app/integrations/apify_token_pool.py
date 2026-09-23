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
        self._exhausted: set[int] = set()
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

    def is_exhausted(self, index: int) -> bool:
        if not self._tokens:
            return True
        idx = index % len(self._tokens)
        if idx in self._exhausted:
            return True
        if self._redis is not None:
            token_sig = hashlib.sha256(self._tokens[idx].encode()).hexdigest()[:16]
            val = self._redis_call("get", f"{self._key}:exhausted:{token_sig}")
            if val is not None and val is not _REDIS_ERROR:
                self._exhausted.add(idx)
                return True
        return False

    def mark_exhausted(self, index_or_token: int | str) -> None:
        if not self._tokens:
            return
        if isinstance(index_or_token, int):
            idx = index_or_token % len(self._tokens)
        else:
            try:
                idx = self._tokens.index(index_or_token.strip())
            except ValueError:
                return
        self._exhausted.add(idx)
        if self._redis is not None:
            token_sig = hashlib.sha256(self._tokens[idx].encode()).hexdigest()[:16]
            self._redis_call(
                "set",
                f"{self._key}:exhausted:{token_sig}",
                "1",
                ex=self._exhausted_ttl_seconds,
            )

    def current(self) -> str:
        self._sync()
        if not self._tokens:
            raise ApifyAllAccountsExhaustedError(
                "No Apify accounts configured."
            )
        if self.is_exhausted(self._index):
            available = self._find_first_available()
            if available is None:
                raise ApifyAllAccountsExhaustedError(
                    "All configured Apify accounts are exhausted."
                )
            self._index = available
            if self._redis is not None:
                self._redis_call("set", f"{self._key}:current", self._index)
        return self._tokens[self._index % len(self._tokens)]

    def _find_first_available(self) -> int | None:
        for i in range(len(self._tokens)):
            candidate = (self._index + i) % len(self._tokens)
            if not self.is_exhausted(candidate):
                return candidate
        return None

    def token_at(self, index: int) -> str:
        if not self._tokens:
            raise ApifyAllAccountsExhaustedError(
                "No Apify accounts configured."
            )
        idx = index % len(self._tokens)
        if self.is_exhausted(idx):
            try:
                return self.current()
            except ApifyAllAccountsExhaustedError:
                return self._tokens[idx]
        return self._tokens[idx]

    def rotate(self, marker: dict | None = None) -> str | None:
        self._sync()
        if not self._tokens:
            return None
        previous = self._index % len(self._tokens)

        next_index = None
        for i in range(1, len(self._tokens) + 1):
            candidate = (previous + i) % len(self._tokens)
            if not self.is_exhausted(candidate):
                next_index = candidate
                break

        if next_index is None:
            # If all are exhausted or only 1 token and it is exhausted:
            if not self.is_exhausted(previous):
                next_index = previous
            else:
                return None

        self._index = next_index
        if self._redis is not None:
            self._redis_call("set", f"{self._key}:current", next_index)

        event = {
            "switched_at": datetime.now(timezone.utc).isoformat(),
            "from_account_index": previous,
            "to_account_index": next_index,
            **(marker or {}),
        }
        self.last_switch = event
        if self._redis is not None:
            self._redis_call("set", f"{self._key}:last_switch", json.dumps(event, default=str))
        return self._tokens[next_index]

    def _sync(self) -> None:
        if self._redis is None or not self._tokens:
            return
        value = self._redis_call("get", f"{self._key}:current")
        if value is _REDIS_ERROR or value is None:
            return
        try:
            self._index = int(value) % len(self._tokens)
        except (TypeError, ValueError):
            pass

    def _next_available(self, previous: int) -> int | None:
        if not self._tokens:
            return None
        return (previous + 1) % len(self._tokens)

    def _redis_call(self, method: str, *args, **kwargs):
        try:
            return getattr(self._redis, method)(*args, **kwargs)
        except self._redis_errors as exc:
            # Redis coordinates workers but must not turn a cache outage into a
            # crawler outage. This process continues with its in-memory index.
            logger.warning("Redis Apify account state unavailable: %s", exc)
            return _REDIS_ERROR
