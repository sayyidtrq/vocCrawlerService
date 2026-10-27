"""Stateless AI contracts use fake providers and an audit-only SQLite database."""

import copy
import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.crawler_auth as crawler_auth
from app.config import Settings
from app.db.audit_models import AuditAnalysis
from app.db.base import Base
from app.services import stateless_ai_service as service_module
from app.services.analysis_service import AnalysisService, RATING_FALLBACK_MODEL
from app.services.integration_review_service import IntegrationRequestError
from app.services.stateless_ai_service import StatelessAiService
from app.services.taxonomy_service import Taxonomy, validate_body
from apps.api.app_api.routers.v2_ai import get_stateless_ai_service
from apps.api.app_api.v2_common import V2_API_VERSION
from apps.api.main import create_app

ANALYSIS_URL = "/api/integration/v2/analysis"
REPLY_URL = "/api/integration/v2/reply-suggestion"
HEADERS = {"Authorization": "Bearer shared-secret", "X-Request-ID": "v2-ai-test"}
TAXONOMY = {
    "key": "health:v1", "version": "v1",
    "aspects": [{"slug": slug} for slug in ("lainnya", "pujian_umum", "antrean")],
    "risk_flags": [
        {"slug": "viral", "severity": "high", "legacy_field": "is_potential_viral"},
        {"slug": "safety", "severity": "critical"},
    ],
}
PRESETS = [{"id": "apology", "when_to_use": "A long wait"}]
RAW_MARKER = "private-provider-output"


class FakeAnalysisClient:
    model_name = "fake-model"

    def __init__(self, factory):
        self.factory = factory
        self.last_usage = {}
        self.calls = []
        self.owner = threading.get_ident()

    def analyze_review(self, review):
        assert threading.get_ident() == self.owner
        if self.factory.barrier is not None and not self.calls:
            self.factory.barrier.wait(timeout=5)
        self.calls.append(copy.deepcopy(review))
        with self.factory.lock:
            self.factory.analysis_calls.append(copy.deepcopy(review))
            failures = self.factory.failures.get(review["id"], 0)
            self.factory.failures[review["id"]] = failures - 1
        if failures > 0:
            raise RuntimeError("secret provider key and review content")
        number = int(review["id"].removeprefix("r")) + 1
        self.last_usage = {"prompt_tokens": number, "completion_tokens": number * 2, "total_tokens": number * 3}
        return {
            "sentiment": "negative", "sentiment_score": 0.9,
            "issue_category": "antrean" if "taxonomy" in review else "waiting_time",
            "urgency": "high", "summary": "A long wait.", "recommended_action": "Check the queue.",
            "keywords": ["queue"], "raw_provider_output": RAW_MARKER,
            **self.factory.analysis_answer,
        }

    def suggest_reply(self, text, presets, risk_flags):
        self.factory.reply_calls.append((text, copy.deepcopy(presets), copy.deepcopy(risk_flags)))
        if self.factory.reply_error:
            raise RuntimeError("secret suggestion provider detail")
        self.last_usage = {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}
        return {
            "preset_id": "apology", "confidence": 0.88, "language": "en", "risk_flags": {},
            "usage": dict(self.last_usage), "raw_provider_output": RAW_MARKER,
            **self.factory.reply_answer,
        }


class FakeClientFactory:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []
        self.calls = []
        self.analysis_calls = []
        self.reply_calls = []
        self.failures = {}
        self.analysis_answer = {}
        self.reply_answer = {}
        self.reply_error = False
        self.error = False
        self.barrier = None

    def __call__(self, settings, provider):
        if self.error:
            raise RuntimeError("secret missing key")
        client = FakeAnalysisClient(self)
        with self.lock:
            self.calls.append((settings, provider))
            self.clients.append(client)
        return client


@pytest.fixture()
def api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:", crawler_api_token="shared-secret",
        analysis_provider="absa", analysis_llm_max_retries=2,
        analysis_llm_retry_backoff_seconds=0, analysis_llm_concurrency=1,
    )
    clients = FakeClientFactory()
    service = StatelessAiService(settings, client_factory=clients, session_factory=factory)
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[get_stateless_ai_service] = lambda: service
    with TestClient(app) as client:
        yield SimpleNamespace(
            app=app, client=client, service=service, clients=clients,
            factory=factory, settings=settings, engine=engine,
        )
    engine.dispose()


def review(index=0, **updates):
    return {"id": f"r{index}", "review_hash": f"hash-{index}", "rating": 2, "text": f"Input review text {index}", **updates}


def analysis_body(**updates):
    return {"reviews": [review()], **updates}


def reply_body(**updates):
    return {"review_hash": "hash-reply", "text": "Input reply review text", "taxonomy": copy.deepcopy(TAXONOMY), "presets": PRESETS, **updates}


def post(api, url=ANALYSIS_URL, **updates):
    body = analysis_body(**updates) if url == ANALYSIS_URL else reply_body(**updates)
    return api.client.post(url, headers=HEADERS, json=body)


def audit_rows(api):
    with api.factory() as session:
        return list(session.scalars(select(AuditAnalysis).order_by(AuditAnalysis.id)))


@pytest.mark.parametrize("url", [ANALYSIS_URL, REPLY_URL])
@pytest.mark.parametrize("authorization,expected", [
    (None, 401), ("Basic shared-secret", 401), ("Bearer wrong", 401), ("Bearer shared-secret", 200),
])
def test_auth_and_response_without_database(api, url, authorization, expected, caplog):
    calls = []

    def broken_factory():
        calls.append(True)
        raise RuntimeError("audit unavailable")

    api.service.session_factory = broken_factory
    headers = {"X-Request-ID": "auth-test"}
    if authorization:
        headers["Authorization"] = authorization
    response = api.client.post(url, headers=headers, json=analysis_body() if url == ANALYSIS_URL else reply_body())
    assert response.status_code == expected, response.text
    assert len(calls) == (1 if expected == 200 else 0)
    if expected == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {"error": {"code": "INVALID_SERVICE_TOKEN", "message": "Invalid service token.", "request_id": "auth-test"}}
        assert not api.clients.calls
    else:
        assert response.json()["data"]
        assert response.json()["meta"] == {"api_version": V2_API_VERSION, "request_id": "auth-test"}
        assert "V2 AI audit write failed" in caplog.text


@pytest.mark.parametrize("url", [ANALYSIS_URL, REPLY_URL])
def test_auth_unconfigured(api, url, monkeypatch):
    monkeypatch.setattr(crawler_auth, "get_settings", lambda: api.settings.model_copy(update={"crawler_api_token": None}))
    response = post(api, url)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "V2_NOT_CONFIGURED"
    assert not api.clients.calls


@pytest.mark.parametrize("updates", [
    {"reviews": []}, {"reviews": [review(i) for i in range(51)]},
    {"reviews": [review(), review()]},
    *({"reviews": [review(rating=value)]} for value in (0, 6, True, 1.5, "2")),
    {"reviews": [review(text="x" * 10001)]},
    {"reviews": [review(id="")]}, {"reviews": [review(id="x" * 65)]},
    {"reviews": [review(review_hash="x" * 256)]},
    {"reviews": [review(reviewer_name="x" * 256)]}, {"reviews": [review(unknown=True)]},
    {"provider": "unknown"}, {"unknown": True}, {"site_id": -1}, {"site_id": True},
    {"taxonomy_key": ""}, {"taxonomy_key": "x" * 81}, {"taxonomy": []},
])
def test_analysis_validation(api, updates):
    response = post(api, **updates)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert not api.clients.calls and audit_rows(api) == []


@pytest.mark.parametrize("taxonomy", [
    {}, {"aspects": []}, {"aspects": [{"slug": "only_one"}]},
    {**TAXONOMY, "aspects": [*TAXONOMY["aspects"], {"slug": "lainnya"}]},
    {**TAXONOMY, "aliases": 3}, {**TAXONOMY, "risk_flags": ["bad"]},
    {**TAXONOMY, "key": "x" * 81},
])
def test_analysis_invalid_non_null_taxonomy(api, taxonomy):
    response = post(api, taxonomy=taxonomy)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TAXONOMY"
    assert not api.clients.calls


@pytest.mark.parametrize("with_taxonomy", [False, True])
def test_analysis_model_input_and_clean_output(api, with_taxonomy):
    options = {"taxonomy": TAXONOMY} if with_taxonomy else {}
    response = post(api, reviews=[review(reviewer_name="Private reviewer")], **options)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    expected_review = {
        "id": "r0", "rating": 2, "review_text": review()["text"], "reviewer_name": "Private reviewer",
        "review_time": None, "location_id": None,
    }
    if with_taxonomy:
        expected_review["taxonomy"] = validate_body(TAXONOMY["key"], TAXONOMY)
    assert api.clients.analysis_calls == [expected_review]
    raw = {
        "sentiment": "negative", "sentiment_score": 0.9,
        "issue_category": "antrean" if with_taxonomy else "waiting_time",
        "urgency": "high", "summary": "A long wait.", "recommended_action": "Check the queue.", "keywords": ["queue"],
    }
    cleaned, corrected = AnalysisService._validate_result(raw, Taxonomy(expected_review["taxonomy"]) if with_taxonomy else None)
    assert data["results"] == [{
        "id": "r0", "review_hash": "hash-0", "status": "analyzed", "corrected": corrected, "analysis": cleaned, "error": None,
    }]
    assert data["summary"] == {"analyzed": 1, "rating_fallback": 0, "failed": 0}
    assert data["model"] == "fake-model"
    assert data["usage"] == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    for forbidden in (RAW_MARKER, "raw_provider_output", review()["text"], "Private reviewer", "shared-secret"):
        assert forbidden not in response.text


def test_analysis_cleans_invalid_provider_fields(api):
    api.clients.analysis_answer = {"sentiment": "invalid", "sentiment_score": 5, "issue_category": "invalid", "keywords": "wrong"}
    result = post(api).json()["data"]["results"][0]
    assert result["corrected"] is True
    assert result["analysis"]["sentiment"] == "unknown"
    assert result["analysis"]["sentiment_score"] == 1.0
    assert result["analysis"]["issue_category"] == "other"


@pytest.mark.parametrize("url", [ANALYSIS_URL, REPLY_URL])
def test_taxonomy_key_fills_missing_body_key(api, url):
    taxonomy = {key: value for key, value in TAXONOMY.items() if key != "key"}
    response = post(api, url, taxonomy=taxonomy, taxonomy_key="supplied:v2")
    assert response.status_code == 200
    assert audit_rows(api)[0].taxonomy_key == "supplied:v2"
    if url == ANALYSIS_URL:
        assert api.clients.analysis_calls[0]["taxonomy"]["key"] == "supplied:v2"


def test_body_taxonomy_key_takes_precedence(api):
    assert post(api, taxonomy=TAXONOMY, taxonomy_key="ignored:v2").status_code == 200
    assert api.clients.analysis_calls[0]["taxonomy"]["key"] == TAXONOMY["key"]


@pytest.mark.parametrize("taxonomy", [None, TAXONOMY])
def test_rating_fallback_never_creates_client(api, taxonomy):
    reviews = [review(0, text=""), review(1, text=" \t\n", rating=None)]
    data = post(api, reviews=reviews, taxonomy=taxonomy).json()["data"]
    assert data["summary"] == {"analyzed": 0, "rating_fallback": 2, "failed": 0}
    assert [item["status"] for item in data["results"]] == ["rating_fallback"] * 2
    assert [item["analysis"]["sentiment"] for item in data["results"]] == ["negative", "unknown"]
    assert data["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert data["model"] == RATING_FALLBACK_MODEL
    assert not api.clients.calls


def test_analysis_retry_succeeds_and_honours_retry_limit(api):
    api.service.settings = api.settings.model_copy(update={"analysis_llm_max_retries": 2, "analysis_llm_retry_backoff_seconds": 0})
    api.clients.failures = {"r0": 1}
    result = post(api).json()["data"]["results"][0]
    assert result["status"] == "analyzed"
    assert len(api.clients.analysis_calls) == 2 and len(api.clients.clients) == 1


def test_permanent_failure_is_per_review_and_does_not_reuse_usage(api):
    api.clients.failures = {"r1": 99}
    response = post(api, reviews=[review(i) for i in range(3)])
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"analyzed": 2, "rating_fallback": 0, "failed": 1}
    failed = data["results"][1]
    assert failed["analysis"] is None and failed["corrected"] is False
    assert failed["error"] == {"code": "ANALYSIS_FAILED", "message": "Analysis failed."}
    assert [call["id"] for call in api.clients.analysis_calls] == ["r0", "r1", "r1", "r1", "r2"]
    assert data["usage"] == {"prompt_tokens": 4, "completion_tokens": 8, "total_tokens": 12}
    assert "secret" not in response.text
    assert audit_rows(api)[1].result == failed["error"]


def test_retry_backoff_is_exponential_and_capped(api, monkeypatch):
    api.service.settings = api.settings.model_copy(update={"analysis_llm_max_retries": 4, "analysis_llm_retry_backoff_seconds": 3})
    api.clients.failures = {"r0": 4}
    sleeps = []
    monkeypatch.setattr(service_module.time, "sleep", sleeps.append)
    assert post(api).json()["data"]["results"][0]["status"] == "analyzed"
    assert sleeps == [3.0, 6.0, 8.0, 8.0]


def test_analysis_threads_have_separate_clients_and_ordered_usage(api):
    api.service.settings = api.settings.model_copy(update={"analysis_llm_concurrency": 4})
    api.clients.barrier = threading.Barrier(4)
    data = post(api, reviews=[review(i) for i in range(12)]).json()["data"]
    assert [result["id"] for result in data["results"]] == [f"r{i}" for i in range(12)]
    assert data["summary"] == {"analyzed": 12, "rating_fallback": 0, "failed": 0}
    assert len(api.clients.calls) == 4
    assert len({client.owner for client in api.clients.clients}) == 4
    assert sum(len(client.calls) for client in api.clients.clients) == 12
    assert data["usage"] == {"prompt_tokens": 78, "completion_tokens": 156, "total_tokens": 234}
    rows = audit_rows(api)
    assert [row.total_tokens for row in rows] == [(i + 1) * 3 for i in range(12)]


@pytest.mark.parametrize("provider,expected", [(None, "absa"), ("jev", "jev"), ("openai", "openai"), ("absa", "absa")])
def test_provider_selection(api, provider, expected):
    data = post(api, provider=provider).json()["data"]
    assert data["provider"] == expected
    assert [call[1] for call in api.clients.calls] == [expected]


def test_client_creation_error_is_safe_503(api):
    api.clients.error = True
    response = post(api)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_NOT_CONFIGURED"
    assert "secret" not in response.text


@pytest.mark.parametrize("answer,options,mode", [
    ({}, {}, "preset"),
    ({"risk_flags": {"safety": True}, "confidence": 0.99}, {}, "escalate"),
    ({"risk_flags": {"viral": True}}, {}, "preset"),
    ({"confidence": 0.6}, {}, "none"),
    ({"preset_id": "never_offered", "confidence": 0.99}, {}, "none"),
    ({"confidence": 0.6}, {"thresholds": {"preset": 0.5}}, "preset"),
    ({}, {"thresholds": {"preset": 0.9}}, "none"),
    ({}, {"generated": {"allowed": True}}, "preset"),
])
def test_reply_decisions(api, answer, options, mode):
    api.clients.reply_answer = answer
    response = post(api, REPLY_URL, **options)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["mode"] == mode
    assert (data["tokens_used"], data["model"], data["language"]) == (15, "fake-model", "en")
    assert data["risk_flags"] == {"viral": answer.get("risk_flags", {}).get("viral", False), "safety": answer.get("risk_flags", {}).get("safety", False)}
    if mode == "preset":
        assert data["preset_id"] == "apology"
    else:
        assert "preset_id" not in data
    assert api.clients.reply_calls == [(reply_body()["text"], PRESETS, TAXONOMY["risk_flags"])]
    assert api.clients.calls[0][1] == "jev"
    assert RAW_MARKER not in response.text and reply_body()["text"] not in response.text


@pytest.mark.parametrize("options,reason", [
    ({"taxonomy": {}}, "taxonomy_unavailable"),
    ({"taxonomy": {**TAXONOMY, "risk_flags": ["invalid"]}}, "taxonomy_unavailable"),
    ({"taxonomy": {}, "text": "", "presets": []}, "taxonomy_unavailable"),
    ({"text": ""}, "no_text"), ({"text": " \t\n"}, "no_text"), ({"presets": []}, "no_presets"),
])
def test_reply_early_decisions_without_client(api, options, reason):
    response = post(api, REPLY_URL, **options)
    assert response.status_code == 200
    assert response.json()["data"] == {"mode": "none", "reason": reason, "tokens_used": 0}
    assert not api.clients.calls
    assert audit_rows(api)[0].result == response.json()["data"]


@pytest.mark.parametrize("factory_error", [False, True])
def test_reply_provider_error_is_safe_502_and_audited(api, factory_error):
    api.clients.error = factory_error
    api.clients.reply_error = True
    response = post(api, REPLY_URL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "SUGGESTION_FAILED"
    assert response.json()["error"]["message"] == "The AI provider could not suggest a reply."
    assert "secret" not in response.text
    row = audit_rows(api)[0]
    assert row.kind == "reply_suggestion" and row.status == "failed"
    assert row.result == {"code": "SUGGESTION_FAILED", "message": "The AI provider could not suggest a reply."}


@pytest.mark.parametrize("change", [
    {"taxonomy": None}, {"taxonomy": []}, {"text": "x" * 10001},
    {"presets": PRESETS * 31}, {"presets": [{"id": "Bad Id", "when_to_use": "x"}]},
    {"presets": [{"id": "ok", "when_to_use": ""}]},
    {"presets": [{"id": "ok", "when_to_use": "x", "extra": True}]},
    {"thresholds": {"preset": 1.1}}, {"thresholds": {"preset": -0.1}},
    {"thresholds": {"extra": True}}, {"generated": {"extra": True}},
    {"extra": True}, {"site_id": -1}, {"taxonomy_key": ""},
])
def test_reply_validation(api, change):
    response = post(api, REPLY_URL, **change)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert not api.clients.calls


@pytest.mark.parametrize("field", ["taxonomy", "text", "presets"])
def test_reply_required_fields(api, field):
    payload = reply_body()
    del payload[field]
    response = api.client.post(REPLY_URL, headers=HEADERS, json=payload)
    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_analysis_audit_is_append_only_and_contains_no_inputs(api):
    reviews = [review(0, reviewer_name="Private reviewer"), review(1, text="", rating=5), review(2)]
    api.clients.failures = {"r2": 99}
    data = post(api, site_id=123, taxonomy=TAXONOMY, reviews=reviews).json()["data"]
    rows = audit_rows(api)
    assert len(rows) == 3
    for row, result in zip(rows, data["results"]):
        assert (row.site_id, row.review_ref, row.review_hash) == (123, result["id"], result["review_hash"])
        assert (row.kind, row.status, row.provider, row.taxonomy_key) == ("analysis", result["status"], "absa", TAXONOMY["key"])
        assert row.model == (RATING_FALLBACK_MODEL if result["status"] == "rating_fallback" else "fake-model")
        assert row.result == (result["analysis"] or result["error"])
        assert row.created_at is not None
        serialized = json.dumps(row.result)
        for forbidden in (review()["text"], review(2)["text"], "Private reviewer", RAW_MARKER):
            assert forbidden not in serialized
    assert [(row.prompt_tokens, row.completion_tokens, row.total_tokens) for row in rows] == [(1, 2, 3), (0, 0, 0), (0, 0, 0)]
    assert post(api, site_id=123, reviews=[review()]).status_code == 200
    assert len(audit_rows(api)) == 4


@pytest.mark.parametrize("review_hash", [None, "", "hash-reply", "h" * 255])
def test_reply_audit_linkage_and_usage(api, review_hash):
    data = post(api, REPLY_URL, site_id=42, review_hash=review_hash).json()["data"]
    row = audit_rows(api)[0]
    assert (row.kind, row.provider, row.status) == ("reply_suggestion", "jev", "preset")
    assert row.site_id == 42 and row.model == "fake-model" and row.taxonomy_key == TAXONOMY["key"]
    assert row.review_ref == (review_hash or "")[:64] and row.review_hash == review_hash
    assert row.result == data
    assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (12, 3, 15)
    assert reply_body()["text"] not in json.dumps(row.result)


@pytest.mark.parametrize("url", [ANALYSIS_URL, REPLY_URL])
def test_audit_write_failure_keeps_identical_response(api, url, monkeypatch, caplog):
    expected = post(api, url).json()

    def fail_write(*args):
        raise RuntimeError("audit write rejected")

    monkeypatch.setattr(api.factory.class_, "add_all", fail_write)
    response = post(api, url)
    assert response.status_code == 200 and response.json() == expected
    assert "V2 AI audit write failed: audit write rejected" in caplog.text
    assert all(record.levelname == "WARNING" for record in caplog.records)


def test_one_short_audit_transaction_after_all_model_calls(api):
    transactions, statements = [], []

    def factory():
        assert len(api.clients.analysis_calls) == 3
        transactions.append(True)
        return api.factory()

    api.service.session_factory = factory
    event.listen(api.engine, "before_cursor_execute", lambda conn, cursor, statement, parameters, context, executemany: statements.append(statement))
    assert post(api, reviews=[review(i) for i in range(3)]).status_code == 200
    assert transactions == [True]
    assert statements and all(statement.lstrip().upper().startswith("INSERT INTO AUDIT_ANALYSES") for statement in statements)


@pytest.mark.parametrize("url,method", [(ANALYSIS_URL, "analyze"), (REPLY_URL, "suggest_reply")])
def test_shared_route_retains_retry_after(api, url, method, monkeypatch):
    def limited(params):
        raise IntegrationRequestError(429, "TEST_LIMIT", "Capacity reached.")

    monkeypatch.setattr(api.service, method, limited)
    response = post(api, url)
    assert response.status_code == 429 and response.headers["Retry-After"] == "60"
    assert response.json()["error"] == {"code": "TEST_LIMIT", "message": "Capacity reached.", "request_id": "v2-ai-test"}


def test_openapi_contract(api):
    schema = api.app.openapi()
    for path in (ANALYSIS_URL, REPLY_URL):
        assert "422" not in schema["paths"][path]["post"]["responses"]
        assert schema["paths"][path]["post"]["security"] == [{"HTTPBearer": []}]
    analysis = schema["components"]["schemas"]["AnalysisResult"]["properties"]["analysis"]
    assert analysis["anyOf"][0]["additionalProperties"] is True


def test_ai_audit_migration_matches_metadata_and_downgrades():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261027_0016_stateless_ai_audit.py"
    spec = importlib.util.spec_from_file_location("ai_audit_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20261026_0015"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        assert inspect(connection).get_table_names() == ["audit_analyses"]
        assert inspect(connection).get_foreign_keys("audit_analyses") == []
        assert inspect(connection).get_unique_constraints("audit_analyses") == []
        assert {tuple(index["column_names"]) for index in inspect(connection).get_indexes("audit_analyses")} == {
            ("site_id", "review_hash"), ("site_id", "created_at"),
        }
        scoped_context = MigrationContext.configure(connection, opts={
            "compare_type": True, "compare_server_default": True,
            "include_object": lambda obj, name, type_, reflected, compare_to: type_ != "table" or name == "audit_analyses",
        })
        assert compare_metadata(scoped_context, Base.metadata) == []
        connection.execute(AuditAnalysis.__table__.insert().values(review_ref="r0", kind="analysis", provider="jev", status="analyzed", result={}))
        row = connection.execute(AuditAnalysis.__table__.select()).mappings().one()
        assert row["site_id"] == row["prompt_tokens"] == row["completion_tokens"] == row["total_tokens"] == 0
        assert row["created_at"] is not None
        with Operations.context(context):
            migration.downgrade()
        assert inspect(connection).get_table_names() == []
    engine.dispose()
