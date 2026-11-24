"""Fixtures for the industry-taxonomy tests (names are prefixed to stay clear of per-file ones)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company

# Identical copy of onecloud/onecloud/tests/voc/fixtures/worklist_taxonomy_fixture.json
# (a kesehatan and a spbu item). Regenerate it from OneBox, never edit it here.
TAXONOMY_FIXTURE = Path(__file__).parent / "fixtures" / "worklist_taxonomy_fixture.json"


@pytest.fixture()
def tx_fixture():
    return json.loads(TAXONOMY_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def tx_spbu(tx_fixture):
    return copy.deepcopy(
        next(body for key, body in tx_fixture["taxonomies"].items() if key.startswith("spbu:"))
    )


@pytest.fixture()
def tx_kesehatan(tx_fixture):
    return copy.deepcopy(
        next(body for key, body in tx_fixture["taxonomies"].items() if key.startswith("kesehatan:"))
    )


@pytest.fixture()
def tx_tagged():
    """body -> the same snapshot with the site's tagging config switched on."""

    def make(body, max_tags=5, thresholds=None):
        tagged = copy.deepcopy(body)
        tagged["tagging"] = {"enabled": True, "max_tags": max_tags, "thresholds": thresholds or {}}
        return tagged

    return make


@pytest.fixture()
def tx_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def tx_settings(tmp_path):
    return Settings(
        app_env="test",
        app_name="Review System",
        log_level="INFO",
        export_dir=tmp_path / "exports",
        database_url="sqlite+pysqlite:///:memory:",
        cors_allowed_origins=("http://localhost:3000",),
        review_source_mode="mock",
        google_maps_api_key=None,
        google_places_language_code="id",
        google_places_region_code="ID",
        local_llm_base_url="http://localhost:11434/v1/",
        local_llm_api_key="test",
        local_llm_model="mock",
        fetch_limit_per_location=50,
        fetch_timeout_seconds=1,
        fetch_max_retry=0,
        crawl_max_target_reviews=300,
        analysis_batch_size=3,
        analysis_llm_max_retries=0,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


@pytest.fixture()
def tx_company_id(tx_session_factory):
    with tx_session_factory() as session:
        company = Company(
            name="Tenant", ai_enable_flag=True, total_enable_review=100, analyze_competitor_flag=False
        )
        session.add(company)
        session.commit()
        return company.id
