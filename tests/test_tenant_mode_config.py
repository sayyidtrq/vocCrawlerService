"""MT-11: ONEBOX_TENANT_MODE memilih antara satu tenant dari env (single, perilaku
lama) dan tenant yang didaftarkan OneBox (managed), tanpa jalur pull."""

import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, _EnvSettings
from app.db.base import Base
from app.services.crawl_queue import CrawlQueue
from app.services.integration_review_service import IntegrationRequestError
from app.services.worklist_sync_service import WorklistSyncError, WorklistSyncService

DB = "sqlite+pysqlite:///:memory:"
PULL_VALUES = {
    "onebox_base_url": "http://onebox.test",
    "onebox_service_email": "voc@test.invalid",
    "onebox_service_password": "secret",
    "onebox_site_id": 169,
    "onebox_company_id": 1,
}


# Dua field ini hanya bisa diisi lewat alias saat konstruksi (model_copy memakai nama field).
ALIASES = {"onebox_service_email": "ONEBOX_SVC_EMAIL", "onebox_service_password": "ONEBOX_SVC_PASSWORD"}


def env_settings(**overrides):
    return _EnvSettings(database_url=DB, **{ALIASES.get(k, k): v for k, v in overrides.items()})


# --- konfigurasi -------------------------------------------------------------


def test_default_mode_is_single_and_keeps_todays_behaviour():
    assert env_settings().onebox_tenant_mode == "single"
    assert Settings(database_url=DB).onebox_tenant_mode == "single"
    assert env_settings(**PULL_VALUES).onebox_site_id == 169


@pytest.mark.parametrize("raw, expected", [("managed", "managed"), (" Managed ", "managed"), ("SINGLE", "single"), ("", "single")])
def test_mode_is_normalised(raw, expected):
    assert env_settings(onebox_tenant_mode=raw).onebox_tenant_mode == expected


def test_unknown_mode_fails_at_startup_instead_of_picking_one_silently():
    with pytest.raises(ValidationError, match="onebox_tenant_mode"):
        env_settings(onebox_tenant_mode="multi")


def test_managed_mode_needs_no_onebox_values():
    settings = env_settings(onebox_tenant_mode="managed")

    assert settings.onebox_managed is True
    assert settings.onebox_site_id is None
    assert settings.onebox_company_id is None


@pytest.mark.parametrize("name", ["onebox_site_id", "onebox_company_id"])
def test_managed_mode_rejects_a_single_tenant_identity(name):
    with pytest.raises(ValidationError, match="ONEBOX_TENANT_MODE=managed"):
        env_settings(onebox_tenant_mode="managed", **{name: 169})
    with pytest.raises(ValidationError, match="ONEBOX_TENANT_MODE=managed"):
        Settings(database_url=DB, onebox_tenant_mode="managed", **{name: 169})


def test_managed_mode_only_warns_about_leftover_onebox_credentials(caplog):
    with caplog.at_level(logging.WARNING, logger="app.config"):
        settings = env_settings(
            onebox_tenant_mode="managed",
            onebox_base_url="http://onebox.test",
            onebox_service_email="voc@test.invalid",
            onebox_service_password="secret",
        )

    assert settings.onebox_managed is True
    warning = "\n".join(record.getMessage() for record in caplog.records)
    assert "ONEBOX_SVC_EMAIL" in warning and "ONEBOX_SVC_PASSWORD" in warning
    assert "secret" not in warning


def test_single_mode_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="app.config"):
        env_settings(**PULL_VALUES)

    assert not [r for r in caplog.records if "ONEBOX" in r.getMessage()]


# --- jalur pull mati di managed ----------------------------------------------


def managed_with_all_pull_values():
    # model_copy melewati validator, jadi ini keadaan terburuk: semua nilai pull
    # terisi tetapi mode managed.
    base = Settings(database_url=DB)
    return base.model_copy(update={**PULL_VALUES, "onebox_tenant_mode": "managed"})


def test_pull_is_not_configured_in_managed_mode_even_with_every_value_set():
    assert WorklistSyncService.is_configured(managed_with_all_pull_values()) is False
    single = Settings(database_url=DB).model_copy(update=PULL_VALUES)
    assert WorklistSyncService.is_configured(single) is True


class ExplodingClient:
    calls = 0

    def get_worklist(self):
        ExplodingClient.calls += 1
        raise AssertionError("managed mode must never pull from OneBox")


def test_refresh_refuses_to_pull_in_managed_mode():
    ExplodingClient.calls = 0
    service = WorklistSyncService(
        company_id=1,
        session_factory=lambda: None,
        settings=managed_with_all_pull_values(),
        client=ExplodingClient(),
    )

    with pytest.raises(WorklistSyncError, match="managed"):
        service.refresh()

    assert ExplodingClient.calls == 0


@pytest.fixture()
def session_factory():
    engine = create_engine(DB, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_enqueue_auto_refresh_does_nothing_in_managed_mode(session_factory, monkeypatch, caplog):
    ExplodingClient.calls = 0
    monkeypatch.setattr(
        "app.services.worklist_sync_service.OneBoxWorklistClient", lambda _settings: ExplodingClient()
    )
    queue = CrawlQueue(session_factory=session_factory, settings=managed_with_all_pull_values())

    with caplog.at_level(logging.WARNING):
        assert queue._refresh_worklist_once(1, [123]) is False

    assert ExplodingClient.calls == 0
    assert "ONEBOX_BASE_URL" not in caplog.text  # pesan "belum dikonfigurasi" menyesatkan di managed
    assert "managed" in caplog.text


def test_analysis_lookup_skips_the_refresh_in_managed_mode(session_factory, monkeypatch):
    from apps.api.app_api.routers import integration_analysis

    calls = []
    monkeypatch.setattr(WorklistSyncService, "refresh", lambda self: calls.append(self) or None)
    monkeypatch.setattr(integration_analysis, "get_settings", managed_with_all_pull_values)

    with pytest.raises(IntegrationRequestError) as error:
        integration_analysis._require_location(1, session_factory, location_id=999)

    assert error.value.status_code == 404
    assert calls == []
