"""Apify-backed crawls with an independent, best-effort audit trail."""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.audit_models import AuditCrawlRun, AuditReview
from app.db.session import get_session_factory
from app.integrations.apify_client import ApifyAccountExhaustedError, ApifyClient
from app.integrations.apify_review_client import ApifyReviewClient
from app.integrations.apify_review_parser import ApifyReviewParser
from app.integrations.apify_token_pool import ApifyAllAccountsExhaustedError, ApifyTokenPool
from app.integrations.review_source_client import ReviewSourceError
from app.services.integration_review_service import IntegrationRequestError
from app.utils.date_parser import is_within_date_range, parse_datetime, parse_relative_datetime
from app.utils.hashing import generate_review_hash

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "READY": "running", "RUNNING": "running", "SUCCEEDED": "succeeded",
    "FAILED": "failed", "ABORTING": "aborted", "ABORTED": "aborted",
    "TIMING-OUT": "timed_out", "TIMED-OUT": "timed_out",
}
FINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
HANDLE_FIELDS = {
    "v", "run_id", "dataset_id", "token_index", "place_id", "site_id",
    "mode", "date_from", "date_to", "limit",
}


def encode_crawl_id(handle: dict) -> str:
    return base64.urlsafe_b64encode(
        # sort_keys: JSONB (PostgreSQL) reorders keys, and a replay must give the same id.
        json.dumps(handle, separators=(",", ":"), allow_nan=False, sort_keys=True).encode()
    ).decode().rstrip("=")


def decode_crawl_id(crawl_id: str, token_count: int) -> dict:
    try:
        if len(crawl_id) > 8192 or not re.fullmatch(r"[A-Za-z0-9_-]+", crawl_id):
            raise ValueError("Invalid encoding")
        handle = json.loads(base64.b64decode(
            crawl_id + "=" * (-len(crawl_id) % 4), altchars=b"-_", validate=True
        ))
        if not isinstance(handle, dict) or set(handle) != HANDLE_FIELDS:
            raise ValueError("Invalid fields")
        for field, lower, upper in (
            ("v", 1, 1), ("token_index", 0, token_count - 1),
            ("site_id", 0, None), ("limit", 1, 100000),
        ):
            value = handle[field]
            if type(value) is not int or value < lower or (upper is not None and value > upper):
                raise ValueError("Invalid integer")
        for field, length in (("run_id", 64), ("dataset_id", 255), ("place_id", 255)):
            if not isinstance(handle[field], str) or not 1 <= len(handle[field]) <= length:
                raise ValueError("Invalid identifier")
        if not isinstance(handle["mode"], str) or handle["mode"] not in {"backfill", "delta", "range"}:
            raise ValueError("Invalid mode")
        dates = {}
        for field in ("date_from", "date_to"):
            value = handle[field]
            if value is None:
                dates[field] = None
            else:
                if not isinstance(value, str):
                    raise ValueError("Invalid date")
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError("Missing timezone")
                dates[field] = parsed
        if handle["mode"] == "range":
            if dates["date_from"] is None or dates["date_to"] is None or dates["date_from"] > dates["date_to"]:
                raise ValueError("Invalid range")
        elif dates["date_to"] is not None:
            raise ValueError("Unexpected date_to")
        return handle
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise IntegrationRequestError(
            400, "INVALID_CRAWL_ID", "Invalid crawl id."
        ) from exc


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _apify_error(exc: Exception, *, polling: bool = False) -> IntegrationRequestError:
    if not polling and isinstance(exc, ApifyAllAccountsExhaustedError):
        return IntegrationRequestError(503, "APIFY_ACCOUNTS_EXHAUSTED", "All Apify accounts are exhausted.")
    if isinstance(exc, ReviewSourceError):
        if exc.code == "APIFY_RATE_LIMITED":
            return IntegrationRequestError(429, "APIFY_CONCURRENCY_LIMIT", "Apify concurrency or rate limit reached.")
        # The existing client exposes HTTP failures as a code and message only.
        if polling and exc.code == "APIFY_HTTP_ERROR" and any(
            term in str(exc).lower() for term in (
                "404", "401", "403", "not found", "does not exist",
                "not valid", "invalid token", "unauthorized", "not have permission",
            )
        ):
            return IntegrationRequestError(404, "CRAWL_NOT_FOUND", "Crawl not found.")
    return IntegrationRequestError(502, "APIFY_RUN_FAILED", "Apify crawl request failed.")


class StatelessCrawlService:
    def __init__(
        self, settings: Settings, *, apify_client=None, token_pool=None,
        session_factory=None,
    ):
        self.settings = settings
        self.apify_client = apify_client if apify_client is not None else ApifyClient(settings)
        self.token_pool = token_pool if token_pool is not None else ApifyTokenPool(
            settings.apify_api_tokens, redis_url=settings.redis_url,
            exhausted_ttl_seconds=settings.apify_account_exhausted_ttl_seconds,
        )
        self.token_count = len([token for token in settings.apify_api_tokens if token.strip()])
        self.session_factory = session_factory if session_factory is not None else lambda: get_session_factory()()

    def _start_run(self, place_id: str, params: dict) -> dict:
        actor_input = ApifyReviewClient._actor_input(
            place_id, params["max_reviews"], params["sort_by"], parse_datetime(params["date_from"])
        )
        for _ in range(self.token_count):
            token = self.token_pool.current()
            token_index = self.token_pool.current_index
            try:
                run_id, dataset_id = self.apify_client.start_run(
                    self.settings.apify_actor_id, actor_input, token=token
                )
                return {
                    "v": 1, "run_id": run_id, "dataset_id": dataset_id,
                    "token_index": token_index, "place_id": place_id,
                    "site_id": params["site_id"], "mode": params["mode"],
                    "date_from": params["date_from"], "date_to": params["date_to"],
                    "limit": params["max_reviews"],
                }
            except ApifyAccountExhaustedError:
                self.token_pool.mark_exhausted(token_index)
                if self.token_pool.rotate() is None:
                    break
        raise ApifyAllAccountsExhaustedError("All configured Apify accounts are exhausted.")

    def _replay_handles(self, site_id: int, key: str | None) -> dict:
        if key is None:
            return {}
        try:
            with self.session_factory() as session:
                rows = session.scalars(select(AuditCrawlRun).where(
                    AuditCrawlRun.site_id == site_id, AuditCrawlRun.idempotency_key == key
                )).all()
                return {row.place_id: row.handle for row in rows}
        except Exception as exc:
            logger.warning("V2 audit replay lookup failed: %s", exc)
            return {}

    @staticmethod
    def _started(handle: dict) -> dict:
        return {
            "place_id": handle["place_id"], "crawl_id": encode_crawl_id(handle),
            "run_id": handle["run_id"], "status": "started", "error": None,
        }

    def start_crawls(self, params: dict, idempotency_key: str | None = None) -> dict:
        stored = self._replay_handles(params["site_id"], idempotency_key)
        replay = all(target["place_id"] in stored for target in params["targets"])
        runs, errors = [], []
        for target in params["targets"]:
            place_id = target["place_id"]
            if place_id in stored:
                runs.append(self._started(stored[place_id]))
                continue
            try:
                handle = self._start_run(place_id, params)
            except Exception as exc:
                error = _apify_error(exc)
                errors.append(error)
                runs.append({
                    "place_id": place_id, "crawl_id": None, "run_id": None,
                    "status": "failed", "error": {"code": error.code, "message": error.message},
                })
                continue
            runs.append(self._started(handle))
            options = {key: value for key, value in params.items() if key not in {"targets", "site_id"}}
            options["place_id"] = place_id
            self._write_audit(lambda session: self._upsert_run(
                session, handle, params=options, idempotency_key=idempotency_key
            ))
        if not any(run["status"] == "started" for run in runs):
            # Prefer actionable capacity/credit failures over a generic upstream failure.
            raise min(errors, key=lambda error: {429: 0, 503: 1, 502: 2}[error.status_code])
        return {"idempotent_replay": replay, "runs": runs}

    @staticmethod
    def _normalize_review(item: dict, place_id: str) -> dict:
        parsed = ApifyReviewParser.parse_review(item)
        review_time = parse_datetime(parsed["review_time"])
        if review_time is None and parsed["review_relative_time"] and parsed["scraped_at"]:
            review_time = parse_relative_datetime(
                parsed["review_relative_time"], parse_datetime(parsed["scraped_at"])
            ) if parse_datetime(parsed["scraped_at"]) is not None else None
        try:
            rating = int(parsed["rating"]) if parsed["rating"] not in (None, "") else None
        except (ValueError, TypeError):
            rating = None
        if rating is not None and not 1 <= rating <= 5:
            rating = None
        review = {
            key: parsed[key] for key in (
                "source", "external_review_id", "reviewer_profile_url", "review_url",
                "review_photo_urls", "review_time_precision", "is_edited", "owner_response_text",
            )
        }
        review.update(
            external_place_id=place_id, reviewer_name=str(parsed["reviewer_name"] or "Anonymous").strip(),
            rating=rating, review_text=str(parsed["review_text"] or ""), review_time=review_time,
            edited_at=parse_datetime(parsed["edited_at"]),
            owner_response_time=parse_datetime(parsed["owner_response_time"]),
            date_approximate=parsed["review_time_precision"] in {"week", "month", "year"},
        )
        review["review_hash"] = generate_review_hash(review)
        for field in ("review_time", "edited_at", "owner_response_time"):
            value = _utc(review[field])
            review[field] = value.isoformat().replace("+00:00", "Z") if value is not None else None
        return review

    def get_crawl(self, crawl_id: str, *, cursor: str | None = None, limit: int = 100) -> dict:
        handle = decode_crawl_id(crawl_id, self.token_count)
        if cursor is not None and not re.fullmatch(r"[0-9]+", cursor):
            raise IntegrationRequestError(400, "INVALID_PARAMETER", "Cursor must contain digits only.")
        try:
            offset = int(cursor) if cursor is not None else 0
        except ValueError as exc:
            raise IntegrationRequestError(400, "INVALID_PARAMETER", "Cursor is too large.") from exc
        try:
            token = self.token_pool.token_at(handle["token_index"])
            apify_status = self.apify_client.get_run_status_once(handle["run_id"], token=token).upper()
            items = self.apify_client.get_dataset_items(handle["dataset_id"], token=token, offset=offset, limit=limit)
            count = self.apify_client.dataset_item_count(handle["dataset_id"], token=token)
        except Exception as exc:
            raise _apify_error(exc, polling=True) from exc
        reviews, seen = [], set()
        for item in items:
            review = self._normalize_review(item, handle["place_id"])
            if review["review_hash"] in seen:
                continue
            seen.add(review["review_hash"])
            if handle["mode"] == "range" and not is_within_date_range(
                parse_datetime(review["review_time"]), parse_datetime(handle["date_from"]), parse_datetime(handle["date_to"])
            ):
                continue
            reviews.append(review)
        next_offset = offset + len(items)
        at_end = next_offset >= count if count is not None else len(items) < limit
        final = apify_status in FINAL_STATUSES
        done = final and at_end
        data = {
            "crawl_id": crawl_id, "run_id": handle["run_id"], "place_id": handle["place_id"],
            "status": STATUS_MAP.get(apify_status, "unknown"), "fetched_so_far": count,
            "reviews": reviews, "next_cursor": None if done else str(next_offset), "done": done,
        }
        now = datetime.now(timezone.utc)
        for review in reviews:
            self._write_audit(lambda session: self._upsert_review(session, handle, review, now))
        self._write_audit(lambda session: self._upsert_run(
            session, handle, page=data, items_seen=next_offset, final=final, now=now
        ))
        return data

    def _write_audit(self, operation) -> None:
        for attempt in range(2):
            try:
                with self.session_factory() as session:
                    operation(session)
                    session.commit()
                return
            except IntegrityError as exc:
                logger.warning("V2 audit write conflict%s: %s", "; retrying" if attempt == 0 else "", exc)
            except Exception as exc:
                logger.warning("V2 audit write failed: %s", exc)
                return

    @staticmethod
    def _upsert_run(
        session, handle: dict, *, params=None, idempotency_key=None, page=None,
        items_seen=0, final=False, now=None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        run = session.scalar(select(AuditCrawlRun).where(
            AuditCrawlRun.run_id == handle["run_id"]
        ).with_for_update())
        if run is None:
            run = AuditCrawlRun(
                run_id=handle["run_id"], site_id=handle["site_id"], place_id=handle["place_id"],
                mode=handle["mode"], handle=handle, idempotency_key=idempotency_key,
                params=params if params is not None else {
                    "place_id": handle["place_id"], "mode": handle["mode"],
                    "date_from": handle["date_from"], "date_to": handle["date_to"], "max_reviews": handle["limit"],
                },
                status="started", fetched_count=0, started_at=now, created_at=now,
            )
            session.add(run)
        if page is not None:
            run.status = page["status"]
            run.fetched_count = max(run.fetched_count, page["fetched_so_far"] or items_seen)
            run.last_polled_at = now
            if final and run.finished_at is None:
                run.finished_at = now

    @staticmethod
    def _upsert_review(session, handle: dict, review: dict, now: datetime) -> None:
        row = session.scalar(select(AuditReview).where(
            AuditReview.site_id == handle["site_id"], AuditReview.review_hash == review["review_hash"]
        ).with_for_update())
        if row is None:
            row = AuditReview(
                site_id=handle["site_id"], place_id=handle["place_id"], review_hash=review["review_hash"],
                first_run_id=handle["run_id"], first_seen_at=now, seen_count=1,
            )
            session.add(row)
        elif row.last_run_id != handle["run_id"]:
            row.seen_count += 1
        row.payload = review
        row.review_time = parse_datetime(review["review_time"])
        row.last_run_id = handle["run_id"]
        row.last_seen_at = now
