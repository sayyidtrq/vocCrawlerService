"""MT-40: tenant weight provisioning and migration."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import apps.api.app_api.service_auth as service_auth_module
from app.config import Settings
from app.db.models import Company
from app.services.tenant_registry_service import (
    TenantRegistryService,
    provisioning_key_hash,
)
from apps.api.app_api.routers.integration_tenants import get_tenant_registry_service
from apps.api.main import create_app

KEY = "vocprov_test-weight-key-0123456789abcdef0123456789abcdef"
HEADERS = {"Authorization": f"Bearer {KEY}"}
TENANTS = "/api/integration/v1/tenants"


@pytest.fixture()
def registry(tx_session_factory):
    settings = Settings(
        database_url="sqlite://",
        app_env="local",
        onebox_tenant_mode="managed",
        service_token_pepper="test-weight-pepper",
        onebox_provisioning_key_hash=provisioning_key_hash(KEY, "test-weight-pepper"),
    )
    return TenantRegistryService(session_factory=tx_session_factory, settings=settings)


@pytest.fixture()
def api(registry, monkeypatch):
    monkeypatch.setattr(service_auth_module, "get_settings", lambda: registry.settings)
    application = create_app()
    application.dependency_overrides[get_tenant_registry_service] = lambda: registry
    with TestClient(application) as client:
        yield client


def test_weight_post_patch_get_and_idempotent_registration(api, tx_session_factory):
    created = api.post(
        TENANTS,
        headers=HEADERS,
        json={"site_id": 177, "site_name": "Site", "weight": 3},
    )
    assert created.status_code == 201
    company_id = created.json()["data"]["company_id"]
    assert created.json()["data"]["weight"] == 3

    changed = api.patch(f"{TENANTS}/177", headers=HEADERS, json={"weight": 2})
    assert changed.status_code == 200 and changed.json()["data"]["weight"] == 2
    renamed = api.patch(
        f"{TENANTS}/177", headers=HEADERS, json={"site_name": "Renamed"}
    )
    assert renamed.status_code == 200 and renamed.json()["data"]["weight"] == 2

    repeated = api.post(
        TENANTS,
        headers=HEADERS,
        json={"site_id": 177, "site_name": "Site", "weight": 4},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["company_id"] == company_id
    assert repeated.json()["data"]["weight"] == 4
    assert repeated.json()["data"]["created"] is False
    assert repeated.json()["data"]["token"] is None
    absent = api.post(
        TENANTS, headers=HEADERS, json={"site_id": 177, "site_name": "Site"}
    )
    assert absent.status_code == 200 and absent.json()["data"]["weight"] == 4
    got = api.get(f"{TENANTS}/177", headers=HEADERS)
    assert got.status_code == 200 and got.json()["data"]["weight"] == 4
    with tx_session_factory() as session:
        assert session.get(Company, company_id).weight == 4


def test_new_tenant_without_weight_defaults_to_one(api):
    response = api.post(
        TENANTS, headers=HEADERS, json={"site_id": 177, "site_name": "Site"}
    )
    assert response.status_code == 201 and response.json()["data"]["weight"] == 1
    assert api.get(f"{TENANTS}/177", headers=HEADERS).json()["data"]["weight"] == 1


@pytest.mark.parametrize("weight", [0, -1, "x", 101, True, 1.5, "2"])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_invalid_weight_uses_contract_error_without_changing_tenant(
    api, method, weight
):
    api.post(TENANTS, headers=HEADERS, json={"site_id": 177, "site_name": "Site"})
    if method == "post":
        response = api.post(
            TENANTS,
            headers=HEADERS,
            json={"site_id": 177, "site_name": "Changed", "weight": weight},
        )
    else:
        response = api.patch(
            f"{TENANTS}/177",
            headers=HEADERS,
            json={"site_name": "Changed", "weight": weight},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"
    data = api.get(f"{TENANTS}/177", headers=HEADERS).json()["data"]
    assert data["weight"] == 1 and data["site_name"] == "Site"


def test_weight_upper_bound_is_accepted(api):
    response = api.post(
        TENANTS,
        headers=HEADERS,
        json={"site_id": 177, "site_name": "Site", "weight": 100},
    )
    assert response.status_code == 201 and response.json()["data"]["weight"] == 100


@pytest.mark.parametrize("weight", [0, -1, "x", 101, True, 1.5])
def test_service_also_validates_weight(registry, weight):
    with pytest.raises(ValueError, match="weight"):
        registry.register(177, "Site", weight=weight)
    assert registry.register(177, "Site").view.weight == 1
    with pytest.raises(ValueError, match="weight"):
        registry.update(177, weight=weight)
    assert registry.get(177).weight == 1


def test_weight_migration_upgrade_constraints_and_downgrade():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20261026_0014_weighted_crawl_claims.py"
    )
    spec = importlib.util.spec_from_file_location("weighted_claims_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE crawl_jobs (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, "
                "status VARCHAR(30) NOT NULL, available_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (id, name) VALUES (1, 'Existing')")
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert (
            connection.execute(
                text("SELECT weight FROM companies WHERE id = 1")
            ).scalar_one()
            == 1
        )
        connection.execute(text("INSERT INTO companies (id, name) VALUES (2, 'New')"))
        assert (
            connection.execute(
                text("SELECT weight FROM companies WHERE id = 2")
            ).scalar_one()
            == 1
        )
        connection.execute(text("UPDATE companies SET weight = 7 WHERE id = 1"))

    weight_column = next(
        column
        for column in inspect(engine).get_columns("companies")
        if column["name"] == "weight"
    )
    assert weight_column["nullable"] is False
    assert any(
        check["name"] == "ck_companies_weight_positive"
        for check in inspect(engine).get_check_constraints("companies")
    )
    index = next(
        index
        for index in inspect(engine).get_indexes("crawl_jobs")
        if index["name"] == "idx_crawl_jobs_company_claim"
    )
    assert index["column_names"] == ["company_id", "status", "available_at"]
    assert (
        weight_column["type"].python_type == Company.__table__.c.weight.type.python_type
    )
    for invalid in (0, -1, None):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("UPDATE companies SET weight = :weight WHERE id = 1"),
                {"weight": invalid},
            )

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(
            text("SELECT id, name FROM companies ORDER BY id")
        ).all() == [(1, "Existing"), (2, "New")]
    assert "weight" not in {
        column["name"] for column in inspect(engine).get_columns("companies")
    }
    assert "idx_crawl_jobs_company_claim" not in {
        index["name"] for index in inspect(engine).get_indexes("crawl_jobs")
    }
    engine.dispose()
