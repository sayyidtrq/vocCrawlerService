from __future__ import annotations

import pytest

from app.services.taxonomy_service import upsert_snapshots
from scripts import try_replies
from scripts.try_examples import REPLY_EXAMPLES
from scripts.try_replies import offered_presets
from scripts.try_examples import ReplyExample
from scripts.try_replies import judge

KESEHATAN = "kesehatan:0e20266e"
ALL_REPLIES = [e for examples in REPLY_EXAMPLES.values() for e in examples]


def answer(preset_id, confidence, flags, tokens=300):
    return {"preset_id": preset_id, "confidence": confidence, "language": "id", "risk_flags": flags, "usage": {"total_tokens": tokens}}


def ideal(example, presets, risk_flags):
    """What an ideal model answers: the expected preset with high confidence, or the critical flags raised."""
    flags = {f["slug"]: False for f in risk_flags}
    if example is None:
        return answer(presets[0]["id"], 0.9, flags)
    if example.mode == "escalate":
        flags.update({slug: True for slug in example.flags})
        return answer(presets[0]["id"], 0.9, flags)
    return answer(example.presets[0], 0.95, flags)


class FakeJev:
    model_name = "fake-jev"

    def __init__(self, behave=ideal):
        self.behave = behave
        self.calls: list[dict] = []

    def suggest_reply(self, text, presets, risk_flags):
        self.calls.append({"text": text, "presets": presets, "flags": [f["slug"] for f in risk_flags]})
        example = next((e for e in ALL_REPLIES if e.text == text), None)
        return self.behave(example, presets, risk_flags)


@pytest.fixture()
def stored(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, {KESEHATAN: tx_fixture["taxonomies"][KESEHATAN]})
        session.commit()
    return tx_session_factory


def run(args, *, client=None, factory=None):
    lines: list[str] = []
    code = try_replies.main(args, client=client, session_factory=factory, out=lines.append)
    return code, "\n".join(lines)


def test_judge_names_every_miss():
    example = ReplyExample("x", "t", "preset", ("mohon_maaf_waktu_tunggu",))
    assert all(ok for ok, _ in judge(example, {"mode": "preset", "preset_id": "mohon_maaf_waktu_tunggu"}))
    assert [m for ok, m in judge(example, {"mode": "preset", "preset_id": "mohon_maaf_umum"}) if not ok] == [
        "preset mohon_maaf_waktu_tunggu (got mohon_maaf_umum)"
    ]
    assert [m for ok, m in judge(example, {"mode": "none"}) if not ok] == ["mode preset (got none)", "preset mohon_maaf_waktu_tunggu (got None)"]

    escalate = ReplyExample("x", "t", "escalate", flags=("keselamatan_pasien",))
    assert all(ok for ok, _ in judge(escalate, {"mode": "escalate", "risk_flags": {"keselamatan_pasien": True}}))
    assert [m for ok, m in judge(escalate, {"mode": "escalate", "risk_flags": {"keselamatan_pasien": False}}) if not ok] == [
        "risk flag keselamatan_pasien raised (it was not)"
    ]


def test_every_example_runs_and_an_ideal_model_passes(stored):
    model = FakeJev()
    code, text = run([], client=model, factory=stored)

    assert code == 0, text
    assert len(model.calls) == len(REPLY_EXAMPLES["kesehatan"])
    assert "kesehatan:0e20266e (industry kesehatan, sent by OneBox), 9 presets offered" in text  # 10 minus the escalation preset
    assert "provider: fake-jev   threshold: 0.75" in text
    assert "decision  : preset   preset: terima_kasih_pujian   confidence: 0.95" in text
    assert "decision  : escalate" in text and "keselamatan_pasien=YES" in text
    assert f"expectations met across {len(REPLY_EXAMPLES['kesehatan'])} reviews, {300 * len(model.calls)} tokens" in text


def test_the_model_is_offered_the_industry_presets_without_the_escalation_preset_and_the_packs_flags(stored):
    model = FakeJev()
    run(["--only", "pujian"], client=model, factory=stored)

    (call,) = model.calls
    assert [p["id"] for p in call["presets"]] == [p["id"] for p in offered_presets("kesehatan")]
    assert "privasi_pasien_hubungi_kami" not in {p["id"] for p in call["presets"]}  # Kesehatan's escalation preset
    assert all(set(p) == {"id", "when_to_use"} for p in call["presets"])
    assert call["flags"] == ["risiko_viral", "keselamatan_pasien"]


def test_a_wrong_preset_fails_the_run_and_says_which(stored):
    def always_generic(example, presets, risk_flags):
        flags = {f["slug"]: False for f in risk_flags}
        if example is not None and example.mode == "escalate":
            flags.update({slug: True for slug in example.flags})
        return answer("mohon_maaf_umum", 0.95, flags)

    code, text = run([], client=FakeJev(always_generic), factory=stored)

    assert code == 1
    assert "FAIL  preset mohon_maaf_waktu_tunggu (got mohon_maaf_umum)" in text
    assert "ok    mode escalate (got escalate)" in text  # the safety path does not depend on the preset


def test_a_missed_critical_flag_is_a_failure_on_both_the_mode_and_the_flag(stored):
    def blind(example, presets, risk_flags):
        return answer("mohon_maaf_umum", 0.95, {f["slug"]: False for f in risk_flags})

    code, text = run(["--only", "salah obat"], client=FakeJev(blind), factory=stored)

    assert code == 1
    assert "FAIL  mode escalate (got preset)" in text and "FAIL  risk flag keselamatan_pasien raised (it was not)" in text


def test_below_the_threshold_no_preset_is_offered(stored):
    code, text = run(["--only", "pujian", "--threshold", "0.99"], client=FakeJev(), factory=stored)

    assert code == 1
    assert "FAIL  mode preset (got none)" in text and "threshold: 0.99" in text


def test_an_industry_onebox_has_not_sent_uses_the_built_in_presets(stored):
    model = FakeJev()
    code, text = run(["--industry", "spbu"], client=model, factory=stored)

    assert code == 0, text
    assert "industry spbu, built-in catalog copy: OneBox has not sent this industry), 9 presets offered" in text
    assert len(model.calls) == len(REPLY_EXAMPLES["spbu"])
    assert "mohon_maaf_takaran_bbm" in {p["id"] for p in model.calls[0]["presets"]}
    assert model.calls[0]["flags"] == ["risiko_viral", "kecurangan_bbm", "risiko_kebakaran"]


def test_all_industries_runs_every_industry(stored):
    model = FakeJev()
    code, text = run(["--all-industries"], client=model, factory=stored)

    assert code == 0, text
    assert len(model.calls) == len(ALL_REPLIES)
    assert text.count("#####") == len(REPLY_EXAMPLES)
    assert f"expectations met across {len(ALL_REPLIES)} reviews" in text


def test_list_needs_no_model_or_database():
    code, text = run(["--list"])
    assert code == 0 and all(e.name in text for e in REPLY_EXAMPLES["kesehatan"]) and "escalate" in text and "[spbu]" in text


def test_only_filters_and_a_miss_is_reported(stored):
    code, text = run(["--only", "tidak ada contoh begini"], client=FakeJev(), factory=stored)
    assert code == 2 and "No example of this industry matches --only" in text


def test_a_provider_that_cannot_suggest_replies_is_refused_clearly(stored):
    class Absa:
        model_name = "absa-only"

    code, text = run([], client=Absa(), factory=stored)
    assert code == 2 and "needs the Jev provider" in text


def test_free_text_is_decided_without_expectations(stored):
    model = FakeJev(lambda example, presets, risk_flags: answer("mohon_maaf_waktu_tunggu", 0.9, {f["slug"]: False for f in risk_flags}))
    code, text = run(["--text", "Antre lama sekali"], client=model, factory=stored)

    assert code == 0
    assert [c["text"] for c in model.calls] == ["Antre lama sekali"]
    assert "Your text" in text and "preset: mohon_maaf_waktu_tunggu" in text and "expectations met" not in text


def test_without_a_stored_taxonomy_it_says_what_to_do(tx_session_factory):
    code, text = run(["--text", "x"], client=FakeJev(), factory=tx_session_factory)
    assert code == 2 and "Taksonomi industri aktif" in text and "refresh_worklist" in text
