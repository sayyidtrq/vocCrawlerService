"""MT-13: OneBox mengirim snapshot worklist lengkap; crawler menerapkannya utuh
atau tidak sama sekali, dan menolak versi yang tidak lebih baru."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, Competitor, Location, WorklistSyncState
from app.services.worklist_sync_service import (
    WorklistSnapshotInvalidError,
    WorklistSyncError,
    WorklistSyncService,
    WorklistTenantInactiveError,
)

DB = "sqlite+pysqlite:///:memory:"
MANAGED = Settings(database_url=DB, onebox_tenant_mode="managed")


@pytest.fixture()
def session_factory():
    engine = create_engine(DB, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def make_company(session_factory, name="Tenant", site_id=169, **extra):
    with session_factory() as session:
        company = Company(name=name, onebox_site_id=site_id, **extra)
        session.add(company)
        session.commit()
        return company.id


def service(session_factory, company_id, settings=MANAGED):
    return WorklistSyncService(
        company_id=company_id, session_factory=session_factory, settings=settings, client=object()
    )


def item(place="place-a", kind="location", target=None, name="Cabang A", **extra):
    base = {
        "kind": kind,
        "external_place_id": place,
        "branch_name": name,
        "organization_name": "Org",
        "city": "Depok",
        "onebox_target_id": target,
        "onebox_connection_id": 10,
        "active": True,
        "crawl_enabled": kind == "location",
        "ingest_reviews": kind == "location",
    }
    base.update(extra)
    return base


def locations(session_factory, company_id):
    with session_factory() as session:
        rows = session.scalars(select(Location).where(Location.company_id == company_id)).all()
        return {row.external_place_id: row for row in rows}


def state(session_factory, company_id):
    with session_factory() as session:
        return session.scalar(
            select(WorklistSyncState).where(WorklistSyncState.company_id == company_id)
        )


# --- penerapan ---------------------------------------------------------------


def test_snapshot_creates_targets_and_records_the_version(session_factory):
    company_id = make_company(session_factory, site_id=177)

    result = service(session_factory, company_id).apply_snapshot(
        1, [item("place-a"), item("place-b", name="Cabang B"), item("rival", kind="competitor", name="Rival")]
    )

    assert (result.status, result.fetched, result.upserted, result.deactivated) == ("applied", 3, 3, 0)
    assert result.snapshot_version == 1 and result.site_id == 177
    assert set(locations(session_factory, company_id)) == {"place-a", "place-b"}
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Competitor).where(Competitor.company_id == company_id)) == 1
    saved = state(session_factory, company_id)
    assert (saved.site_id, saved.snapshot_version, saved.item_count) == (177, 1, 3)
    assert saved.applied_at is not None and saved.last_success_at is not None and saved.last_error is None


def test_a_newer_snapshot_updates_and_soft_deactivates_what_is_missing(session_factory):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(1, [item("place-a"), item("place-b", name="Cabang B")])

    result = svc.apply_snapshot(2, [item("place-a", name="Cabang A baru")])

    rows = locations(session_factory, company_id)
    assert rows["place-a"].branch_name == "Cabang A baru" and rows["place-a"].is_active
    assert rows["place-b"].is_active is False and rows["place-b"].crawl_enabled is False
    assert result.deactivated == 1  # tidak dihapus: datanya tetap
    assert state(session_factory, company_id).snapshot_version == 2


def test_an_empty_snapshot_deactivates_every_managed_target(session_factory):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(1, [item("place-a")])

    result = svc.apply_snapshot(2, [])

    assert result.status == "applied" and result.deactivated == 1
    assert locations(session_factory, company_id)["place-a"].is_active is False


def test_targets_not_managed_by_onebox_are_left_alone(session_factory):
    company_id = make_company(session_factory)
    with session_factory() as session:
        session.add(
            Location(company_id=company_id, source="manual", external_place_id="manual-1",
                     organization_name="O", branch_name="Manual", is_active=True)
        )
        session.commit()

    service(session_factory, company_id).apply_snapshot(1, [item("place-a")])

    assert locations(session_factory, company_id)["manual-1"].is_active is True


# --- versi -------------------------------------------------------------------


@pytest.mark.parametrize("sent", [1, 2])
def test_an_equal_or_older_version_is_stale_and_changes_nothing(session_factory, sent):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(2, [item("place-a", name="Terbaru")])

    result = svc.apply_snapshot(sent, [item("place-a", name="Basi"), item("place-z")])

    assert result.status == "stale" and result.snapshot_version == 2 and result.upserted == 0
    rows = locations(session_factory, company_id)
    assert set(rows) == {"place-a"} and rows["place-a"].branch_name == "Terbaru"
    assert state(session_factory, company_id).snapshot_version == 2


@pytest.mark.parametrize("bad", [0, -1, "3", True, None, 1.5])
def test_the_version_must_be_a_positive_integer(session_factory, bad):
    company_id = make_company(session_factory)

    with pytest.raises(WorklistSnapshotInvalidError, match="snapshot_version"):
        service(session_factory, company_id).apply_snapshot(bad, [item()])

    assert locations(session_factory, company_id) == {}


# --- atomik ------------------------------------------------------------------


def test_an_invalid_snapshot_is_rejected_whole_and_does_not_consume_the_version(session_factory):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(1, [item("place-a")])

    with pytest.raises(WorklistSnapshotInvalidError, match="external_place_id"):
        svc.apply_snapshot(2, [item("place-b"), item("")])

    assert set(locations(session_factory, company_id)) == {"place-a"}
    saved = state(session_factory, company_id)
    assert saved.snapshot_version == 1
    assert "external_place_id" in saved.last_error  # terlihat untuk operator

    # Versi 2 belum terpakai: kiriman yang sudah diperbaiki diterima.
    assert svc.apply_snapshot(2, [item("place-a"), item("place-b")]).status == "applied"
    assert state(session_factory, company_id).last_error is None


@pytest.mark.parametrize(
    "items",
    [
        [item("dup"), item("dup", name="Lagi")],
        [item("a", target=5), item("b", target=5)],
        [{"kind": "branch", "external_place_id": "x"}],
        ["bukan objek"],
    ],
)
def test_other_invalid_items_are_rejected_whole(session_factory, items):
    company_id = make_company(session_factory)

    with pytest.raises(WorklistSnapshotInvalidError):
        service(session_factory, company_id).apply_snapshot(1, items)

    assert locations(session_factory, company_id) == {}
    assert state(session_factory, company_id).snapshot_version is None


def test_a_failure_in_the_middle_of_writing_rolls_everything_back(session_factory, monkeypatch):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(1, [item("place-a", name="Lama")])
    calls = {"n": 0}
    real = WorklistSyncService._apply_location

    def explode_on_second(entity, payload, now):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk penuh")
        real(entity, payload, now)

    monkeypatch.setattr(WorklistSyncService, "_apply_location", staticmethod(explode_on_second))

    with pytest.raises(RuntimeError):
        svc.apply_snapshot(2, [item("place-a", name="Baru"), item("place-b")])

    rows = locations(session_factory, company_id)
    assert set(rows) == {"place-a"} and rows["place-a"].branch_name == "Lama"
    assert state(session_factory, company_id).snapshot_version == 1


# --- isolasi dan syarat ------------------------------------------------------


def test_a_snapshot_only_touches_its_own_company(session_factory):
    a = make_company(session_factory, "A", site_id=169)
    b = make_company(session_factory, "B", site_id=177)
    service(session_factory, b).apply_snapshot(1, [item("shared", name="Milik B")])

    service(session_factory, a).apply_snapshot(1, [item("shared", name="Milik A")])
    service(session_factory, a).apply_snapshot(2, [])

    assert locations(session_factory, b)["shared"].branch_name == "Milik B"
    assert locations(session_factory, b)["shared"].is_active is True
    assert locations(session_factory, a)["shared"].is_active is False
    assert state(session_factory, b).snapshot_version == 1


def test_pushing_requires_managed_mode(session_factory):
    company_id = make_company(session_factory)
    single = Settings(database_url=DB)

    with pytest.raises(WorklistSyncError, match="managed"):
        service(session_factory, company_id, single).apply_snapshot(1, [item()])

    assert locations(session_factory, company_id) == {}


def test_a_company_without_a_onebox_site_cannot_receive_a_snapshot(session_factory):
    company_id = make_company(session_factory, site_id=None)

    with pytest.raises(WorklistSyncError, match="not linked"):
        service(session_factory, company_id).apply_snapshot(1, [item()])


def test_an_unknown_company_is_an_error(session_factory):
    with pytest.raises(WorklistSyncError, match="does not exist"):
        service(session_factory, 999).apply_snapshot(1, [item()])


def test_an_inactive_tenant_rejects_snapshots_and_keeps_its_data(session_factory):
    company_id = make_company(session_factory)
    svc = service(session_factory, company_id)
    svc.apply_snapshot(1, [item("place-a")])
    with session_factory() as session:
        session.get(Company, company_id).is_active = False
        session.commit()

    with pytest.raises(WorklistTenantInactiveError):
        svc.apply_snapshot(2, [])

    assert locations(session_factory, company_id)["place-a"].is_active is True
    assert state(session_factory, company_id).snapshot_version == 1


def test_a_service_without_a_company_is_an_error(session_factory):
    svc = WorklistSyncService(session_factory=session_factory, settings=MANAGED, client=object())

    with pytest.raises(WorklistSyncError, match="company"):
        svc.apply_snapshot(1, [item()])
