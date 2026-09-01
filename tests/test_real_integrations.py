from __future__ import annotations

from types import SimpleNamespace

from app.config import Settings
from app.integrations.gemini_client import GeminiClient
from app.integrations.google_places_client import GooglePlacesClient
from app.integrations.review_source_client import ReviewSourceError


def make_settings(tmp_path, **overrides):
    values = {
        "app_env": "test",
        "app_name": "Review System",
        "log_level": "INFO",
        "export_dir": tmp_path / "exports",
        "database_url": "sqlite+pysqlite:///:memory:",
        "cors_allowed_origins": ("http://localhost:3000",),
        "review_source_mode": "google_places",
        "google_maps_api_key": "test-google-key",
        "google_places_language_code": "id",
        "google_places_region_code": "ID",
        "gemini_mode": "real",
        "gemini_api_key": "test-gemini-key",
        "gemini_model": "gemini-2.5-flash",
        "local_llm_base_url": "http://localhost:11434/v1/",
        "local_llm_api_key": "test",
        "local_llm_model": "mock",
        "fetch_limit_per_location": 50,
        "fetch_timeout_seconds": 30,
        "fetch_max_retry": 0,
        "selenium_headless": True,
        "selenium_default_target_reviews": 100,
        "selenium_max_target_reviews": 300,
        "selenium_scroll_delay_seconds": 2,
        "selenium_max_scroll_attempts": 100,
        "selenium_wait_timeout_seconds": 20,
        "selenium_user_data_dir": None,
        "analysis_batch_size": 20,
        "prompt_version": "v1",
        "page_size": 20,
        "show_raw_payload": False,
    }
    values.update(overrides)
    return Settings(**values)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self.payload


class FakeHttpSession:
    def __init__(self, response):
        self.response = response
        self.last_request = None

    def get(self, url, **kwargs):
        self.last_request = (url, kwargs)
        return self.response


def test_google_places_maps_official_review_payload(tmp_path):
    payload = {
        "id": "ChIJ-real-place",
        "reviews": [
            {
                "name": "places/ChIJ-real-place/reviews/review-1",
                "originalText": {
                    "text": "Pelayanan dokter sangat baik.",
                    "languageCode": "id",
                },
                "text": {
                    "text": "The doctor's service was excellent.",
                    "languageCode": "en",
                },
                "rating": 5,
                "authorAttribution": {"displayName": "Andi"},
                "publishTime": "2026-06-19T09:00:00Z",
            }
        ],
    }
    http = FakeHttpSession(FakeResponse(payload))
    client = GooglePlacesClient(make_settings(tmp_path), http_session=http)
    location = SimpleNamespace(external_place_id="ChIJ-real-place")

    reviews = client.fetch_reviews(location, limit=50)

    assert len(reviews) == 1
    assert reviews[0]["source"] == "google_places"
    assert reviews[0]["external_review_id"].endswith("/reviews/review-1")
    assert reviews[0]["reviewer_name"] == "Andi"
    assert reviews[0]["review_text"] == "Pelayanan dokter sangat baik."
    assert reviews[0]["language"] == "id"
    _, request = http.last_request
    assert request["headers"]["X-Goog-FieldMask"] == (
        "id,displayName,rating,userRatingCount,reviews"
    )
    assert request["params"] == {"languageCode": "id", "regionCode": "ID"}


def test_google_places_marks_rate_limit_as_retriable(tmp_path):
    response = FakeResponse(
        {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded.",
            }
        },
        status_code=429,
    )
    client = GooglePlacesClient(
        make_settings(tmp_path), http_session=FakeHttpSession(response)
    )

    try:
        client.fetch_reviews(SimpleNamespace(external_place_id="place-1"))
    except ReviewSourceError as exc:
        assert exc.retriable is True
        assert "Quota exceeded" in str(exc)
    else:
        raise AssertionError("Expected ReviewSourceError")


class FakeGeminiModels:
    def __init__(self):
        self.last_call = None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(
            parsed={
                "sentiment": "negative",
                "sentiment_score": 0.91,
                "issue_category": "waiting_time",
                "urgency": "medium",
                "summary": "Pasien mengeluhkan antrean yang lama.",
                "recommended_action": "Evaluasi kapasitas layanan pada jam ramai.",
                "keywords": ["antrean", "lama"],
                "is_potential_viral": False,
                "is_patient_safety_issue": False,
            },
            text=None,
        )


def test_gemini_uses_structured_output_schema(tmp_path):
    models = FakeGeminiModels()
    sdk = SimpleNamespace(models=models)
    client = GeminiClient(make_settings(tmp_path), sdk_client=sdk)

    result = client.analyze_review(
        {
            "rating": 2,
            "reviewer_name": "Budi",
            "review_time": "2026-06-19T09:00:00Z",
            "review_text": "Antrean terlalu lama.",
        }
    )

    assert result["sentiment"] == "negative"
    assert result["issue_category"] == "waiting_time"
    assert models.last_call["model"] == "gemini-2.5-flash"
    config = models.last_call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["type"] == "object"
