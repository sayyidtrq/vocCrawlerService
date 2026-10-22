"""Industry taxonomy delivered by OneBox: storage, lookup and result normalisation.

OneBox owns the taxonomy; the Crawler only caches the snapshots it is sent and
never invents one. A location without a snapshot behaves exactly as before,
through the built-in legacy snapshot below.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaxonomySnapshot

logger = logging.getLogger(__name__)

LEGACY_KEY = "legacy"
# Used when a pack leaves a tag threshold and min_confidence unset (0.0).
DEFAULT_TAG_THRESHOLD = 0.5
MAX_TAGS_CAP = 10
# What the review says about ONE aspect (a review can praise one and criticise another).
TAG_SENTIMENTS = ("positive", "negative", "neutral", "mixed")
REQUIRED_SLUGS = ("lainnya", "pujian_umum")

# The vocabulary this build shipped with, kept as a constant (not a file) so it
# cannot be lost: locations OneBox has not given a taxonomy keep this behaviour.
LEGACY_CATEGORIES = (
    "product_quality",
    "service_quality",
    "professional_service",
    "staff_service",
    "administration",
    "waiting_time",
    "cleanliness",
    "facility",
    "parking",
    "accessibility",
    "price_value",
    "billing_payment",
    "availability",
    "delivery_fulfillment",
    "customer_service",
    "booking_ordering",
    "digital_experience",
    "safety_security",
    "food_beverage",
    "general_praise",
    "other",
)
LEGACY_SNAPSHOT = {
    "key": LEGACY_KEY,
    "version": LEGACY_KEY,
    "industry": LEGACY_KEY,
    "aspects": [{"slug": slug, "criteria": ""} for slug in LEGACY_CATEGORIES],
    "risk_flags": [],
    "aliases": {},
    "absa_map": {},
}


def _slug(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


class Taxonomy:
    """Read-only view over one snapshot body (an item of OneBox ``taxonomies``)."""

    def __init__(self, body: dict):
        self.body = body
        self.key = str(body.get("key") or "")
        self.version = str(body.get("version") or "")
        self.industry = str(body.get("industry") or "")
        self.legacy = self.key == LEGACY_KEY
        self.aspects: dict[str, dict] = {a["slug"]: a for a in body.get("aspects", [])}
        self.slugs = list(self.aspects)
        self.aliases: dict[str, str] = dict(body.get("aliases") or {})
        self.risk_flags: list[dict] = list(body.get("risk_flags") or [])
        self.absa_map: dict[str, str] = dict(body.get("absa_map") or {})
        self.min_confidence = _clamp(body.get("min_confidence"), 0.0, 1.0, 0.0)
        self.persona = str(body.get("persona") or "")
        tagging = body.get("tagging") if isinstance(body.get("tagging"), dict) else {}
        self.tagging_enabled = bool(tagging.get("enabled"))
        self.max_tags = int(_clamp(tagging.get("max_tags"), 1, MAX_TAGS_CAP, 5))
        self.tag_thresholds = dict(tagging.get("thresholds") or {})
        self.fallback = "lainnya" if "lainnya" in self.aspects else "other"
        self.praise = "pujian_umum" if "pujian_umum" in self.aspects else "general_praise"

    @classmethod
    def legacy_taxonomy(cls) -> "Taxonomy":
        return cls(LEGACY_SNAPSHOT)

    def canonical(self, value: Any) -> str:
        slug = _slug(value)
        return self.aliases.get(slug, slug)

    def category(self, value: Any) -> tuple[str, bool]:
        """Slug in this taxonomy, and whether the model's answer had to be replaced."""
        slug = self.canonical(value)
        if slug in self.aspects:
            return slug, False
        return self.fallback, True

    def flags(self, raw: Any) -> dict[str, bool]:
        raw = raw if isinstance(raw, dict) else {}
        return {f["slug"]: _to_bool(raw.get(f["slug"])) for f in self.risk_flags}

    def is_safety(self, flags: dict[str, bool]) -> bool:
        return any(flags.get(f["slug"]) for f in self.risk_flags if f.get("severity") == "critical")

    def is_viral(self, flags: dict[str, bool]) -> bool:
        return any(
            flags.get(f["slug"])
            for f in self.risk_flags
            if f.get("legacy_field") == "is_potential_viral"
        )

    def threshold(self, slug: str) -> float:
        value = self.tag_thresholds.get(slug)
        if value is None:
            return self.min_confidence if self.min_confidence > 0 else DEFAULT_TAG_THRESHOLD
        return _clamp(value, 0.0, 1.0, DEFAULT_TAG_THRESHOLD)

    def pick_tags(self, probabilities: dict[str, float]) -> list[dict]:
        """Aspects whose probability clears their threshold, most likely first."""
        passing = [
            {"slug": slug, "p": round(float(p), 4)}
            for slug, p in probabilities.items()
            if slug in self.aspects and float(p) >= self.threshold(slug)
        ]
        return sorted(passing, key=lambda tag: -tag["p"])[: self.max_tags]

    def add_primary(self, tags: list[dict], category: str, p: float | None) -> list[dict]:
        """The primary category is always a tag (at its own confidence), except the fallback next to real tags."""
        if category in {tag["slug"] for tag in tags} or (category == self.fallback and tags):
            return tags
        return [*tags, {"slug": category, "p": p}]

    def clean_tags(self, raw: Any) -> list[dict]:
        """Closed-list tags: canonical slugs only, no duplicates, best probability kept.

        Each tag carries the sentiment the review expresses about that aspect (None when the
        engine gave none); duplicates that disagree become `mixed`."""
        best: dict[str, dict] = {}
        seen: dict[str, set[str]] = {}
        for item in raw if isinstance(raw, list) else []:
            slug = self.canonical(item.get("slug") if isinstance(item, dict) else item)
            if slug not in self.aspects:
                continue
            p = item.get("p") if isinstance(item, dict) else None
            p = round(_clamp(p, 0.0, 1.0, -1.0), 4) if p is not None else None
            p = None if p is not None and p < 0 else p
            tag_sentiment = tag_sentiment_of(item.get("sentiment") if isinstance(item, dict) else None)
            if tag_sentiment:
                seen.setdefault(slug, set()).add(tag_sentiment)
            current = best.get(slug)
            if current is None or (p is not None and (current["p"] is None or p > current["p"])):
                best[slug] = {"slug": slug, "p": p, "sentiment": None}
        for slug, tag in best.items():
            tag["sentiment"] = merge_tag_sentiments(seen.get(slug, ()))
        return _rank(list(best.values()))

    def finalize_tags(self, raw: Any, primary: str, sentiment: str) -> list[dict]:
        """Part 3 rules: closed list, `lainnya` only when nothing else passed (praise when
        positive), the primary category always present, at most max_tags, and every tag with
        a sentiment (the review's own when the engine gave none for that aspect)."""
        tags = self.clean_tags(raw)
        if not tags:
            tags = [{"slug": self.praise if sentiment == "positive" else self.fallback, "p": None, "sentiment": None}]
        # `lainnya` only when nothing else passed.
        tags = [tag for tag in tags if tag["slug"] != self.fallback] or tags
        present = {tag["slug"] for tag in tags}
        if primary not in present and not (primary == self.fallback and tags):
            tags.append({"slug": primary, "p": None, "sentiment": None})
        tags = _rank(tags)
        keep = tags[: self.max_tags]
        primary_tag = next((tag for tag in tags if tag["slug"] == primary), None)
        if primary_tag is not None and primary_tag not in keep:
            keep[-1] = primary_tag  # the cap never pushes the primary category out
        default = tag_sentiment_of(sentiment) or "neutral"
        for tag in keep:
            tag["sentiment"] = tag.get("sentiment") or default
        return keep


def tag_sentiment_of(value: Any) -> str | None:
    """A valid per-aspect sentiment, or None."""
    value = str(value or "").strip().lower()
    return value if value in TAG_SENTIMENTS else None


def merge_tag_sentiments(values: Iterable[str]) -> str | None:
    """One sentiment for an aspect that was judged more than once (several ABSA hits, duplicates)."""
    found = {v for v in (tag_sentiment_of(v) for v in values) if v}
    if "mixed" in found or {"positive", "negative"} <= found:
        return "mixed"
    for value in ("negative", "positive", "neutral"):
        if value in found:
            return value
    return None


def _rank(tags: list[dict]) -> list[dict]:
    return sorted(tags, key=lambda tag: -(tag["p"] if tag["p"] is not None else -1.0))


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def validate_body(key: str, body: Any) -> dict | None:
    """The snapshot as stored, or None when it is not a usable taxonomy."""
    if not isinstance(body, dict):
        return None
    aspects = body.get("aspects")
    if not isinstance(aspects, list) or not aspects:
        return None
    slugs = []
    for aspect in aspects:
        if not isinstance(aspect, dict) or not _slug(aspect.get("slug")):
            return None
        slugs.append(aspect["slug"])
    if len(set(slugs)) != len(slugs) or any(slug not in slugs for slug in REQUIRED_SLUGS):
        return None
    return {**body, "key": key, "version": str(body.get("version") or key.rpartition(":")[2])[:16]}


def upsert_snapshots(session: Session, company_id: int, taxonomies: Any) -> int:
    """Store every valid snapshot of a worklist; invalid ones are skipped, never fatal."""
    if not isinstance(taxonomies, dict):
        return 0
    stored = 0
    now = datetime.now(timezone.utc)
    for key, raw in taxonomies.items():
        body = validate_body(str(key), raw)
        if body is None or len(str(key)) > 80:
            logger.warning("taxonomy.snapshot.invalid key=%s", key)
            continue
        row = session.scalar(
            select(TaxonomySnapshot).where(
                TaxonomySnapshot.company_id == company_id, TaxonomySnapshot.key == str(key)
            )
        )
        if row is None:
            row = TaxonomySnapshot(company_id=company_id, key=str(key), version=body["version"], body=body)
            session.add(row)
        # Replaced even when the version is unchanged: the tagging config sits
        # outside the version hash and can change on its own.
        row.version, row.body, row.received_at = body["version"], body, now
        stored += 1
    return stored


def company_aliases(session: Session, company_id: int | None) -> dict[str, str]:
    """Legacy slug -> canonical slug across every snapshot the company received.

    OneBox keeps one global alias table (a slug has one meaning platform-wide),
    so snapshots never disagree and a plain union is enough.
    """
    statement = select(TaxonomySnapshot.body)
    if company_id is not None:
        statement = statement.where(TaxonomySnapshot.company_id == company_id)
    merged: dict[str, str] = {}
    for body in session.scalars(statement):
        merged.update((body or {}).get("aliases") or {})
    return merged


def merge_issue_counts(
    rows: Iterable[tuple], aliases: dict[str, str], limit: int = 5
) -> list[tuple]:
    """Add up counts of slugs that mean the same thing (doctor_service + pelayanan_dokter)."""
    merged: dict[str | None, int] = {}
    for slug, count in rows:
        key = aliases.get(slug, slug)
        merged[key] = merged.get(key, 0) + int(count or 0)
    ranked = sorted(merged.items(), key=lambda item: (-item[1], str(item[0] or "")))
    return ranked[:limit]


def load_taxonomies(
    session: Session, company_id: int | None, keys: Iterable[str]
) -> dict[str, Taxonomy]:
    wanted = {str(key) for key in keys if key}
    if not wanted:
        return {}
    statement = select(TaxonomySnapshot).where(TaxonomySnapshot.key.in_(wanted))
    if company_id is not None:
        statement = statement.where(TaxonomySnapshot.company_id == company_id)
    return {row.key: Taxonomy(row.body) for row in session.scalars(statement)}
