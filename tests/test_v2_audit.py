"""Audit reads use seeded SQLite data and never change the backup."""

import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.crawler_auth as crawler_auth
from app.config import Settings
from app.db.audit_models import AuditAnalysis, AuditCrawlRun, AuditReview
from app.db.base import Base
from app.services import audit_query_service as service_module
from app.services.audit_query_service import AuditQueryService
from apps.api.app_api.integration_schemas import API_VERSION
from apps.api.app_api.routers.v2_audit import get_audit_query_service
from apps.api.main import create_app

SUMMARY_URL = "/api/integration/v2/audit/summary"
RECONCILE_URL = "/api/integration/v2/audit/reconcile"
HEADERS = {"Authorization": "Bearer shared-secret", "X-Request-ID": "v2-audit-test"}
MARKERS = ("private-review-text", "private-reviewer-name", "private-handle", "private-params", "private-idempotency", "private-analysis-result")
TABLES = (AuditReview.__table__, AuditCrawlRun.__table__, AuditAnalysis.__table__)


def at(day, hour=0, minute=0, second=0, microsecond=0):
    return datetime(2026, 10, day, hour, minute, second, microsecond, tzinfo=timezone.utc)


NOW = at(27, 12)


def review(review_hash, place_id="p", site_id=0, **updates):
    return AuditReview(**{
        "site_id": site_id, "place_id": place_id, "review_hash": review_hash,
        "payload": {"review_text": MARKERS[0], "reviewer_name": MARKERS[1]},
        "review_time": at(20), "first_seen_at": at(21), "last_seen_at": at(26),
        "seen_count": 2, **updates,
    })


def run(run_id, place_id="p", site_id=0, **updates):
    return AuditCrawlRun(**{
        "run_id": run_id, "site_id": site_id, "place_id": place_id,
        "mode": "delta", "status": "succeeded", "fetched_count": 4,
        "params": {"secret": MARKERS[3]}, "handle": {"secret": MARKERS[2]},
        "idempotency_key": f"{MARKERS[4]}-{run_id}",
        "started_at": at(25), "finished_at": at(25, 0, 10), "created_at": at(25), **updates,
    })


def analysis(review_hash, status="analyzed", site_id=0, **updates):
    return AuditAnalysis(**{
        "site_id": site_id, "review_ref": "caller-ref", "review_hash": review_hash,
        "kind": "analysis", "provider": "jev", "status": status,
        "result": {"secret": MARKERS[5]}, "created_at": at(25), **updates,
    })


def database_state(factory):
    with factory() as session:
        state = []
        for table in TABLES:
            rows = [dict(row) for row in session.execute(select(table).order_by(table.c.id)).mappings()]
            checksum = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
            state.append((len(rows), checksum))
        return state


@pytest.fixture()
def api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=list(TABLES))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", crawler_api_token="shared-secret")
    service = AuditQueryService(session_factory=factory, clock=lambda: NOW)
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[get_audit_query_service] = lambda: service
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    with TestClient(app) as client:
        original_request = client.request

        def read_only_request(*args, **kwargs):
            before = database_state(factory)
            statements.clear()
            event.listen(engine, "before_cursor_execute", record_statement)
            try:
                return original_request(*args, **kwargs)
            finally:
                event.remove(engine, "before_cursor_execute", record_statement)
                assert database_state(factory) == before
                # Every call, including auth/validation/failure responses, must only SELECT.
                assert all(statement.lstrip().upper().startswith("SELECT") for statement, _ in statements)
                assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for statement, _ in statements)

        client.request = read_only_request
        yield SimpleNamespace(
            app=app, client=client, service=service, factory=factory,
            engine=engine, settings=settings, statements=statements,
        )
    engine.dispose()


def seed(api, *rows):
    with api.factory() as session:
        session.add_all(rows)
        session.commit()


def summary(api, **params):
    return api.client.get(SUMMARY_URL, headers=HEADERS, params=params)


def reconcile(api, **updates):
    return api.client.post(RECONCILE_URL, headers=HEADERS, json={
        "place_id": "p", "review_hashes": [], **updates,
    })


def call(api, endpoint, headers=HEADERS):
    if endpoint == "site":
        return api.client.get(SUMMARY_URL, headers=headers)
    if endpoint == "place":
        return api.client.get(SUMMARY_URL, headers=headers, params={"place_id": "p"})
    return api.client.post(RECONCILE_URL, headers=headers, json={"place_id": "p", "review_hashes": []})


@pytest.mark.parametrize("endpoint", ["site", "place", "reconcile"])
@pytest.mark.parametrize("authorization,expected", [
    (None, 401), ("Basic shared-secret", 401), ("Bearer wrong", 401), ("Bearer shared-secret", 200),
])
def test_auth(api, endpoint, authorization, expected):
    headers = {"X-Request-ID": "auth-test"}
    if authorization:
        headers["Authorization"] = authorization
    response = call(api, endpoint, headers)
    assert response.status_code == expected, response.text
    if expected == 401:
        assert api.statements == []
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {"error": {
            "code": "INVALID_SERVICE_TOKEN", "message": "Invalid service token.", "request_id": "auth-test",
        }}
    else:
        assert response.json()["meta"] == {"api_version": API_VERSION, "request_id": "auth-test"}


@pytest.mark.parametrize("endpoint", ["site", "place", "reconcile"])
@pytest.mark.parametrize("with_header", [False, True])
def test_auth_unconfigured(api, endpoint, with_header, monkeypatch):
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: api.settings.model_copy(update={"crawler_api_token": None}))

    def unexpected_dependency():
        pytest.fail("Authentication must run before constructing the service")

    api.app.dependency_overrides[get_audit_query_service] = unexpected_dependency
    response = call(api, endpoint, HEADERS if with_header else {})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "V2_NOT_CONFIGURED"
    assert api.statements == []


@pytest.fixture()
def place_data(api):
    seed(api,
        review("a", review_time=at(1), first_seen_at=at(2), last_seen_at=at(22)),
        review("b", review_time=at(10), first_seen_at=at(3), last_seen_at=at(24)),
        review("c", review_time=None, first_seen_at=at(4), last_seen_at=at(27, 11, 59, 50, 250000)),
        review("d", first_seen_at=at(5), last_seen_at=at(25)),
        run("latest"), run("old", started_at=at(21), finished_at=at(26)),
        run("middle", started_at=at(23), finished_at=None, status="failed"),
        analysis("a", created_at=at(22)), analysis("a", "failed", created_at=at(23)),
        analysis("b", "failed", created_at=at(24)), analysis("c", "rating_fallback"),
        analysis("d", kind="reply_suggestion", created_at=at(26)),
        analysis("unlinked", created_at=at(26)), analysis(None, created_at=at(26)),
        review("a", site_id=1, review_time=at(26)), review("d", site_id=1),
        analysis("d", site_id=1, created_at=at(27)), run("other-site", site_id=1, started_at=at(27)),
    )
    return api


def test_place_summary_exact_counts_and_only_successful_analyses_count(place_data):
    response = summary(place_data, place_id="p", limit=1)
    assert response.status_code == 200, response.text
    assert response.json() == {"data": {
        "site_id": 0, "place_id": "p", "as_of": "2026-10-27T12:00:00Z",
        "reviews": {
            "stored_count": 4, "newest_review_time": "2026-10-20T00:00:00Z",
            "oldest_review_time": "2026-10-01T00:00:00Z", "first_seen_at": "2026-10-02T00:00:00Z",
            "last_seen_at": "2026-10-27T11:59:50.250000Z", "last_seen_age_seconds": 9,
            "unanalyzed_count": 2,
        },
        "crawls": {
            "run_count": 3, "last_run": {
                "run_id": "latest", "mode": "delta", "status": "succeeded",
                "started_at": "2026-10-25T00:00:00Z", "finished_at": "2026-10-25T00:10:00Z", "fetched_count": 4,
            },
            "last_crawl_at": "2026-10-25T00:00:00Z", "last_crawl_age_seconds": 216000,
        },
        "analyses": {
            "count": 4, "last_analysis_at": "2026-10-25T00:00:00Z",
            "by_status": {"analyzed": 1, "failed": 2, "rating_fallback": 1},
        },
    }, "meta": {"api_version": API_VERSION, "request_id": "v2-audit-test"}}
    assert all(marker not in response.text for marker in MARKERS)


def test_place_summary_site_isolation(place_data):
    data = summary(place_data, site_id=1, place_id="p").json()["data"]
    assert data["reviews"]["stored_count"] == 2
    assert data["reviews"]["unanalyzed_count"] == 1
    assert data["reviews"]["newest_review_time"] == "2026-10-26T00:00:00Z"
    assert data["analyses"] == {"count": 1, "last_analysis_at": "2026-10-27T00:00:00Z", "by_status": {"analyzed": 1}}
    assert data["crawls"]["run_count"] == 1
    assert data["crawls"]["last_run"]["run_id"] == "other-site"


def test_empty_place_returns_zeroes_and_nulls(place_data):
    response = summary(place_data, place_id="missing")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reviews"] == {
        "stored_count": 0, "newest_review_time": None, "oldest_review_time": None,
        "first_seen_at": None, "last_seen_at": None, "last_seen_age_seconds": None, "unanalyzed_count": 0,
    }
    assert data["crawls"] == {"run_count": 0, "last_run": None, "last_crawl_at": None, "last_crawl_age_seconds": None}
    assert data["analyses"] == {"count": 0, "last_analysis_at": None, "by_status": {}}


def test_empty_site_returns_zeroes(place_data):
    response = summary(place_data, site_id=999)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "site_id": 999, "as_of": "2026-10-27T12:00:00Z",
        "totals": {"places": 0, "reviews": 0, "runs": 0, "analyses": 0},
        "places": [], "total_places": 0, "truncated": False,
    }
    assert summary(place_data, site_id=999, place_id="p").json()["data"]["reviews"]["stored_count"] == 0


def test_place_with_null_review_time_and_unfinished_run(api):
    seed(api, review("a", review_time=None), run("running", status="running", finished_at=None))
    data = summary(api, place_id="p").json()["data"]
    assert data["reviews"]["newest_review_time"] is data["reviews"]["oldest_review_time"] is None
    assert data["crawls"]["last_run"]["finished_at"] is None
    assert data["crawls"]["last_crawl_age_seconds"] == 216000
    assert data["analyses"]["last_analysis_at"] is None


def test_site_summary_union_stalest_first_totals_and_isolation(api):
    seed(api,
        review("a", "never-a"), review("b", "never-b"), review("c", "old-b"),
        review("d", "old-a"), review("e", "recent"),
        run("old-b", "old-b", started_at=at(10)), run("old-a", "old-a", started_at=at(10)),
        run("only-run", "only-run", started_at=at(11)),
        run("recent-old", "recent", started_at=at(20)), run("recent", "recent"),
        analysis("a"), analysis("a", "failed"), analysis("b", "failed"),
        analysis("c", kind="reply_suggestion"), analysis("orphan"), analysis(None),
        review("e", "recent", site_id=1), analysis("e", site_id=1),
        review("other", "other-site-only", site_id=1), run("other-site", "recent", site_id=1),
    )
    response = summary(api, limit=4)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["totals"] == {"places": 6, "reviews": 5, "runs": 5, "analyses": 5}
    assert data["total_places"] == 6 and data["truncated"] is True
    assert [row["place_id"] for row in data["places"]] == ["never-a", "never-b", "old-a", "old-b"]
    assert data["places"][0] == {
        "place_id": "never-a", "stored_count": 1, "newest_review_time": "2026-10-20T00:00:00Z",
        "last_seen_at": "2026-10-26T00:00:00Z", "last_crawl_at": None, "last_crawl_age_seconds": None,
        "unanalyzed_count": 0,
    }
    assert [row["unanalyzed_count"] for row in data["places"]] == [0, 1, 1, 1]
    assert all(marker not in response.text for marker in MARKERS)
    all_data = summary(api, limit=6).json()["data"]
    assert all_data["truncated"] is False
    assert [row["place_id"] for row in all_data["places"]] == ["never-a", "never-b", "old-a", "old-b", "only-run", "recent"]
    assert all_data["places"][4] == {
        "place_id": "only-run", "stored_count": 0, "newest_review_time": None, "last_seen_at": None,
        "last_crawl_at": "2026-10-11T00:00:00Z", "last_crawl_age_seconds": 1425600, "unanalyzed_count": 0,
    }
    assert all_data["places"][-1]["unanalyzed_count"] == 1
    assert all_data["places"][-1]["last_crawl_age_seconds"] == 216000
    other = summary(api, site_id=1).json()["data"]
    assert other["totals"] == {"places": 2, "reviews": 2, "runs": 1, "analyses": 1}
    assert other["places"][-1]["place_id"] == "recent"
    assert other["places"][-1]["stored_count"] == 1 and other["places"][-1]["unanalyzed_count"] == 0


def test_site_summary_uses_grouped_queries_and_default_limit(api):
    seed(api, *(review(f"hash-{i}", f"place-{i:03}") for i in range(220)))
    for limit, expected in ((None, 50), (200, 200)):
        data = summary(api, **({"limit": limit} if limit is not None else {})).json()["data"]
        assert len(data["places"]) == expected
        assert data["total_places"] == 220 and data["truncated"] is True
        assert data["totals"] == {"places": 220, "reviews": 220, "runs": 0, "analyses": 0}
        assert len(api.statements) == 2
        assert "GROUP BY" in api.statements[-1][0] and "NOT (EXISTS" in api.statements[-1][0]


@pytest.mark.parametrize("params", [
    {"site_id": -1}, {"site_id": "bad"}, {"place_id": ""}, {"place_id": "x" * 256},
    {"limit": 0}, {"limit": 201}, {"limit": "bad"},
])
def test_summary_validation(api, params):
    response = summary(api, **params)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert api.statements == []


@pytest.fixture()
def reconcile_data(api):
    seed(api,
        review("a", review_time=at(1)), review("b", review_time=at(10)),
        review("c", review_time=None), review("d"), review("e", "other"),
        review("f", site_id=1), review("a", site_id=1),
        analysis("a"), run("one"),
    )
    return api


def test_reconcile_exact_set_arithmetic_and_duplicates(reconcile_data):
    response = reconcile(reconcile_data, review_hashes=["z", "b", "e", "f", "b"])
    assert response.status_code == 200, response.text
    assert response.json() == {"data": {
        "site_id": 0, "place_id": "p", "since": None, "caller_count": 4, "backup_count": 4,
        "matched": 1, "missing_in_caller": ["a", "c", "d"], "missing_in_caller_count": 3,
        "missing_in_caller_truncated": False, "missing_in_backup": ["f", "z"],
        "missing_in_backup_count": 2, "missing_in_backup_truncated": False,
        "other_place_count": 1, "as_of": "2026-10-27T12:00:00Z",
    }, "meta": {"api_version": API_VERSION, "request_id": "v2-audit-test"}}
    assert all(marker not in response.text for marker in MARKERS)


def test_reconcile_empty_caller(reconcile_data):
    data = reconcile(reconcile_data).json()["data"]
    assert data["caller_count"] == data["matched"] == data["other_place_count"] == 0
    assert data["backup_count"] == data["missing_in_caller_count"] == 4
    assert data["missing_in_caller"] == ["a", "b", "c", "d"]
    assert data["missing_in_backup"] == [] and data["missing_in_backup_count"] == 0
    assert data["missing_in_caller_truncated"] is data["missing_in_backup_truncated"] is False


def test_reconcile_since_inclusive_null_time_and_unrestricted_existence(reconcile_data):
    response = reconcile(reconcile_data, review_hashes=["a", "b", "e", "z"], since="2026-10-10T07:00:00+07:00")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["since"] == "2026-10-10T00:00:00Z"
    assert data["backup_count"] == 3 and data["matched"] == 1
    assert data["missing_in_caller"] == ["c", "d"] and data["missing_in_caller_count"] == 2
    assert data["missing_in_backup"] == ["z"] and data["missing_in_backup_count"] == 1
    assert data["other_place_count"] == 1
    future = reconcile(reconcile_data, since="2026-10-28T00:00:00Z").json()["data"]
    assert future["backup_count"] == 1 and future["missing_in_caller"] == ["c"]


def test_reconcile_truncation_sorted_lists_and_exact_counts(reconcile_data):
    data = reconcile(reconcile_data, review_hashes=["z", "f", "e", "b"], limit=1).json()["data"]
    assert data["missing_in_caller"] == ["a"] and data["missing_in_caller_count"] == 3
    assert data["missing_in_backup"] == ["f"] and data["missing_in_backup_count"] == 2
    assert data["missing_in_caller_truncated"] is data["missing_in_backup_truncated"] is True
    data = reconcile(reconcile_data, review_hashes=["z", "f", "e", "b"], limit=3).json()["data"]
    assert data["missing_in_caller_truncated"] is data["missing_in_backup_truncated"] is False


def test_reconcile_site_isolation_and_empty_backup(reconcile_data):
    data = reconcile(reconcile_data, site_id=1, review_hashes=["a", "b", "e"]).json()["data"]
    assert data["backup_count"] == 2 and data["matched"] == 1
    assert data["missing_in_caller"] == ["f"] and data["missing_in_backup"] == ["b", "e"]
    assert data["other_place_count"] == 0
    data = reconcile(reconcile_data, site_id=99, review_hashes=["a"]).json()["data"]
    assert data["caller_count"] == 1 and data["backup_count"] == data["matched"] == 0
    assert data["missing_in_caller"] == [] and data["missing_in_backup"] == ["a"]
    assert data["other_place_count"] == 0


@pytest.mark.parametrize("updates", [
    {"site_id": -1}, {"site_id": True}, {"site_id": "1"},
    {"place_id": ""}, {"place_id": "x" * 256}, {"place_id": None},
    {"review_hashes": [""]}, {"review_hashes": ["x" * 256]}, {"review_hashes": [1]},
    {"review_hashes": ["x"] * 10001}, {"review_hashes": None},
    {"since": "2026-10-01T00:00:00"}, {"since": "2026-10-01"}, {"since": "invalid"},
    {"limit": 0}, {"limit": 5001}, {"limit": True}, {"limit": 1.5}, {"limit": "2"}, {"extra": True},
])
def test_reconcile_validation(api, updates):
    response = reconcile(api, **updates)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert api.statements == []


@pytest.mark.parametrize("field", ["place_id", "review_hashes"])
def test_reconcile_required_fields(api, field):
    body = {"place_id": "p", "review_hashes": []}
    del body[field]
    response = api.client.post(RECONCILE_URL, headers=HEADERS, json=body)
    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_reconcile_maximum_request_duplicates_collapse(api):
    data = reconcile(api, review_hashes=["dup"] * 10000, limit=5000).json()["data"]
    assert data["caller_count"] == 1 and data["missing_in_backup"] == ["dup"]
    assert data["missing_in_backup_count"] == 1


def test_reconcile_cap_counts_first_without_loading_hashes(reconcile_data, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_RECONCILE_ROWS", 3)
    response = reconcile(reconcile_data, review_hashes=["b"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RECONCILE_TOO_LARGE"
    assert "since" in response.json()["error"]["message"]
    assert len(reconcile_data.statements) == 1
    assert "count(*)" in reconcile_data.statements[0][0]
    response = reconcile(reconcile_data, since="2026-10-10T00:00:00Z")
    assert response.status_code == 200 and response.json()["data"]["backup_count"] == 3


def test_reconcile_chunked_hash_lookup_with_1200_hashes(api):
    seed(api,
        *(review(f"h{i:04}", "p" if i < 600 else "other") for i in range(900)),
        *(review(f"z{i}") for i in range(5)),
    )
    response = reconcile(api, review_hashes=[f"h{i:04}" for i in range(1200)])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["caller_count"] == 1200 and data["backup_count"] == 605 and data["matched"] == 600
    assert data["other_place_count"] == 300
    assert data["missing_in_caller_count"] == 5 and data["missing_in_caller"] == [f"z{i}" for i in range(5)]
    assert data["missing_in_backup_count"] == 300
    assert data["missing_in_backup"] == [f"h{i:04}" for i in range(900, 1200)]
    assert [len(params) for statement, params in api.statements if " IN (" in statement] == [501, 501, 201]


@pytest.mark.parametrize("endpoint", ["site", "place", "reconcile"])
@pytest.mark.parametrize("failure", ["factory", "query", "default_factory"])
def test_database_failures_are_generic_503(api, endpoint, failure, monkeypatch):
    seed(api, review("a"), run("one"), analysis("a"))

    def broken(*args, **kwargs):
        raise RuntimeError("secret database connection and query details")

    if failure == "factory":
        api.service.session_factory = broken
    elif failure == "query":
        session = api.factory()
        monkeypatch.setattr(session, "_execute_internal", broken)
        api.service.session_factory = lambda: session
    else:
        monkeypatch.setattr(service_module, "get_session_factory", broken)
        api.app.dependency_overrides.pop(get_audit_query_service)
    response = call(api, endpoint)
    assert response.status_code == 503
    assert response.json() == {"error": {
        "code": "AUDIT_UNAVAILABLE", "message": "The audit database is unavailable.", "request_id": "v2-audit-test",
    }}
    assert "secret" not in response.text and "details" not in response.text


def test_default_service_dependency_and_clock(api, monkeypatch):
    seed(api, review("a"))
    monkeypatch.setattr(service_module, "get_session_factory", lambda: api.factory)
    api.app.dependency_overrides.pop(get_audit_query_service)
    before = datetime.now(timezone.utc)
    response = summary(api, place_id="p")
    after = datetime.now(timezone.utc)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["reviews"]["stored_count"] == 1
    assert data["as_of"].endswith("Z")
    assert before <= datetime.fromisoformat(data["as_of"].replace("Z", "+00:00")) <= after


def test_openapi_contract_and_documented_analysis_rule(api):
    schema = api.app.openapi()
    for path, method in ((SUMMARY_URL, "get"), (RECONCILE_URL, "post")):
        operation = schema["paths"][path][method]
        assert "422" not in operation["responses"]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert set(operation["responses"]) == {"200", "400", "401", "503"}
    for name in ("ReviewStats", "PlaceFreshness"):
        description = schema["components"]["schemas"][name]["properties"]["unanalyzed_count"]["description"]
        assert "Only status analyzed or rating_fallback" in description
    request = schema["components"]["schemas"]["ReconcileRequest"]
    assert request["additionalProperties"] is False
    assert request["properties"]["review_hashes"]["maxItems"] == 10000
