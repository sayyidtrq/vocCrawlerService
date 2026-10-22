from __future__ import annotations

import pytest

from app.services.taxonomy_service import upsert_snapshots
from scripts import try_reviews
from scripts.try_reviews import EXAMPLES, Example, judge

KESEHATAN = "kesehatan:0e20266e"


class FakeModel:
    model_name = "fake-model"

    def __init__(self, answer=None):
        self.answer = answer or perfect
        self.seen: list[dict] = []
        self.last_usage: dict = {}

    def analyze_review(self, review):
        self.seen.append(review)
        self.last_usage = {"total_tokens": 100}
        return self.answer(next((e for e in EXAMPLES if e.text == review["review_text"]), None), review)


def perfect(example, review):
    """The analysis an ideal model gives: what the example expects, nothing else."""
    if example is None:
        return raw("neutral", [])
    return raw(
        example.sentiment[0],
        [{"slug": slugs[0], "p": 0.9, "sentiment": sentiment} for slugs, sentiment in example.tags],
        category=example.tags[0][0][0] if example.tags else "lainnya",
        flags={flag: True for flag in example.flags},
    )


def raw(sentiment, tags, category="lainnya", flags=None):
    return {
        "sentiment": sentiment, "sentiment_score": 0.9, "issue_category": category, "urgency": "low", "summary": "s",
        "recommended_action": "a", "keywords": [], "is_potential_viral": False, "is_safety_issue": False,
        "risk_flags": flags or {}, "tags": tags,
    }


@pytest.fixture()
def stored(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, {KESEHATAN: tx_fixture["taxonomies"][KESEHATAN]})
        session.commit()
    return tx_session_factory


def run(args, *, client=None, factory=None):
    lines: list[str] = []
    code = try_reviews.main(args, client=client, session_factory=factory, out=lines.append)
    return code, "\n".join(lines)


def test_the_examples_only_name_slugs_and_flags_the_kesehatan_pack_has(tx_kesehatan):
    aspects = {a["slug"] for a in tx_kesehatan["aspects"]}
    flags = {f["slug"] for f in tx_kesehatan["risk_flags"]}
    for example in EXAMPLES:
        assert example.tags or example.flags, example.name
        for slugs, sentiment in example.tags:
            assert set(slugs) <= aspects, (example.name, set(slugs) - aspects)
            assert sentiment in {"positive", "negative", "neutral", "mixed"}
        assert set(example.flags) <= flags, example.name


def test_there_are_positive_negative_and_mixed_examples_with_unique_names():
    assert len({e.name for e in EXAMPLES}) == len(EXAMPLES)
    overall = {s for e in EXAMPLES for s in e.sentiment}
    assert {"positive", "negative", "mixed"} <= overall
    assert any(e.none_negative for e in EXAMPLES) and any(e.flags for e in EXAMPLES)


def test_judge_passes_a_correct_analysis_and_names_every_miss():
    example = Example("x", 3, "t", ("mixed",), ((("pelayanan_dokter",), "positive"), (("parkir",), "negative")), flags=("risiko_viral",), none_negative=False)
    good = raw("mixed", [{"slug": "pelayanan_dokter", "sentiment": "positive"}, {"slug": "parkir", "sentiment": "negative"}], flags={"risiko_viral": True})
    assert all(ok for ok, _ in judge(example, good))

    wrong_overall = judge(example, {**good, "sentiment": "positive"})
    assert [msg for ok, msg in wrong_overall if not ok] == ["overall sentiment mixed (got positive)"]

    flipped = {**good, "tags": [{"slug": "pelayanan_dokter", "sentiment": "positive"}, {"slug": "parkir", "sentiment": "positive"}]}
    assert [msg for ok, msg in judge(example, flipped) if not ok] == ["parkir = negative (got parkir=positive)"]

    missing = {**good, "tags": [{"slug": "pelayanan_dokter", "sentiment": "positive"}]}
    (miss,) = [msg for ok, msg in judge(example, missing) if not ok]
    assert "parkir = negative (got: not tagged" in miss and "pelayanan_dokter" in miss

    unflagged = {**good, "risk_flags": {"risiko_viral": False}}
    assert [msg for ok, msg in judge(example, unflagged) if not ok] == ["risk flag risiko_viral raised (it was not)"]


def test_judge_accepts_any_of_the_listed_slugs_and_flags_a_negative_on_a_compliment():
    example = Example("x", 5, "t", ("positive",), ((("pujian_umum", "kualitas_layanan"), "positive"),), none_negative=True)
    assert all(ok for ok, _ in judge(example, raw("positive", [{"slug": "kualitas_layanan", "sentiment": "positive"}])))
    tainted = raw("positive", [{"slug": "pujian_umum", "sentiment": "positive"}, {"slug": "parkir", "sentiment": "negative"}])
    assert [msg for ok, msg in judge(example, tainted) if not ok] == ["no negative tag on a compliment (got parkir)"]
    assert not any(ok for ok, _ in judge(example, {"sentiment": None, "tags": None})[:1])  # a missing analysis never passes


def test_every_example_runs_and_a_perfect_model_passes(stored):
    model = FakeModel()
    code, text = run(["--tagging"], client=model, factory=stored)

    assert code == 0, text
    assert len(model.seen) == len(EXAMPLES)
    assert all(call["taxonomy"]["industry"] == "kesehatan" and call["rating"] is not None for call in model.seen)
    assert "taxonomy kesehatan:0e20266e (industry kesehatan), multi-tag ON" in text
    assert "provider: fake-model" in text
    assert "Dokternya bagus dan sabar menjelaskan, tapi parkirnya penuh" in text  # the review itself is shown
    assert "pelayanan_dokter (0.90) positive | parkir (0.90) negative" in text  # tags with their sentiment
    assert "risk flags: risiko_viral=YES" in text or "keselamatan_pasien=YES" in text
    assert "FAIL" not in text.replace("lone FAIL", "")
    assert f"expectations met across {len(EXAMPLES)} reviews, {100 * len(EXAMPLES)} tokens" in text


def test_a_model_that_gets_a_tag_sentiment_wrong_fails_the_run_and_says_where(stored):
    def parking_praised(example, review):
        answer = perfect(example, review)
        for tag in answer["tags"]:
            if tag["slug"] == "parkir":
                tag["sentiment"] = "positive"
        return answer

    code, text = run(["--tagging"], client=FakeModel(parking_praised), factory=stored)

    assert code == 1
    assert "FAIL  parkir = negative (got parkir=positive)" in text
    assert "expectations met" in text and "FAIL  overall" not in text


def test_a_missing_model_sentiment_falls_back_to_the_review_sentiment_before_judging(stored):
    def no_tag_sentiment(example, review):
        answer = perfect(example, review)
        for tag in answer["tags"]:
            tag.pop("sentiment")
        return answer

    code, text = run(["--only", "pujian singkat", "--tagging"], client=FakeModel(no_tag_sentiment), factory=stored)
    assert code == 0  # AnalysisService gives each tag the review's own sentiment: positive here
    assert "pujian_umum (0.90) positive" in text


def test_only_filters_the_examples_and_list_needs_no_model_or_database(stored):
    model = FakeModel()
    code, text = run(["--only", "CAMPURAN", "--tagging"], client=model, factory=stored)
    assert len(model.seen) == sum("campuran" in e.name.lower() for e in EXAMPLES) == 3 and code == 0

    code, text = run(["--only", "tidak ada contoh begini"], client=FakeModel(), factory=stored)
    assert code == 2 and "No example matches" in text

    code, text = run(["--list"])
    assert code == 0 and all(e.name in text for e in EXAMPLES)


def test_a_free_text_review_is_analysed_without_expectations(stored):
    model = FakeModel(lambda example, review: raw("mixed", [{"slug": "parkir", "p": 0.8, "sentiment": "negative"}]))
    code, text = run(["--text", "Dokter ramah tapi parkir penuh", "--rating", "3", "--tagging"], client=model, factory=stored)

    assert code == 0
    assert [(c["review_text"], c["rating"]) for c in model.seen] == [("Dokter ramah tapi parkir penuh", 3)]
    assert "Your text" in text and "parkir (0.80) negative" in text and "expectations met" not in text


def test_without_a_stored_taxonomy_it_says_what_to_do(tx_session_factory):
    code, text = run(["--text", "x"], client=FakeModel(), factory=tx_session_factory)
    assert code == 2 and "Taksonomi industri aktif" in text and "refresh_worklist" in text


def test_tagging_off_in_onebox_is_stated_and_shows_no_tags(stored):
    code, text = run(["--text", "x"], client=FakeModel(lambda example, review: raw("neutral", [])), factory=stored)
    assert code == 0
    assert "multi-tag OFF (use --tagging to force it on)" in text and "(multi-tag is off for this taxonomy)" in text


def test_key_and_company_pick_the_taxonomy_and_other_industries_get_a_note(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, tx_fixture["taxonomies"])
        session.commit()

    code, text = run(["--key", "spbu:6285c2fa", "--text", "x"], client=FakeModel(lambda e, r: raw("neutral", [])), factory=tx_session_factory)
    assert code == 0 and "taxonomy spbu:6285c2fa (industry spbu)" in text

    code, text = run(["--key", "spbu:6285c2fa"], client=FakeModel(), factory=tx_session_factory)
    assert "the built-in examples are hospital reviews" in text

    code, text = run(["--key", "belum:ada", "--text", "x"], client=FakeModel(), factory=tx_session_factory)
    assert code == 2

    code, text = run(["--company-id", str(tx_company_id + 99), "--text", "x"], client=FakeModel(), factory=tx_session_factory)
    assert code == 2  # an explicit company never falls back to someone else's taxonomy
