from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.integrations import jev_client
from app.integrations.jev_client import JevAiClient


def settings():
    return Settings(database_url="sqlite+pysqlite:///:memory:")


class Recorder:
    """Fake TypeSafe: records every request and answers from a function."""

    def __init__(self, answer):
        self.answer = answer
        self.requests: list[dict] = []

    def client(self):
        def handler(request):
            body = json.loads(request.content)
            self.requests.append(body)
            return httpx.Response(200, json=self.answer(body["questions"]))

        return JevAiClient(
            settings(),
            http_client=httpx.Client(base_url="https://api.typesafe.test", transport=httpx.MockTransport(handler)),
        )


def answers(*, sentiment="negative", category="takaran_bbm", conf=0.9, noul=None, usage=(100, 20), tag_sentiments=None):
    noul = noul or {}
    tag_sentiments = tag_sentiments or {}

    def make(questions):
        out = {
            "sentiment": {"choice": sentiment, "confidence": 0.8},
            "category": {"choice": category, "confidence": conf},
        }
        for key in questions:
            if key.startswith(("flag_", "tag_")):
                out[key] = {"noul": noul.get(key, 0.0)}
            elif key.startswith("sent_") and key[5:] in tag_sentiments:
                out[key] = {"choice": tag_sentiments[key[5:]], "confidence": 0.8}
        return {"answers": {k: v for k, v in out.items() if k in questions}, "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}

    return make


REVIEW = {"review_text": "Takaran kurang dan antre lama.", "rating": 1}


def test_questions_are_built_from_the_snapshot_in_one_request(tx_spbu):
    rec = Recorder(answers())
    result = rec.client().analyze_review({**REVIEW, "taxonomy": tx_spbu})

    assert len(rec.requests) == 1
    questions = rec.requests[0]["questions"]
    assert set(questions["category"]["criteria"]) == {a["slug"] for a in tx_spbu["aspects"]}
    assert "Takaran kurang" in questions["category"]["criteria"]["takaran_bbm"]
    assert {k for k in questions if k.startswith("flag_")} == {
        "flag_risiko_viral", "flag_kecurangan_bbm", "flag_risiko_kebakaran",
    }
    assert questions["flag_risiko_kebakaran"]["type"] == "noul"
    assert not any(k.startswith("tag_") for k in questions)  # tagging is opt-in
    assert "is_safety_issue" not in questions  # the hospital-era question is gone
    assert result["issue_category"] == "takaran_bbm" and "tags" not in result


def test_a_choice_outside_the_list_becomes_lainnya_and_praise_becomes_pujian_umum(tx_spbu):
    taxonomy = {**tx_spbu}
    assert Recorder(answers(category="pelayanan_dokter")).client().analyze_review(
        {**REVIEW, "taxonomy": taxonomy}
    )["issue_category"] == "lainnya"
    assert Recorder(answers(sentiment="positive", category="mystery")).client().analyze_review(
        {**REVIEW, "taxonomy": taxonomy}
    )["issue_category"] == "pujian_umum"


def test_urgency_comes_from_the_flags_severity(tx_spbu):
    def run(noul, rating=3, sentiment="negative"):
        rec = Recorder(answers(sentiment=sentiment, noul=noul))
        return rec.client().analyze_review({"review_text": "x", "rating": rating, "taxonomy": tx_spbu})

    critical = run({"flag_risiko_kebakaran": 0.9})
    assert (critical["urgency"], critical["is_safety_issue"]) == ("critical", True)
    assert critical["risk_flags"]["risiko_kebakaran"] is True

    high = run({"flag_kecurangan_bbm": 0.8})
    assert (high["urgency"], high["is_safety_issue"]) == ("high", False)

    viral = run({"flag_risiko_viral": 0.8})
    assert (viral["urgency"], viral["is_potential_viral"]) == ("high", True)

    assert run({})["urgency"] == "medium"
    assert run({}, rating=1)["urgency"] == "high"  # one star + negative
    assert run({}, sentiment="positive", rating=5)["urgency"] == "low"


def test_tag_questions_are_asked_only_when_tagging_is_on(tx_spbu, tx_tagged):
    tagged = tx_tagged(tx_spbu, max_tags=3, thresholds={"takaran_bbm": 0.7})
    rec = Recorder(answers(noul={"tag_waktu_tunggu": 0.91, "tag_parkir": 0.3, "tag_kebersihan": 0.55}, conf=0.9))
    result = rec.client().analyze_review({**REVIEW, "taxonomy": tagged})

    questions = rec.requests[0]["questions"]
    assert {k for k in questions if k.startswith("tag_")} == {f"tag_{a['slug']}" for a in tagged["aspects"]}
    # waktu_tunggu .91 and kebersihan .55 clear the default 0.5, parkir .3 does not;
    # the primary category is appended with its choice confidence
    assert [(t["slug"], t["p"]) for t in result["tags"]] == [
        ("waktu_tunggu", 0.91),
        ("kebersihan", 0.55),
        ("takaran_bbm", 0.9),
    ]


def test_each_tag_is_judged_in_one_extra_request(tx_spbu, tx_tagged):
    tagged = tx_tagged(tx_spbu, max_tags=3)
    rec = Recorder(
        answers(
            noul={"tag_waktu_tunggu": 0.91, "tag_kebersihan": 0.8},
            tag_sentiments={"waktu_tunggu": "negative", "kebersihan": "positive", "takaran_bbm": "mixed"},
        )
    )
    client = rec.client()
    result = client.analyze_review({**REVIEW, "taxonomy": tagged})

    assert len(rec.requests) == 2  # core + tag questions, then the per-tag sentiments
    asked = rec.requests[1]["questions"]
    assert set(asked) == {"sent_waktu_tunggu", "sent_kebersihan", "sent_takaran_bbm"}  # exactly the tagged aspects
    question = asked["sent_waktu_tunggu"]
    assert question["type"] == "choice" and set(question["criteria"]) == {"positive", "negative", "neutral", "mixed"}
    waktu_tunggu = next(a for a in tagged["aspects"] if a["slug"] == "waktu_tunggu")
    assert waktu_tunggu["criteria"] in question["instructions"]
    assert {t["slug"]: t["sentiment"] for t in result["tags"]} == {
        "waktu_tunggu": "negative", "kebersihan": "positive", "takaran_bbm": "mixed",
    }
    # both requests are paid for, and the raw answers keep the sentiments for audit
    assert client.last_usage["total_tokens"] == 2 * 120
    assert result["jev"]["sent_kebersihan"]["choice"] == "positive"


def test_an_unanswered_tag_sentiment_is_left_for_the_review_sentiment(tx_spbu, tx_tagged):
    tagged = tx_tagged(tx_spbu, max_tags=3)
    rec = Recorder(answers(noul={"tag_waktu_tunggu": 0.91}, tag_sentiments={"waktu_tunggu": "not-a-sentiment"}))
    result = rec.client().analyze_review({**REVIEW, "taxonomy": tagged})
    assert all(t["sentiment"] is None for t in result["tags"])  # AnalysisService fills these in


def test_the_fallback_tag_is_judged_too_and_tagging_off_asks_nothing(tx_spbu, tx_tagged):
    rec = Recorder(answers(category="lainnya", conf=0.9))
    rec.client().analyze_review({**REVIEW, "taxonomy": tx_tagged(tx_spbu)})
    # lainnya is the tag when nothing else passed, so it gets its own sentiment question
    assert set(rec.requests[-1]["questions"]) == {"sent_lainnya"}
    rec_off = Recorder(answers())
    rec_off.client().analyze_review({**REVIEW, "taxonomy": tx_spbu})
    assert len(rec_off.requests) == 1  # tagging off: nothing to judge


def test_lainnya_is_not_added_next_to_real_tags(tx_spbu, tx_tagged):
    rec = Recorder(answers(category="mystery", noul={"tag_waktu_tunggu": 0.9}))
    result = rec.client().analyze_review({**REVIEW, "taxonomy": tx_tagged(tx_spbu)})
    assert [t["slug"] for t in result["tags"]] == ["waktu_tunggu"]
    assert result["issue_category"] == "lainnya"


def test_a_failed_sentiment_request_fails_the_analysis_instead_of_dropping_sentiments(tx_spbu, tx_tagged):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["questions"])
        if len(calls) == 2:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json=answers(noul={"tag_waktu_tunggu": 0.9})(calls[-1]))

    client = JevAiClient(
        settings(), http_client=httpx.Client(base_url="https://api.typesafe.test", transport=httpx.MockTransport(handler))
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        client.analyze_review({**REVIEW, "taxonomy": tx_tagged(tx_spbu)})


def test_a_per_aspect_threshold_beats_the_default(tx_spbu, tx_tagged):
    tagged = tx_tagged(tx_spbu, thresholds={"waktu_tunggu": 0.95})
    rec = Recorder(answers(noul={"tag_waktu_tunggu": 0.9}))
    result = rec.client().analyze_review({**REVIEW, "taxonomy": tagged})
    assert "waktu_tunggu" not in {t["slug"] for t in result["tags"]}


def test_extra_questions_are_chunked_and_usage_is_summed(tx_spbu, tx_tagged, monkeypatch):
    monkeypatch.setattr(jev_client, "MAX_QUESTIONS_PER_REQUEST", 10)
    rec = Recorder(answers(noul={"tag_waktu_tunggu": 0.9}, usage=(100, 20)))
    client = rec.client()
    result = client.analyze_review({**REVIEW, "taxonomy": tx_tagged(tx_spbu)})

    assert len(rec.requests) > 1
    assert all(len(r["questions"]) <= 10 for r in rec.requests)
    assert "sentiment" in rec.requests[0]["questions"] and "sentiment" not in rec.requests[1]["questions"]
    assert client.last_usage == {
        "prompt_tokens": 100 * len(rec.requests),
        "completion_tokens": 20 * len(rec.requests),
        "total_tokens": 120 * len(rec.requests),
    }
    assert "waktu_tunggu" in {t["slug"] for t in result["tags"]}


def test_without_a_taxonomy_the_legacy_questions_are_unchanged():
    rec = Recorder(lambda q: {"answers": {"sentiment": {"choice": "negative", "confidence": 0.8}, "category": {"choice": "waiting time", "confidence": 0.9}, "is_safety_issue": {"noul": 0.1}, "is_viral_risk": {"noul": 0.1}}, "usage": {}})
    result = rec.client().analyze_review(REVIEW)

    assert set(rec.requests[0]["questions"]) == {"sentiment", "category", "is_safety_issue", "is_viral_risk"}
    assert result["issue_category"] == "waiting_time" and "risk_flags" not in result


def test_suggest_reply_asks_one_request_and_maps_the_answer():
    presets = [{"id": "mohon_maaf_umum", "when_to_use": "Keluhan umum"}, {"id": "terima_kasih_pujian", "when_to_use": "Pujian"}]
    flags = [{"slug": "risiko_viral", "question": "Ancaman viral?"}]

    def answer(questions):
        return {
            "answers": {
                "preset": {"choice": "mohon_maaf_umum", "confidence": 0.88},
                "language": {"choice": "en"},
                "flag_risiko_viral": {"noul": 0.9},
            },
            "usage": {"input_tokens": 300, "output_tokens": 12},
        }

    rec = Recorder(answer)
    out = rec.client().suggest_reply("Bad service", presets, flags)

    assert len(rec.requests) == 1
    questions = rec.requests[0]["questions"]
    assert questions["preset"]["criteria"] == {"mohon_maaf_umum": "Keluhan umum", "terima_kasih_pujian": "Pujian"}
    assert questions["flag_risiko_viral"]["instructions"] == "Ancaman viral?"
    assert out == {
        "preset_id": "mohon_maaf_umum",
        "confidence": 0.88,
        "language": "en",
        "risk_flags": {"risiko_viral": True},
        "usage": {"prompt_tokens": 300, "completion_tokens": 12, "total_tokens": 312},
    }


def test_a_provider_error_is_raised_not_swallowed(tx_spbu):
    client = JevAiClient(
        settings(),
        http_client=httpx.Client(
            base_url="https://api.typesafe.test",
            transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")),
        ),
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        client.analyze_review({**REVIEW, "taxonomy": tx_spbu})
