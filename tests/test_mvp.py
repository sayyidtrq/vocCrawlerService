from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, FetchLog, Location, Review, ReviewAnalysis
from app.integrations.local_llm_client import LocalLLMClient
from app.integrations.mock_gemini_client import MockGeminiClient
from app.services.analysis_service import AnalysisService
from app.services.export_service import ExportService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.summary_service import SummaryService
from app.utils.hashing import generate_review_hash
from apps.api.app_api.schemas import AnalysisPendingResponse


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
def settings(tmp_path):
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
        selenium_headless=True,
        selenium_default_target_reviews=100,
        selenium_max_target_reviews=300,
        selenium_scroll_delay_seconds=2,
        selenium_max_scroll_attempts=100,
        selenium_wait_timeout_seconds=20,
        selenium_user_data_dir=None,
        analysis_batch_size=3,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


@pytest.fixture()
def company_id(session_factory):
    with session_factory() as session:
        company = Company(
            name="Test Company",
            ai_enable_flag=True,
            total_enable_review=100,
            analyze_competitor_flag=False,
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        return company.id


def add_location(session_factory, company_id):
    return LocationService(
        company_id=company_id, session_factory=session_factory
    ).add_location(
        hospital_name="Hermina",
        branch_name="Hermina Depok",
        city="Depok",
        address="Jl. Siliwangi",
        latitude="",
        longitude="",
        source="google_places",
        external_place_id="mock-hermina-depok",
        is_active=True,
    )


def test_hash_is_deterministic():
    review = {
        "source": "mock",
        "external_place_id": "place-1",
        "external_review_id": "review-1",
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Baik",
        "review_time": "2026-06-19T09:00:00+07:00",
    }
    assert generate_review_hash(review) == generate_review_hash(dict(review))


def test_fetch_deduplicates_and_dry_run_does_not_insert(
    session_factory, settings, company_id
):
    location = add_location(session_factory, company_id)
    service = FetchService(
        company_id=company_id, session_factory=session_factory, settings=settings
    )

    first = service.fetch_location(location.id)
    second = service.fetch_location(location.id)
    dry_run = service.dry_run_location(location.id)

    assert first["status"] == "success"
    assert first["total_inserted"] == 10
    assert second["total_inserted"] == 0
    assert second["total_duplicate"] == 10
    assert dry_run["total_fetched"] == 10

    with session_factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 10
        assert session.scalar(select(func.count(FetchLog.id))) == 3
        statuses = list(
            session.scalars(select(FetchLog.status).order_by(FetchLog.id))
        )
        assert statuses == ["success", "success", "dry_run"]


def test_analysis_is_structured_and_rerun_is_append_only(
    session_factory, settings, company_id
):
    location = add_location(session_factory, company_id)
    FetchService(
        company_id=company_id, session_factory=session_factory, settings=settings
    ).fetch_location(location.id)
    mock_client = MockGeminiClient()
    mock_client.last_usage = {
        "prompt_tokens": 5,
        "completion_tokens": 2,
        "total_tokens": 7,
    }
    analysis = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=mock_client,
    )

    initial = analysis.analyze_pending()
    rerun = analysis.rerun_review(1)

    assert initial["success"] == 10
    assert initial["failed"] == 0
    assert initial["tokens_used"] == 70
    assert initial["token_usage"] == {
        "prompt_tokens": 50,
        "completion_tokens": 20,
        "total_tokens": 70,
    }
    assert rerun["success"] == 1
    assert rerun["tokens_used"] == 7
    with session_factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 11
        assert (
            session.scalar(
                select(func.count(ReviewAnalysis.id)).where(
                    ReviewAnalysis.review_id == 1
                )
            )
            == 2
        )


def test_rating_only_review_uses_deterministic_fallback(
    session_factory, settings, company_id
):
    location = add_location(session_factory, company_id)
    with session_factory() as session:
        session.add(
            Review(
                company_id=company_id,
                location_id=location.id,
                source="google_maps",
                external_review_id="rating-only-1",
                review_hash="rating-only-hash-1",
                reviewer_name="Anonymous",
                rating=1,
                review_text="",
            )
        )
        session.commit()

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=MockGeminiClient(),
    ).analyze_pending()

    assert result["success"] == 1
    assert result["failed"] == 0
    assert result["skipped_empty"] == 0
    assert result["rating_fallback"] == 1
    assert result["tokens_used"] == 0
    response = AnalysisPendingResponse.model_validate(result).model_dump()
    assert response["rating_fallback"] == 1
    assert response["tokens_used"] == 0
    assert response["token_usage"]["total_tokens"] == 0
    with session_factory() as session:
        analysis = session.scalar(select(ReviewAnalysis))
        assert analysis.sentiment == "negative"
        assert analysis.urgency == "medium"
        assert analysis.issue_category == "other"
        assert analysis.model_name == "rating-fallback-v1"
        assert analysis.is_patient_safety_issue is False
        assert "tanpa komentar tertulis" in analysis.summary


def test_analysis_status_distinguishes_completed_incomplete_and_failed(
    session_factory, settings, company_id
):
    location = add_location(session_factory, company_id)
    with session_factory() as session:
        session.add_all(
            [
                Review(
                    company_id=company_id,
                    location_id=location.id,
                    source="google_maps",
                    review_hash=f"status-{name}",
                    review_text=name,
                )
                for name in ("complete", "incomplete", "failed")
            ]
        )
        session.commit()

    class StatusClient:
        model_name = "status-test"

        def __init__(self):
            self.last_usage = {}

        def analyze_review(self, review):
            if review["review_text"] == "failed":
                raise RuntimeError("provider secret must not leak")
            return {
                "issue_category": "general_praise",
                "urgency": "low",
                "summary": "Ringkasan" if review["review_text"] == "complete" else "",
                "recommended_action": "Pertahankan pelayanan",
            }

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=StatusClient(),
    ).analyze_pending()

    assert result["success"] == 2
    assert result["failed"] == 1
    assert result["errors"] == [{"review_id": 3, "error": "Analysis failed."}]
    with session_factory() as session:
        statuses = list(session.scalars(select(Review.analysis_status).order_by(Review.id)))
        assert statuses == ["completed", "incomplete", "failed"]
    assert AnalysisService._result_status(
        {
            "urgency": "low",
            "issue_category": "general_praise",
            "summary": "Ringkasan",
            "recommended_action": "Pertahankan pelayanan",
        }
    ) == "completed"


def test_local_llm_normalizes_invalid_category_and_boolean(settings):
    content = json.dumps(
        {
            "sentiment": "negative",
            "sentiment_score": 0.8,
            "issue_category": "staff_service",
            "urgency": "medium",
            "summary": "Ringkasan.",
            "recommended_action": "Tindak lanjuti.",
            "keywords": ["staf"],
            "is_potential_viral": "low",
            "is_patient_safety_issue": "false",
        }
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: response)
        )
    )

    result = LocalLLMClient(settings, sdk_client=sdk).analyze_review(
        {
            "rating": 2,
            "reviewer_name": "Anonymous",
            "review_time": None,
            "review_text": "Pelayanan perlu diperbaiki.",
        }
    )

    assert result["issue_category"] == "staff_communication"
    assert result["is_potential_viral"] is False
    assert result["is_patient_safety_issue"] is False


def test_summary_and_exports(session_factory, settings, company_id):
    location = add_location(session_factory, company_id)
    FetchService(
        company_id=company_id, session_factory=session_factory, settings=settings
    ).fetch_location(location.id)
    AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=MockGeminiClient(),
    ).analyze_pending()

    with session_factory() as session:
        summary = SummaryService(
            company_id=company_id, session=session
        ).overall_summary()
    export = ExportService(
        company_id=company_id, session_factory=session_factory, settings=settings
    )
    reviews_csv = export.export_all_reviews_csv()
    location_csv = export.export_location_reviews_csv(location.id)
    summary_csv = export.export_analysis_summary_csv()
    raw_json = export.export_raw_reviews_json()

    assert summary["total_locations"] == 1
    assert summary["total_reviews"] == 10
    assert summary["analyzed_reviews"] == 10
    assert summary["pending_analysis"] == 0
    assert all(
        path.exists()
        for path in [reviews_csv, location_csv, summary_csv, raw_json]
    )


def set_ai_config(session_factory, location_id, **fields):
    with session_factory() as session:
        row = session.get(Location, location_id)
        for key, value in fields.items():
            setattr(row, key, value)
        session.commit()


def fetched_location(session_factory, settings, company_id):
    location = add_location(session_factory, company_id)
    FetchService(
        company_id=company_id, session_factory=session_factory, settings=settings
    ).fetch_location(location.id)
    return location


def test_analysis_uses_the_model_onebox_chose(session_factory, settings, company_id):
    """The model recorded against the analysis is the one OneBox picked."""
    location = fetched_location(session_factory, settings, company_id)
    set_ai_config(session_factory, location.id, ai_model="llama3.2-1b")

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=MockGeminiClient(),
    ).analyze_pending()

    assert result["success"] == 10
    assert result["skipped_ai_disabled"] == 0
    with session_factory() as session:
        models = {row.model_name for row in session.scalars(select(ReviewAnalysis))}
    assert models == {"llama3.2-1b"}


def test_analysis_leaves_the_injected_client_alone_when_onebox_is_silent(
    session_factory, settings, company_id
):
    """No choice from OneBox must not mean "swap in the local LLM".

    The client is injectable. Falling back to settings.local_llm_model here
    would silently retag every analysis with a model that never ran.
    """
    fetched_location(session_factory, settings, company_id)

    client = MockGeminiClient()
    AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=client,
    ).analyze_pending()

    with session_factory() as session:
        models = {row.model_name for row in session.scalars(select(ReviewAnalysis))}
    assert models == {"mock-gemini-v1"}
    assert client.model_name == "mock-gemini-v1"


def test_analysis_skips_a_location_onebox_disabled(
    session_factory, settings, company_id
):
    """ai_enabled=0 must stop the write, not just the model call.

    Checked before the rating-only fallback, which also writes an analysis
    row: skipping only the model call would still leave rows behind for a
    branch whose analysis was explicitly switched off.
    """
    location = fetched_location(session_factory, settings, company_id)
    set_ai_config(session_factory, location.id, ai_enabled=False)

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=MockGeminiClient(),
    ).analyze_pending()

    assert result["success"] == 0
    assert result["skipped_ai_disabled"] == 10
    with session_factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 0


class FlakyClient(MockGeminiClient):
    """Fails a fixed number of times, then succeeds — for retry tests."""

    model_name = "flaky-v1"

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def analyze_review(self, review):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient failure")
        return super().analyze_review(review)


class AlwaysFailingClient(MockGeminiClient):
    model_name = "always-fail-v1"

    def analyze_review(self, review):
        raise RuntimeError("boom")


class DiscoverableModelClient(MockGeminiClient):
    model_name = "mock"

    def list_models(self):
        return ["mock"]


def test_unavailable_onebox_model_falls_back_to_deployment_default(
    session_factory, settings, company_id
):
    location = fetched_location(session_factory, settings, company_id)
    set_ai_config(session_factory, location.id, ai_model="llama3.2-1b")

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=DiscoverableModelClient(),
    ).analyze_pending()

    assert result["success"] == 10
    assert result["failed"] == 0
    assert result["model_fallbacks"] == 1
    assert "using deployment default 'mock'" in result["warnings"][0]
    with session_factory() as session:
        models = {row.model_name for row in session.scalars(select(ReviewAnalysis))}
    assert models == {"mock"}


def test_analysis_retries_a_transient_llm_failure_then_succeeds(
    session_factory, settings, company_id
):
    """A network blip must not permanently fail a review (DNGO19-3407).

    Backoff is forced to 0 so the test does not actually sleep — what is
    being checked is that the retry happens and the review still succeeds,
    not the exact delay.
    """
    fetched_location(session_factory, settings, company_id)
    fast_settings = settings.model_copy(
        update={"analysis_llm_retry_backoff_seconds": 0.0}
    )
    client = FlakyClient(fail_times=1)

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=fast_settings,
        client=client,
    ).analyze_pending()

    assert result["success"] == 10
    assert result["failed"] == 0
    assert result["llm_calls"] == 11
    assert result["llm_retries"] == 1
    # Two attempts for the first review (1 failure + 1 success), one each
    # for the rest.
    assert client.calls == 11


def test_analysis_runs_llm_calls_with_bounded_concurrency(
    session_factory, settings, company_id
):
    """Network calls overlap, while the service still persists serially."""

    fetched_location(session_factory, settings, company_id)
    concurrent_settings = settings.model_copy(
        update={"analysis_llm_concurrency": 3}
    )
    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    class ProbeClient(MockGeminiClient):
        model_name = "concurrency-probe-v1"

        def analyze_review(self, review):
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.02)
                return super().analyze_review(review)
            finally:
                with lock:
                    state["active"] -= 1

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=concurrent_settings,
        client=ProbeClient(),
        client_factory=ProbeClient,
    ).analyze_pending()

    assert result["success"] == 10
    assert result["failed"] == 0
    assert result["concurrency"] == 3
    assert result["max_in_flight"] == 3
    assert state["max_active"] == 3


def test_analysis_gives_up_after_max_retries(session_factory, settings, company_id):
    """A model that is genuinely down must still fail — retry is bounded.

    Circuit breaker disabled here on purpose: this test isolates PER-REVIEW
    retry exhaustion, not the run-level breaker (covered separately below).
    """
    fetched_location(session_factory, settings, company_id)
    fast_settings = settings.model_copy(
        update={
            "analysis_llm_max_retries": 1,
            "analysis_llm_retry_backoff_seconds": 0.0,
            "analysis_circuit_breaker_threshold": 0,
        }
    )

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=fast_settings,
        client=AlwaysFailingClient(),
    ).analyze_pending()

    assert result["success"] == 0
    assert result["failed"] == 10
    assert len(result["errors"]) == 10
    assert result["circuit_breaker_tripped"] is False
    with session_factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 0


def test_analysis_circuit_breaker_stops_after_consecutive_failures(
    session_factory, settings, company_id
):
    """FALLBACK (DNGO19-3407): a model that is down must not be hammered

    for every remaining review in the queue — stop after N failures in a
    row and leave the rest untouched (not marked failed) so a normal
    re-run picks them straight back up as pending.
    """
    fetched_location(session_factory, settings, company_id)
    fast_settings = settings.model_copy(
        update={
            "analysis_llm_max_retries": 0,
            "analysis_circuit_breaker_threshold": 3,
        }
    )

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=fast_settings,
        client=AlwaysFailingClient(),
    ).analyze_pending()

    assert result["failed"] == 3
    assert result["not_attempted"] == 7
    assert result["circuit_breaker_tripped"] is True
    with session_factory() as session:
        # Untouched, not failed: analysis_status is still the column default.
        pending = session.scalar(
            select(func.count(Review.id)).where(Review.analysis_status == "pending")
        )
    assert pending == 7


def test_analysis_quality_flags_a_result_the_model_got_wrong(
    session_factory, settings, company_id
):
    """A model that ignores the contract must be visible as a quality signal.

    An out-of-contract issue_category is silently normalized to "other" so
    storage never breaks — but that correction has to be COUNTED somewhere,
    or a model that is quietly wrong 40% of the time looks identical to one
    that is not.
    """
    fetched_location(session_factory, settings, company_id)

    class WrongCategoryClient(MockGeminiClient):
        model_name = "wrong-category-v1"

        def analyze_review(self, review):
            result = super().analyze_review(review)
            result["issue_category"] = "not_a_real_category"
            return result

    result = AnalysisService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=WrongCategoryClient(),
    ).analyze_pending()

    assert result["success"] == 10
    assert result["quality"]["corrected"] == 10
    assert result["quality"]["valid"] == 0
    with session_factory() as session:
        categories = {
            row.issue_category for row in session.scalars(select(ReviewAnalysis))
        }
    assert categories == {"other"}


class NamedModelClient(MockGeminiClient):
    """MockGeminiClient with a caller-chosen model_name, for rollback tests."""

    def __init__(self, model_name):
        self.model_name = model_name


def test_rollback_analyses_reverts_to_the_prior_model_when_one_exists(
    session_factory, settings, company_id
):
    """Prosedur rollback (DNGO19-3407): a bad rollout must not leave a hole.

    model-a analyzes everything first, then model-b (the bad rollout) reruns
    all of it, appending a second row per review. Rolling back model-b must
    bring every review back to model-a's answer, not to nothing.
    """
    location = fetched_location(session_factory, settings, company_id)
    AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
        client=NamedModelClient("model-a"),
    ).analyze_pending()
    AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
        client=NamedModelClient("model-b"),
    ).rerun_location(location.id)

    with session_factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 20

    summary = AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
    ).rollback_analyses(model_name="model-b")

    assert summary["analyses_removed"] == 10
    assert summary["reviews_affected"] == 10
    assert summary["reverted_to_prior_analysis"] == 10
    assert summary["reset_to_pending"] == 0

    with session_factory() as session:
        remaining = list(session.scalars(select(ReviewAnalysis)))
        statuses = {row.analysis_status for row in session.scalars(select(Review))}
    assert {row.model_name for row in remaining} == {"model-a"}
    assert len(remaining) == 10
    assert statuses == {"completed"}


def test_rollback_analyses_resets_to_pending_with_no_prior_model(
    session_factory, settings, company_id
):
    """No earlier answer to fall back to -> the review goes back to pending,

    so the next normal run picks it up rather than it silently staying
    unanalyzed forever.
    """
    fetched_location(session_factory, settings, company_id)
    AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
        client=NamedModelClient("only-model"),
    ).analyze_pending()

    summary = AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
    ).rollback_analyses(model_name="only-model")

    assert summary["analyses_removed"] == 10
    assert summary["reverted_to_prior_analysis"] == 0
    assert summary["reset_to_pending"] == 10
    with session_factory() as session:
        assert session.scalar(select(func.count(ReviewAnalysis.id))) == 0
        statuses = {row.analysis_status for row in session.scalars(select(Review))}
    assert statuses == {"pending"}


def test_rollback_analyses_requires_a_model_name(session_factory, settings, company_id):
    """No target = wipe the wrong thing by accident. Refuse it outright."""
    service = AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
    )
    with pytest.raises(ValueError):
        service.rollback_analyses(model_name="")


def test_quality_summary_reports_the_recent_status_distribution(
    session_factory, settings, company_id
):
    """Monitoring (DNGO19-3407): failed vs completed must be visible without

    an operator noticing manually first.
    """
    fetched_location(session_factory, settings, company_id)
    fast_settings = settings.model_copy(
        update={
            "analysis_llm_max_retries": 0,
            "analysis_circuit_breaker_threshold": 0,
        }
    )

    class HalfFailingClient(MockGeminiClient):
        model_name = "half-failing-v1"

        def __init__(self):
            self.calls = 0

        def analyze_review(self, review):
            self.calls += 1
            if self.calls % 2 == 0:
                raise RuntimeError("boom")
            return super().analyze_review(review)

    AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=fast_settings,
        client=HalfFailingClient(),
    ).analyze_pending()

    summary = AnalysisService(
        company_id=company_id, session_factory=session_factory, settings=settings,
    ).quality_summary(hours=24)

    assert summary["total"] == 10
    assert summary["by_status"]["completed"] == 5
    assert summary["by_status"]["failed"] == 5
    assert summary["failure_rate"] == 0.5
