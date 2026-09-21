from unittest.mock import patch

import pytest

from app.config import Settings
from app.integrations.analysis_client import create_analysis_client


def settings(**updates):
    return Settings(database_url="sqlite+pysqlite:///:memory:").model_copy(
        update=updates
    )


def test_absa_is_the_default_provider():
    with patch("app.integrations.analysis_client.LocalLLMClient") as client:
        create_analysis_client(settings())

    client.assert_called_once_with(settings())


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
