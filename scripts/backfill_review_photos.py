"""Isi `review_photo_urls` / `review_url` baris lama dari `raw_payload` Apify.

Review yang disimpan sebelum normalizer membawa foto punya kolom kosong, tapi
item Apify aslinya utuh di `raw_payload`. Jalankan sekali setelah deploy fix
itu supaya tidak perlu menarik ulang (dan membayar) Apify.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit

from sqlalchemy import func, select

from app.db.models import Review
from app.db.session import get_db_session
from app.services.review_repository import backfill_missing_fields

BATCH = 500
FIELDS = ("review_url", "review_photo_urls")


def _valid_url(value) -> bool:
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def backfill(
    session, *, company_id=None, location_id=None, dry_run=False, photos_only=False
) -> dict:
    stats = {
        "scanned": 0, "updated": 0, "photos": 0,
        "photo_reviews": 0, "urls": 0, "invalid_payloads": 0,
    }
    fields = ("review_photo_urls",) if photos_only else FIELDS
    scope = []
    if company_id is not None:
        scope.append(Review.company_id == company_id)
    if location_id is not None:
        scope.append(Review.location_id == location_id)
    # Bound the scan so concurrent inserts cannot extend maintenance indefinitely.
    upper_id = session.scalar(select(func.max(Review.id)).where(*scope)) or 0
    # Ekspresi yang sama dengan jalur re-crawl (review_service.enrich).
    bump = (
        func.clock_timestamp()
        if session.get_bind().dialect.name == "postgresql"
        else datetime.now(timezone.utc)
    )
    last_id = 0
    while True:
        query = (
            select(Review)
            .where(*scope, Review.id > last_id, Review.id <= upper_id)
            .order_by(Review.id)
            .limit(BATCH)
            .execution_options(populate_existing=True)
        )
        if not dry_run:
            # Read current values under a lock before filling empty columns.
            query = query.with_for_update()
        rows = session.scalars(query).all()
        if not rows:
            return stats
        for review in rows:
            payload = review.raw_payload or {}
            if not isinstance(payload, dict):
                stats["invalid_payloads"] += 1
                continue
            photos = payload.get("review_photos_urls") or []
            url = None if photos_only else payload.get("review_url")
            invalid = False
            if not isinstance(photos, list) or not all(_valid_url(p) for p in photos):
                photos = []
                invalid = True
            if url is not None and url != "" and not _valid_url(url):
                url = None
                invalid = True
            stats["invalid_payloads"] += int(invalid)
            photos_added = not review.review_photo_urls and bool(photos)
            url_added = not review.review_url and bool(url)
            incoming = SimpleNamespace(
                review_url=url,
                review_photo_urls=photos,
            )
            if backfill_missing_fields(session, review, incoming, fields):
                # OneBox hanya menarik ulang baris yang sync_updated_at-nya maju.
                review.sync_updated_at = bump
                stats["updated"] += 1
                stats["photos"] += len(photos) if photos_added else 0
                stats["photo_reviews"] += int(photos_added)
                stats["urls"] += int(url_added)
        stats["scanned"] += len(rows)
        last_id = rows[-1].id
        session.rollback() if dry_run else session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--location-id", type=int, help="crawler locations.id")
    parser.add_argument("--dry-run", action="store_true", help="hitung saja, tanpa menulis")
    parser.add_argument("--photos-only", action="store_true", help="isi foto saja, tanpa link review")
    args = parser.parse_args()
    if args.company_id is None and not args.dry_run:
        parser.error("--company-id is required when writing")
    for name in ("company_id", "location_id"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    with get_db_session() as session:
        stats = backfill(
            session,
            company_id=args.company_id,
            location_id=args.location_id,
            dry_run=args.dry_run,
            photos_only=args.photos_only,
        )
    print(("DRY RUN " if args.dry_run else "") + " ".join(f"{k}={v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
