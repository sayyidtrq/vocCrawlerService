from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.integrations.absa_client import AbsaClient
from app.integrations.analysis_client import create_analysis_client


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

def test_jev_provider():
    with patch("app.integrations.analysis_client.JevAiClient") as client:
        create_analysis_client(settings(), "jev")

    client.assert_called_once_with(settings())
