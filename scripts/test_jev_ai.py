import os
import json
from pprint import pprint

# Force environment to local
os.environ["APP_ENV"] = "local"
# Set JEV base URL to whatever the user has or keep default
os.environ["JEV_BASE_URL"] = os.getenv("JEV_BASE_URL", "http://localhost:9091/api")

from app.config import get_settings
from app.integrations.jev_client import JevAiClient

def main():
    settings = get_settings()
    client = JevAiClient(settings)

    print(f"Testing JevAiClient against: {client._http.base_url}")
    
    review = {
        "review_text": "Pertama kalinya harus dirawat di RS pakai BPJS, cukup kaget karena pelayanan di sini memuaskan, cepat, dan gak ribet utk BPJS.",
        "rating": 5
    }
    
    print("\nReview Input:")
    pprint(review)

    try:
        # Check models available
        models = client.list_models()
        print("\nAvailable models:", models)
    except Exception as e:
        print("\nCould not fetch models (server might not be running locally or /inference/engines is not implemented):", e)
        print("Will try to call analyze_review directly.")

    try:
        print("\nCalling analyze_review...")
        result = client.analyze_review(review)
        print("\nAnalysis Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print("\nError calling analyze_review:", e)
        print("Please ensure your JEV AI server is running locally.")

if __name__ == "__main__":
    main()
