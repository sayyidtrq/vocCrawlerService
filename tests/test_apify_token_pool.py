import json

import pytest

from app.config import _EnvSettings
from app.integrations.apify_token_pool import (
    ApifyAllAccountsExhaustedError,
    ApifyTokenPool,
)


def test_single_token_is_current_until_exhausted():
    pool = ApifyTokenPool(["token-a"])

    assert pool.current() == "token-a"
    assert pool.rotate() is None
    with pytest.raises(ApifyAllAccountsExhaustedError):
        pool.current()


def test_two_tokens_rotate_once_then_exhaust():
    pool = ApifyTokenPool(["token-a", "token-b"])

    assert pool.rotate() == "token-b"
    assert pool.current() == "token-b"
    assert pool.rotate() is None


def test_empty_pool_reports_no_remaining_token():
    pool = ApifyTokenPool([])

    assert pool.rotate() is None
    with pytest.raises(ApifyAllAccountsExhaustedError):
        pool.current()


def test_apify_tokens_parse_from_comma_separated_environment_value():
    settings = _EnvSettings(
        database_url="sqlite+pysqlite:///:memory:",
        review_source_mode="apify",
        apify_api_tokens=" token-a, ,token-b ",
    )

    assert settings.apify_api_tokens == ["token-a", "token-b"]


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        self.values[key] = value
        return True

    def exists(self, key):
        return key in self.values


def test_redis_keeps_rotation_across_pool_recreation_without_storing_tokens():
    redis = FakeRedis()
    first = ApifyTokenPool(
        ["token-a", "token-b"], redis_client=redis
    )

    assert first.rotate({"request": {"path": "/runs"}}) == "token-b"
    second = ApifyTokenPool(
        ["token-a", "token-b"], redis_client=redis
    )

    assert second.current() == "token-b"
    switch = next(
        json.loads(value)
        for key, value in redis.values.items()
        if key.endswith(":last_switch")
    )
    assert switch["from_account_index"] == 0
    assert switch["to_account_index"] == 1
    assert switch["request"] == {"path": "/runs"}
    assert "token-a" not in json.dumps(redis.values)
    assert "token-b" not in json.dumps(redis.values)


def test_redis_keeps_all_accounts_exhausted_across_pool_recreation():
    redis = FakeRedis()
    first = ApifyTokenPool(["token-a", "token-b"], redis_client=redis)
    assert first.rotate() == "token-b"
    assert first.rotate() is None

    restarted = ApifyTokenPool(["token-a", "token-b"], redis_client=redis)

    with pytest.raises(ApifyAllAccountsExhaustedError):
        restarted.current()
