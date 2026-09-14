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
