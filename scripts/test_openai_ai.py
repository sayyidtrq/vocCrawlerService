"""Send one real review through the application's OpenAI analysis client."""

from __future__ import annotations

import argparse
import json
import os

from app.config import get_settings
from app.integrations.analysis_client import create_analysis_client
from app.integrations.local_llm_client import LLMProviderError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review",
        default="Dokternya ramah, tetapi antrean sangat lama.",
    )
    parser.add_argument("--rating", type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()

    settings = get_settings()
    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    model = os.getenv("OPENAI_MODEL") or settings.openai_model or "gpt-4.1-mini"
    if not api_key:
        raise SystemExit("ERROR: OPENAI_API_KEY is required.")

    client = create_analysis_client(
        settings.model_copy(
            update={"openai_api_key": api_key, "openai_model": model}
        ),
        "openai",
    )
    try:
        result = client.analyze_review(
            {
                "review_text": args.review,
                "rating": args.rating,
                "reviewer_name": "OpenAI smoke test",
            }
        )
    except LLMProviderError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("=== OpenAI analysis response ===")
    print(
        json.dumps(
            {"model": client.model_name, "analysis": result, "usage": client.last_usage},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
