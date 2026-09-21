from __future__ import annotations

from app.config import AnalysisProvider, Settings
from app.integrations.absa_client import AbsaClient
from app.integrations.gemini_client import GeminiClientBase
from app.integrations.local_llm_client import LocalLLMClient


def create_analysis_client(
    settings: Settings, provider: AnalysisProvider | None = None
) -> GeminiClientBase:
    selected = provider or settings.analysis_provider
    if selected == "absa":
        return AbsaClient(settings)
    if selected == "openai":
        if not settings.openai_api_key or not settings.openai_model:
            raise RuntimeError(
                "OPENAI_API_KEY and OPENAI_MODEL are required when "
                "ANALYSIS_PROVIDER=openai."
            )
        return LocalLLMClient(
            settings,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
        )
    raise ValueError("provider must be absa or openai.")
