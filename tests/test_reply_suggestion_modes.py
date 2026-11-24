from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models import Company, Location, Review
from app.services import reply_suggestion_service as service_module
from app.services.reply_suggestion_service import ReplySuggestionService
from app.services.taxonomy_service import upsert_snapshots
from apps.api.app_api.routers.integration_analysis import get_integration_analysis_session_factory
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal
from apps.api.main import create_app

PRESETS = [
    {"id": "mohon_maaf_waktu_tunggu", "when_to_use": "Keluhan antrean"},
    {"id": "mohon_maaf_umum", "when_to_use": "Keluhan umum"},
]
KEY = "kesehatan:0e20266e"


class FakeJev:
    model_name = "jev-latest"

    def __init__(self, **answer):
        self.calls = []
        self.answer = {
            "preset_id": "mohon_maaf_waktu_tunggu",
            "confidence": 0.88,
            "language": "id",
            "risk_flags": {},
            "usage": {"prompt_tokens": 380, "completion_tokens": 32, "total_tokens": 412},
            **answer,
        }

    def suggest_reply(self, text, presets, risk_flags):
        self.calls.append({"text": text, "presets": presets, "risk_flags": [f["slug"] for f in risk_flags]})
        return self.answer


@pytest.fixture()
def seeded(tx_session_factory, tx_fixture):
    with tx_session_factory() as session:
        company = Company(name="T", ai_enable_flag=True)
        other = Company(name="Other", ai_enable_flag=True)
        session.add_all([company, other])
        session.flush()
        upsert_snapshots(session, company.id, tx_fixture["taxonomies"])
        reviews = {}
        for name, owner, text in (("text", company, "Antre lama sekali"), ("empty", company, ""), ("theirs", other, "Bagus")):
            location = Location(
                company_id=owner.id, hospital_name="Org", branch_name=f"C-{name}", source="onebox", external_place_id=f"p-{name}"
            )
            session.add(location)
            session.flush()
            review = Review(
                company_id=owner.id, location_id=location.id, source="google_maps", review_hash=f"h-{name}",
                review_text=text, rating=2,
            )
            session.add(review)
            session.flush()
            reviews[name] = review.id
        session.commit()
        return {"company_id": company.id, "reviews": reviews}


def suggest(factory, seeded, jev, review="text", **kwargs):
    return ReplySuggestionService(
        company_id=seeded["company_id"], session_factory=factory, client=jev
    ).suggest(seeded["reviews"][review], kwargs.pop("presets", PRESETS), kwargs.pop("key", KEY), **kwargs)


def test_a_confident_offered_preset_is_returned(tx_session_factory, seeded):
    jev = FakeJev(risk_flags={"risiko_viral": False})
    out = suggest(tx_session_factory, seeded, jev)

    assert out["mode"] == "preset" and out["preset_id"] == "mohon_maaf_waktu_tunggu"
    assert (out["confidence"], out["language"], out["tokens_used"], out["model"]) == (0.88, "id", 412, "jev-latest")
    assert out["risk_flags"] == {"risiko_viral": False, "keselamatan_pasien": False}
    # one call; Jev sees the review text, the offered presets and the pack's flags
    assert len(jev.calls) == 1 and jev.calls[0]["text"] == "Antre lama sekali"
    assert [p["id"] for p in jev.calls[0]["presets"]] == [p["id"] for p in PRESETS]
    assert jev.calls[0]["risk_flags"] == ["risiko_viral", "keselamatan_pasien"]


def test_a_critical_flag_escalates_even_when_a_preset_matched(tx_session_factory, seeded):
    out = suggest(tx_session_factory, seeded, FakeJev(risk_flags={"keselamatan_pasien": True}, confidence=0.99))

    assert out["mode"] == "escalate" and "preset_id" not in out
    assert out["risk_flags"]["keselamatan_pasien"] is True and out["tokens_used"] == 412


def test_a_high_flag_alone_keeps_the_preset_path(tx_session_factory, seeded):
    out = suggest(tx_session_factory, seeded, FakeJev(risk_flags={"risiko_viral": True}))

    assert out["mode"] == "preset" and out["risk_flags"]["risiko_viral"] is True


def test_below_the_threshold_is_none_not_a_guess(tx_session_factory, seeded):
    low = suggest(tx_session_factory, seeded, FakeJev(confidence=0.6))
    assert (low["mode"], low["confidence"]) == ("none", 0.6)

    # the threshold is the caller's to tune, no deploy needed
    assert suggest(tx_session_factory, seeded, FakeJev(confidence=0.6), threshold=0.5)["mode"] == "preset"
    assert suggest(tx_session_factory, seeded, FakeJev(confidence=0.88), threshold=0.9)["mode"] == "none"


def test_an_id_that_was_never_offered_is_none(tx_session_factory, seeded):
    out = suggest(tx_session_factory, seeded, FakeJev(preset_id="privasi_pasien_hubungi_kami", confidence=0.99))
    assert out["mode"] == "none"


def test_without_the_taxonomy_the_safety_gate_cannot_run_so_nothing_is_offered(tx_session_factory, seeded):
    jev = FakeJev()
    for key in (None, "kesehatan:unknown"):
        out = suggest(tx_session_factory, seeded, jev, key=key)
        assert (out["mode"], out["reason"], out["tokens_used"]) == ("none", "taxonomy_unavailable", 0)
    assert jev.calls == []  # no model call, no tokens spent


def test_an_empty_review_or_empty_offer_costs_no_model_call(tx_session_factory, seeded):
    jev = FakeJev()
    assert suggest(tx_session_factory, seeded, jev, review="empty")["reason"] == "no_text"
    assert suggest(tx_session_factory, seeded, jev, presets=[])["reason"] == "no_presets"
    assert jev.calls == []


def test_another_tenants_review_is_not_found(tx_session_factory, seeded):
    with pytest.raises(ValueError):
        suggest(tx_session_factory, seeded, FakeJev(), review="theirs")


# ------------------------------------------------------------------ route --------------------------------

def make_client(factory, company_id, monkeypatch, jev=None, scopes=("analysis:write",)):
    monkeypatch.setattr(service_module, "create_analysis_client", lambda settings, provider=None: jev or FakeJev())
    app = create_app()
    app.dependency_overrides[get_integration_analysis_session_factory] = lambda: factory
    app.dependency_overrides[require_service_principal] = lambda: ServicePrincipal(
        client_id=company_id, key_id="k", company_id=company_id, scopes=frozenset(scopes)
    )
    return TestClient(app)


def body(**updates):
    return {"taxonomy_key": KEY, "presets": PRESETS, "thresholds": {"preset": 0.75}, "generated": {"allowed": False}, **updates}


def url(seeded, name="text"):
    return f"/api/integration/v1/reviews/{seeded['reviews'][name]}/reply-suggestion"


def test_route_returns_the_preset_envelope(tx_session_factory, seeded, monkeypatch):
    client = make_client(tx_session_factory, seeded["company_id"], monkeypatch)
    response = client.post(url(seeded), json=body())

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["mode"] == "preset" and data["preset_id"] == "mohon_maaf_waktu_tunggu" and data["tokens_used"] == 412
    assert response.json()["meta"]["api_version"] == "v1"


def test_route_needs_the_analysis_scope(tx_session_factory, seeded, monkeypatch):
    client = make_client(tx_session_factory, seeded["company_id"], monkeypatch, scopes=("reviews:read",))
    response = client.post(url(seeded), json=body())

    assert response.status_code == 403 and response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_route_requires_ai_to_be_enabled_for_the_tenant(tx_session_factory, seeded, monkeypatch):
    with tx_session_factory() as session:
        session.get(Company, seeded["company_id"]).ai_enable_flag = False
        session.commit()
    response = make_client(tx_session_factory, seeded["company_id"], monkeypatch).post(url(seeded), json=body())

    assert response.status_code == 403 and response.json()["error"]["code"] == "AI_NOT_ENABLED"


@pytest.mark.parametrize(
    "payload",
    [
        body(presets=[{"id": "Bad Id", "when_to_use": "x"}]),
        body(presets=[{"id": "ok_id", "when_to_use": ""}]),
        body(thresholds={"preset": 1.5}),
        {"taxonomy_key": KEY},
    ],
)
def test_route_rejects_malformed_requests_with_400(tx_session_factory, seeded, monkeypatch, payload):
    response = make_client(tx_session_factory, seeded["company_id"], monkeypatch).post(url(seeded), json=payload)

    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_route_hides_other_tenants_reviews(tx_session_factory, seeded, monkeypatch):
    response = make_client(tx_session_factory, seeded["company_id"], monkeypatch).post(url(seeded, "theirs"), json=body())

    assert response.status_code == 404 and response.json()["error"]["code"] == "REVIEW_NOT_FOUND"


def test_route_turns_a_provider_failure_into_502_without_leaking_it(tx_session_factory, seeded, monkeypatch):
    class Broken(FakeJev):
        def suggest_reply(self, *args):
            raise RuntimeError("secret provider detail")

    response = make_client(tx_session_factory, seeded["company_id"], monkeypatch, jev=Broken()).post(url(seeded), json=body())

    assert response.status_code == 502 and response.json()["error"]["code"] == "SUGGESTION_FAILED"
    assert "secret" not in response.text
