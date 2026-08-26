from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.service_auth as service_auth_module
from app.config import get_settings
from app.db.base import Base
from app.db.models import ApiClient, Company
from app.services.api_client_service import ApiClientService, InvalidServiceToken
from apps.api.app_api.routers.integration_reviews import get_integration_session_factory
from apps.api.main import create_app


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def service(session_factory):
    settings = replace(get_settings(), app_env="local", service_token_pepper="test-pepper")
    with session_factory() as session:
        session.add_all([Company(name="Tenant A"), Company(name="Tenant B")])
        session.commit()
    return ApiClientService(session_factory=session_factory, settings=settings)


def test_issue_stores_only_hmac_and_token_verifies(service, session_factory):
    issued = service.issue(1, "onebox-staging")
    assert issued.token.startswith("voc_local_")
    assert len(issued.token.split(".", 1)[1]) >= 32
    assert service.verify(issued.token).company_id == 1

    with session_factory() as session:
        client = session.scalar(select(ApiClient).where(ApiClient.key_id == issued.client.key_id))
        assert client is not None
        assert issued.token not in client.secret_hash
        assert issued.token.split(".", 1)[1] not in client.secret_hash
        assert client.secret_hash != ""


def test_wrong_malformed_and_cross_environment_tokens_are_generic_invalid(service):
    token = service.issue(1, "onebox").token
    cases = [
        "not-a-token",
        token.replace(token.rsplit(".", 1)[1], "x" * 43),
        token.replace("voc_local_", "voc_production_"),
        token[:-1],
    ]
    for candidate in cases:
        with pytest.raises(InvalidServiceToken):
            service.verify(candidate)


def test_revoke_and_expiry_are_enforced(service):
    issued = service.issue(1, "onebox")
    service.revoke(issued.client.key_id)
    with pytest.raises(InvalidServiceToken):
        service.verify(issued.token)

    expired = service.issue(
        1,
        "expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(InvalidServiceToken):
        service.verify(expired.token)


def test_rotation_can_overlap_or_revoke_immediately(service):
    first = service.issue(1, "onebox")
    replacement = service.rotate(first.client.key_id, overlap_hours=24)
    assert service.verify(first.token).company_id == 1
    assert service.verify(replacement.token).company_id == 1

    final = service.rotate(replacement.client.key_id)
    with pytest.raises(InvalidServiceToken):
        service.verify(replacement.token)
    assert service.verify(final.token).company_id == 1


def test_grant_scopes_keeps_the_existing_token_valid(service):
    issued = service.issue(1, "onebox", scopes=["reviews:read", "crawl:enqueue"])

    updated = service.grant_scopes(issued.client.key_id, ["analysis:write"])

    assert updated.scopes == ["analysis:write", "crawl:enqueue", "reviews:read"]
    assert service.verify(issued.token).scopes == updated.scopes


def test_token_company_binding_cannot_be_changed_by_request_data(service):
    tenant_a = service.issue(1, "onebox-a")
    tenant_b = service.issue(2, "onebox-b")
    assert service.verify(tenant_a.token).company_id == 1
    assert service.verify(tenant_b.token).company_id == 2
    assert service.verify(tenant_a.token).company_id != service.verify(tenant_b.token).company_id

def test_http_bearer_whoami_returns_token_tenant(monkeypatch, service, session_factory):
    issued = service.issue(1, "onebox")
    monkeypatch.setattr(service_auth_module, "ApiClientService", lambda: service)
    application = create_app()
    application.dependency_overrides[get_integration_session_factory] = lambda: session_factory

    response = TestClient(application).get(
        "/api/integration/v1/whoami",
        headers={"Authorization": f"Bearer {issued.token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "company_id": 1,
        "company_name": "Tenant A",
        "scopes": ["reviews:read"],
    }

