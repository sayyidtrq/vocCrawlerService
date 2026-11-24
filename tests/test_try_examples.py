"""The try_* examples must keep naming slugs, flags and presets that OneBox's catalog copy still has."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.taxonomy_service import Taxonomy, validate_body
from scripts.try_examples import REPLY_EXAMPLES, REVIEW_EXAMPLES
from scripts.try_replies import offered_presets
from scripts.try_reviews import DATA, builtin_industries

INDUSTRIES = sorted(builtin_industries())


def snapshot(industry: str) -> dict:
    return builtin_industries()[industry]["snapshot"]


def test_the_catalog_copy_holds_every_industry_with_a_usable_snapshot_and_presets():
    assert DATA.exists() and len(INDUSTRIES) == 8
    for industry in INDUSTRIES:
        body = snapshot(industry)
        assert validate_body(body["key"], body) is not None, industry  # the Crawler would accept it
        assert body["key"] == f"{industry}:{body['version']}" and body["industry"] == industry
        reply = builtin_industries()[industry]["reply"]
        ids = [p["id"] for p in reply["presets"]]
        assert reply["escalation_preset"] in ids and len(ids) == len(set(ids)), industry
        assert all(set(p) == {"id", "when_to_use"} for p in reply["presets"]), industry  # no reply text leaks in
        assert Taxonomy(body).risk_flags, industry


def test_every_industry_has_review_and_reply_examples():
    assert sorted(REVIEW_EXAMPLES) == INDUSTRIES
    assert sorted(REPLY_EXAMPLES) == INDUSTRIES


def test_example_texts_are_unique_because_the_test_doubles_find_them_by_text():
    review_texts = [e.text for examples in REVIEW_EXAMPLES.values() for e in examples]
    reply_texts = [e.text for examples in REPLY_EXAMPLES.values() for e in examples]
    assert len(review_texts) == len(set(review_texts)) and len(reply_texts) == len(set(reply_texts))


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_review_examples_only_name_slugs_and_flags_of_their_industry(industry):
    body = snapshot(industry)
    aspects = {a["slug"] for a in body["aspects"]}
    flags = {f["slug"] for f in body["risk_flags"]}
    for example in REVIEW_EXAMPLES[industry]:
        assert example.tags or example.flags, example.name
        for slugs, sentiment in example.tags:
            assert set(slugs) <= aspects, (industry, example.name, set(slugs) - aspects)
            assert sentiment in {"positive", "negative", "neutral", "mixed"}
        assert set(example.flags) <= flags, (industry, example.name, set(example.flags) - flags)
        assert 1 <= example.rating <= 5


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_each_industry_has_positive_negative_and_mixed_examples_and_exercises_its_own_flags(industry):
    examples = REVIEW_EXAMPLES[industry]
    assert len({e.name for e in examples}) == len(examples)
    assert {"positive", "negative"} <= {s for e in examples for s in e.sentiment}
    assert any("mixed" in e.sentiment for e in examples) or industry == "umum" and len(examples) >= 3
    covered = {flag for e in examples for flag in e.flags}
    # risiko_viral is in every pack; it is exercised by the Umum and Kesehatan examples, the rest by their own industry
    own = {f["slug"] for f in snapshot(industry)["risk_flags"]} - {"risiko_viral"}
    assert own <= covered, (industry, "a flag no example raises", own - covered)


def test_the_shared_viral_flag_is_exercised_somewhere():
    assert any("risiko_viral" in e.flags for examples in REVIEW_EXAMPLES.values() for e in examples)


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_reply_examples_only_expect_offered_presets_and_critical_flags(industry):
    offered = {p["id"] for p in offered_presets(industry)}
    critical = {f["slug"] for f in snapshot(industry)["risk_flags"] if f["severity"] == "critical"}
    escalation = builtin_industries()[industry]["reply"]["escalation_preset"]
    assert escalation not in offered  # the escalation preset is never offered to the model
    for example in REPLY_EXAMPLES[industry]:
        assert example.mode in {"preset", "escalate", "none"}
        if example.mode == "preset":
            assert example.presets and set(example.presets) <= offered, (industry, example.name, set(example.presets) - offered)
        if example.mode == "escalate":
            assert example.flags and set(example.flags) <= critical, (industry, example.name)
    assert any(e.mode == "escalate" for e in REPLY_EXAMPLES[industry]) == bool(critical), industry
    assert any(e.mode == "preset" for e in REPLY_EXAMPLES[industry])


def test_the_catalog_copy_is_plain_utf8_json_with_a_regeneration_note():
    raw = json.loads(Path(DATA).read_text(encoding="utf-8"))
    assert "voc_industries_fixture_check.php --write" in raw["_comment"]
