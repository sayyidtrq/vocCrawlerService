"""Report tenant fetch usage for OneBox quotas."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import apps.api.app_api.service_auth as service_auth_module
from app.config import get_settings
from app.db.base import Base
from app.db.models import FetchLog, Location
from app.services.tenant_registry_service import (
    TenantRegistryService,
    provisioning_key_hash,
)
from apps.api.app_api.routers.integration_tenants import get_tenant_registry_service
from apps.api.main import create_app

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
MONTH_START = datetime(2026, 10, 1, tzinfo=timezone.utc)
MONTH_END = datetime(2026, 11, 1, tzinfo=timezone.utc)
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
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def registry(session_factory):
    return TenantRegistryService(
        session_factory=session_factory, settings=make_settings(), clock=lambda: NOW
    )


@pytest.fixture()
def tenant_location(session_factory, registry):
    tenant = registry.register(177, "Site Testing")
    with session_factory() as session:
        location = Location(
            company_id=tenant.view.company_id,
            organization_name="Site Testing",
            branch_name="Branch",
            source="apify_google_maps",
            external_place_id="place-177",
        )
        session.add(location)
        session.commit()
        return location


def add_log(
    session_factory, location, coverage, total_fetched, *,
    started_at=NOW, created_at=NOW, status="completed",
):
    with session_factory() as session:
        session.add(
            FetchLog(
                company_id=location.company_id,
                location_id=location.id,
                source="apify_google_maps",
                metadata_json={"coverage": coverage} if coverage is not None else {},
                total_fetched=total_fetched,
                status=status,
                started_at=started_at,
                created_at=created_at,
            )
        )
        session.commit()


def test_backfill_total_counts_full_backfills_across_the_tenant_lifetime(
    session_factory, registry, tenant_location,
):
    add_log(
        session_factory, tenant_location, "full_backfill", 100,
        started_at=datetime(2025, 8, 10, tzinfo=timezone.utc),
    )
    add_log(session_factory, tenant_location, "full_backfill", 250)

    view = registry.get(177)

    assert view.backfill_fetched_total == 350
    assert view.operating_fetched_month == 0


def test_operating_total_counts_only_delta_and_date_window_rows_in_the_current_month(
    session_factory, registry, tenant_location,
):
    add_log(session_factory, tenant_location, "delta", 7, started_at=MONTH_START)
    add_log(
        session_factory, tenant_location, "date_window", 11,
        started_at=MONTH_END - timedelta(microseconds=1),
    )
    add_log(
        session_factory, tenant_location, "delta", 100,
        started_at=MONTH_START - timedelta(microseconds=1),
    )
    add_log(session_factory, tenant_location, "date_window", 200, started_at=MONTH_END)

    view = registry.get(177)

    assert view.operating_period == "2026-10"
    assert view.operating_fetched_month == 18
    assert view.backfill_fetched_total == 0


@pytest.mark.parametrize("status", ["completed", "partial", "failed", None])
def test_dry_run_and_legacy_rows_are_ignored_while_other_statuses_count(
    session_factory, registry, tenant_location, status,
):
    for coverage in ("full_backfill", "delta", "date_window"):
        add_log(session_factory, tenant_location, coverage, 100, status="dry_run")
    add_log(session_factory, tenant_location, None, 100)
    add_log(session_factory, tenant_location, "full_backfill", 5, status=status)
    add_log(session_factory, tenant_location, "delta", 7, status=status)

    view = registry.get(177)

    assert view.backfill_fetched_total == 5
    assert view.operating_fetched_month == 7


def test_other_tenants_fetches_never_leak_into_usage(
    session_factory, registry, tenant_location,
):
    other = registry.register(200, "Other Tenant")
    with session_factory() as session:
        other_location = Location(
            company_id=other.view.company_id,
            organization_name="Other Tenant",
            branch_name="Other Branch",
            source="apify_google_maps",
            external_place_id="place-200",
        )
        session.add(other_location)
        session.commit()
    add_log(session_factory, tenant_location, "full_backfill", 5)
    add_log(session_factory, tenant_location, "delta", 7)
    add_log(session_factory, other_location, "full_backfill", 100)
    add_log(session_factory, other_location, "delta", 200)
    add_log(session_factory, other_location, "date_window", 300)

    view = registry.get(177)

    assert view.backfill_fetched_total == 5
    assert view.operating_fetched_month == 7
    other_view = registry.get(200)
    assert other_view.backfill_fetched_total == 100
    assert other_view.operating_fetched_month == 500


def test_tenant_without_logs_reports_zeros_and_the_current_operating_period(registry):
    registry.register(177, "Site Testing")

    view = registry.get(177)

    assert view.operating_period == "2026-10"
    assert view.backfill_fetched_total == 0
    assert view.operating_fetched_month == 0


@pytest.mark.parametrize(
    "started_at, created_at, expected",
    [
        (None, MONTH_START, 13),
        (None, MONTH_START - timedelta(microseconds=1), 0),
        (None, MONTH_END, 0),
        (MONTH_START - timedelta(microseconds=1), NOW, 0),
        (NOW, MONTH_START - timedelta(microseconds=1), 13),
    ],
)
def test_operating_month_uses_created_at_only_when_started_at_is_null(
    session_factory, registry, tenant_location, started_at, created_at, expected,
):
    add_log(
        session_factory, tenant_location, "date_window", 13,
        started_at=started_at, created_at=created_at,
    )

    assert registry.get(177).operating_fetched_month == expected


def test_operating_month_uses_utc_and_handles_year_rollover(
    session_factory, tenant_location,
):
    local_now = datetime(2027, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=7)))
    registry = TenantRegistryService(
        session_factory=session_factory, settings=make_settings(), clock=lambda: local_now
    )
    add_log(
        session_factory, tenant_location, "delta", 3,
        started_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    add_log(
        session_factory, tenant_location, "date_window", 5,
        started_at=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    add_log(
        session_factory, tenant_location, "delta", 100,
        started_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )

    view = registry.get(177)

    assert view.operating_period == "2026-12"
    assert view.operating_fetched_month == 8


def test_usage_is_computed_with_one_sql_aggregate_query(
    session_factory, registry, tenant_location,
):
    add_log(session_factory, tenant_location, "full_backfill", 5)
    add_log(session_factory, tenant_location, "delta", 7)
    statements = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        if "fetch_logs" in statement.lower():
            statements.append(statement.lower())

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        view = registry.get(177)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert view.backfill_fetched_total == 5
    assert view.operating_fetched_month == 7
    assert len(statements) == 1
    assert "sum(" in statements[0]
    assert "group by" in statements[0]


@pytest.fixture()
def api(registry, monkeypatch):
    monkeypatch.setattr(service_auth_module, "get_settings", lambda: registry.settings)
    application = create_app()
    application.dependency_overrides[get_tenant_registry_service] = lambda: registry
    return TestClient(application)


def auth():
    return {"Authorization": f"Bearer {KEY}"}


def test_get_tenant_returns_usage_over_http(api, session_factory, tenant_location):
    add_log(session_factory, tenant_location, "full_backfill", 125)
    add_log(session_factory, tenant_location, "delta", 17)
    add_log(session_factory, tenant_location, "date_window", 23)

    response = api.get("/api/integration/v1/tenants/177", headers=auth())

    assert response.status_code == 200
    assert response.json()["data"]["usage"] == {
        "operating_period": "2026-10",
        "backfill_fetched_total": 125,
        "operating_fetched_month": 40,
    }
