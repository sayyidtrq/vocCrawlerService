"""Register OneBox sites as tenants and manage the token OneBox uses for each."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import ApiClient, Company, WorklistSyncState
from app.db.session import get_session_factory
from app.services.api_client_service import ApiClientService, IssuedServiceToken, _secret_hash

# Token yang dipegang OneBox untuk satu tenant. Nama ini yang membedakannya dari
# token lain milik company yang sama (mis. yang diterbitkan lewat CLI), jadi
# rotasi dari OneBox tidak pernah menyentuh token yang bukan miliknya.
TENANT_TOKEN_NAME = "onebox-tenant"
TENANT_TOKEN_SCOPES = (
    "analysis:write",
    "crawl:enqueue",
    "crawl:read",
    "reviews:read",
    "worklist:write",
)
DEFAULT_ROTATION_OVERLAP_HOURS = 24
MAX_ROTATION_OVERLAP_HOURS = 168


class TenantNotFound(LookupError):
    """No company is linked to the requested OneBox site."""


def new_provisioning_key() -> str:
    return "vocprov_" + secrets.token_urlsafe(32)


def provisioning_key_hash(key: str, pepper: str) -> str:
    return _secret_hash(key, pepper)


@dataclass(frozen=True)
class TenantView:
    """Keadaan tenant untuk OneBox. Tidak pernah memuat token atau hash-nya."""

    company_id: int
    site_id: int
    site_name: str
    is_active: bool
    deactivated_at: datetime | None
    worklist_snapshot_version: int | None
    worklist_applied_at: datetime | None
    worklist_items: int
    worklist_last_error: str | None
    token_key_id: str | None
    token_last_used_at: datetime | None
    token_expires_at: datetime | None


@dataclass(frozen=True)
class RegisteredTenant:
    view: TenantView
    created: bool
    token: IssuedServiceToken | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _validated_site_id(site_id: object) -> int:
    if isinstance(site_id, bool) or not isinstance(site_id, int) or site_id < 1:
        raise ValueError("site_id must be a positive integer")
    return site_id


def _validated_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("site_name is required")
    cleaned = name.strip()
    if len(cleaned) > 255:
        raise ValueError("site_name is too long")
    return cleaned


class TenantRegistryService:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        self._tokens = ApiClientService(self.session_factory, self.settings)

    def register(self, site_id: object, site_name: object) -> RegisteredTenant:
        """Daftarkan site, idempoten. Dipanggil OneBox saat paket VoC diaktifkan.

        Company dan token dibuat dalam satu transaksi. Memanggil ulang untuk site
        yang sama tidak membuat token kedua (token mentah hanya tampil sekali;
        yang hilang diganti lewat rotate_token). Site yang tidak aktif diaktifkan
        kembali, datanya utuh. Nama company tidak diubah oleh panggilan ulang.
        """
        site = _validated_site_id(site_id)
        name = _validated_name(site_name)
        with self.session_factory() as session:
            company = self._lock_company(session, site)
            created = False
            if company is None:
                company = Company(name=name, onebox_site_id=site)
                session.add(company)
                try:
                    session.flush()
                    created = True
                except IntegrityError:
                    # Pendaftaran bersamaan untuk site yang sama: yang kalah
                    # memakai company yang dibuat pemenangnya.
                    session.rollback()
                    company = self._lock_company(session, site)
                    if company is None:
                        raise
            elif not company.is_active:
                company.is_active = True
                company.deactivated_at = None

            issued = None
            if not self._active_tokens(session, company.id):
                issued = self._tokens.issue(
                    company.id,
                    TENANT_TOKEN_NAME,
                    list(TENANT_TOKEN_SCOPES),
                    session=session,
                )
            session.commit()
            view = self._view(session, company)
        return RegisteredTenant(view=view, created=created, token=issued)

    def get(self, site_id: object) -> TenantView:
        site = _validated_site_id(site_id)
        with self.session_factory() as session:
            company = self._require_company(session, site)
            return self._view(session, company)

    def update(
        self,
        site_id: object,
        *,
        active: bool | None = None,
        site_name: object | None = None,
    ) -> TenantView:
        """Ubah status/nama tenant.

        Hanya menandai tenant. Pembatalan job yang menunggu dan penolakan crawl
        baru untuk tenant nonaktif ditangani terpisah (MT-23).
        """
        site = _validated_site_id(site_id)
        name = _validated_name(site_name) if site_name is not None else None
        with self.session_factory() as session:
            company = self._require_company(session, site, lock=True)
            if name is not None:
                company.name = name
            if active is False and company.is_active:
                company.is_active = False
                company.deactivated_at = _now()
            elif active is True and not company.is_active:
                company.is_active = True
                company.deactivated_at = None
            session.commit()
            return self._view(session, company)

    def rotate_token(
        self, site_id: object, overlap_hours: int = DEFAULT_ROTATION_OVERLAP_HOURS
    ) -> IssuedServiceToken:
        """Terbitkan token baru; token lama berlaku `overlap_hours` lagi, lalu mati.

        Token lama yang sudah dijadwalkan mati lebih cepat tidak diperpanjang.
        Dengan overlap 0 token lama langsung dicabut.
        """
        site = _validated_site_id(site_id)
        if (
            isinstance(overlap_hours, bool)
            or not isinstance(overlap_hours, int)
            or not 0 <= overlap_hours <= MAX_ROTATION_OVERLAP_HOURS
        ):
            raise ValueError(
                f"overlap_hours must be between 0 and {MAX_ROTATION_OVERLAP_HOURS}"
            )
        with self.session_factory() as session:
            company = self._require_company(session, site, lock=True)
            previous = self._active_tokens(session, company.id)
            issued = self._tokens.issue(
                company.id, TENANT_TOKEN_NAME, list(TENANT_TOKEN_SCOPES), session=session
            )
            now = _now()
            for old in previous:
                if overlap_hours == 0:
                    old.is_active = False
                    old.revoked_at = now
                    continue
                cutoff = now + timedelta(hours=overlap_hours)
                if old.expires_at is None or _aware(old.expires_at) > cutoff:
                    old.expires_at = cutoff
            session.commit()
        return issued

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _lock_company(session: Session, site_id: int) -> Company | None:
        return session.scalar(
            select(Company).where(Company.onebox_site_id == site_id).with_for_update()
        )

    def _require_company(self, session: Session, site_id: int, lock: bool = False) -> Company:
        statement = select(Company).where(Company.onebox_site_id == site_id)
        if lock:
            statement = statement.with_for_update()
        company = session.scalar(statement)
        if company is None:
            raise TenantNotFound(f"No tenant is registered for OneBox site {site_id}.")
        return company

    @staticmethod
    def _active_tokens(session: Session, company_id: int) -> list[ApiClient]:
        now = _now()
        candidates = session.scalars(
            select(ApiClient)
            .where(
                ApiClient.company_id == company_id,
                ApiClient.name == TENANT_TOKEN_NAME,
                ApiClient.is_active.is_(True),
                ApiClient.revoked_at.is_(None),
            )
            .order_by(ApiClient.id)
        ).all()
        return [
            client
            for client in candidates
            if client.expires_at is None or _aware(client.expires_at) > now
        ]

    def _view(self, session: Session, company: Company) -> TenantView:
        state = session.scalar(
            select(WorklistSyncState).where(WorklistSyncState.company_id == company.id)
        )
        active = self._active_tokens(session, company.id)
        token = active[-1] if active else None
        return TenantView(
            company_id=company.id,
            site_id=int(company.onebox_site_id),
            site_name=company.name,
            is_active=bool(company.is_active),
            deactivated_at=company.deactivated_at,
            worklist_snapshot_version=state.snapshot_version if state else None,
            worklist_applied_at=state.applied_at if state else None,
            worklist_items=state.item_count if state else 0,
            worklist_last_error=state.last_error if state else None,
            token_key_id=token.key_id if token else None,
            token_last_used_at=token.last_used_at if token else None,
            token_expires_at=token.expires_at if token else None,
        )
