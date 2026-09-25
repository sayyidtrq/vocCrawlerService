import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.integrations.absa_client import AbsaClient
from app.integrations.analysis_client import create_analysis_client
from app.integrations.jev_client import JevAiClient
from app.integrations.local_llm_client import LocalLLMClient
from apps.api.app_api.integration_schemas import IntegrationReviewItem


def settings(**updates):
    return Settings(database_url="sqlite+pysqlite:///:memory:").model_copy(
        update=updates
    )


def test_absa_is_the_default_provider():
    with patch("app.integrations.analysis_client.AbsaClient") as client:
        create_analysis_client(settings())

    client.assert_called_once_with(settings())


def test_absa_calls_v14_api_and_maps_the_response():
    def handler(request):
        assert request.url.path == "/api/inference/single"
        assert request.read()
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "aspect": "antrean",
                        "opinion": "lama",
                        "sentiment": "negative",
                        "taxonomy": "Waiting Time",
                        "confidence": 0.91,
                    },
                    {
                        "aspect": "dokter",
                        "opinion": "ramah",
                        "sentiment": "positive",
                        "taxonomy": "Doctor",
                        "confidence": 0.88,
                    },
                ]
            },
        )

    http_client = httpx.Client(
        base_url="http://absa.test/api",
        transport=httpx.MockTransport(handler),
    )
    result = AbsaClient(settings(), http_client=http_client).analyze_review(
        {"review_text": "Dokter ramah tetapi antrean lama.", "rating": 2}
    )

    assert result["sentiment"] == "mixed"
    assert result["issue_category"] == "waiting_time"
    assert result["keywords"] == ["antrean", "lama", "dokter", "ramah"]


def test_openai_uses_its_own_credentials_and_model():
    config = settings(
        openai_api_key="secret",
        openai_model="paid-model",
    )
    with patch("app.integrations.analysis_client.LocalLLMClient") as client:
        create_analysis_client(config, "openai")

    client.assert_called_once_with(
        config,
        base_url="https://api.openai.com/v1",
        api_key="secret",
        model_name="paid-model",
    )


def test_openai_requires_key_and_model():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY and OPENAI_MODEL"):
        create_analysis_client(settings(analysis_provider="openai"))


def test_openai_maps_the_response():
    content = json.dumps(
        {
            "sentiment": "negative",
            "sentiment_score": 0.9,
            "issue_category": "waiting_time",
            "urgency": "high",
            "summary": "Antrean terlalu lama.",
            "recommended_action": "Tinjau waktu tunggu.",
            "keywords": ["antrean"],
            "is_potential_viral": False,
            "is_patient_safety_issue": False,
        }
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )
    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))
    )

    result = LocalLLMClient(settings(), sdk_client=sdk).analyze_review(
        {"review_text": "Antrean terlalu lama.", "rating": 1}
    )

    assert result["sentiment"] == "negative"
    assert result["issue_category"] == "waiting_time"


def test_jev_provider():
    with patch("app.integrations.analysis_client.JevAiClient") as client:
        create_analysis_client(settings(), "jev")

    client.assert_called_once_with(settings())


def test_jev_calls_systemone_and_maps_the_response():
    openrouter_payload = {
        "answers": {
            "sentiment": {
                "choice": "negative",
                "probabilities": {
                    "negative": 0.85,
                    "positive": 0.05,
                    "neutral": 0.1,
                    "mixed": 0.0,
                },
                "confidence": 0.85,
            },
            "category": {
                "choice": "waiting time",
                "probabilities": {"waiting time": 0.9, "doctor": 0.1},
                "confidence": 0.9,
            },
            "is_safety_issue": {"noul": 0.05},
            "is_viral_risk": {"noul": 0.88},
        }
    }

    review = {
        "review_text": "Antrean sangat lambat, saya akan viralkan ini di Twitter!",
        "rating": 1,
    }

    def handler(request):
        assert request.url.path == "/api/v1/systemone"
        assert json.loads(request.content)["state"] == review["review_text"]
        return httpx.Response(200, json=openrouter_payload)

    http_client = httpx.Client(
        base_url="https://openrouter.test/api",
        transport=httpx.MockTransport(handler),
    )
    result = JevAiClient(settings(), http_client=http_client).analyze_review(review)

    # Validate that it strictly adheres to the schema fields required by OneBox
    assert result["sentiment"] == "negative"
    assert result["sentiment_score"] == 0.85
    assert result["issue_category"] == "waiting_time"
    # Because of viral risk and rating=1 with negative sentiment, urgency should be "high"
    assert result["urgency"] == "high"
    assert "Pelanggan menyampaikan keluhan" in result["summary"]
    assert "Tinjau aspek layanan" in result["recommended_action"]
    assert result["keywords"] == []
    assert result["is_potential_viral"] is True
    assert result["is_patient_safety_issue"] is False

    # Check it passes Pydantic Integration schema validation
    now = datetime.now(timezone.utc)

    # We construct a dummy item with the analysis results attached to ensure types match
    item_data = {
        "id": 1,
        "location_id": 100,
        "location": "Test Clinic",
        "source": "google",
        "review_hash": "abc",
        "review_text": review["review_text"],
        "updated_at": now,
        "sync_updated_at": now,
        "analysis_status": "completed",
        "analyzed": True,
        # Merge the fields generated by _to_analysis
        "sentiment": result["sentiment"],
        "sentiment_score": result["sentiment_score"],
        "issue_category": result["issue_category"],
        "urgency": result["urgency"],
        "summary": result["summary"],
        "recommended_action": result["recommended_action"],
        "keywords": result["keywords"],
        "is_potential_viral": result["is_potential_viral"],
        "is_patient_safety_issue": result["is_patient_safety_issue"],
    }

    # This will raise a ValidationError if any type or constraint fails (e.g. invalid enum choice)
    parsed_item = IntegrationReviewItem(**item_data)

    assert parsed_item.sentiment == "negative"
    assert parsed_item.issue_category == "waiting_time"
