from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from app.config import Settings
from app.integrations.absa_client import AbsaClient
from app.integrations.local_llm_client import LocalLLMClient


def settings():
    return Settings(database_url="sqlite+pysqlite:///:memory:")


def llm(reply: dict):
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        content = json.dumps(
            {
                "sentiment": "negative", "sentiment_score": 0.9, "issue_category": "lainnya", "urgency": "high",
                "summary": "s", "recommended_action": "a", "keywords": [], "is_potential_viral": False,
                "is_safety_issue": False, **reply,
            }
        )
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        return SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return LocalLLMClient(settings(), sdk_client=sdk), sent


def test_openai_prompt_names_the_location_vocabulary_and_flags(tx_spbu, tx_tagged):
    client, sent = llm({"issue_category": "takaran_bbm", "risk_flags": {"kecurangan_bbm": True}, "tags": ["takaran_bbm"]})
    result = client.analyze_review({"review_text": "Takaran kurang", "rating": 1, "taxonomy": tx_tagged(tx_spbu)})

    system = sent["messages"][0]["content"]
    assert "TAXONOMY OVERRIDE" in system and "pelanggan SPBU" in system
    assert "- takaran_bbm: " in system and "- risiko_kebakaran: " in system
    assert "`tags`" in system  # tagging is on for this site
    assert result["issue_category"] == "takaran_bbm"
    assert result["risk_flags"] == {"kecurangan_bbm": True} and result["tags"] == ["takaran_bbm"]


def test_openai_without_taxonomy_keeps_the_original_prompt_and_vocabulary():
    client, sent = llm({"issue_category": "waiting_time"})
    result = client.analyze_review({"review_text": "Antre lama", "rating": 2})

    assert "TAXONOMY OVERRIDE" not in sent["messages"][0]["content"]
    assert result["issue_category"] == "waiting_time"
    assert result["risk_flags"] is None and result["tags"] is None


def test_openai_example_in_the_prompt_ignores_the_optional_taxonomy_fields():
    client, _ = llm({})
    assert '"risk_flags"' not in client.system_instruction and '"tags"' not in client.system_instruction


def test_openai_out_of_list_category_is_replaced_by_the_taxonomy_fallback(tx_spbu):
    client, _ = llm({"issue_category": "pelayanan_dokter"})
    assert client.analyze_review({"review_text": "x", "rating": 1, "taxonomy": tx_spbu})["issue_category"] == "lainnya"


def absa(results, review):
    http = httpx.Client(
        base_url="http://absa.test/api", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": results}))
    )
    return AbsaClient(settings(), http_client=http).analyze_review(review)


ABSA_RESULTS = [
    {"aspect": "pompa", "opinion": "habis", "sentiment": "negative", "taxonomy": "Availability", "confidence": 0.9},
    {"aspect": "antrean", "opinion": "lama", "sentiment": "negative", "taxonomy": "Waiting Time", "confidence": 0.7},
]


def test_absa_maps_its_labels_through_the_pack(tx_spbu, tx_tagged):
    result = absa(ABSA_RESULTS, {"review_text": "Pompa habis, antre lama", "rating": 2, "taxonomy": tx_tagged(tx_spbu)})

    assert result["issue_category"] == "ketersediaan_bbm"  # availability -> the SPBU aspect
    assert result["tags"] == [{"slug": "ketersediaan_bbm", "p": 0.9}, {"slug": "waktu_tunggu", "p": 0.7}]


def test_absa_unknown_label_falls_back_and_praise_becomes_pujian_umum(tx_spbu):
    unknown = [{"aspect": "x", "opinion": "y", "sentiment": "negative", "taxonomy": "Doctor", "confidence": 0.9}]
    assert absa(unknown, {"review_text": "x", "rating": 1, "taxonomy": tx_spbu})["issue_category"] == "lainnya"

    praise = [{"aspect": "x", "opinion": "y", "sentiment": "positive", "taxonomy": "Doctor", "confidence": 0.9}]
    assert absa(praise, {"review_text": "x", "rating": 5, "taxonomy": tx_spbu})["issue_category"] == "pujian_umum"


def test_absa_without_taxonomy_is_unchanged():
    result = absa(ABSA_RESULTS, {"review_text": "x", "rating": 2})
    assert result["issue_category"] == "availability" and "tags" not in result
