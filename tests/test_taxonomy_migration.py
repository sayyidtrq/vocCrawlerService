"""The taxonomy revision on its own: the older chain is PostgreSQL-only (JSONB), so it cannot run on SQLite."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

REVISION = Path(__file__).parent.parent / "alembic" / "versions" / "20261021_0012_add_industry_taxonomy.py"


def load_revision():
    spec = importlib.util.spec_from_file_location("taxonomy_revision", REVISION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def columns(connection, table):
    return {c["name"] for c in sa.inspect(connection).get_columns(table)}


def test_revision_chains_after_the_previous_head_and_round_trips():
    revision = load_revision()
    assert (revision.revision, revision.down_revision) == ("20261021_0012", "20261001_0011")

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        for name in ("companies", "locations", "review_analysis"):
            connection.execute(sa.text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))

        with Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
            assert {"taxonomy_key", "taxonomy_version"} <= columns(connection, "locations")
            assert {"taxonomy_version", "risk_flags", "tags"} <= columns(connection, "review_analysis")
            assert {"company_id", "key", "version", "body", "received_at"} <= columns(connection, "taxonomy_snapshots")

            # one snapshot per (company, key)
            connection.execute(sa.text("INSERT INTO companies (id) VALUES (1)"))
            insert = "INSERT INTO taxonomy_snapshots (company_id, key, version, body) VALUES (1, 'spbu:x', 'x', '{}')"
            connection.execute(sa.text(insert))
            try:
                connection.execute(sa.text(insert))
            except sa.exc.IntegrityError:
                pass
            else:
                raise AssertionError("duplicate (company_id, key) must be rejected")

        # existing rows stay valid: the new columns are nullable
        connection.execute(sa.text("INSERT INTO locations (id) VALUES (1)"))

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            revision.downgrade()
        assert "taxonomy_key" not in columns(connection, "locations")
        assert not {"taxonomy_version", "risk_flags", "tags"} & columns(connection, "review_analysis")
        assert "taxonomy_snapshots" not in sa.inspect(connection).get_table_names()
