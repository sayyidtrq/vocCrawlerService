import os
import json
from pprint import pprint

# Force environment to local
os.environ["APP_ENV"] = "local"
# Ensure we hit openrouter if not specified
if "JEV_BASE_URL" not in os.environ:
    os.environ["JEV_BASE_URL"] = "https://openrouter.ai/api"
if "JEV_ENGINE_VERSION" not in os.environ:
    os.environ["JEV_ENGINE_VERSION"] = "~typesafe/jev-latest"

from app.config import get_settings
from app.integrations.jev_client import JevAiClient

def main():
    settings = get_settings()
    client = JevAiClient(settings)

    print(f"Testing JevAiClient against: {client._http.base_url}")
    if not settings.jev_api_key:
        print("WARNING: JEV_API_KEY is not set. The request will likely fail with a 401 Unauthorized.")
        print("Please set your OpenRouter API key with: export JEV_API_KEY='your_api_key'")
    
    review = {
        "review_text": "Pertama kalinya harus dirawat di RS pakai BPJS, cukup kaget karena pelayanan di sini memuaskan, cepat, dan gak ribet utk BPJS.",
        "rating": 5
    }
    
    print("\nReview Input:")
    pprint(review)

    try:
        models = client.list_models()
        print("\nAvailable models:", models)
    except Exception as e:
        print("\nCould not fetch models:", e)

    try:
        print("\nCalling analyze_review...")
        result = client.analyze_review(review)
        print("\nAnalysis Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print("\nError calling analyze_review:", e)

if __name__ == "__main__":
    main()
