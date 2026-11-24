from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "_mapping"):
        return to_jsonable(dict(value._mapping))
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def location_to_dict(location: Any) -> dict[str, Any]:
    return to_jsonable(
        {
            "id": location.id,
            "organization_name": location.organization_name,
            "branch_name": location.branch_name,
            "city": location.city,
            "address": location.address,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "source": location.source,
            "external_place_id": location.external_place_id,
            "google_maps_url": location.google_maps_url,
            "google_reviews_url": location.google_reviews_url,
            "target_review_count": location.target_review_count,
            "is_active": location.is_active,
            "created_at": location.created_at,
            "updated_at": location.updated_at,
        }
    )


def hide_raw_payload(review: dict[str, Any]) -> dict[str, Any]:
    output = dict(review)
    output.pop("raw_payload", None)
    return output
