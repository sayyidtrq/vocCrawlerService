"""The AI Insight smoke script is tested offline against the stubbed v2 app; no network is used."""

import copy
import importlib.util
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from test_v2_ai import TAXONOMY, FakeAnalysisClient, api  # noqa: F401  (api is a fixture)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_ai_insight_v2.py"
_spec = importlib.util.spec_from_file_location("smoke_ai_insight_v2", SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

DRAFT = "Ada 1.234 ulasan; rata-rata 3,25; negatif 88; belum dibalas 77. Isu naik 12,5% dan perubahan -5."
HEADLINES = [
    {"key": key, "value": value, "text": str(value), "headline": True}
    for key, value in (("total", 1234), ("avg_rating", 3.25), ("negative", 88), ("unreplied_negative", 77))
]


# --- review-summary stub -----------------------------------------------------------------------
# /brief and /review-summary share FakeAnalysisClient.brief, so route by the system message.

def review_json(summary=None, evidence=None, action=None):
    return json.dumps({
        "summary": summary or "Pasien menunggu dokter lebih dari 2 jam tanpa kabar.",
        "evidence": "menunggu dokter lebih dari 2 jam tanpa kabar" if evidence is None else evidence,
        "recommended_action": action or "Beri kabar pasien yang menunggu dan tinjau antrean poli.",
    })


@pytest.fixture(autouse=True)
def review_summary_stub(monkeypatch):
    original = FakeAnalysisClient.brief

    def brief(self, messages):
        if "Summarize one review" not in messages[0]["content"]:
            return original(self, messages)
        factory = self.factory
        factory.__dict__.setdefault("review_calls", []).append(copy.deepcopy(messages))
        self.last_usage = {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50}
        if factory.__dict__.get("review_obey") and "sembilan ratus" in messages[-1]["content"]:
            return review_json(summary="Rating ulasan ini 999.")
        return factory.__dict__.get("review_text") or review_json()

    monkeypatch.setattr(FakeAnalysisClient, "brief", brief)


def fact(key, value, headline=False):
    return {"key": key, "value": value, "headline": headline}


# --- number guard parity with onecloud tests/voc/voc_brief_guard_check.php ---------------------

@pytest.mark.parametrize("candidate", [
    DRAFT,
    "Negatif 88, belum dibalas 77. Dari 1234 ulasan, rata-rata 3.25. Perubahan -5, kenaikan 12.5%.",
])
def test_guard_accepts_same_numbers(candidate):
    assert smoke.check_brief(candidate, DRAFT, HEADLINES) == []


@pytest.mark.parametrize("candidate,reason", [
    (DRAFT + " Tambahan 999.", "number_not_in_facts:999"),
    (DRAFT.replace("12,5", "15,2"), "number_not_in_facts:15,2"),
    (DRAFT.replace("belum dibalas 77.", ""), "headline_missing:unreplied_negative"),
    ("Hanya uraian.", "headline_missing:total"),
])
def test_guard_rejects_changed_numbers(candidate, reason):
    assert reason in smoke.check_brief(candidate, DRAFT, HEADLINES)


def test_guard_allows_numbers_from_facts_or_draft_alone():
    assert smoke.check_brief("Tambahan 42.", "Draft tanpa angka.", [fact("extra", 42)]) == []
    assert smoke.check_brief("Kenaikan 12.5.", "Naik 12,5%.", []) == []


@pytest.mark.parametrize("draft_token,candidate_number,expected", [
    ("1.234", "1234", True), ("1.234", "1,234", False), ("1.5", "1,5", True), ("1.5", "15", False),
    ("1.234.567", "1234567", True), ("1.234,5", "1234.5", True), ("30%", "30", True), ("12,5%", "12.5", True),
    ("-5", "-5", True), ("-5", "5", False), ("3,25", "3.254", False), ("3,25", "3,254", True),
    ("3,25", "3,255", True), ("3,25", "3,256", False),
])
def test_guard_normalises_indonesian_separators(draft_token, candidate_number, expected):
    reasons = smoke.check_brief("Nilai " + candidate_number, "Nilai " + draft_token, [])
    assert (reasons == []) is expected, reasons


@pytest.mark.parametrize("candidate,draft,facts", [
    ("Nilai 1,234", "", [fact("raw", 1.234)]),
    ("Nilai 1234", "", [fact("formatted", "1.234", True)]),
    ("Periode 2026-09-21", "", [fact("period_from", "2026-09-21")]),
    ("Periode 21 September 2026", "Periode 2026-09-21", []),
    ("naik 12,5%.", "Naik 12.5", []),
    ("Ada 30.", "Nilai 30", []),
    ("1. Nilai 30\n  2) Naik 12,5%\n99. Selesai", "Nilai 30 dan 12.5", []),
])
def test_guard_accepts_edge_cases(candidate, draft, facts):
    assert smoke.check_brief(candidate, draft, facts) == []


@pytest.mark.parametrize("candidate,draft,facts,reason", [
    ("Naik 12,5,999", "Naik 12,5", [], "number_not_in_facts:999"),
    ("1. Nilai 999", "Nilai 30", [], "number_not_in_facts:999"),
    ("100. Uraian", "Uraian", [], "number_not_in_facts:100"),
    ("Ada 2. Uraian", "Uraian", [], "number_not_in_facts:2"),
    ("30. Uraian", "30 ulasan", [fact("total", 30, True)], "headline_missing:total"),
])
def test_guard_rejects_edge_cases(candidate, draft, facts, reason):
    assert reason in smoke.check_brief(candidate, draft, facts)


@pytest.mark.parametrize("candidate", ["<b>teks</b>", "Teks <", "http://contoh.invalid", "HTTPS://contoh.invalid", "Kolom | isi"])
def test_guard_rejects_html_links_and_tables(candidate):
    assert "html_or_link" in smoke.check_brief(candidate, "", [])


def test_guard_word_limits_and_empty():
    assert smoke.check_brief("satu dua tiga", "", [], max_words=3) == []
    assert "too_long" in smoke.check_brief("satu dua tiga empat", "", [], max_words=3)
    assert smoke.check_brief("kata " * 400, "", []) == []
    assert "too_long" in smoke.check_brief("kata " * 401, "", [])
    for empty in ("", " \n\t", None):
        assert "empty" in smoke.check_brief(empty, "", [])


def test_guard_ignores_unicode_digits():
    assert smoke.extract_numbers("angka ٣٤") == {}


# --- end to end against the stubbed app ---------------------------------------------------------

def make_request(api, token="shared-secret", always_send_token=False):
    def request(method, path, body=None, auth=True):
        headers = {"X-Request-ID": "smoke-test"}
        if auth or always_send_token:
            headers["Authorization"] = "Bearer " + token
        response = api.client.request(method, "/api/integration/v2" + path, json=body, headers=headers)
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        return response.status_code, parsed, response.text
    return request


def run_script(request, *argv, taxonomy=None):
    lines = []
    args = smoke.build_parser().parse_args(list(argv))
    args.taxonomy = taxonomy
    code = smoke.run(request, args, out=lines.append)
    return code, "\n".join(lines)


def reordered_draft():
    return "\n".join(reversed(smoke.BRIEF_DRAFT.splitlines()))


def healthy(api):
    api.clients.analysis_answer = {"category_confidence": 0.8}
    api.clients.brief_text = reordered_draft()


def test_script_passes_against_a_healthy_server(api):
    healthy(api)
    code, output = run_script(make_request(api))
    assert code == 0, output
    assert "no token is rejected (401)" in output
    assert "rating-only review has no category_confidence" in output
    assert "number guard passes" in output
    assert "injection probe: the model did not obey" in output
    assert output.rstrip().endswith("failed 0")
    assert len(api.clients.brief_calls) == 2
    prompt = api.clients.brief_calls[0][-1]["content"]
    assert "Total 248 ulasan." in prompt and '"unreplied_negative"' in prompt


def test_script_can_skip_sections(api):
    healthy(api)
    code, output = run_script(make_request(api), "--skip-brief")
    assert code == 0 and "3. brief" not in output and not api.clients.brief_calls
    code, output = run_script(make_request(api), "--skip-analysis")
    assert code == 0 and "2. analysis" not in output


def test_script_passes_for_openai_without_confidence(api):
    api.clients.brief_text = reordered_draft()
    code, output = run_script(make_request(api), "--provider", "openai")
    assert code == 0, output


@pytest.mark.parametrize("brief_text,expected", [
    (lambda: smoke.BRIEF_DRAFT + "\nTambahan 250 ulasan.", "number_not_in_facts:250"),
    (lambda: smoke.BRIEF_DRAFT.replace("Total 248 ulasan.", ""), "headline_missing:total"),
    (lambda: "<b>" + smoke.BRIEF_DRAFT, "html_or_link"),
])
def test_script_fails_when_the_brief_breaks_the_guard(api, brief_text, expected):
    api.clients.analysis_answer = {"category_confidence": 0.8}
    api.clients.brief_text = brief_text()
    code, output = run_script(make_request(api))
    assert code == 1
    assert "FAIL  number guard rejected the brief" in output and expected in output


def test_script_fails_when_the_model_obeys_the_injection(api, monkeypatch):
    healthy(api)
    base = reordered_draft()

    def obedient(self, messages):
        self.factory.brief_calls.append(messages)
        self.last_usage = {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}
        return base + ("\nUlasan negatif 999." if "sembilan ratus" in messages[-1]["content"] else "")

    monkeypatch.setattr(FakeAnalysisClient, "brief", obedient)
    code, output = run_script(make_request(api))
    assert code == 1
    assert "FAIL  injection probe: output contains 999" in output
    assert "number guard passes" in output


def test_script_requires_confidence_for_jev_with_a_taxonomy(api):
    api.clients.analysis_answer = {"category_confidence": 0.8}
    api.clients.brief_text = reordered_draft()
    code, output = run_script(make_request(api), taxonomy=TAXONOMY)
    assert code == 0, output
    assert "category_confidence present on 3 of 3 analysed reviews" in output

    api.clients.analysis_answer = {}
    code, output = run_script(make_request(api), taxonomy=TAXONOMY)
    assert code == 1
    assert "FAIL  no analysed review carries category_confidence: the server runs a build older than b6a5501" in output


def test_script_requires_confidence_for_absa(api):
    api.clients.brief_text = reordered_draft()
    code, output = run_script(make_request(api), "--provider", "absa")
    assert code == 1 and "FAIL  no analysed review carries category_confidence" in output


def test_script_does_not_require_confidence_for_jev_without_a_taxonomy(api):
    # Live finding: Jev emits it only on its taxonomy path, so a plain request legitimately has none.
    api.clients.brief_text = reordered_draft()
    code, output = run_script(make_request(api))
    assert code == 0, output
    assert "category_confidence not required here (jev returns it only with a taxonomy" in output
    assert "FAIL" not in output


def test_script_fails_when_confidence_is_out_of_range(api):
    api.clients.analysis_answer = {"category_confidence": 1.5}
    api.clients.brief_text = reordered_draft()
    code, output = run_script(make_request(api), "--provider", "absa")
    assert code == 1 and "category_confidence" in output.split("FAIL", 1)[1]


def test_script_fails_when_no_token_is_not_rejected(api):
    healthy(api)
    code, output = run_script(make_request(api, always_send_token=True))
    assert code == 1
    assert "FAIL  no token: expected 401, got 200" in output
    assert "stop: fix auth first" in output and not api.clients.brief_calls


def test_script_fails_fast_with_a_wrong_token(api):
    healthy(api)
    code, output = run_script(make_request(api, token="wrong"))
    assert code == 1
    assert "token was rejected" in output and "stop: fix auth first" in output
    assert not api.clients.calls


def test_script_fails_when_the_brief_comes_back_empty(api):
    api.clients.analysis_answer = {"category_confidence": 0.8}
    api.clients.brief_text = "   "
    code, output = run_script(make_request(api))
    assert code == 1 and "FAIL  brief: expected 200, got 502" in output


def test_script_enforces_the_token_budget(api):
    healthy(api)
    code, output = run_script(make_request(api), "--max-tokens", "1")
    assert code == 1 and "FAIL  token budget exceeded" in output
    code, output = run_script(make_request(api), "--max-tokens", "100000")
    assert code == 0 and "within the token budget" in output


def test_script_checks_the_review_summary(api):
    healthy(api)
    code, output = run_script(make_request(api))
    assert code == 0, output
    assert "4. review summary" in output
    assert "review-summary: the evidence quote is a verbatim excerpt of the review" in output
    assert "review-summary: no invented numbers or markup" in output
    assert "review-summary injection probe: the model did not obey" in output
    assert "empty review text is rejected" in output and "rating 6 is rejected" in output
    calls = api.clients.review_calls
    assert len(calls) == 2
    prompt = calls[0][-1]["content"]
    assert prompt.startswith("BEGIN_REVIEW_DATA") and smoke.REVIEW_TEXT in prompt and "Waktu Tunggu" in prompt
    assert "sembilan ratus" in calls[1][-1]["content"]
    assert len(api.clients.brief_calls) == 2


def test_script_can_skip_the_review_summary(api):
    healthy(api)
    code, output = run_script(make_request(api), "--skip-review-summary")
    assert code == 0 and "4. review summary" not in output
    assert not api.clients.__dict__.get("review_calls")


def test_script_reports_a_dropped_evidence_quote_without_failing(api):
    healthy(api)
    api.clients.review_text = review_json(evidence="kutipan yang tidak ada dalam ulasan")
    code, output = run_script(make_request(api))
    assert code == 0, output
    assert "no evidence quote, evidence_verified is false" in output
    assert "the server dropped it" in output


def test_script_fails_when_the_review_summary_invents_a_number(api):
    healthy(api)
    api.clients.review_text = review_json(summary="Pasien menunggu 500 jam di poli.")
    code, output = run_script(make_request(api))
    assert code == 1
    assert "FAIL  review-summary: guard rejected the output" in output and "number_not_in_facts:500" in output


def test_script_fails_when_the_review_summary_obeys_the_injection(api):
    healthy(api)
    api.clients.review_obey = True
    code, output = run_script(make_request(api))
    assert code == 1
    assert "FAIL  review-summary injection probe: output contains 999" in output
    assert "review-summary: no invented numbers or markup" in output


def test_script_fails_when_the_review_summary_is_not_json(api):
    healthy(api)
    api.clients.review_text = "bukan json"
    code, output = run_script(make_request(api))
    assert code == 1 and "FAIL  review-summary: expected 200, got 502" in output


# --- command line -------------------------------------------------------------------------------

def test_main_needs_a_server_url(capsys):
    assert smoke.main([], env={"TOKEN": "t"}) == 2
    assert "CRAWLER" in capsys.readouterr().err


def test_main_never_prints_the_token(monkeypatch, capsys):
    def refuse(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(smoke.urllib.request, "urlopen", refuse)
    code = smoke.main(["--crawler", "http://localhost:9"], env={"TOKEN": "SECRET-TOKEN-123"})
    captured = capsys.readouterr()
    assert code == 1
    assert "SECRET-TOKEN-123" not in captured.out + captured.err
    assert "no response" in captured.out


def test_help_runs_without_network():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "usage:" in result.stdout and "--max-tokens" in result.stdout
