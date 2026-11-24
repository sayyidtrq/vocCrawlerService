"""`alembic upgrade head` (run by entrypoint.sh) refuses to start when two branches each add a head."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def _script_directory() -> ScriptDirectory:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_the_migration_chain_has_exactly_one_head():
    heads = _script_directory().get_heads()
    assert len(heads) == 1, f"parallel migrations need a merge revision, heads: {sorted(heads)}"


def test_every_revision_is_reachable_from_the_head():
    script = _script_directory()
    reachable = {revision.revision for revision in script.walk_revisions()}
    on_disk = {path.stem.split("_", 2)[0] + "_" + path.stem.split("_", 2)[1] for path in (ROOT / "alembic" / "versions").glob("2*.py")}
    assert on_disk <= reachable, f"not in the chain: {sorted(on_disk - reachable)}"
