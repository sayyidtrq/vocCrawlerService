from hashlib import sha256


def _hash_value(value) -> str:
    return " ".join(str(value or "").split())


def _sha256_parts(parts: list[object]) -> str:
    return sha256(
        "|".join(_hash_value(part) for part in parts).encode("utf-8")
    ).hexdigest()


def generate_review_hash(review: dict) -> str:
    return _sha256_parts(
        [
            review.get("source"),
            review.get("external_place_id"),
            review.get("external_review_id"),
            review.get("reviewer_name"),
            review.get("rating"),
            review.get("review_text"),
            review.get("review_time"),
        ]
    )


def generate_selenium_review_hash(review: dict) -> str:
    external_review_id = _hash_value(review.get("external_review_id"))
    if external_review_id:
        return _sha256_parts(
            [
                review.get("source"),
                review.get("location_id"),
                external_review_id,
            ]
        )
    return _sha256_parts(
        [
            review.get("source"),
            review.get("location_id"),
            review.get("reviewer_profile_url"),
            review.get("reviewer_name"),
            review.get("rating"),
            review.get("review_text"),
            review.get("review_time"),
        ]
    )
