from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from app.db.models import Location, Review, ReviewAnalysis
from app.services.analysis_service import AnalysisService
from app.services.taxonomy_service import Taxonomy, upsert_snapshots


class RecordingClient:
    """Answers like a taxonomy-aware provider and remembers what it was handed."""

    model_name = "fake-model"

    def __init__(self, reply=None):
        self.seen: list[dict] = []
        self.last_usage = {}
        self.reply = reply or {}

    def analyze_review(self, review):
        self.seen.append(review)
        return {
            "sentiment": "negative",
            "sentiment_score": 0.9,
            "issue_category": "takaran_bbm",
            "urgency": "high",
            "summary": "Takaran kurang.",
            "recommended_action": "Periksa pompa.",
            "keywords": [],
            "is_potential_viral": False,
            "is_safety_issue": False,
            **self.reply,
        }


def seed(session_factory, company_id, fixture, *, keys, texts=("Takaran kurang di pompa 3.",), versions=None):
    """One location per entry of `keys` (None = no taxonomy), each with the given reviews."""
    with session_factory() as session:
        upsert_snapshots(session, company_id, fixture["taxonomies"])
        for index, key in enumerate(keys):
            location = Location(
                company_id=company_id,
                hospital_name="Org",
                branch_name=f"Cabang {index}",
                source="onebox",
                external_place_id=f"place-{index}",
                ai_enabled=True,
                ai_output_schema_version=(versions or {}).get(index),
                taxonomy_key=key,
                taxonomy_version=key.rpartition(":")[2] if key else None,
            )
            session.add(location)
            session.flush()
            for n, text in enumerate(texts):
                session.add(
                    Review(
                        company_id=company_id,
                        location_id=location.id,
                        source="google_maps",
                        review_hash=f"h-{index}-{n}",
                        review_text=text,
                        rating=1,
                    )
                )
        session.commit()


def run(session_factory, settings, company_id, client):
    return AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings, client=client
    ).analyze_pending()


def analyses(session_factory):
    with session_factory() as session:
        return list(session.scalars(select(ReviewAnalysis).order_by(ReviewAnalysis.id)))


def test_the_client_gets_the_location_snapshot_and_the_result_keeps_taxonomy_fields(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=["spbu:6285c2fa"])
    client = RecordingClient({"risk_flags": {"risiko_kebakaran": True, "bogus": True}})

    result = run(tx_session_factory, tx_settings, tx_company_id, client)

    assert result["success"] == 1 and result["quality"] == {"valid": 1, "corrected": 0}
    assert client.seen[0]["taxonomy"]["key"] == "spbu:6285c2fa"
    row = analyses(tx_session_factory)[0]
    assert row.issue_category == "takaran_bbm"
    assert row.taxonomy_version == "6285c2fa"
    assert row.risk_flags == {"risiko_viral": False, "kecurangan_bbm": False, "risiko_kebakaran": True}
    # the legacy booleans are derived from the pack: a critical flag is a safety issue
    assert row.is_safety_issue is True
    assert row.tags is None  # tagging is off for this site


def test_a_location_without_a_taxonomy_behaves_exactly_as_before(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=[None])
    client = RecordingClient({"issue_category": "waiting_time"})

    run(tx_session_factory, tx_settings, tx_company_id, client)

    assert "taxonomy" not in client.seen[0]
    row = analyses(tx_session_factory)[0]
    assert (row.issue_category, row.taxonomy_version, row.risk_flags, row.tags) == ("waiting_time", None, None, None)


def test_a_key_whose_snapshot_was_never_received_stays_legacy(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, caplog
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=["spbu:deadbeef"])
    client = RecordingClient({"issue_category": "waiting_time"})

    with caplog.at_level(logging.WARNING):
        run(tx_session_factory, tx_settings, tx_company_id, client)

    assert "taxonomy" not in client.seen[0]
    assert analyses(tx_session_factory)[0].taxonomy_version is None
    assert "analysis.taxonomy.missing" in caplog.text


def test_an_answer_outside_the_taxonomy_becomes_lainnya_and_is_counted(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=["spbu:6285c2fa"])
    # a slug from another industry: not valid for this location
    client = RecordingClient({"issue_category": "pelayanan_dokter"})

    result = run(tx_session_factory, tx_settings, tx_company_id, client)

    assert result["quality"]["corrected"] == 1
    assert analyses(tx_session_factory)[0].issue_category == "lainnya"


def test_a_legacy_slug_from_the_model_is_accepted_through_the_alias(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=["spbu:6285c2fa"])

    result = run(tx_session_factory, tx_settings, tx_company_id, RecordingClient({"issue_category": "waiting_time"}))

    assert result["quality"]["corrected"] == 0
    assert analyses(tx_session_factory)[0].issue_category == "waktu_tunggu"


def test_tags_are_validated_capped_and_always_include_the_primary(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, tx_tagged
):
    fixture = {"taxonomies": {k: tx_tagged(v, max_tags=2) for k, v in tx_fixture["taxonomies"].items()}}
    seed(tx_session_factory, tx_company_id, fixture, keys=["spbu:6285c2fa"])
    client = RecordingClient(
        {"tags": [{"slug": "waktu_tunggu", "p": 0.9}, "kebersihan", {"slug": "pelayanan_dokter", "p": 1.0}, {"slug": "parkir", "p": 0.8}]}
    )

    run(tx_session_factory, tx_settings, tx_company_id, client)

    tags = analyses(tx_session_factory)[0].tags
    assert len(tags) == 2
    assert "pelayanan_dokter" not in {t["slug"] for t in tags}  # not in this taxonomy
    assert "takaran_bbm" in {t["slug"] for t in tags}  # the primary is never pushed out


def test_a_review_that_mentions_nothing_gets_lainnya_as_its_tag(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, tx_tagged
):
    fixture = {"taxonomies": {k: tx_tagged(v) for k, v in tx_fixture["taxonomies"].items()}}
    seed(tx_session_factory, tx_company_id, fixture, keys=["spbu:6285c2fa"])
    client = RecordingClient({"issue_category": "tidak_dikenal", "tags": []})

    run(tx_session_factory, tx_settings, tx_company_id, client)

    row = analyses(tx_session_factory)[0]
    assert row.tags == [{"slug": "lainnya", "p": None, "sentiment": row.sentiment}]


def test_a_rating_only_review_uses_the_taxonomy_fallback(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, tx_tagged
):
    fixture = {"taxonomies": {k: tx_tagged(v) for k, v in tx_fixture["taxonomies"].items()}}
    seed(tx_session_factory, tx_company_id, fixture, keys=["spbu:6285c2fa"], texts=("",))
    client = RecordingClient()

    result = run(tx_session_factory, tx_settings, tx_company_id, client)

    assert client.seen == [] and result["rating_fallback"] == 1
    row = analyses(tx_session_factory)[0]
    assert (row.issue_category, row.taxonomy_version) == ("lainnya", "6285c2fa")
    assert row.tags == [{"slug": "lainnya", "p": None, "sentiment": row.sentiment}]


def test_every_stored_tag_carries_the_sentiment_about_its_own_aspect(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, tx_tagged
):
    fixture = {"taxonomies": {k: tx_tagged(v, max_tags=5) for k, v in tx_fixture["taxonomies"].items()}}
    seed(tx_session_factory, tx_company_id, fixture, keys=["spbu:6285c2fa"])
    client = RecordingClient(
        {
            "sentiment": "mixed",
            "issue_category": "takaran_bbm",
            "tags": [
                {"slug": "waktu_tunggu", "p": 0.9, "sentiment": "negative"},
                {"slug": "kebersihan", "p": 0.8, "sentiment": "positive"},
                {"slug": "parkir", "p": 0.7},  # the engine gave no sentiment for this one
            ],
        }
    )

    run(tx_session_factory, tx_settings, tx_company_id, client)

    row = analyses(tx_session_factory)[0]
    by_slug = {t["slug"]: t["sentiment"] for t in row.tags}
    assert by_slug["waktu_tunggu"] == "negative" and by_slug["kebersihan"] == "positive"
    assert by_slug["parkir"] == by_slug["takaran_bbm"] == "mixed"  # the review's own sentiment
    assert all(t["sentiment"] in {"positive", "negative", "neutral", "mixed"} for t in row.tags)


def test_two_locations_in_one_run_each_get_their_own_taxonomy(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=["spbu:6285c2fa", "kesehatan:0e20266e", None])
    client = RecordingClient({"issue_category": "kebersihan"})

    run(tx_session_factory, tx_settings, tx_company_id, client)

    keys = sorted(str(r.get("taxonomy", {}).get("key")) for r in client.seen)
    assert keys == ["None", "kesehatan:0e20266e", "spbu:6285c2fa"]
    assert {a.taxonomy_version for a in analyses(tx_session_factory)} == {None, "0e20266e", "6285c2fa"}


@pytest.mark.parametrize("version,warns", [("v2", False), ("v3", False), (None, False), ("v9", True)])
def test_only_unknown_schema_versions_warn(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, caplog, version, warns
):
    seed(tx_session_factory, tx_company_id, tx_fixture, keys=[None], versions={0: version})

    with caplog.at_level(logging.WARNING):
        run(tx_session_factory, tx_settings, tx_company_id, RecordingClient({"issue_category": "waiting_time"}))

    assert ("expects output schema" in caplog.text) is warns


def test_validate_result_without_a_taxonomy_is_the_legacy_behaviour():
    cleaned, corrected = AnalysisService._validate_result({"issue_category": "takaran_bbm", "sentiment": "negative"})
    assert corrected and cleaned["issue_category"] == "other"
    assert "risk_flags" not in cleaned and "taxonomy_version" not in cleaned and "tags" not in cleaned


def test_validate_result_derives_the_legacy_booleans_from_the_flags(tx_spbu, tx_kesehatan):
    cleaned, _ = AnalysisService._validate_result(
        {"issue_category": "lainnya", "sentiment": "negative", "risk_flags": {"risiko_viral": True}}, Taxonomy(tx_kesehatan)
    )
    assert cleaned["is_potential_viral"] is True and cleaned["is_safety_issue"] is False
    cleaned, _ = AnalysisService._validate_result(
        {"issue_category": "lainnya", "sentiment": "negative", "risk_flags": {"keselamatan_pasien": 1}}, Taxonomy(tx_kesehatan)
    )
    assert cleaned["is_safety_issue"] is True
    # missing flags are all false, never an error
    cleaned, _ = AnalysisService._validate_result({"issue_category": "lainnya", "sentiment": "negative"}, Taxonomy(tx_spbu))
    assert set(cleaned["risk_flags"].values()) == {False}
