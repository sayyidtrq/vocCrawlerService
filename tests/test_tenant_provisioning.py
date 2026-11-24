"""MT-20: OneBox mendaftarkan tenant (site) dan mendapat token tenant, tanpa CLI."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.service_auth as service_auth_module
from app.config import get_settings
from app.db.base import Base
from app.db.models import ApiClient, Company, WorklistSyncState
from app.services.api_client_service import ApiClientService, InvalidServiceToken
from app.services.tenant_registry_service import (
    TENANT_TOKEN_NAME,
    TENANT_TOKEN_SCOPES,
    TenantNotFound,
    TenantRegistryService,
    new_provisioning_key,
    provisioning_key_hash,
)
from apps.api.app_api.routers.integration_tenants import get_tenant_registry_service
from apps.api.main import create_app

PEPPER = "test-pepper"
KEY = "vocprov_test-key-0123456789abcdef0123456789abcdef"


def make_settings(**update):
    base = {
        "app_env": "local",
        "service_token_pepper": PEPPER,
        "onebox_tenant_mode": "managed",
        "onebox_provisioning_key_hash": provisioning_key_hash(KEY, PEPPER),
    }
    base.update(update)
    return get_settings().model_copy(update=base)


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
def registry(session_factory):
    return TenantRegistryService(session_factory=session_factory, settings=make_settings())


@pytest.fixture()
def tokens(session_factory):
    return ApiClientService(session_factory=session_factory, settings=make_settings())


def clients(session_factory, company_id=None):
    with session_factory() as session:
        statement = select(ApiClient).order_by(ApiClient.id)
        if company_id is not None:
            statement = statement.where(ApiClient.company_id == company_id)
        return list(session.scalars(statement).all())


# --- pendaftaran -------------------------------------------------------------


def test_register_creates_a_linked_active_company_and_one_tenant_token(registry, tokens, session_factory):
    result = registry.register(177, "Site Testing")

    assert result.created is True
    assert (result.view.site_id, result.view.site_name, result.view.is_active) == (177, "Site Testing", True)
    issued = result.token
    assert issued is not None
    assert tokens.verify(issued.token).company_id == result.view.company_id
    [client] = clients(session_factory, result.view.company_id)
    assert client.name == TENANT_TOKEN_NAME
    assert tuple(client.scopes) == tuple(sorted(TENANT_TOKEN_SCOPES))
    assert issued.token.split(".", 1)[1] not in client.secret_hash


def test_register_is_idempotent_and_does_not_issue_a_second_token(registry, session_factory):
    first = registry.register(177, "Site Testing")

    second = registry.register(177, "Nama lain")

    assert second.created is False and second.token is None
    assert second.view.company_id == first.view.company_id
    assert second.view.site_name == "Site Testing"  # POST ulang tidak mengganti nama
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Company)) == 1
    assert len(clients(session_factory)) == 1


def test_register_links_an_existing_company_without_touching_its_other_tokens(registry, tokens, session_factory):
    with session_factory() as session:
        company = Company(name="Hermina", onebox_site_id=169)
        session.add(company)
        session.commit()
        company_id = company.id
    legacy = tokens.issue(company_id, "onebox-hermina", ["reviews:read"])

    result = registry.register(169, "Hermina Group")

    assert result.created is False and result.token is not None
    assert result.view.site_name == "Hermina"
    assert tokens.verify(legacy.token).company_id == company_id  # token lama tetap berlaku
    assert len(clients(session_factory, company_id)) == 2


def test_register_reactivates_an_inactive_tenant_and_keeps_its_token(registry, session_factory):
    first = registry.register(177, "Site Testing")
    registry.update(177, active=False)

    again = registry.register(177, "Site Testing")

    assert again.view.is_active is True and again.view.deactivated_at is None
    assert again.created is False and again.token is None
    assert len(clients(session_factory, first.view.company_id)) == 1


@pytest.mark.parametrize("site_id, name", [(0, "x"), (-5, "x"), (True, "x"), ("177", "x"), (177, "  "), (177, "")])
def test_register_rejects_bad_input(registry, site_id, name):
    with pytest.raises(ValueError):
        registry.register(site_id, name)


def test_two_tenants_get_separate_companies_and_tokens(registry, tokens):
    a = registry.register(169, "A")
    b = registry.register(177, "B")

    assert a.view.company_id != b.view.company_id
    assert tokens.verify(a.token.token).company_id == a.view.company_id
    assert tokens.verify(b.token.token).company_id == b.view.company_id


# --- baca dan ubah -----------------------------------------------------------


def test_get_reports_state_without_any_secret(registry, session_factory):
    created = registry.register(177, "Site Testing")
    with session_factory() as session:
        session.add(
            WorklistSyncState(
                company_id=created.view.company_id, site_id=177, snapshot_version=7,
                item_count=12, last_error="boom",
            )
        )
        session.commit()

    view = registry.get(177)

    assert view.worklist_snapshot_version == 7 and view.worklist_items == 12
    assert view.worklist_last_error == "boom"
    assert view.token_key_id == created.token.client.key_id
    assert created.token.token not in repr(view) and "secret" not in repr(view).lower()


def test_unknown_tenants_are_not_found(registry):
    with pytest.raises(TenantNotFound):
        registry.get(999)
    with pytest.raises(TenantNotFound):
        registry.update(999, active=False)
    with pytest.raises(TenantNotFound):
        registry.rotate_token(999)


def test_update_deactivates_and_reactivates_without_touching_data(registry, session_factory):
    created = registry.register(177, "Site Testing")

    off = registry.update(177, active=False)
    assert off.is_active is False and off.deactivated_at is not None

    on = registry.update(177, active=True)
    assert on.is_active is True and on.deactivated_at is None
    assert len(clients(session_factory, created.view.company_id)) == 1


def test_update_can_rename_and_ignores_absent_fields(registry):
    registry.register(177, "Lama")

    renamed = registry.update(177, site_name="  Baru  ")

    assert renamed.site_name == "Baru" and renamed.is_active is True
    with pytest.raises(ValueError):
        registry.update(177, site_name="   ")


def test_deactivating_twice_keeps_the_first_timestamp(registry):
    registry.register(177, "X")
    first = registry.update(177, active=False).deactivated_at

    second = registry.update(177, active=False).deactivated_at

    # SQLite membuang zona waktu saat dibaca ulang; yang dibandingkan waktunya.
    assert second.replace(tzinfo=None) == first.replace(tzinfo=None)


# --- rotasi ------------------------------------------------------------------


def test_rotation_with_overlap_keeps_the_old_token_valid_only_for_a_while(registry, tokens, session_factory):
    created = registry.register(177, "Site Testing")
    old = created.token

    new = registry.rotate_token(177, overlap_hours=24)

    company_id = created.view.company_id
    assert tokens.verify(new.token).company_id == company_id
    assert tokens.verify(old.token).company_id == company_id  # masih berlaku selama tumpang tindih
    expires = next(c for c in clients(session_factory, company_id) if c.key_id == old.client.key_id).expires_at
    expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
    remaining = expires - datetime.now(timezone.utc)
    assert timedelta(hours=23) < remaining <= timedelta(hours=24)


def test_rotation_never_extends_an_existing_earlier_expiry(registry, session_factory):
    created = registry.register(177, "Site Testing")
    soon = datetime.now(timezone.utc) + timedelta(hours=1)
    with session_factory() as session:
        session.get(ApiClient, clients(session_factory)[0].id).expires_at = soon
        session.commit()

    registry.rotate_token(177, overlap_hours=24)

    expires = next(c for c in clients(session_factory) if c.key_id == created.token.client.key_id).expires_at
    expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
    assert expires <= soon + timedelta(seconds=1)


def test_rotation_without_overlap_revokes_the_old_token_at_once(registry, tokens):
    created = registry.register(177, "Site Testing")

    new = registry.rotate_token(177, overlap_hours=0)

    assert tokens.verify(new.token).company_id == created.view.company_id
    with pytest.raises(InvalidServiceToken):
        tokens.verify(created.token.token)


def test_rotation_only_touches_tenant_tokens_of_that_company(registry, tokens, session_factory):
    a = registry.register(169, "A")
    registry.register(177, "B")
    other = tokens.issue(a.view.company_id, "onebox-manual", ["reviews:read"])
    b_token = clients(session_factory, registry.get(177).company_id)[0]

    registry.rotate_token(169, overlap_hours=0)

    assert tokens.verify(other.token).company_id == a.view.company_id
    assert next(c for c in clients(session_factory) if c.id == b_token.id).is_active is True


@pytest.mark.parametrize("hours", [-1, 169])
def test_rotation_overlap_is_bounded(registry, hours):
    registry.register(177, "X")

    with pytest.raises(ValueError):
        registry.rotate_token(177, overlap_hours=hours)


# --- kunci provisioning ------------------------------------------------------


def test_provisioning_key_hash_is_peppered_and_not_reversible_to_a_service_token():
    assert provisioning_key_hash(KEY, "a") != provisioning_key_hash(KEY, "b")
    assert provisioning_key_hash(KEY, "a") == provisioning_key_hash(KEY, "a")
    assert KEY not in provisioning_key_hash(KEY, "a")


def test_generated_provisioning_keys_are_unique_long_and_not_a_service_token(session_factory):
    first, second = new_provisioning_key(), new_provisioning_key()

    assert first != second and len(first) >= 40 and first.startswith("vocprov_")
    with pytest.raises(InvalidServiceToken):
        ApiClientService(session_factory=session_factory, settings=make_settings()).verify(first)


# --- API ---------------------------------------------------------------------


@pytest.fixture()
def api(session_factory, monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(service_auth_module, "get_settings", lambda: settings)
    application = create_app()
    application.dependency_overrides[get_tenant_registry_service] = lambda: TenantRegistryService(
        session_factory=session_factory, settings=settings
    )
    client = TestClient(application)
    client.settings = settings
    return client


def auth(key=KEY):
    return {"Authorization": f"Bearer {key}"}


def test_the_api_requires_the_provisioning_key(api):
    for headers in ({}, auth("salah"), {"Authorization": "Basic abc"}):
        response = api.post("/api/integration/v1/tenants", json={"site_id": 177, "site_name": "X"}, headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_PROVISIONING_KEY"


def test_a_tenant_token_cannot_provision_tenants(api, registry):
    token = registry.register(177, "X").token.token

    response = api.post("/api/integration/v1/tenants", json={"site_id": 200, "site_name": "Y"}, headers=auth(token))

    assert response.status_code == 401


def test_the_api_is_disabled_until_a_provisioning_key_is_configured(session_factory, monkeypatch):
    settings = make_settings(onebox_provisioning_key_hash=None)
    monkeypatch.setattr(service_auth_module, "get_settings", lambda: settings)

    response = TestClient(create_app()).post(
        "/api/integration/v1/tenants", json={"site_id": 1, "site_name": "X"}, headers=auth()
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVISIONING_NOT_CONFIGURED"


def test_the_api_is_only_available_in_managed_mode(session_factory, monkeypatch):
    settings = make_settings(onebox_tenant_mode="single")
    monkeypatch.setattr(service_auth_module, "get_settings", lambda: settings)

    response = TestClient(create_app()).post(
        "/api/integration/v1/tenants", json={"site_id": 1, "site_name": "X"}, headers=auth()
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TENANT_MODE_NOT_MANAGED"


def test_post_creates_then_answers_200_without_a_token(api, tokens):
    created = api.post("/api/integration/v1/tenants", json={"site_id": 177, "site_name": "Site Testing"}, headers=auth())

    assert created.status_code == 201
    body = created.json()
    assert body["meta"]["api_version"] == "v1" and body["meta"]["request_id"]
    data = body["data"]
    assert (data["site_id"], data["is_active"], data["created"]) == (177, True, True)
    value = data["token"]["value"]
    assert value.startswith("voc_local_") and data["token"]["key_id"] in value
    assert sorted(data["token"]["scopes"]) == sorted(TENANT_TOKEN_SCOPES)
    assert tokens.verify(value).company_id == data["company_id"]

    again = api.post("/api/integration/v1/tenants", json={"site_id": 177, "site_name": "Site Testing"}, headers=auth())
    assert again.status_code == 200
    assert again.json()["data"]["token"] is None and again.json()["data"]["created"] is False


def test_extra_fields_from_onebox_are_ignored_for_now(api):
    response = api.post(
        "/api/integration/v1/tenants",
        json={"site_id": 177, "site_name": "X", "weight": 3, "settings": {"a": 1}},
        headers=auth(),
    )

    assert response.status_code == 201


@pytest.mark.parametrize("body", [{}, {"site_id": 0, "site_name": "X"}, {"site_id": 1, "site_name": ""}, {"site_id": "a", "site_name": "X"}])
def test_post_rejects_bad_bodies_with_the_contract_error(api, body):
    response = api.post("/api/integration/v1/tenants", json=body, headers=auth())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_get_patch_and_rotate_over_http(api, tokens):
    api.post("/api/integration/v1/tenants", json={"site_id": 177, "site_name": "S"}, headers=auth())

    got = api.get("/api/integration/v1/tenants/177", headers=auth())
    assert got.status_code == 200 and got.json()["data"]["site_id"] == 177
    assert "value" not in str(got.json())

    off = api.patch("/api/integration/v1/tenants/177", json={"active": False}, headers=auth())
    assert off.status_code == 200 and off.json()["data"]["is_active"] is False

    rotated = api.post("/api/integration/v1/tenants/177/token:rotate", json={"overlap_hours": 1}, headers=auth())
    assert rotated.status_code == 200
    assert tokens.verify(rotated.json()["data"]["token"]["value"]).company_id == got.json()["data"]["company_id"]


def test_unknown_tenants_are_404_over_http(api):
    for call in (
        lambda: api.get("/api/integration/v1/tenants/999", headers=auth()),
        lambda: api.patch("/api/integration/v1/tenants/999", json={"active": False}, headers=auth()),
        lambda: api.post("/api/integration/v1/tenants/999/token:rotate", json={}, headers=auth()),
    ):
        response = call()
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TENANT_NOT_FOUND"


def test_rotate_overlap_out_of_range_is_a_bad_parameter(api):
    api.post("/api/integration/v1/tenants", json={"site_id": 177, "site_name": "S"}, headers=auth())

    response = api.post("/api/integration/v1/tenants/177/token:rotate", json={"overlap_hours": 500}, headers=auth())

    assert response.status_code == 400
