"""Product decisions use mocked Jev and OpenAI; no database or provider writes."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

import app.integrations.jev_client as module
from app.config import Settings, _EnvSettings
from app.integrations.jev_client import JevAiClient
from app.services.stateless_ai_service import StatelessAiService
from apps.api.app_api.v2_ai_schemas import AnalysisRequest, AnalysisResponse

CATALOG = [{"slug": "product_10", "name": "Clinic", "sub_products": [
    {"slug": "waiting_room", "name": "Waiting Room", "condition": "Complaints about the waiting room"},
    {"slug": "billing", "name": "Billing", "condition": "Incorrect bills"},
]}]
REVIEW = {"id": "r1", "rating": 2, "review_text": "The waiting room is crowded", "product_catalog": CATALOG}
TAXONOMY = {"key": "health:v1", "version": "v1", "aspects": [
    {"slug": "lainnya"}, {"slug": "pujian_umum"}, {"slug": "queue"},
], "risk_flags": []}


def client(monkeypatch, answer="waiting_room", llm='{"match":"billing"}', model="configured-model"):
    settings = Settings(database_url="sqlite:///:memory:", sub_product_llm_model=model, openai_api_key="dummy")
    sdk = Mock()
    sdk.__enter__ = Mock(return_value=sdk)
    sdk.__exit__ = Mock(return_value=False)
    sdk.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=llm))],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
    )
    factory = Mock(return_value=sdk)
    monkeypatch.setattr(module, "OpenAI", factory)
    calls = []

    def jev(request):
        body = json.loads(request.content)
        calls.append(body)
        questions = body["questions"]
        answers = {"sentiment": {"choice": "negative", "confidence": .9},
                   "category": {"choice": "queue", "confidence": .9}}
        if "product" in questions:
            answers = {"product": {"choice": "product_10"}}
        if "sub_product" in questions:
            answers = {"sub_product": {"choice": answer}}
        return httpx.Response(200, json={"answers": answers, "usage": {"input_tokens": 2, "output_tokens": 1}})

    instance = JevAiClient(settings, http_client=httpx.Client(base_url="https://jev.test", transport=httpx.MockTransport(jev)))
    return instance, calls, sdk, factory


@pytest.mark.parametrize("taxonomy", [None, TAXONOMY])
def test_known_jev_choice_never_calls_llm(monkeypatch, taxonomy):
    instance, calls, _, factory = client(monkeypatch)
    review = {**REVIEW, **({"taxonomy": taxonomy} if taxonomy else {})}
    result = instance.analyze_review(review)
    assert result["product"] == "product_10"
    assert result["sub_product"] == "waiting_room"
    assert result["sub_product_source"] == "jev"
    assert result["sub_product_proposal"] is None
    factory.assert_not_called()
    product = next(c["questions"]["product"] for c in calls if "product" in c["questions"])
    sub = next(c["questions"]["sub_product"] for c in calls if "sub_product" in c["questions"])
    assert product["type"] == sub["type"] == "choice"
    assert product["criteria"] == {"product_10": "The review concerns Clinic."}
    assert sub["criteria"]["waiting_room"] == CATALOG[0]["sub_products"][0]["condition"]
    assert list(sub["criteria"])[-1] == "other"


@pytest.mark.parametrize("jev_answer", ["other", "unknown", "", None, 42, {}, []])
def test_other_branch_llm_wins(monkeypatch, jev_answer):
    instance, _, sdk, factory = client(monkeypatch, answer=jev_answer)
    result = instance.analyze_review(REVIEW)
    assert result["sub_product"] == "billing"
    assert result["sub_product_source"] == "llm"
    factory.assert_called_once()
    assert factory.call_args.kwargs["timeout"] == 20.0
    assert factory.call_args.kwargs["max_retries"] == 0
    params = sdk.chat.completions.create.call_args.kwargs
    assert params["model"] == "configured-model"
    data = json.loads(params["messages"][1]["content"])
    assert data == {"review": REVIEW["review_text"], "product": CATALOG[0]}
    assert instance.last_usage["total_tokens"] >= 5


@pytest.mark.parametrize("name, expected", [("  New   Service ", None), ("  wAiTiNg   ROOM ", "waiting_room"), ("BILLING", "billing")])
def test_llm_new_and_duplicate(monkeypatch, name, expected):
    instance, *_ = client(monkeypatch, answer="other", llm=json.dumps({"new": {"name": name, "condition": "When it applies"}}))
    result = instance.analyze_review(REVIEW)
    assert result["sub_product_source"] == "llm"
    assert result["sub_product"] == expected
    assert result["sub_product_proposal"] == (None if expected else {"name": "New Service", "condition": "When it applies"})


@pytest.mark.parametrize("answer", ['bad json', '[]', '{"match":"disabled"}', '{"match":12}',
    '{"new":{"name":"x","condition":""}}', '{"match":"billing","extra":1}',
    '{"new":{"name":3,"condition":"x"}}'])
def test_invalid_llm_falls_back_to_product(monkeypatch, answer):
    instance, *_ = client(monkeypatch, answer="other", llm=answer)
    result = instance.analyze_review(REVIEW)
    assert result["product"] == "product_10"
    assert result["sub_product"] is result["sub_product_source"] is result["sub_product_proposal"] is None


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError()])
def test_llm_exception_is_nonfatal(monkeypatch, failure):
    instance, _, sdk, _ = client(monkeypatch, answer="other")
    sdk.chat.completions.create.side_effect = failure
    result = instance.analyze_review(REVIEW)
    assert result["product"] == "product_10" and result["sub_product"] is None
    assert result["sub_product_proposal"] is None


def test_feature_off_and_missing_catalog(monkeypatch):
    instance, calls, _, factory = client(monkeypatch, answer="other", model="")
    result = instance.analyze_review(REVIEW)
    assert result["product"] == "product_10" and result["sub_product"] is None
    factory.assert_not_called()
    calls.clear()
    result = instance.analyze_review({**REVIEW, "product_catalog": []})
    assert result["product"] is None
    assert all("product" not in c["questions"] for c in calls)


def test_llm_setting_is_read_from_env_and_defaults_off(monkeypatch):
    monkeypatch.delenv("SUB_PRODUCT_LLM_MODEL", raising=False)
    assert _EnvSettings(_env_file=None, database_url="sqlite:///:memory:").sub_product_llm_model == ""
    monkeypatch.setenv("SUB_PRODUCT_LLM_MODEL", "owner-configured-model")
    assert _EnvSettings(_env_file=None, database_url="sqlite:///:memory:").sub_product_llm_model == "owner-configured-model"


@pytest.mark.parametrize("provider", ["openai", "absa"])
def test_other_analysis_engines_still_use_jev_for_product(monkeypatch, provider):
    jev, _, _, factory = client(monkeypatch)
    analysis = SimpleNamespace(model_name="analysis-model", last_usage={}, analyze_review=Mock(return_value={
        "sentiment": "negative", "summary": "Summary", "urgency": "medium", "issue_category": "waiting_time",
        "product": "untrusted_non_jev_product",
    }))
    create = Mock(side_effect=lambda settings, selected: jev if selected == "jev" else analysis)
    service = StatelessAiService(jev.settings, client_factory=create)
    monkeypatch.setattr(service, "_write_audit", Mock())
    data = service.analyze({"provider": provider, "product_catalog": CATALOG, "reviews": [
        {"id": "r1", "text": REVIEW["review_text"], "rating": 2}]})
    result = data["results"][0]
    assert result["status"] == "analyzed"
    assert result["analysis"]["product"] == "product_10"
    assert result["analysis"]["sub_product"] == "waiting_room"
    assert result["analysis"]["sub_product_source"] == "jev"
    assert [call.args[1] for call in create.call_args_list] == [provider, "jev"]
    factory.assert_not_called()


def test_new_name_under_different_product_is_still_proposed(monkeypatch):
    instance, *_ = client(monkeypatch, answer="other", llm='{"new":{"name":"Elsewhere","condition":"New"}}')
    catalog = copy.deepcopy(CATALOG)
    catalog.append({"slug": "product_20", "name": "Other clinic", "sub_products": [
        {"slug": "elsewhere", "name": "Elsewhere", "condition": "Other product only"}]})
    result = instance.analyze_review({**REVIEW, "product_catalog": catalog})
    assert result["product"] == "product_10"
    assert result["sub_product_proposal"] == {"name": "Elsewhere", "condition": "New"}


def test_request_rejects_disabled_rows_other_and_empty_products():
    base = {"reviews": [{"id": "r1", "text": "review"}], "product_catalog": copy.deepcopy(CATALOG)}
    assert AnalysisRequest.model_validate(base).product_catalog[0].slug == "product_10"
    for change in (lambda p: p[0]["sub_products"][0].update(enabled=0),
                   lambda p: p[0]["sub_products"][0].update(slug="other"),
                   lambda p: p[0].update(sub_products=[]),
                   lambda p: p.append(copy.deepcopy(p[0]))):
        bad = copy.deepcopy(base)
        change(bad["product_catalog"])
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate(bad)


@pytest.mark.parametrize("taxonomy", [None, TAXONOMY])
def test_stateless_request_and_clean_response_keep_product_fields(monkeypatch, taxonomy):
    instance, _, _, _ = client(monkeypatch, answer="other", llm='{"new":{"name":"New Service","condition":"New condition"}}')
    service = StatelessAiService(instance.settings, client_factory=lambda *_: instance)
    audit = Mock()
    monkeypatch.setattr(service, "_write_audit", audit)
    request = AnalysisRequest.model_validate({"provider": "jev", "site_id": 169,
        "reviews": [{"id": "r1", "text": REVIEW["review_text"], "rating": 2}],
        "product_catalog": CATALOG, "taxonomy": taxonomy})
    data = service.analyze(request.model_dump())
    result = data["results"][0]
    assert result["status"] == "analyzed"
    assert result["analysis"]["product"] == "product_10"
    assert result["analysis"]["sub_product"] is None
    assert result["analysis"]["sub_product_source"] == "llm"
    assert result["analysis"]["sub_product_proposal"] == {"name": "New Service", "condition": "New condition"}
    assert "jev" not in result["analysis"]
    assert AnalysisResponse.model_validate({"data": data, "meta": {"api_version": "v2", "request_id": "test"}})
