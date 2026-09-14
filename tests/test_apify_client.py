import pytest

from app.config import Settings
from app.integrations.apify_client import ApifyAccountExhaustedError, ApifyClient
from app.integrations.review_source_client import ReviewSourceError


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.ok = 200 <= status_code < 300

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


def settings():
    return Settings(database_url="sqlite+pysqlite:///:memory:", fetch_timeout_seconds=1)


def test_429_retries_with_the_same_token(monkeypatch):
    session = FakeSession(
        [
            FakeResponse(429, {"error": {"message": "rate limited"}}),
            FakeResponse(201, {"data": {"id": "run-1", "defaultDatasetId": "data-1"}}),
        ]
    )
    monkeypatch.setattr("app.integrations.apify_client.time.sleep", lambda _: None)

    assert ApifyClient(settings(), session).start_run(
        "actor/name", {}, token="same-token"
    ) == ("run-1", "data-1")
    assert [call[2]["headers"]["Authorization"] for call in session.calls] == [
        "Bearer same-token",
        "Bearer same-token",
    ]


def test_402_raises_account_exhaustion_signal():
    session = FakeSession(
        [
            FakeResponse(
                402,
                {
                    "error": {
                        "type": "insufficient-credits",
                        "message": "credits exhausted",
                    }
                },
            )
        ]
    )

    with pytest.raises(ApifyAccountExhaustedError):
        ApifyClient(settings(), session).start_run("actor/name", {}, token="token")


def test_429_never_becomes_account_exhaustion():
    session = FakeSession(
        [FakeResponse(429, {"error": {"message": "rate quota exceeded"}})]
    )

    with pytest.raises(ReviewSourceError) as caught:
        ApifyClient(
            settings(), session, max_rate_limit_retries=0
        ).start_run("actor/name", {}, token="token")
    assert caught.value.code == "APIFY_RATE_LIMITED"
    assert caught.value.retriable is True


def test_dataset_pagination_continues_until_an_empty_page():
    session = FakeSession([FakeResponse(200, [{"id": 1}]), FakeResponse(200, [])])

    assert list(
        ApifyClient(settings(), session).iter_dataset_items("dataset", token="token")
    ) == [{"id": 1}]
    assert [call[2]["params"]["offset"] for call in session.calls] == [0, 1]
