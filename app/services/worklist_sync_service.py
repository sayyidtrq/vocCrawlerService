from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings, resolve_onebox_base_url
from app.db.models import Company, Competitor, Location, WorklistSyncState
from app.db.session import get_session_factory
from app.integrations.onebox_worklist_client import (
    OneBoxAuthenticationError,
    OneBoxUnavailableError,
    OneBoxWorklistClient,
    OneBoxWorklistError,
)

logger = logging.getLogger(__name__)


class WorklistSyncError(RuntimeError):
    """The worklist could not be safely synchronized."""


@dataclass(frozen=True)
class WorklistSyncResult:
    status: str
    company_id: int
    site_id: int
    fetched: int = 0
    upserted: int = 0
    deactivated: int = 0
    cache_age_seconds: int | None = None
    last_success_at: str | None = None
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "company_id": self.company_id,
            "site_id": self.site_id,
            "fetched": self.fetched,
            "upserted": self.upserted,
            "deactivated": self.deactivated,
            "cache_age_seconds": self.cache_age_seconds,
            "last_success_at": self.last_success_at,
            "warning": self.warning,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_seconds(value: datetime | None) -> int | None:
    value = _utc(value)
    if value is None:
        return None
    return max(0, int((_now() - value).total_seconds()))


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_int(value: Any, field: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorklistSyncError(f"Worklist field {field} must be an integer.") from exc


def _target(value: Any) -> int:
    if value is None or value == "":
        return 100
    try:
        target = int(value)
    except (TypeError, ValueError) as exc:
        raise WorklistSyncError(
            "Worklist field target_review_count must be an integer."
        ) from exc
    if not 1 <= target <= 300:
        raise WorklistSyncError(
            "Worklist field target_review_count must be between 1 and 300."
        )
    return target


class WorklistSyncService:
    """Synchronizes OneBox's worklist into the local crawl target cache."""

    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: OneBoxWorklistClient | Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.company_id = company_id if company_id is not None else self.settings.onebox_company_id
        self.session_factory = session_factory or get_session_factory()
        self.client = client or OneBoxWorklistClient(self.settings)

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        try:
            base_url = resolve_onebox_base_url(settings)
        except ValueError:
            return False
        return all(
            value is not None and (not isinstance(value, str) or bool(value.strip()))
            for value in (
                base_url,
                settings.onebox_service_email,
                settings.onebox_service_password,
                settings.onebox_site_id,
                settings.onebox_company_id,
            )
        )

    def refresh(self) -> WorklistSyncResult:
        company_id = self._require_company_id()
        site_id = self._require_site_id()
        try:
            payload = self.client.get_worklist()
            items = self._validate_payload(payload, site_id)
            return self._apply(company_id, site_id, items)
        except OneBoxAuthenticationError as exc:
            self._record_error(company_id, site_id, str(exc))
            raise WorklistSyncError(
                "OneBox authentication failed. Check service account, site ID, and permissions."
            ) from exc
        except (OneBoxUnavailableError, OneBoxWorklistError) as exc:
            return self._fallback_or_raise(company_id, site_id, str(exc))
        except WorklistSyncError as exc:
            self._record_error(company_id, site_id, str(exc))
            raise

    def _require_company_id(self) -> int:
        if self.company_id is None:
            raise WorklistSyncError(
                "ONEBOX_COMPANY_ID is required; never infer a tenant from the worklist."
            )
        return int(self.company_id)

    def _require_site_id(self) -> int:
        if self.settings.onebox_site_id is None:
            raise WorklistSyncError("ONEBOX_SITE_ID is required.")
        return int(self.settings.onebox_site_id)

    def _validate_payload(self, payload: Any, site_id: int) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise WorklistSyncError("OneBox worklist must contain data[].")
        payload_site = payload.get("site_id")
        meta = payload.get("meta")
        if payload_site is None and isinstance(meta, dict):
            payload_site = meta.get("site_id")
        if payload_site is not None and _optional_int(payload_site, "site_id") != site_id:
            raise WorklistSyncError("OneBox worklist site_id does not match configuration.")

        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for index, raw in enumerate(payload["data"]):
            if not isinstance(raw, dict):
                raise WorklistSyncError(f"Worklist item {index} must be an object.")
            kind = str(raw.get("kind") or "").strip().lower()
            if kind not in {"location", "competitor"}:
                raise WorklistSyncError(
                    f"Worklist item {index} has unsupported kind; expected location or competitor."
                )
            external = str(raw.get("external_place_id") or "").strip()
            if not external:
                raise WorklistSyncError(
                    f"Worklist item {index} is missing external_place_id."
                )
            key = (kind, external)
            if key in seen:
                raise WorklistSyncError(f"Duplicate worklist item: {kind}/{external}.")
            seen.add(key)
            default_crawl = kind == "location"
            default_ingest = kind == "location"
            item = {
                "kind": kind,
                "external_place_id": external,
                "onebox_connection_id": _optional_int(
                    raw.get("onebox_connection_id", raw.get("connection_id")),
                    "onebox_connection_id",
                ),
                "onebox_location_id": _optional_int(
                    raw.get("onebox_location_id", raw.get("location_id")),
                    "onebox_location_id",
                ),
                "hospital_name": str(
                    raw.get("hospital_name") or raw.get("branch_name") or "Hospital"
                ).strip(),
                "branch_name": str(
                    raw.get("branch_name") or raw.get("name") or "Unnamed location"
                ).strip(),
                "city": str(raw.get("city") or "").strip() or None,
                "google_maps_url": str(raw.get("google_maps_url") or "").strip() or None,
                "google_reviews_url": str(raw.get("google_reviews_url") or "").strip() or None,
                "target_review_count": _target(raw.get("target_review_count")),
                "active": _bool(raw.get("active"), True),
                "crawl_enabled": _bool(raw.get("crawl_enabled"), default_crawl),
                "ingest_reviews": _bool(raw.get("ingest_reviews"), default_ingest),
                "is_mock": _bool(raw.get("mock", raw.get("is_mock")), False),
            }
            if not item["branch_name"]:
                raise WorklistSyncError(f"Worklist item {index} has no branch/name.")
            items.append(item)
        return items

    def _apply(
        self, company_id: int, site_id: int, items: list[dict[str, Any]]
    ) -> WorklistSyncResult:
        now = _now()
        location_keys = {
            item["external_place_id"] for item in items if item["kind"] == "location"
        }
        competitor_keys = {
            item["external_place_id"]
            for item in items
            if item["kind"] == "competitor"
        }
        upserted = 0
        deactivated = 0
        with self.session_factory() as session:
            if session.get(Company, company_id) is None:
                raise WorklistSyncError(f"Company {company_id} does not exist.")
            for item in items:
                if item["kind"] == "location":
                    entity = self._find_location(session, company_id, item["external_place_id"])
                    if entity is None:
                        entity = Location(
                            company_id=company_id,
                            source="onebox",
                            external_place_id=item["external_place_id"],
                            hospital_name=item["hospital_name"],
                            branch_name=item["branch_name"],
                        )
                        session.add(entity)
                    self._apply_location(entity, item, now)
                else:
                    entity = self._find_competitor(session, company_id, item["external_place_id"])
                    if entity is None:
                        entity = Competitor(
                            company_id=company_id,
                            source="onebox",
                            external_place_id=item["external_place_id"],
                            name=item["branch_name"],
                        )
                        session.add(entity)
                    self._apply_competitor(entity, item, now)
                upserted += 1
            managed_locations = session.scalars(
                select(Location).where(
                    Location.company_id == company_id,
                    Location.onebox_connection_id.is_not(None),
                )
            ).all()
            for entity in managed_locations:
                if entity.external_place_id not in location_keys:
                    if entity.is_active or entity.crawl_enabled:
                        deactivated += 1
                    entity.is_active = False
                    entity.crawl_enabled = False
                    entity.worklist_synced_at = now
            managed_competitors = session.scalars(
                select(Competitor).where(
                    Competitor.company_id == company_id,
                    Competitor.onebox_connection_id.is_not(None),
                )
            ).all()
            for entity in managed_competitors:
                if entity.external_place_id not in competitor_keys:
                    if entity.is_active or entity.crawl_enabled:
                        deactivated += 1
                    entity.is_active = False
                    entity.crawl_enabled = False
                    entity.worklist_synced_at = now
            state = session.scalar(
                select(WorklistSyncState).where(WorklistSyncState.company_id == company_id)
            )
            if state is None:
                state = WorklistSyncState(company_id=company_id, site_id=site_id)
                session.add(state)
            state.site_id = site_id
            state.last_attempt_at = now
            state.last_success_at = now
            state.last_error = None
            state.item_count = len(items)
            session.commit()
        return WorklistSyncResult(
            status="synced",
            company_id=company_id,
            site_id=site_id,
            fetched=len(items),
            upserted=upserted,
            deactivated=deactivated,
            cache_age_seconds=0,
            last_success_at=now.isoformat(),
        )

    @staticmethod
    def _find_location(session: Session, company_id: int, external: str) -> Location | None:
        entity = session.scalar(
            select(Location)
            .where(Location.company_id == company_id, Location.external_place_id == external)
            .order_by(Location.id)
        )
        if entity is not None:
            return entity
        conflict = session.scalar(
            select(Location).where(
                Location.source == "onebox", Location.external_place_id == external
            )
        )
        if conflict is not None and conflict.company_id != company_id:
            raise WorklistSyncError(
                "OneBox external_place_id is already owned by another company."
            )
        return None

    @staticmethod
    def _find_competitor(session: Session, company_id: int, external: str) -> Competitor | None:
        return session.scalar(
            select(Competitor)
            .where(
                Competitor.company_id == company_id,
                Competitor.external_place_id == external,
            )
            .order_by(Competitor.id)
        )

    @staticmethod
    def _apply_location(entity: Location, item: dict[str, Any], now: datetime) -> None:
        entity.source = "onebox"
        entity.external_place_id = item["external_place_id"]
        entity.hospital_name = item["hospital_name"]
        entity.branch_name = item["branch_name"]
        entity.city = item["city"]
        entity.google_maps_url = item["google_maps_url"]
        entity.google_reviews_url = item["google_reviews_url"]
        entity.target_review_count = item["target_review_count"]
        entity.onebox_connection_id = item["onebox_connection_id"]
        entity.onebox_location_id = item["onebox_location_id"]
        entity.crawl_enabled = item["crawl_enabled"]
        entity.ingest_reviews = item["ingest_reviews"]
        entity.is_mock = item["is_mock"]
        entity.is_active = item["active"]
        entity.worklist_synced_at = now

    @staticmethod
    def _apply_competitor(entity: Competitor, item: dict[str, Any], now: datetime) -> None:
        entity.source = "onebox"
        entity.external_place_id = item["external_place_id"]
        entity.name = item["branch_name"]
        entity.city = item["city"]
        entity.google_maps_url = item["google_maps_url"]
        entity.google_reviews_url = item["google_reviews_url"]
        entity.target_review_count = item["target_review_count"]
        entity.onebox_connection_id = item["onebox_connection_id"]
        entity.onebox_location_id = item["onebox_location_id"]
        entity.crawl_enabled = item["crawl_enabled"]
        entity.ingest_reviews = item["ingest_reviews"]
        entity.is_mock = item["is_mock"]
        entity.is_active = item["active"]
        entity.worklist_synced_at = now

    def _fallback_or_raise(self, company_id: int, site_id: int, error: str) -> WorklistSyncResult:
        self._record_error(company_id, site_id, error)
        with self.session_factory() as session:
            state = session.scalar(
                select(WorklistSyncState).where(WorklistSyncState.company_id == company_id)
            )
            if state is None or state.last_success_at is None:
                raise WorklistSyncError(
                    "OneBox worklist is unavailable and no successful local cache exists."
                )
            age = _age_seconds(state.last_success_at)
            stale = age is not None and age > self.settings.onebox_cache_stale_after_seconds
            warning = "Using cached worklist because OneBox is unavailable."
            if stale:
                warning += " Cache is older than the configured stale threshold."
            return WorklistSyncResult(
                status="cached",
                company_id=company_id,
                site_id=site_id,
                fetched=state.item_count,
                cache_age_seconds=age,
                last_success_at=_utc(state.last_success_at).isoformat(),
                warning=warning,
            )

    def _record_error(self, company_id: int, site_id: int, error: str) -> None:
        now = _now()
        with self.session_factory() as session:
            state = session.scalar(
                select(WorklistSyncState).where(WorklistSyncState.company_id == company_id)
            )
            if state is None:
                state = WorklistSyncState(company_id=company_id, site_id=site_id, item_count=0)
                session.add(state)
            state.site_id = site_id
            state.last_attempt_at = now
            state.last_error = error[:1000]
            session.commit()
        logger.warning(
            "OneBox worklist sync failed for company_id=%s site_id=%s: %s",
            company_id,
            site_id,
            error,
        )


