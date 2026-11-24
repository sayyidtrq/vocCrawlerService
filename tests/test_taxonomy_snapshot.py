from __future__ import annotations

import copy

from sqlalchemy import func, select

from app.db.models import Company, TaxonomySnapshot
from app.services.taxonomy_service import (
    DEFAULT_TAG_THRESHOLD,
    LEGACY_CATEGORIES,
    TAG_SENTIMENTS,
    Taxonomy,
    company_aliases,
    load_taxonomies,
    merge_issue_counts,
    merge_tag_sentiments,
    upsert_snapshots,
    validate_body,
)


def _count(session_factory):
    with session_factory() as session:
        return session.scalar(select(func.count(TaxonomySnapshot.id)))


def test_upsert_is_idempotent(tx_session_factory, tx_company_id, tx_fixture):
    for _ in range(2):
        with tx_session_factory() as session:
            assert upsert_snapshots(session, tx_company_id, tx_fixture["taxonomies"]) == 2
            session.commit()
    assert _count(tx_session_factory) == 2


def test_tagging_change_replaces_the_body_under_the_same_version(
    tx_session_factory, tx_company_id, tx_fixture, tx_tagged
):
    key, body = next(iter(tx_fixture["taxonomies"].items()))
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, {key: body})
        upsert_snapshots(session, tx_company_id, {key: tx_tagged(body)})
        session.commit()
    with tx_session_factory() as session:
        stored = load_taxonomies(session, tx_company_id, [key])[key]
    assert stored.tagging_enabled and stored.version == body["version"]


def test_invalid_snapshots_are_skipped_not_fatal(tx_session_factory, tx_company_id, tx_fixture, tx_spbu):
    broken = copy.deepcopy(tx_spbu)
    broken["aspects"] = [a for a in broken["aspects"] if a["slug"] != "lainnya"]
    duplicate = copy.deepcopy(tx_spbu)
    duplicate["aspects"].append(dict(duplicate["aspects"][0]))
    taxonomies = {**tx_fixture["taxonomies"], "spbu:bad1": broken, "spbu:bad2": duplicate, "x:y": "nope", "z:w": {}}
    with tx_session_factory() as session:
        assert upsert_snapshots(session, tx_company_id, taxonomies) == 2
        session.commit()
    assert _count(tx_session_factory) == 2
    with tx_session_factory() as session:
        assert upsert_snapshots(session, tx_company_id, None) == 0
        assert upsert_snapshots(session, tx_company_id, ["not", "a", "map"]) == 0


def test_snapshots_are_company_scoped(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        other = Company(name="Other", ai_enable_flag=True)
        session.add(other)
        session.commit()
        other_id = other.id
        upsert_snapshots(session, tx_company_id, tx_fixture["taxonomies"])
        session.commit()
    keys = list(tx_fixture["taxonomies"])
    with tx_session_factory() as session:
        assert set(load_taxonomies(session, tx_company_id, keys)) == set(keys)
        assert load_taxonomies(session, other_id, keys) == {}
        assert load_taxonomies(session, tx_company_id, [None, ""]) == {}


def test_validate_body_stamps_key_and_version(tx_spbu):
    body = validate_body("spbu:6285c2fa", {**tx_spbu, "key": "ignored", "version": ""})
    assert body["key"] == "spbu:6285c2fa" and body["version"] == "6285c2fa"


def test_the_legacy_snapshot_is_built_in():
    legacy = Taxonomy.legacy_taxonomy()
    assert legacy.legacy and legacy.slugs == list(LEGACY_CATEGORIES)
    assert (legacy.fallback, legacy.praise) == ("other", "general_praise")
    # legacy vocabulary: an unknown slug still falls back to `other`, flagged as corrected
    assert legacy.category("waiting_time") == ("waiting_time", False)
    assert legacy.category("takaran_bbm") == ("other", True)


def test_category_resolves_aliases_and_flags_replacements(tx_spbu):
    taxonomy = Taxonomy(tx_spbu)
    assert taxonomy.category("takaran_bbm") == ("takaran_bbm", False)
    assert taxonomy.category("Waiting-Time") == ("waktu_tunggu", False)  # legacy alias, not a correction
    assert taxonomy.category("pelayanan_dokter") == ("lainnya", True)  # another industry's slug
    assert taxonomy.category("") == ("lainnya", True)
    assert taxonomy.category(None) == ("lainnya", True)


def test_risk_flags_follow_the_pack(tx_spbu, tx_kesehatan):
    spbu = Taxonomy(tx_spbu)
    flags = spbu.flags({"risiko_kebakaran": True, "kecurangan_bbm": "true", "risiko_viral": 0, "asing": True})
    assert flags == {"risiko_viral": False, "kecurangan_bbm": True, "risiko_kebakaran": True}
    assert spbu.is_safety(flags) and not spbu.is_viral(flags)
    assert spbu.flags("bukan objek") == {"risiko_viral": False, "kecurangan_bbm": False, "risiko_kebakaran": False}
    # only a critical flag is a safety issue: a high flag alone is not
    assert not spbu.is_safety({"kecurangan_bbm": True, "risiko_kebakaran": False})
    assert Taxonomy(tx_kesehatan).is_viral({"risiko_viral": True})


def test_threshold_prefers_pack_value_then_min_confidence_then_default(tx_spbu, tx_tagged):
    assert Taxonomy(tx_spbu).threshold("takaran_bbm") == DEFAULT_TAG_THRESHOLD
    tagged = tx_tagged(tx_spbu, thresholds={"takaran_bbm": 0.7})
    assert Taxonomy(tagged).threshold("takaran_bbm") == 0.7
    assert Taxonomy({**tagged, "min_confidence": 0.6}).threshold("kualitas_bbm") == 0.6


def test_pick_tags_keeps_passing_aspects_most_likely_first_capped(tx_spbu, tx_tagged):
    taxonomy = Taxonomy(tx_tagged(tx_spbu, max_tags=2))
    picked = taxonomy.pick_tags(
        {"waktu_tunggu": 0.91, "takaran_bbm": 0.97, "kebersihan": 0.4, "tidak_ada": 0.99, "parkir": 0.6}
    )
    assert [tag["slug"] for tag in picked] == ["takaran_bbm", "waktu_tunggu"]


def test_finalize_tags_rules(tx_spbu, tx_tagged):
    taxonomy = Taxonomy(tx_tagged(tx_spbu, max_tags=3))

    # nothing passed: lainnya, or pujian_umum for a positive review; the tag takes the review's sentiment
    assert taxonomy.finalize_tags([], "lainnya", "negative") == [{"slug": "lainnya", "p": None, "sentiment": "negative"}]
    assert taxonomy.finalize_tags([], "pujian_umum", "positive") == [{"slug": "pujian_umum", "p": None, "sentiment": "positive"}]

    # the primary category is always present; unknown slugs and duplicates are dropped
    tags = taxonomy.finalize_tags(
        [{"slug": "waktu_tunggu", "p": 0.9}, {"slug": "waiting_time", "p": 0.95}, {"slug": "nonsense", "p": 1}],
        "takaran_bbm",
        "negative",
    )
    assert {t["slug"] for t in tags} == {"waktu_tunggu", "takaran_bbm"}
    assert [t for t in tags if t["slug"] == "waktu_tunggu"][0]["p"] == 0.95

    # lainnya is not added next to real tags
    only_fallback = taxonomy.finalize_tags([{"slug": "parkir", "p": 0.8}], "lainnya", "negative")
    assert [t["slug"] for t in only_fallback] == ["parkir"]

    # the cap never pushes the primary category out
    crowded = [{"slug": s, "p": 0.9 - i / 100} for i, s in enumerate(["parkir", "kebersihan", "fasilitas", "waktu_tunggu"])]
    capped = taxonomy.finalize_tags(crowded, "takaran_bbm", "negative")
    assert len(capped) == 3 and "takaran_bbm" in {t["slug"] for t in capped}


def test_lainnya_only_stands_alone(tx_spbu, tx_tagged):
    taxonomy = Taxonomy(tx_tagged(tx_spbu))

    # a model that lists lainnya next to real aspects does not get it kept
    mixed = taxonomy.finalize_tags([{"slug": "lainnya", "p": 0.9}, {"slug": "parkir", "p": 0.8}], "lainnya", "negative")
    assert [t["slug"] for t in mixed] == ["parkir"]
    assert [t["slug"] for t in taxonomy.finalize_tags([{"slug": "lainnya", "p": 0.9}], "lainnya", "negative")] == ["lainnya"]

    # the primary-category helper follows the same rule
    assert taxonomy.add_primary([], "lainnya", 0.3) == [{"slug": "lainnya", "p": 0.3}]
    parkir = [{"slug": "parkir", "p": 0.8}]
    assert taxonomy.add_primary(parkir, "lainnya", 0.3) == parkir
    assert taxonomy.add_primary(parkir, "parkir", 0.3) == parkir
    assert taxonomy.add_primary(parkir, "takaran_bbm", 0.3)[-1] == {"slug": "takaran_bbm", "p": 0.3}


def test_every_tag_gets_a_sentiment(tx_spbu, tx_tagged):
    taxonomy = Taxonomy(tx_tagged(tx_spbu, max_tags=6))
    tags = taxonomy.finalize_tags(
        [
            {"slug": "waktu_tunggu", "p": 0.9, "sentiment": "Negative"},  # case is normalised
            {"slug": "kebersihan", "p": 0.8, "sentiment": "positive"},
            {"slug": "parkir", "p": 0.7},  # the engine gave none
            {"slug": "fasilitas", "p": 0.6, "sentiment": "angry"},  # not a sentiment
            "layanan_pelanggan",  # a bare slug
        ],
        "takaran_bbm",
        "mixed",
    )
    by_slug = {t["slug"]: t["sentiment"] for t in tags}
    assert by_slug["waktu_tunggu"] == "negative" and by_slug["kebersihan"] == "positive"
    # missing or invalid: the review's own sentiment
    assert by_slug["parkir"] == by_slug["fasilitas"] == by_slug["layanan_pelanggan"] == by_slug["takaran_bbm"] == "mixed"
    assert all(t["sentiment"] in TAG_SENTIMENTS for t in tags)
    # a review-level 'unknown' is not a tag sentiment
    assert {t["sentiment"] for t in taxonomy.finalize_tags([], "lainnya", "unknown")} == {"neutral"}


def test_a_duplicate_tag_that_disagrees_with_itself_is_mixed(tx_spbu, tx_tagged):
    taxonomy = Taxonomy(tx_tagged(tx_spbu))
    tags = taxonomy.clean_tags(
        [{"slug": "waktu_tunggu", "p": 0.9, "sentiment": "positive"}, {"slug": "waiting_time", "p": 0.8, "sentiment": "negative"}]
    )
    assert tags == [{"slug": "waktu_tunggu", "p": 0.9, "sentiment": "mixed"}]
    assert taxonomy.clean_tags([{"slug": "parkir", "sentiment": "negative"}, {"slug": "parkir", "p": 0.4}]) == [
        {"slug": "parkir", "p": 0.4, "sentiment": "negative"}
    ]


def test_merge_tag_sentiments():
    assert merge_tag_sentiments([]) is None
    assert merge_tag_sentiments(["", "angry"]) is None
    assert merge_tag_sentiments(["negative", "negative"]) == "negative"
    assert merge_tag_sentiments(["positive", "negative"]) == "mixed"
    assert merge_tag_sentiments(["mixed", "positive"]) == "mixed"
    assert merge_tag_sentiments(["neutral", "positive"]) == "positive"
    assert merge_tag_sentiments(["neutral", "negative"]) == "negative"
    assert merge_tag_sentiments(["Neutral"]) == "neutral"


def test_company_aliases_and_issue_count_merge(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, tx_fixture["taxonomies"])
        session.commit()
    with tx_session_factory() as session:
        aliases = company_aliases(session, tx_company_id)
    assert aliases["doctor_service"] == "pelayanan_dokter"

    merged = merge_issue_counts(
        [("doctor_service", 2), ("pelayanan_dokter", 1), ("waiting_time", 1), (None, 1)], aliases
    )
    assert merged[0] == ("pelayanan_dokter", 3)
    assert dict(merged)["waktu_tunggu"] == 1
    assert len(merge_issue_counts([(f"slug_{i}", 1) for i in range(9)], {}, limit=5)) == 5
