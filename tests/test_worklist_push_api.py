"""MT-21: PUT /api/integration/v1/worklist - OneBox mendorong worklist satu tenant
dengan token tenant yang didapat dari provisioning."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.routers.integration_worklist as worklist_router
import apps.api.app_api.service_auth as service_auth_module
from app.config import get_settings
from app.db.base import Base
from app.db.models import Company, Location, WorklistSyncState
from app.services.api_client_service import ApiClientService
from app.services.tenant_registry_service import TenantRegistryService
from apps.api.main import create_app

URL = "/api/integration/v1/worklist"


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
def settings():
    return get_settings().model_copy(
        update={"app_env": "local", "service_token_pepper": "test-pepper", "onebox_tenant_mode": "managed"}
    )


@pytest.fixture()
def env(session_factory, settings, monkeypatch):
    """Token asli: service_auth memverifikasi ke DB test, router memakai settings test."""
    monkeypatch.setattr(
        service_auth_module,
        "ApiClientService",
        lambda: ApiClientService(session_factory=session_factory, settings=settings),
    )
    monkeypatch.setattr(worklist_router, "get_settings", lambda: settings)
    application = create_app()
    application.dependency_overrides[worklist_router.get_worklist_session_factory] = lambda: session_factory
    return {
        "client": TestClient(application),
        "registry": TenantRegistryService(session_factory=session_factory, settings=settings),
        "tokens": ApiClientService(session_factory=session_factory, settings=settings),
        "session_factory": session_factory,
        "settings": settings,
        "app": application,
    }


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def item(place="place-a", name="Cabang A", **extra):
    base = {
        "kind": "location",
        "external_place_id": place,
        "branch_name": name,
        "organization_name": "Org",
        "onebox_connection_id": 10,
        "active": True,
        "crawl_enabled": True,
    }
    base.update(extra)
    return base


def push(env, token, version, items):
    return env["client"].put(URL, json={"snapshot_version": version, "items": items}, headers=bearer(token))


def tenant(env, site_id, name="T"):
    result = env["registry"].register(site_id, name)
    return result.view.company_id, result.token.token


def places(env, company_id):
    with env["session_factory"]() as session:
        rows = session.scalars(select(Location).where(Location.company_id == company_id)).all()
        return {row.external_place_id: row for row in rows}


# --- jalan lengkap -----------------------------------------------------------


def test_a_provisioned_tenant_can_push_its_worklist_end_to_end(env):
    company_id, token = tenant(env, 177, "Site Testing")

    response = push(env, token, 1, [item("place-a"), item("place-b", "Cabang B")])

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["api_version"] == "v1" and body["meta"]["request_id"]
    data = body["data"]
    assert (data["status"], data["snapshot_version"], data["site_id"], data["company_id"]) == ("applied", 1, 177, company_id)
    assert (data["fetched"], data["upserted"], data["deactivated"]) == (2, 2, 0)
    assert set(places(env, company_id)) == {"place-a", "place-b"}
    assert env["registry"].get(177).worklist_snapshot_version == 1


def test_pushing_the_same_or_an_older_version_is_a_successful_no_op(env):
    company_id, token = tenant(env, 177)
    push(env, token, 2, [item("place-a", "Terbaru")])

    for version in (2, 1):
        response = push(env, token, version, [item("place-a", "Basi"), item("place-z")])
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "stale" and data["snapshot_version"] == 2 and data["upserted"] == 0

    rows = places(env, company_id)
    assert set(rows) == {"place-a"} and rows["place-a"].branch_name == "Terbaru"


def test_an_empty_snapshot_switches_every_target_off_without_deleting(env):
    company_id, token = tenant(env, 177)
    push(env, token, 1, [item("place-a")])

    response = push(env, token, 2, [])

    assert response.status_code == 200 and response.json()["data"]["deactivated"] == 1
    assert places(env, company_id)["place-a"].is_active is False


def test_the_request_id_header_is_echoed(env):
    _, token = tenant(env, 177)

    response = env["client"].put(
        URL,
        json={"snapshot_version": 1, "items": []},
        headers={**bearer(token), "X-Request-ID": "req-123"},
    )

    assert response.json()["meta"]["request_id"] == "req-123"


# --- isolasi -----------------------------------------------------------------


def test_each_tenant_token_only_writes_its_own_worklist(env):
    a_id, a_token = tenant(env, 169, "A")
    b_id, b_token = tenant(env, 177, "B")
    push(env, a_token, 1, [item("shared", "Milik A"), item("only-a")])

    push(env, b_token, 1, [item("shared", "Milik B")])
    push(env, b_token, 2, [])  # B mengosongkan miliknya

    assert places(env, a_id)["shared"].branch_name == "Milik A" and places(env, a_id)["shared"].is_active
    assert places(env, a_id)["only-a"].is_active
    assert places(env, b_id)["shared"].is_active is False
    with env["session_factory"]() as session:
        versions = dict(session.execute(select(WorklistSyncState.company_id, WorklistSyncState.snapshot_version)).all())
    assert versions == {a_id: 1, b_id: 2}


def test_the_body_cannot_name_another_tenant(env):
    a_id, _ = tenant(env, 169, "A")
    b_id, b_token = tenant(env, 177, "B")

    response = env["client"].put(
        URL,
        json={"snapshot_version": 1, "items": [item("x")], "site_id": 169, "company_id": a_id},
        headers=bearer(b_token),
    )

    assert response.status_code == 200 and response.json()["data"]["company_id"] == b_id
    assert places(env, a_id) == {} and set(places(env, b_id)) == {"x"}


# --- autentikasi dan scope ---------------------------------------------------


def test_a_missing_or_invalid_token_is_unauthorized(env):
    for headers in ({}, bearer("salah"), bearer("voc_local_abcdefgh.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")):
        response = env["client"].put(URL, json={"snapshot_version": 1, "items": []}, headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_SERVICE_TOKEN"


def test_a_token_without_the_worklist_scope_is_forbidden(env):
    company_id, _ = tenant(env, 177)
    read_only = env["tokens"].issue(company_id, "onebox-read", ["reviews:read"])

    response = push(env, read_only.token, 1, [item()])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    assert places(env, company_id) == {}


# --- penolakan ---------------------------------------------------------------


def test_an_invalid_snapshot_is_rejected_whole_with_its_reason(env):
    company_id, token = tenant(env, 177)
    push(env, token, 1, [item("place-a")])

    response = push(env, token, 2, [item("place-b"), item("")])

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_SNAPSHOT" and "external_place_id" in error["message"]
    assert set(places(env, company_id)) == {"place-a"}
    assert env["registry"].get(177).worklist_snapshot_version == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"items": []},
        {"snapshot_version": 1},
        {"snapshot_version": "3", "items": []},
        {"snapshot_version": 0, "items": []},
        {"snapshot_version": 1, "items": "bukan list"},
    ],
)
def test_a_malformed_body_is_a_bad_parameter(env, body):
    _, token = tenant(env, 177)

    response = env["client"].put(URL, json=body, headers=bearer(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_an_oversized_snapshot_is_rejected_before_it_is_applied(env):
    company_id, token = tenant(env, 177)

    response = push(env, token, 1, [item(f"p{n}") for n in range(worklist_router.MAX_SNAPSHOT_ITEMS + 1)])

    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert places(env, company_id) == {}


def test_an_inactive_tenant_cannot_push_but_keeps_its_data(env):
    company_id, token = tenant(env, 177)
    push(env, token, 1, [item("place-a")])
    env["registry"].update(177, active=False)

    response = push(env, token, 2, [])

    assert response.status_code == 409 and response.json()["error"]["code"] == "TENANT_INACTIVE"
    assert places(env, company_id)["place-a"].is_active is True


def test_pushing_is_refused_outside_managed_mode(env, monkeypatch):
    _, token = tenant(env, 177)
    monkeypatch.setattr(worklist_router, "get_settings", lambda: get_settings().model_copy(update={"app_env": "local"}))

    response = push(env, token, 1, [item()])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TENANT_MODE_NOT_MANAGED"


def test_a_company_not_linked_to_a_onebox_site_cannot_push(env):
    with env["session_factory"]() as session:
        company = Company(name="Standalone")
        session.add(company)
        session.commit()
        company_id = company.id
    token = env["tokens"].issue(company_id, "manual", ["worklist:write"]).token

    response = push(env, token, 1, [item()])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TENANT_NOT_LINKED"
    assert places(env, company_id) == {}


def test_the_provisioning_key_cannot_push_a_worklist(env):
    response = env["client"].put(
        URL, json={"snapshot_version": 1, "items": []}, headers=bearer("vocprov_" + "a" * 43)
    )

    assert response.status_code == 401


# --- taksonomi (sama dengan worklist pull) -----------------------------------

import json
from pathlib import Path

from app.db.models import TaxonomySnapshot

TAXONOMY_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "worklist_taxonomy_fixture.json").read_text(encoding="utf-8")
)


def snapshots(env, company_id):
    with env["session_factory"]() as session:
        rows = session.scalars(select(TaxonomySnapshot).where(TaxonomySnapshot.company_id == company_id)).all()
        return {row.key: row.version for row in rows}


def test_a_push_stores_the_taxonomies_and_links_each_location(env):
    company_id, token = tenant(env, 177)
    taxonomies = TAXONOMY_FIXTURE["taxonomies"]
    key = next(iter(taxonomies))

    response = env["client"].put(
        URL,
        json={"snapshot_version": 1, "items": [item("place-a", taxonomy_key=key)], "taxonomies": taxonomies},
        headers=bearer(token),
    )

    assert response.status_code == 200 and response.json()["data"]["status"] == "applied"
    assert snapshots(env, company_id) == {k: v["version"] for k, v in taxonomies.items()}
    location = places(env, company_id)["place-a"]
    assert location.taxonomy_key == key
    assert location.taxonomy_version == key.rpartition(":")[2]


def test_taxonomies_stay_with_the_tenant_that_pushed_them(env):
    a_id, a_token = tenant(env, 169, "A")
    b_id, _ = tenant(env, 177, "B")

    env["client"].put(
        URL,
        json={"snapshot_version": 1, "items": [], "taxonomies": TAXONOMY_FIXTURE["taxonomies"]},
        headers=bearer(a_token),
    )

    assert snapshots(env, a_id) and snapshots(env, b_id) == {}


def test_an_invalid_taxonomy_is_skipped_without_rejecting_the_snapshot(env):
    company_id, token = tenant(env, 177)
    good_key, good_body = next(iter(TAXONOMY_FIXTURE["taxonomies"].items()))

    response = env["client"].put(
        URL,
        json={
            "snapshot_version": 1,
            "items": [item("place-a")],
            "taxonomies": {good_key: good_body, "rusak:00000000": {"bukan": "taksonomi"}},
        },
        headers=bearer(token),
    )

    assert response.status_code == 200 and response.json()["data"]["status"] == "applied"
    assert set(snapshots(env, company_id)) == {good_key}
    assert set(places(env, company_id)) == {"place-a"}


def test_a_stale_push_does_not_touch_the_taxonomies(env):
    company_id, token = tenant(env, 177)
    push(env, token, 2, [])

    env["client"].put(
        URL,
        json={"snapshot_version": 1, "items": [], "taxonomies": TAXONOMY_FIXTURE["taxonomies"]},
        headers=bearer(token),
    )

    assert snapshots(env, company_id) == {}


def test_taxonomies_must_be_an_object(env):
    _, token = tenant(env, 177)

    response = env["client"].put(
        URL, json={"snapshot_version": 1, "items": [], "taxonomies": ["bukan", "objek"]}, headers=bearer(token)
    )

    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"
