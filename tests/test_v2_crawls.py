"""The stateless crawl contract uses no live Apify or tenant data."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.crawler_auth as crawler_auth
from app.config import Settings, get_settings
from app.db.audit_models import AuditCrawlRun, AuditReview
from app.db.base import Base
from app.integrations.apify_client import ApifyAccountExhaustedError, ApifyClient
from app.integrations.apify_review_parser import ApifyReviewParser
from app.integrations.apify_token_pool import ApifyAllAccountsExhaustedError
from app.integrations.review_source_client import ReviewSourceError
from app.services.stateless_crawl_service import StatelessCrawlService, decode_crawl_id, encode_crawl_id
from app.utils.date_parser import parse_datetime
from app.utils.hashing import generate_review_hash
from apps.api.app_api.integration_schemas import API_VERSION
from apps.api.app_api.routers.v2_crawls import get_stateless_crawl_service
from apps.api.main import create_app

URL = "/api/integration/v2/crawls"
HEADERS = {"Authorization": "Bearer shared-secret", "X-Request-ID": "v2-test"}
KEY = "crawl-request-001"


def actor_item(index, **updates):
    item = {
        "place_id": "actor-place", "review_id": f"review-{index}",
        "reviewer_name": " Reviewer ", "reviewer_url": "https://maps.example/reviewer",
        "review_url": "https://maps.example/review", "review_photos_urls": [],
        "rating": 5, "content": f"Review {index}",
        "reviewed_at_date": "2026-10-02T07:00:00+07:00", "reviewed_at": "a day ago",
        "scraped_at": "2026-10-03T00:00:00Z", "owner_response": "Thank you",
        "owner_response_at_date": "2026-10-03T07:00:00+07:00",
        "private_actor_field": "must never escape",
    }
    return {**item, **updates}


class FakeTokenPool:
    def __init__(self):
        self.tokens = ["apify-secret-one", "apify-secret-two"]
        self.current_index = 0
        self.exhausted = set()
        self.read_indices = []

    def current(self):
        if self.current_index in self.exhausted:
            raise ApifyAllAccountsExhaustedError("No credits")
        return self.tokens[self.current_index]

    def mark_exhausted(self, index):
        self.exhausted.add(index)

    def rotate(self):
        for index in range(len(self.tokens)):
            if index not in self.exhausted:
                self.current_index = index
                return self.tokens[index]
        return None

    def token_at(self, index):
        self.read_indices.append(index)
        return self.tokens[index]


class FakeApifyClient:
    def __init__(self):
        self.start_calls = []
        self.page_calls = []
        self.status_calls = []
        self.failures = {}
        self.runs = {}
        self.items = {}
        self.count_error = None
        self.count_missing = False
        self.status_error = None
        self.page_error = None

    def start_run(self, actor_id, actor_input, *, token):
        self.start_calls.append((actor_id, actor_input, token))
        place = actor_input["place_ids"][0]
        error = self.failures.get((place, token)) or self.failures.get(place)
        if error:
            raise error
        run_id = f"run-{len(self.runs) + 1}"
        dataset_id = f"dataset-{len(self.runs) + 1}"
        self.runs[run_id] = {"status": "SUCCEEDED", "token": token, "dataset_id": dataset_id}
        self.items[dataset_id] = [actor_item(i) for i in range(5)]
        return run_id, dataset_id

    def get_run_status_once(self, run_id, *, token):
        self.status_calls.append((run_id, token))
        if self.status_error:
            raise self.status_error
        run = self.runs.get(run_id)
        if run is None or run["token"] != token:
            raise ReviewSourceError("Actor run was not found", code="APIFY_HTTP_ERROR")
        return run["status"]

    def get_dataset_items(self, dataset_id, *, token, offset, limit):
        self.page_calls.append((dataset_id, token, offset, limit))
        if self.page_error:
            raise self.page_error
        return self.items[dataset_id][offset:offset + limit]

    def dataset_item_count(self, dataset_id, *, token):
        if self.count_error:
            raise self.count_error
        return None if self.count_missing else len(self.items[dataset_id])


@pytest.fixture()
def api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    pool = FakeTokenPool()
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:", crawler_api_token="shared-secret",
        apify_api_tokens=pool.tokens,
    )
    apify = FakeApifyClient()
    service = StatelessCrawlService(settings, apify_client=apify, token_pool=pool, session_factory=factory)
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[get_stateless_crawl_service] = lambda: service
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, service=service, apify=apify, pool=pool, factory=factory,
            engine=engine, settings=settings, app=app,
        )
    engine.dispose()


def post(api, places=("place-1",), *, key=None, **options):
    headers = {**HEADERS, **({"Idempotency-Key": key} if key is not None else {})}
    return api.client.post(URL, headers=headers, json={
        "targets": [{"place_id": place} for place in places], **options,
    })


def start(api, **options):
    response = post(api, **options)
    assert response.status_code == 202, response.text
    return response.json()["data"]["runs"][0]


def poll(api, run, **params):
    return api.client.get(f"{URL}/{run['crawl_id']}", headers=HEADERS, params=params)


def explode():
    raise RuntimeError("audit database unavailable")


@pytest.mark.parametrize("authorization,expected", [(None, 401), ("Basic shared-secret", 401), ("Bearer wrong", 401), ("Bearer shared-secret", 202)])
def test_auth_without_database(api, authorization, expected, monkeypatch):
    calls = []

    def broken_factory():
        calls.append(True)
        return explode()

    api.service.session_factory = broken_factory
    headers = {"X-Request-ID": "auth-test"}
    if authorization:
        headers["Authorization"] = authorization
    response = api.client.post(URL, headers=headers, json={"targets": [{"place_id": "p"}]})
    assert response.status_code == expected
    if expected == 401:
        assert calls == []
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {"error": {"code": "INVALID_SERVICE_TOKEN", "message": "Invalid service token.", "request_id": "auth-test"}}
    else:
        assert len(calls) == 1


@pytest.mark.parametrize("method", ["post", "get"])
@pytest.mark.parametrize("with_header", [False, True])
def test_unconfigured_never_accepts_token(api, monkeypatch, method, with_header):
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: api.settings.model_copy(update={"crawler_api_token": None}))
    api.app.dependency_overrides[get_stateless_crawl_service] = explode
    kwargs = {"headers": HEADERS if with_header else {}}
    if method == "post":
        kwargs["json"] = {"targets": [{"place_id": "p"}]}
    response = getattr(api.client, method)(URL if method == "post" else URL + "/invalid", **kwargs)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "V2_NOT_CONFIGURED"


def test_auth_get_and_unlabelled_site(api):
    run = start(api)
    api.service.session_factory = explode
    assert api.client.get(f"{URL}/{run['crawl_id']}").status_code == 401
    assert poll(api, run).status_code == 200
    assert decode_crawl_id(run["crawl_id"], 2)["site_id"] == 0


@pytest.mark.parametrize("changes", [
    {"mode": "range"}, {"mode": "range", "date_from": "2026-10-01T00:00:00Z"},
    {"mode": "range", "date_to": "2026-10-01T00:00:00Z"},
    {"mode": "range", "date_from": "2026-10-02T00:00:00Z", "date_to": "2026-10-01T00:00:00Z"},
    {"date_from": "2026-10-01T00:00:00"}, {"date_to": "2026-10-01T00:00:00Z"},
    {"mode": "backfill", "date_to": "2026-10-01T00:00:00Z"},
    {"mode": "range", "date_from": "2026-10-01T00:00:00Z", "date_to": "2026-10-02T00:00:00"},
    {"targets": [{"place_id": "p"}, {"place_id": "p"}]}, {"targets": []},
    {"targets": [{"place_id": str(i)} for i in range(51)]},
    {"targets": [{"place_id": ""}]}, {"targets": [{"place_id": "x" * 256}]},
    {"targets": [{"place_id": "p", "tenant_id": 1}]},
    {"unknown": True}, {"site_id": -1}, {"site_id": True}, {"site_id": 1.5},
    {"max_reviews": 0}, {"max_reviews": 100001}, {"mode": "full"}, {"sort_by": "oldest"},
])
def test_post_validation(api, changes):
    response = api.client.post(URL, headers=HEADERS, json={"targets": [{"place_id": "p"}], **changes})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert response.json()["error"]["request_id"] == "v2-test"
    assert api.apify.start_calls == []


@pytest.mark.parametrize("key", ["", "x" * 7, "x" * 129])
def test_idempotency_key_validation(api, key):
    response = post(api, key=key)
    assert response.status_code == 400
    assert api.apify.start_calls == []


@pytest.mark.parametrize("mode", ["delta", "backfill", "range"])
@pytest.mark.parametrize("sort_by", ["newest", "most_relevant", "highest_rating", "lowest_rating"])
def test_post_starts_exact_actor_input_and_handle(api, mode, sort_by):
    date_from = "2026-10-01T00:00:00+07:00"
    options = {"mode": mode, "date_from": date_from, "sort_by": sort_by, "max_reviews": 42, "site_id": 999999}
    if mode == "range":
        options["date_to"] = "2026-10-02T00:00:00+07:00"
    response = post(api, places=("p1", "p2"), key=KEY, **options)
    assert response.status_code == 202
    body = response.json()
    assert body["meta"] == {"api_version": API_VERSION, "request_id": "v2-test"}
    assert body["data"]["idempotent_replay"] is False
    for place, call, run in zip(("p1", "p2"), api.apify.start_calls, body["data"]["runs"]):
        assert call == (api.settings.apify_actor_id, {
            "place_ids": [place], "limit": 42, "order": sort_by,
            "include_personal": True, "source": "google", "anyDate": "2026-10-01",
        }, api.pool.tokens[0])
        handle = decode_crawl_id(run["crawl_id"], 2)
        assert handle == {
            "v": 1, "run_id": run["run_id"], "dataset_id": api.apify.runs[run["run_id"]]["dataset_id"],
            "token_index": 0, "place_id": place, "site_id": 999999, "mode": mode,
            "date_from": date_from, "date_to": options.get("date_to"), "limit": 42,
        }
        assert encode_crawl_id(handle) == run["crawl_id"]
        assert "=" not in run["crawl_id"]
        assert not any(token in json.dumps(handle) or token in response.text for token in api.pool.tokens)


def test_post_defaults_and_fifty_targets(api):
    response = post(api, places=tuple(f"p{i}" for i in range(50)), key="x" * 128)
    assert response.status_code == 202
    assert len(api.apify.start_calls) == 50
    actor_input = api.apify.start_calls[0][1]
    assert actor_input == {"place_ids": ["p0"], "limit": 100, "order": "newest", "include_personal": True, "source": "google"}


@pytest.mark.parametrize("error,status,code", [
    (ReviewSourceError("concurrency limit", code="APIFY_RATE_LIMITED"), 429, "APIFY_CONCURRENCY_LIMIT"),
    (ApifyAllAccountsExhaustedError("empty"), 503, "APIFY_ACCOUNTS_EXHAUSTED"),
    (RuntimeError("unknown apify-secret-one"), 502, "APIFY_RUN_FAILED"),
])
def test_post_all_fail_and_partial_fail(api, error, status, code):
    api.apify.failures["bad"] = error
    response = post(api, places=("bad",))
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    if status == 429:
        assert response.headers["Retry-After"] == "60"
    response = post(api, places=("bad", "good"))
    assert response.status_code == 202
    failed, good = response.json()["data"]["runs"]
    assert failed["status"] == "failed" and failed["error"]["code"] == code
    assert failed["crawl_id"] is None and failed["run_id"] is None
    assert good["status"] == "started" and good["error"] is None
    assert "apify-secret-one" not in response.text
    with api.factory() as session:
        assert [row.place_id for row in session.scalars(select(AuditCrawlRun))] == ["good"]


def test_rotation_on_exhaustion(api):
    api.apify.failures[("place-1", api.pool.tokens[0])] = ApifyAccountExhaustedError("No credits")
    run = start(api)
    assert [call[2] for call in api.apify.start_calls] == api.pool.tokens
    assert api.pool.exhausted == {0}
    assert decode_crawl_id(run["crawl_id"], 2)["token_index"] == 1
    assert poll(api, run).status_code == 200
    assert api.pool.read_indices == [1]


def test_all_accounts_exhausted_and_no_tokens(api):
    api.apify.failures["place-1"] = ApifyAccountExhaustedError("No credits")
    response = post(api)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "APIFY_ACCOUNTS_EXHAUSTED"
    assert api.pool.exhausted == {0, 1}
    api.service.token_count = 0
    api.apify.start_calls.clear()
    assert post(api).status_code == 503
    assert api.apify.start_calls == []


def test_replay_and_new_places_and_site_isolation(api):
    first = post(api, places=("p1", "p2"), key=KEY).json()["data"]
    api.apify.start_calls.clear()
    replay = post(api, places=("p1", "p2"), key=KEY).json()["data"]
    assert replay == {**first, "idempotent_replay": True}
    assert api.apify.start_calls == []
    mixed = post(api, places=("p2", "p3"), key=KEY).json()["data"]
    assert mixed["idempotent_replay"] is False
    assert mixed["runs"][0] == first["runs"][1]
    assert [call[1]["place_ids"] for call in api.apify.start_calls] == [["p3"]]
    api.apify.start_calls.clear()
    assert post(api, places=("p1",), key=KEY, site_id=1).json()["data"]["idempotent_replay"] is False
    assert len(api.apify.start_calls) == 1


def test_replay_database_failure_is_open(api, caplog):
    start(api, key=KEY)
    api.apify.start_calls.clear()
    api.service.session_factory = explode
    response = post(api, key=KEY)
    assert response.status_code == 202
    assert response.json()["data"]["idempotent_replay"] is False
    assert len(api.apify.start_calls) == 1
    assert "replay lookup failed: audit database unavailable" in caplog.text
    assert "audit write failed: audit database unavailable" in caplog.text


@pytest.mark.parametrize("apify_status,status,done", [
    ("READY", "running", False), ("RUNNING", "running", False),
    ("SUCCEEDED", "succeeded", True), ("FAILED", "failed", True),
    ("ABORTING", "aborted", False), ("ABORTED", "aborted", True),
    ("TIMING-OUT", "timed_out", False), ("TIMED-OUT", "timed_out", True),
    ("NEW-STATUS", "unknown", False),
])
def test_get_statuses_and_produced_items(api, apify_status, status, done):
    run = start(api)
    api.apify.runs[run["run_id"]]["status"] = apify_status
    response = poll(api, run)
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["status"], data["done"], data["next_cursor"]) == (status, done, None if done else "5")
    assert data["fetched_so_far"] == 5 and len(data["reviews"]) == 5
    with api.factory() as session:
        row = session.scalar(select(AuditCrawlRun))
        assert (row.finished_at is not None) is done


def test_three_page_pagination(api):
    run = start(api)
    cursor, reviews = "0", []
    for page, expected_cursor in enumerate(("2", "4", None)):
        response = poll(api, run, cursor=cursor, limit=2)
        assert response.status_code == 200
        data = response.json()["data"]
        reviews.extend(data["reviews"])
        assert data["next_cursor"] == expected_cursor
        assert data["done"] is (page == 2)
        cursor = expected_cursor
    assert [review["external_review_id"] for review in reviews] == [f"review-{i}" for i in range(5)]
    assert len({review["review_hash"] for review in reviews}) == 5
    assert [(call[2], call[3]) for call in api.apify.page_calls] == [(0, 2), (2, 2), (4, 2)]


def test_running_partial_and_empty_tail_then_finish(api):
    run = start(api)
    source = api.apify.runs[run["run_id"]]
    source["status"] = "RUNNING"
    dataset = source["dataset_id"]
    api.apify.items[dataset] = [actor_item(0)]
    first = poll(api, run).json()["data"]
    assert first["next_cursor"] == "1" and first["done"] is False
    empty = poll(api, run, cursor="1").json()["data"]
    assert empty["reviews"] == [] and empty["next_cursor"] == "1" and empty["done"] is False
    api.apify.items[dataset].append(actor_item(1))
    source["status"] = "SUCCEEDED"
    last = poll(api, run, cursor=first["next_cursor"]).json()["data"]
    assert last["done"] is True and last["next_cursor"] is None
    assert [review["external_review_id"] for review in last["reviews"]] == ["review-1"]


def test_range_dedup_and_raw_offset(api):
    run = start(api, mode="range", date_from="2026-10-02T00:00:00Z", date_to="2026-10-03T00:00:00Z")
    dataset = api.apify.runs[run["run_id"]]["dataset_id"]
    api.apify.items[dataset] = [
        actor_item(0, reviewed_at_date="2026-10-01T00:00:00Z"),
        actor_item(1), actor_item(1),
        actor_item(2, reviewed_at_date=None, reviewed_at=None),
        actor_item(3, reviewed_at_date="2026-10-03T00:00:00Z"),
        actor_item(4, reviewed_at_date="2026-10-04T00:00:00Z"),
    ]
    data = poll(api, run, limit=3).json()["data"]
    assert [review["external_review_id"] for review in data["reviews"]] == ["review-1"]
    assert data["next_cursor"] == "3"
    data = poll(api, run, cursor="3", limit=3).json()["data"]
    assert [review["external_review_id"] for review in data["reviews"]] == ["review-2", "review-3"]
    assert data["done"] is True


def test_normalized_fields_hash_and_no_actor_payload(api):
    run = start(api)
    item = actor_item(1)
    api.apify.items[api.apify.runs[run["run_id"]]["dataset_id"]] = [item]
    response = poll(api, run)
    review = response.json()["data"]["reviews"][0]
    parsed = ApifyReviewParser.parse_review(item)
    expected_hash = generate_review_hash({
        **parsed, "external_place_id": "place-1", "reviewer_name": "Reviewer",
        "review_time": parse_datetime(parsed["review_time"]),
    })
    assert review["review_hash"] == expected_hash
    assert review["review_time"] == "2026-10-02T00:00:00Z"
    assert review["owner_response_time"] == "2026-10-03T00:00:00Z"
    assert review["reviewer_name"] == "Reviewer"
    for forbidden in ("raw_payload", "private_actor_field", "must never escape", "scraped_at", *api.pool.tokens):
        assert forbidden not in response.text


def test_real_actor_fixture(api):
    run = start(api)
    dataset = api.apify.runs[run["run_id"]]["dataset_id"]
    api.apify.items[dataset] = json.loads((Path(__file__).parent / "fixtures/apify_google_maps_reviews_sample.json").read_text())
    response = poll(api, run)
    assert response.status_code == 200
    reviews = response.json()["data"]["reviews"]
    assert len(reviews) == 4
    assert reviews[0]["reviewer_name"] == "Anonymous"
    assert reviews[-1]["is_edited"] is True
    assert reviews[-1]["edited_at"].endswith("Z")


@pytest.mark.parametrize("field,value", [
    ("v", 2), ("v", True), ("run_id", 1), ("run_id", ""), ("run_id", "x" * 65),
    ("dataset_id", []), ("dataset_id", ""), ("place_id", {}), ("place_id", "x" * 256),
    ("token_index", -1), ("token_index", 2), ("token_index", "0"), ("token_index", True),
    ("site_id", -1), ("site_id", False), ("site_id", "0"), ("limit", 0), ("limit", 100001),
    ("limit", 1.5), ("mode", "bad"), ("mode", []),
    ("date_from", 1), ("date_from", "2026-10-01"), ("date_from", "bad"),
    ("date_to", "2026-10-01T00:00:00Z"),
])
def test_bad_handle_fields(api, field, value):
    run = start(api)
    handle = decode_crawl_id(run["crawl_id"], 2)
    response = poll(api, {"crawl_id": encode_crawl_id({**handle, field: value})})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CRAWL_ID"
    assert api.apify.status_calls == []


@pytest.mark.parametrize("value", ["!!!", "a", "bm90LWpzb24", "e30", "W10", "bnVsbA", "eyJ2IjoxfQ", "x" * 8193])
def test_malformed_crawl_ids(api, value):
    response = poll(api, {"crawl_id": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CRAWL_ID"


def test_handle_range_validation(api):
    run = start(api, mode="range", date_from="2026-10-01T00:00:00Z", date_to="2026-10-02T00:00:00Z")
    handle = decode_crawl_id(run["crawl_id"], 2)
    for updates in ({"date_from": None}, {"date_to": None}, {"date_from": "2026-10-03T00:00:00Z"}, {"extra": "secret"}):
        assert poll(api, {"crawl_id": encode_crawl_id({**handle, **updates})}).json()["error"]["code"] == "INVALID_CRAWL_ID"


@pytest.mark.parametrize("cursor", ["", "-1", "1.5", "abc", " 1", "١", "9" * 4400])
def test_invalid_cursor(api, cursor):
    response = poll(api, start(api), cursor=cursor)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert api.apify.status_calls == []


@pytest.mark.parametrize("limit", [0, 501, "abc"])
def test_page_limit(api, limit):
    response = poll(api, start(api), limit=limit)
    assert response.status_code == 400


@pytest.mark.parametrize("source", ["status_error", "page_error", "count_error"])
@pytest.mark.parametrize("error,status,code", [
    (ReviewSourceError("Actor run was not found", code="APIFY_HTTP_ERROR"), 404, "CRAWL_NOT_FOUND"),
    (ReviewSourceError("Apify API error (HTTP 404).", code="APIFY_HTTP_ERROR"), 404, "CRAWL_NOT_FOUND"),
    (ReviewSourceError("Authentication token is not valid", code="APIFY_HTTP_ERROR"), 404, "CRAWL_NOT_FOUND"),
    (ReviewSourceError("Rate limit", code="APIFY_RATE_LIMITED"), 429, "APIFY_CONCURRENCY_LIMIT"),
    (ReviewSourceError("Apify API error (HTTP 500).", code="APIFY_HTTP_ERROR"), 502, "APIFY_RUN_FAILED"),
    (RuntimeError("broken"), 502, "APIFY_RUN_FAILED"),
])
def test_get_errors(api, source, error, status, code):
    run = start(api)
    setattr(api.apify, source, error)
    response = poll(api, run)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    if status == 429:
        assert response.headers["Retry-After"] == "60"


def test_unknown_run_and_page_failure(api):
    run = start(api)
    api.apify.runs.clear()
    assert poll(api, run).status_code == 404
    run = start(api)
    api.apify.page_error = ReviewSourceError("too many requests", code="APIFY_RATE_LIMITED")
    assert poll(api, run).status_code == 429


def test_count_unavailable_and_exact_page_boundary(api):
    run = start(api)
    api.apify.count_missing = True
    data = poll(api, run, limit=5).json()["data"]
    assert data["fetched_so_far"] is None
    assert data["done"] is False and data["next_cursor"] == "5"
    data = poll(api, run, cursor="5", limit=5).json()["data"]
    assert data["done"] is True and data["next_cursor"] is None


def test_post_audit_and_page_audit_distinct_runs(api):
    run = start(api, key=KEY, site_id=123, max_reviews=99)
    handle = decode_crawl_id(run["crawl_id"], 2)
    with api.factory() as session:
        audit = session.scalar(select(AuditCrawlRun))
        assert audit.handle == handle and audit.idempotency_key == KEY
        assert audit.params == {"place_id": "place-1", "mode": "delta", "date_from": None, "date_to": None, "max_reviews": 99, "sort_by": "newest"}
        assert audit.status == "started" and audit.fetched_count == 0
        assert audit.started_at is not None and audit.created_at is not None
    data = poll(api, run, limit=2).json()["data"]
    with api.factory() as session:
        rows = list(session.scalars(select(AuditReview).order_by(AuditReview.id)))
        assert [row.payload for row in rows] == data["reviews"]
        assert all(row.site_id == 123 and row.seen_count == 1 for row in rows)
        assert all(row.first_run_id == run["run_id"] == row.last_run_id for row in rows)
        before = rows[0].last_seen_at
    assert poll(api, run, limit=2).json()["data"] == data
    with api.factory() as session:
        row = session.scalar(select(AuditReview).order_by(AuditReview.id))
        assert row.seen_count == 1 and row.last_seen_at > before
    second_run = start(api, site_id=123)
    poll(api, second_run, limit=2)
    with api.factory() as session:
        row = session.scalar(select(AuditReview).order_by(AuditReview.id))
        assert row.seen_count == 2
        assert row.first_run_id == run["run_id"] and row.last_run_id == second_run["run_id"]
    poll(api, run, cursor="2")
    with api.factory() as session:
        row = session.scalar(select(AuditCrawlRun).where(AuditCrawlRun.run_id == run["run_id"]))
        assert row.status == "succeeded" and row.fetched_count == 5
        assert row.last_polled_at is not None and row.finished_at is not None
        finished = row.finished_at
    poll(api, run, cursor="5")
    with api.factory() as session:
        assert session.scalar(select(AuditCrawlRun).where(AuditCrawlRun.run_id == run["run_id"])).finished_at == finished


def test_audit_same_hash_two_site_labels(api):
    first, second = start(api, site_id=0), start(api, site_id=77)
    left = poll(api, first, limit=1).json()["data"]["reviews"][0]
    right = poll(api, second, limit=1).json()["data"]["reviews"][0]
    assert left == right
    with api.factory() as session:
        rows = list(session.scalars(select(AuditReview)))
        assert {row.site_id for row in rows} == {0, 77}
        assert {row.review_hash for row in rows} == {left["review_hash"]}


def test_get_recovers_missing_audit_run(api):
    api.service.session_factory = explode
    run = start(api, mode="range", date_from="2026-10-01T00:00:00Z", date_to="2026-10-04T00:00:00Z", site_id=91)
    api.service.session_factory = api.factory
    assert poll(api, run).status_code == 200
    with api.factory() as session:
        audit = session.scalar(select(AuditCrawlRun))
        assert audit.run_id == run["run_id"] and audit.site_id == 91
        assert audit.handle == decode_crawl_id(run["crawl_id"], 2)
        assert audit.params["date_to"] == "2026-10-04T00:00:00Z"
        assert audit.status == "succeeded" and audit.fetched_count == 5


def test_audit_failure_leaves_identical_response(api, caplog):
    run = start(api)
    expected = poll(api, run).json()
    api.service.session_factory = explode
    response = poll(api, run)
    assert response.status_code == 200 and response.json() == expected
    assert "V2 audit write failed: audit database unavailable" in caplog.text
    assert all(record.levelname == "WARNING" for record in caplog.records)


def test_independent_audit_operations(api, monkeypatch, caplog):
    run = start(api)
    original = api.service._upsert_review

    def fail_one(session, handle, review, now):
        if review["external_review_id"] == "review-0":
            raise RuntimeError("first review write rejected")
        original(session, handle, review, now)

    monkeypatch.setattr(api.service, "_upsert_review", fail_one)
    response = poll(api, run)
    assert response.status_code == 200
    assert len(response.json()["data"]["reviews"]) == 5
    with api.factory() as session:
        assert len(list(session.scalars(select(AuditReview)))) == 4
        assert session.scalar(select(AuditCrawlRun)).fetched_count == 5
    assert "first review write rejected" in caplog.text


def test_run_write_failure_does_not_rollback_reviews(api, monkeypatch, caplog):
    run = start(api)
    monkeypatch.setattr(api.service, "_upsert_run", lambda *args, **kwargs: explode())
    response = poll(api, run)
    assert response.status_code == 200
    with api.factory() as session:
        assert len(list(session.scalars(select(AuditReview)))) == 5
        assert session.scalar(select(AuditCrawlRun)).fetched_count == 0
    assert "audit database unavailable" in caplog.text


def test_integrity_error_retries_with_fresh_session(api, monkeypatch, caplog):
    run = start(api)
    original = api.service._upsert_review
    attempts = []

    def conflict_once(session, handle, review, now):
        attempts.append(session)
        if len(attempts) == 1:
            raise IntegrityError("INSERT", {}, RuntimeError("concurrent insert"))
        original(session, handle, review, now)

    monkeypatch.setattr(api.service, "_upsert_review", conflict_once)
    assert poll(api, run, limit=1).status_code == 200
    assert len(attempts) == 2 and attempts[0] is not attempts[1]
    with api.factory() as session:
        assert session.scalar(select(AuditReview)).seen_count == 1
    assert "concurrent insert" in caplog.text


def test_audit_tables_registered_without_foreign_keys(api):
    inspector = inspect(api.engine)
    for table in ("audit_crawl_runs", "audit_reviews"):
        assert inspector.get_foreign_keys(table) == []
    assert {tuple(item["column_names"]) for item in inspector.get_unique_constraints("audit_crawl_runs")} == {
        ("run_id",), ("site_id", "idempotency_key", "place_id"),
    }


def test_new_dataset_method_uses_request_plumbing(api, monkeypatch):
    client = ApifyClient(api.settings)
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(json=lambda: [actor_item(0)])

    monkeypatch.setattr(client, "_request", request)
    assert client.get_dataset_items("dataset/id", token="private", offset=20, limit=10) == [actor_item(0)]
    assert calls == [(("get", "https://api.apify.com/v2/datasets/dataset%2Fid/items"), {
        "token": "private", "params": {"format": "json", "offset": 20, "limit": 10}, "timeout": 120,
    })]
    for invalid in ({}, [1], None):
        monkeypatch.setattr(client, "_request", lambda *args, **kwargs: SimpleNamespace(json=lambda: invalid))
        with pytest.raises(ReviewSourceError, match="list of objects") as error:
            client.get_dataset_items("d", token="private", offset=0, limit=10)
        assert error.value.code == "APIFY_INVALID_RESPONSE"


def test_crawler_setting_env_default_and_blank(monkeypatch):
    get_settings.cache_clear()
    try:
        assert Settings(database_url="sqlite://").crawler_api_token is None
        monkeypatch.setenv("CRAWLER_API_TOKEN", "from-env")
        assert get_settings().crawler_api_token == "from-env"
        get_settings.cache_clear()
        monkeypatch.setenv("CRAWLER_API_TOKEN", " ")
        assert get_settings().crawler_api_token is None
    finally:
        get_settings.cache_clear()


def test_openapi_crawl_paths(api):
    paths = api.app.openapi()["paths"]
    assert {path for path in paths if "/v2/crawls" in path} == {URL, URL + "/{crawl_id}"}
    assert "422" not in paths[URL]["post"]["responses"]


def test_crawl_id_does_not_depend_on_key_order():
    """JSONB reorders keys; a replay must still hand back the identical id."""
    handle = {
        "v": 1, "run_id": "run-1", "dataset_id": "dataset-1", "token_index": 0,
        "place_id": "place-1", "site_id": 0, "mode": "delta", "date_from": None,
        "date_to": None, "limit": 10,
    }
    assert encode_crawl_id(handle) == encode_crawl_id(dict(reversed(list(handle.items()))))
