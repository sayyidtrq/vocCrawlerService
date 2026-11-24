"""MT-10: companies jadi cermin site OneBox (onebox_site_id, is_active) dan
worklist_sync_states mencatat versi snapshot yang diterapkan."""

import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Company, WorklistSyncState

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_FILE = ROOT / "alembic" / "versions" / "20261022_0012_tenant_registry.py"


def _engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def session_factory():
    engine = _engine()
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


# --- model -------------------------------------------------------------------


def test_new_company_is_active_and_not_linked_to_a_site(session_factory):
    with session_factory() as session:
        company = Company(name="Any")
        session.add(company)
        session.commit()
        session.refresh(company)

        assert company.is_active is True
        assert company.onebox_site_id is None
        assert company.deactivated_at is None


def test_one_onebox_site_maps_to_at_most_one_company(session_factory):
    with session_factory() as session:
        session.add_all([Company(name="A", onebox_site_id=169), Company(name="B", onebox_site_id=169)])
        with pytest.raises(IntegrityError):
            session.commit()


def test_companies_without_a_site_do_not_collide(session_factory):
    with session_factory() as session:
        session.add_all([Company(name="A"), Company(name="B")])
        session.commit()


def test_sync_state_tracks_the_applied_snapshot(session_factory):
    with session_factory() as session:
        company = Company(name="A", onebox_site_id=169)
        session.add(company)
        session.flush()
        state = WorklistSyncState(company_id=company.id, site_id=169)
        session.add(state)
        session.commit()
        assert state.snapshot_version is None
        assert state.applied_at is None

        state.snapshot_version = 2**40
        session.commit()
        session.refresh(state)
        assert state.snapshot_version == 2**40


# --- migration ---------------------------------------------------------------


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0012", MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pre_migration_schema(engine):
    """Bentuk dua tabel yang disentuh migration, sebelum 0012."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE companies (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))
        conn.execute(
            text(
                "CREATE TABLE worklist_sync_states ("
                "id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL UNIQUE, site_id INTEGER NOT NULL)"
            )
        )


def _run(engine, fn_name):
    module = _load_migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def _seed_companies(engine):
    with engine.begin() as conn:
        for company_id, name in [(1, "Clear"), (2, "Twin A"), (3, "Twin B"), (4, "No state")]:
            conn.execute(text("INSERT INTO companies (id, name) VALUES (:i, :n)"), {"i": company_id, "n": name})
        # 1 punya site unik; 2 dan 3 berbagi site 177 (ambigu); 4 tidak punya state.
        for company_id, site_id in [(1, 169), (2, 177), (3, 177)]:
            conn.execute(
                text("INSERT INTO worklist_sync_states (company_id, site_id) VALUES (:c, :s)"),
                {"c": company_id, "s": site_id},
            )


def _sites(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, onebox_site_id FROM companies ORDER BY id")).all())


def test_migration_is_on_the_chain_of_the_single_head():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    # One head (a second one makes `alembic upgrade head` refuse to run); later migrations,
    # such as the merge with the taxonomy migration, may sit on top of this one.
    (head,) = script.get_heads()
    assert "20261022_0012" in {revision.revision for revision in script.walk_revisions(base="base", head=head)}
    assert script.get_revision("20261022_0012").down_revision == "20261001_0011"


def test_upgrade_adds_the_columns_and_keeps_existing_companies_active():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)

    _run(engine, "upgrade")

    inspector = inspect(engine)
    assert {"onebox_site_id", "is_active", "deactivated_at"} <= {c["name"] for c in inspector.get_columns("companies")}
    assert {"snapshot_version", "applied_at"} <= {c["name"] for c in inspector.get_columns("worklist_sync_states")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM companies WHERE is_active = 0")).scalar() == 0


def test_backfill_links_only_unambiguous_sites():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)

    _run(engine, "upgrade")

    # 169 jelas -> terisi. 177 dipakai dua company -> tidak ditebak. Tanpa state -> kosong.
    assert _sites(engine) == {1: 169, 2: None, 3: None, 4: None}


def test_backfill_is_idempotent_and_never_overwrites_a_manual_link():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)
    _run(engine, "upgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE companies SET onebox_site_id = 177 WHERE id = 2"))

    module = _load_migration()
    with engine.begin() as conn:
        module.backfill_onebox_site_id(conn)
        module.backfill_onebox_site_id(conn)

    # Company 2 sudah ditautkan manual ke 177, jadi 3 tetap tidak ditebak.
    assert _sites(engine) == {1: 169, 2: 177, 3: None, 4: None}


def test_unique_site_is_enforced_after_the_migration():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)
    _run(engine, "upgrade")

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE companies SET onebox_site_id = 169 WHERE id = 4"))


def test_downgrade_restores_the_previous_shape_and_keeps_other_data():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)
    _run(engine, "upgrade")

    _run(engine, "downgrade")

    inspector = inspect(engine)
    assert {c["name"] for c in inspector.get_columns("companies")} == {"id", "name"}
    assert {c["name"] for c in inspector.get_columns("worklist_sync_states")} == {"id", "company_id", "site_id"}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM companies")).scalar() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM worklist_sync_states")).scalar() == 3


def test_backfill_skips_a_site_that_is_already_linked_elsewhere():
    engine = _engine()
    _pre_migration_schema(engine)
    _seed_companies(engine)
    _run(engine, "upgrade")
    with engine.begin() as conn:
        # Tautan manual company 4 ke 169 lalu company 1 (state 169) di-reset.
        conn.execute(text("UPDATE companies SET onebox_site_id = NULL WHERE id = 1"))
        conn.execute(text("UPDATE companies SET onebox_site_id = 169 WHERE id = 4"))

    with engine.begin() as conn:
        _load_migration().backfill_onebox_site_id(conn)  # tidak boleh menabrak indeks unik

    assert _sites(engine)[1] is None
    assert _sites(engine)[4] == 169


def test_migrated_schema_matches_the_models():
    migrated = _engine()
    _pre_migration_schema(migrated)
    _run(migrated, "upgrade")
    from_models = _engine()
    Base.metadata.create_all(from_models)

    def shape(engine, table, names):
        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns(table) if c["name"] in names}
        return {n: (type(c["type"]).__name__, c["nullable"]) for n, c in columns.items()}

    companies = {"onebox_site_id", "is_active", "deactivated_at"}
    states = {"snapshot_version", "applied_at"}
    assert shape(migrated, "companies", companies) == shape(from_models, "companies", companies)
    assert shape(migrated, "worklist_sync_states", states) == shape(from_models, "worklist_sync_states", states)
    for engine in (migrated, from_models):
        indexes = {i["name"]: i for i in inspect(engine).get_indexes("companies")}
        assert indexes["uq_companies_onebox_site"]["unique"]
