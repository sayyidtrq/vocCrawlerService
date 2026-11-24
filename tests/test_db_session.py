from types import SimpleNamespace

import pytest

from app.db import session as session_module


@pytest.fixture()
def captured_engine_kwargs(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(session_module, "create_engine", fake_create_engine)
    session_module.get_engine.cache_clear()
    yield captured
    session_module.get_engine.cache_clear()


def _use_database(monkeypatch, url):
    monkeypatch.setattr(session_module, "get_settings", lambda: SimpleNamespace(database_url=url))


def test_postgres_keeps_the_small_bounded_pool(monkeypatch, captured_engine_kwargs):
    # Batas 15 koneksi pooler Supabase bergantung pada ukuran pool ini.
    _use_database(monkeypatch, "postgresql+psycopg://u:p@db.example/app")

    session_module.get_engine()

    assert captured_engine_kwargs["kwargs"] == {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 5,
        "pool_timeout": 30,
        "pool_recycle": 1500,
    }


def test_sqlite_gets_no_queue_pool_arguments(monkeypatch, captured_engine_kwargs):
    _use_database(monkeypatch, "sqlite+pysqlite:///:memory:")

    session_module.get_engine()

    assert captured_engine_kwargs["kwargs"] == {"pool_pre_ping": True}


def test_in_memory_sqlite_engine_is_really_created(monkeypatch):
    session_module.get_engine.cache_clear()
    _use_database(monkeypatch, "sqlite+pysqlite:///:memory:")
    try:
        assert session_module.get_engine().dialect.name == "sqlite"
    finally:
        session_module.get_engine.cache_clear()
