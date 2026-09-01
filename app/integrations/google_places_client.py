from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from app.config import Settings
from app.db.models import Location
from app.integrations.review_source_client import ReviewSourceClient, ReviewSourceError


logger = logging.getLogger(__name__)


class GooglePlacesClient(ReviewSourceClient):
    base_url = "https://places.googleapis.com/v1/places"
    maximum_reviews = 5

    def __init__(
        self, settings: Settings, http_session: requests.Session | None = None
    ):
        self.settings = settings
        self.http_session = http_session or requests.Session()

    def fetch_reviews(self, location: Location, limit: int = 50, **kwargs) -> list[dict]:
        if not self.settings.google_maps_api_key:
            raise ReviewSourceError(
                "Review source API key is missing. Please check your .env configuration."
            )
        place_id = (location.external_place_id or "").strip()
        if not place_id:
            raise ReviewSourceError("External Place ID is required.")

        url = f"{self.base_url}/{quote(place_id, safe='')}"
        headers = {
            "Accept": "application/json",
            "X-Goog-Api-Key": self.settings.google_maps_api_key,
            "X-Goog-FieldMask": (
                "id,displayName,rating,userRatingCount,reviews"
            ),
        }
        params = {}
        if self.settings.google_places_language_code:
            params["languageCode"] = self.settings.google_places_language_code
        if self.settings.google_places_region_code:
            params["regionCode"] = self.settings.google_places_region_code

        try:
            response = self.http_session.get(
                url,
                headers=headers,
                params=params,
                timeout=self.settings.fetch_timeout_seconds,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise ReviewSourceError(
                f"Google Places request failed: {exc}", retriable=True
            ) from exc
        except requests.RequestException as exc:
            raise ReviewSourceError(
                f"Google Places request failed: {exc}"
            ) from exc

        if not response.ok:
            message = self._error_message(response)
            retriable = response.status_code in {408, 429, 500, 502, 503, 504}
            raise ReviewSourceError(message, retriable=retriable)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ReviewSourceError(
                "Google Places returned an invalid JSON response."
            ) from exc

        reviews = payload.get("reviews") or []
        if not reviews and payload.get("userRatingCount"):
            place_name = (payload.get("displayName") or {}).get("text") or place_id
            logger.warning(
                "Google Places returned no review objects for %s despite "
                "userRatingCount=%s. The official API may omit reviews for "
                "this place.",
                place_name,
                payload["userRatingCount"],
            )
        effective_limit = min(max(0, limit), self.maximum_reviews)
        return [
            self._normalize_google_review(review, place_id)
            for review in reviews[:effective_limit]
        ]

    @staticmethod
    def _normalize_google_review(review: dict, place_id: str) -> dict:
        original_text = review.get("originalText") or {}
        localized_text = review.get("text") or {}
        selected_text = original_text or localized_text
        author = review.get("authorAttribution") or {}
        return {
            "source": "google_places",
            "external_place_id": place_id,
            "external_review_id": review.get("name"),
            "reviewer_name": author.get("displayName") or "Anonymous",
            "rating": review.get("rating"),
            "review_text": selected_text.get("text") or "",
            "review_time": review.get("publishTime"),
            "language": selected_text.get("languageCode") or "unknown",
            "raw_payload": review,
        }

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        default = f"Google Places API error (HTTP {response.status_code})."
        try:
            payload = response.json()
        except ValueError:
            return default
        error = payload.get("error") or {}
        message = error.get("message")
        status = error.get("status")
        if message and status:
            return f"Google Places API error [{status}]: {message}"
        return str(message or default)
