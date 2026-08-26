"""Issue and verify opaque service tokens for machine-to-machine callers."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import ApiClient, Company
from app.db.session import get_session_factory


class InvalidServiceToken(ValueError):
    """Internal auth failure; callers expose one generic 401 response."""


@dataclass(frozen=True)
class IssuedServiceToken:
    client: ApiClient
    token: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _secret_hash(secret: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _is_expired(value: datetime, now: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now


class ApiClientService:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()

    def issue(
        self,
        company_id: int,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> IssuedServiceToken:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("name is required")
        normalized_scopes = sorted(set(scopes or ["reviews:read"]))
        if not normalized_scopes:
            raise ValueError("at least one scope is required")

        key_id = secrets.token_urlsafe(12)
        secret = secrets.token_urlsafe(32)
        token = f"voc_{self.settings.app_env}_{key_id}.{secret}"
        client = ApiClient(
            company_id=company_id,
            name=normalized_name,
            key_id=key_id,
            secret_hash=_secret_hash(secret, self.settings.service_token_pepper),
            scopes=normalized_scopes,
            expires_at=expires_at,
        )

        with self.session_factory() as session:
            if session.get(Company, company_id) is None:
                raise ValueError(f"company_id {company_id} does not exist")
            session.add(client)
            session.commit()
            session.refresh(client)
        return IssuedServiceToken(client=client, token=token)

    def verify(self, token: str) -> ApiClient:
        key_id, secret = self._parse(token)
        with self.session_factory() as session:
            client = session.scalar(select(ApiClient).where(ApiClient.key_id == key_id))
            if client is None:
                raise InvalidServiceToken("invalid service token")

            now = _utc_now()
            if (
                not client.is_active
                or client.revoked_at is not None
                or (
                    client.expires_at is not None
                    and _is_expired(client.expires_at, now)
                )
            ):
                raise InvalidServiceToken("invalid service token")

            expected = _secret_hash(secret, self.settings.service_token_pepper)
            if not hmac.compare_digest(client.secret_hash, expected):
                raise InvalidServiceToken("invalid service token")

            # Keep usage metadata useful without adding a write to every pull.
            last_used = client.last_used_at
            if last_used is None or _is_expired(
                last_used + timedelta(minutes=5), now
            ):
                client.last_used_at = now
                session.commit()
            return client

    def revoke(self, key_id: str) -> ApiClient:
        with self.session_factory() as session:
            client = session.scalar(select(ApiClient).where(ApiClient.key_id == key_id))
            if client is None:
                raise ValueError("key_id not found")
            client.is_active = False
            client.revoked_at = _utc_now()
            session.commit()
            session.refresh(client)
            return client

    def grant_scopes(self, key_id: str, scopes: list[str]) -> ApiClient:
        """Add permissions without rotating or exposing the existing secret."""

        requested = {scope.strip() for scope in scopes if scope.strip()}
        if not requested:
            raise ValueError("at least one scope is required")

        with self.session_factory() as session:
            client = session.scalar(select(ApiClient).where(ApiClient.key_id == key_id))
            if client is None:
                raise ValueError("key_id not found")
            client.scopes = sorted(set(client.scopes or []) | requested)
            session.commit()
            session.refresh(client)
            return client

    def rotate(self, key_id: str, overlap_hours: int = 0) -> IssuedServiceToken:
        with self.session_factory() as session:
            old = session.scalar(select(ApiClient).where(ApiClient.key_id == key_id))
            if old is None:
                raise ValueError("key_id not found")
            company_id = old.company_id
            name = old.name
            scopes = list(old.scopes or [])
            expires_at = old.expires_at

        replacement = self.issue(company_id, name, scopes, expires_at)
        if overlap_hours <= 0:
            self.revoke(key_id)
        return replacement

    def list_clients(self, company_id: int | None = None) -> list[ApiClient]:
        with self.session_factory() as session:
            statement = select(ApiClient).order_by(ApiClient.id)
            if company_id is not None:
                statement = statement.where(ApiClient.company_id == company_id)
            return list(session.scalars(statement).all())

    def _parse(self, token: str) -> tuple[str, str]:
        if not isinstance(token, str) or not token.startswith("voc_"):
            raise InvalidServiceToken("invalid service token")
        try:
            prefix, secret = token.split(".", 1)
            _, environment, key_id = prefix.split("_", 2)
        except ValueError as exc:
            raise InvalidServiceToken("invalid service token") from exc

        if (
            environment != self.settings.app_env
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", key_id)
            or len(secret) < 32
        ):
            raise InvalidServiceToken("invalid service token")
        return key_id, secret
