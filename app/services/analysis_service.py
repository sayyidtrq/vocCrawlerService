from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Location, Review, ReviewAnalysis
from app.db.session import get_session_factory
from app.integrations.gemini_client import GeminiClientBase
from app.integrations.local_llm_client import LocalLLMClient

logger = logging.getLogger(__name__)
RATING_FALLBACK_MODEL = "rating-fallback-v1"
# Shape of the analysis fields this build emits on the integration contract.
# Kept in step with apps.api.app_api.integration_schemas.API_VERSION, which is
# what OneBox actually compares against.
OUTPUT_SCHEMA_VERSION = "v1"
ALLOWED_SENTIMENTS = {"positive", "neutral", "negative", "mixed", "unknown"}
ALLOWED_URGENCIES = {"low", "medium", "high", "critical", "unknown"}
ALLOWED_CATEGORIES = {
    "doctor_service",
    "nurse_service",
    "administration",
    "waiting_time",
    "cleanliness",
    "facility",
    "parking",
    "billing",
    "pharmacy",
    "emergency_room",
    "inpatient",
    "customer_service",
    "booking_system",
    "staff_communication",
    "security",
    "food",
    "general_praise",
    "other",
}
ANALYSIS_STATUSES = {"pending", "completed", "failed", "incomplete"}
REQUIRED_ANALYSIS_FIELDS = (
    "urgency",
    "issue_category",
    "summary",
    "recommended_action",
)


class LlmCallError(RuntimeError):
    """Retry-exhausted call with safe timing/count metadata for run metrics."""

    def __init__(self, attempts: int, call_seconds: float):
        super().__init__("LLM call failed after retries.")
        self.attempts = attempts
        self.call_seconds = call_seconds


class AnalysisService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: GeminiClientBase | None = None,
        client_factory=None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        if client:
            self.client = client
            self._client_factory = client_factory
        else:
            self.client = LocalLLMClient(self.settings)
            self._client_factory = client_factory or (
                lambda: LocalLLMClient(self.settings)
            )
        self._worker_local = threading.local()

    def analyze_pending(
        self, location_id: int | None = None, rating: int | None = None
    ) -> dict:
        # DEDUPLICATION (DNGO19-3407): the WHERE below is the dedup — a review
        # with any analysis row is never picked up again by this path.
        #
        # KNOWN GAP, accepted: analyze_pending/rerun_* and the pipeline endpoint
        # (apps/api/app_api/routers/pipeline.py) all call this. Two overlapping
        # runs can both read the same review as pending before either writes,
        # producing a duplicate ReviewAnalysis row for it. Harmless: storage is
        # append-only, the newest row always wins as "latest", and the review
        # never ends up with a wrong or missing answer — just one wasted LLM
        # call. Not worth a locking scheme for a narrow, self-healing race.
        pending_exists = exists(
            select(ReviewAnalysis.id).where(ReviewAnalysis.review_id == Review.id)
        )
        statement = select(Review).where(~pending_exists).order_by(Review.id)
        if self.company_id is not None:
            statement = statement.where(Review.company_id == self.company_id)
        if location_id is not None:
            statement = statement.where(Review.location_id == location_id)
        if rating is not None:
            statement = statement.where(Review.rating == rating)
        with self.session_factory() as session:
            reviews = list(session.scalars(statement))
            review_data = [self._review_to_dict(review) for review in reviews]
        return self._analyze_items(review_data)

    def rerun_review(self, review_id: int) -> dict:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            review = session.scalar(statement)
            if review is None:
                raise ValueError("Review not found.")
            review_data = self._review_to_dict(review)
        return self._analyze_items([review_data])

    def rerun_location(self, location_id: int) -> dict:
        with self.session_factory() as session:
            statement = (
                select(Review)
                .where(Review.location_id == location_id)
                .order_by(Review.id)
            )
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            reviews = list(session.scalars(statement))
            review_data = [self._review_to_dict(review) for review in reviews]
        return self._analyze_items(review_data)

    def _analyze_items(self, reviews: list[dict]) -> dict:
        result = {
            "total": len(reviews),
            "success": 0,
            "failed": 0,
            "skipped_empty": 0,
            "rating_fallback": 0,
            "sentiments": {
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "mixed": 0,
                "unknown": 0,
            },
            "errors": [],
            "skipped_ai_disabled": 0,
            "tokens_used": 0,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            # BASELINE (DNGO19-3407): durasi dan kualitas dari run yang
            # sungguhan, supaya bottleneck ditentukan dari angka nyata.
            "duration_ms": 0.0,
            "llm_calls": 0,
            "llm_retries": 0,
            "llm_call_ms_total": 0.0,
            "quality": {"valid": 0, "corrected": 0},
            "not_attempted": 0,
            "circuit_breaker_tripped": False,
            "concurrency": (
                max(1, int(self.settings.analysis_llm_concurrency or 1))
                if self._client_factory is not None
                else 1
            ),
            "max_in_flight": 0,
        }
        batch_size = max(1, self.settings.analysis_batch_size)
        result["concurrency"] = min(batch_size, result["concurrency"])
        ai_config = self._location_ai_config(
            {review.get("location_id") for review in reviews}
        )
        # Restored in the finally below. The client is reused across batches and
        # may be shared with the caller, so leaking one location's model choice
        # into the next run would be invisible and would only show up as the
        # wrong model_name recorded against unrelated reviews.
        default_model = getattr(self.client, "model_name", None)
        started = time.perf_counter()
        try:
            self._run_batches(reviews, batch_size, ai_config, result, default_model)
        finally:
            if default_model is not None:
                self.client.model_name = default_model
            result["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            # Satu baris terstruktur per run, dipakai monitoring eksternal (grep
            # atau log shipper) tanpa perlu membaca "errors" yang bisa panjang.
            logger.info(
                "analysis.run.summary total=%s success=%s failed=%s not_attempted=%s "
                "rating_fallback=%s skipped_ai_disabled=%s duration_ms=%s "
                "llm_calls=%s llm_call_ms_total=%s quality_corrected=%s "
                "llm_retries=%s concurrency=%s max_in_flight=%s "
                "circuit_breaker_tripped=%s",
                result["total"], result["success"], result["failed"], result["not_attempted"],
                result["rating_fallback"], result["skipped_ai_disabled"],
                result["duration_ms"], result["llm_calls"], result["llm_call_ms_total"],
                result["quality"]["corrected"], result["llm_retries"],
                result["concurrency"], result["max_in_flight"],
                result["circuit_breaker_tripped"],
            )
        return result

    def _run_batches(
        self,
        reviews: list[dict],
        batch_size: int,
        ai_config: dict,
        result: dict,
        default_model: str | None,
    ) -> None:
        """Run bounded LLM waves, then persist results on this thread.

        Only model calls run concurrently. Validation and database writes stay
        ordered and serial, preserving append-only history and sync watermarks.
        The breaker is checked between waves, so at most ``concurrency - 1``
        calls that already started can finish after its threshold is reached.
        """
        breaker_threshold = max(0, int(self.settings.analysis_circuit_breaker_threshold or 0))
        consecutive_failures = 0
        concurrency = max(1, min(batch_size, int(result["concurrency"])))
        executor = (
            ThreadPoolExecutor(
                max_workers=concurrency, thread_name_prefix="voc-analysis"
            )
            if concurrency > 1
            else None
        )

        try:
            for batch_start in range(0, len(reviews), batch_size):
                batch = reviews[batch_start : batch_start + batch_size]

                for wave_start in range(0, len(batch), concurrency):
                    wave = batch[wave_start : wave_start + concurrency]

                    if result["circuit_breaker_tripped"]:
                        result["not_attempted"] += len(reviews) - (
                            batch_start + wave_start
                        )
                        return

                    calls = []
                    for review in wave:
                        config = ai_config.get(review.get("location_id"))

                        if config is not None and not config["enabled"]:
                            result["skipped_ai_disabled"] += 1
                            continue

                        model_name = (
                            config["model"]
                            if config is not None and config["model"]
                            else default_model
                        )

                        if not review["review_text"].strip():
                            raw_result = self._rating_only_result(review.get("rating"))
                            cleaned, corrected = self._validate_result(raw_result)
                            self._record_quality(result, corrected)
                            self._store_analysis(
                                review["id"],
                                cleaned,
                                raw_result,
                                model_name=RATING_FALLBACK_MODEL,
                            )
                            result["success"] += 1
                            result["rating_fallback"] += 1
                            result["sentiments"][cleaned["sentiment"]] += 1
                            continue

                        future = (
                            executor.submit(
                                self._run_llm_task, review, model_name, True
                            )
                            if executor is not None
                            else None
                        )
                        calls.append((review, model_name, future))

                    result["max_in_flight"] = max(
                        result["max_in_flight"], len(calls)
                    )

                    for review, model_name, future in calls:
                        try:
                            outcome = (
                                future.result()
                                if future is not None
                                else self._run_llm_task(review, model_name, False)
                            )
                        except LlmCallError as exc:
                            self._record_call_metrics(
                                result, exc.attempts, exc.call_seconds
                            )
                            self._store_failure_status(review["id"])
                            result["failed"] += 1
                            result["errors"].append(
                                {"review_id": review["id"], "error": "Analysis failed."}
                            )
                            logger.exception(
                                "Analysis failed for review %s", review["id"]
                            )
                            consecutive_failures += 1
                            if (
                                breaker_threshold
                                and consecutive_failures >= breaker_threshold
                            ):
                                result["circuit_breaker_tripped"] = True
                            continue

                        consecutive_failures = 0
                        self._record_call_metrics(
                            result, outcome["attempts"], outcome["call_seconds"]
                        )
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                            result["token_usage"][key] += int(
                                outcome["usage"].get(key, 0) or 0
                            )
                        result["tokens_used"] = result["token_usage"]["total_tokens"]
                        cleaned, corrected = self._validate_result(
                            outcome["raw_result"]
                        )
                        self._record_quality(result, corrected)
                        self._store_analysis(
                            review["id"],
                            cleaned,
                            outcome["raw_result"],
                            model_name=outcome["model_name"],
                        )
                        result["success"] += 1
                        result["sentiments"][cleaned["sentiment"]] += 1
        finally:
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=False)

    def _run_llm_task(
        self, review: dict, model_name: str | None, isolated_client: bool
    ) -> dict:
        client = self._worker_client() if isolated_client else self.client
        if model_name is not None:
            client.model_name = model_name

        raw_result, call_seconds, attempts = self._call_llm_with_retry(
            client, review
        )
        return {
            "raw_result": raw_result,
            "call_seconds": call_seconds,
            "attempts": attempts,
            "usage": dict(getattr(client, "last_usage", {}) or {}),
            "model_name": getattr(client, "model_name", model_name),
        }

    def _worker_client(self):
        client = getattr(self._worker_local, "client", None)
        if client is None:
            if self._client_factory is None:
                return self.client
            client = self._client_factory()
            self._worker_local.client = client
        return client

    @staticmethod
    def _record_call_metrics(
        result: dict, attempts: int, call_seconds: float
    ) -> None:
        result["llm_calls"] += attempts
        result["llm_retries"] += max(0, attempts - 1)
        result["llm_call_ms_total"] += round(call_seconds * 1000, 1)

    def _call_llm_with_retry(self, client, review: dict) -> tuple[dict, float, int]:
        """client.analyze_review dengan retry + backoff eksponensial (DNGO19-3407).

        Pola backoff SAMA dengan OneBoxWorklistClient._backoff
        (min(8.0, base * 2**attempt)), supaya "seberapa sabar sebelum menyerah"
        konsisten di seluruh crawler, bukan konvensi berbeda-beda per klien.

        SEMUA exception dianggap layak dicoba ulang: GeminiClientBase generik
        ini tidak melempar tipe exception yang membedakan gangguan jaringan
        dari JSON yang rusak, keduanya tiba sebagai Exception biasa. Percobaan
        yang gagal permanen tetap dibatasi max_retries, jadi biayanya terbatas.

        Timing includes every actual model attempt but excludes backoff sleep;
        run duration separately captures the full wall-clock cost.
        """
        max_retries = max(0, int(self.settings.analysis_llm_max_retries or 0))
        base_backoff = max(0.0, float(self.settings.analysis_llm_retry_backoff_seconds or 0))

        retries_done = 0
        attempts = 0
        call_seconds = 0.0
        while True:
            started = time.perf_counter()
            attempts += 1
            try:
                raw_result = client.analyze_review(review)
                call_seconds += time.perf_counter() - started
                return raw_result, call_seconds, attempts
            except Exception as exc:
                call_seconds += time.perf_counter() - started
                if retries_done >= max_retries:
                    raise LlmCallError(attempts, call_seconds) from exc
                delay = (
                    min(8.0, base_backoff * (2**retries_done))
                    if base_backoff > 0
                    else 0.0
                )
                retries_done += 1
                logger.warning(
                    "LLM call failed for review %s (attempt %s/%s), retry in %.1fs: %s",
                    review.get("id"), attempts, max_retries + 1, delay, exc,
                )
                if delay > 0:
                    time.sleep(delay)

    @staticmethod
    def _record_quality(result: dict, corrected: bool) -> None:
        result["quality"]["corrected" if corrected else "valid"] += 1

    def _location_ai_config(self, location_ids: set) -> dict:
        """Per-location AI config as delivered by the OneBox worklist.

        Read once per run rather than per review: a catch-up pass sweeps
        thousands of rows and the answer is identical for every review of the
        same branch.

        Locations missing from the map — a review whose location was deleted, or
        a crawler running standalone with no worklist behind it — get no entry,
        and the caller treats that as "no opinion from OneBox" rather than as
        disabled. Silence from the control plane must not stop analysis.
        """
        wanted = {int(value) for value in location_ids if value is not None}
        if not wanted:
            return {}

        with self.session_factory() as session:
            statement = select(Location).where(Location.id.in_(wanted))
            if self.company_id is not None:
                statement = statement.where(Location.company_id == self.company_id)
            rows = list(session.scalars(statement))

        config = {}
        for row in rows:
            expected = row.ai_output_schema_version
            if expected and expected != OUTPUT_SCHEMA_VERSION:
                # Logged, never fatal. OneBox asking for a schema this build
                # cannot produce is a real mismatch worth seeing, but refusing to
                # analyze would turn a version skew into an outage — and OneBox
                # already validates the shape it receives on its own side.
                logger.warning(
                    "Location %s expects output schema %s but this build emits %s.",
                    row.id,
                    expected,
                    OUTPUT_SCHEMA_VERSION,
                )
            config[row.id] = {"enabled": bool(row.ai_enabled), "model": row.ai_model}
        return config

    def _store_analysis(
        self,
        review_id: int,
        cleaned: dict,
        raw_result: dict,
        model_name: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            if session.bind.dialect.name == "postgresql":
                # Serialise against a concurrent analysis of the same review so the
                # two cannot interleave and leave the watermark behind the newer
                # analysis row. SQLite has no row locks and no concurrent writers.
                statement = statement.with_for_update()

            review = session.scalar(statement)
            if review is None:
                raise ValueError(f"Review {review_id} not found in this company.")

            session.add(
                ReviewAnalysis(
                    review_id=review_id,
                    sentiment=cleaned["sentiment"],
                    sentiment_score=cleaned["sentiment_score"],
                    issue_category=cleaned["issue_category"],
                    urgency=cleaned["urgency"],
                    summary=cleaned["summary"],
                    recommended_action=cleaned["recommended_action"],
                    keywords=cleaned["keywords"],
                    is_potential_viral=cleaned["is_potential_viral"],
                    is_patient_safety_issue=cleaned["is_patient_safety_issue"],
                    model_name=model_name or self.client.model_name,
                    prompt_version=self.settings.prompt_version,
                    raw_response=raw_result,
                )
            )
            review.analysis_status = self._result_status(cleaned)
            # Same transaction as the insert, deliberately. If the analysis
            # committed and the watermark did not, the review would sit below every
            # consumer's checkpoint forever and its analysis would never be
            # delivered — silent permanent data loss rather than a retryable error.
            #
            # Postgres: clock_timestamp(), not now(), which is frozen at
            # transaction start and would hand two analyses in one batch the same
            # watermark. SQLite (tests only) has no clock_timestamp, and its
            # CURRENT_TIMESTAMP drops microseconds — since SQLAlchemy stores
            # DATETIME as text, a second-precision value sorts as a prefix of a
            # microsecond one and would corrupt the keyset ordering. Use the Python
            # clock there instead; the single-process test has no skew to worry about.
            review.sync_updated_at = (
                func.clock_timestamp()
                if session.bind.dialect.name == "postgresql"
                else datetime.now(timezone.utc)
            )
            session.commit()

    def _store_failure_status(self, review_id: int) -> None:
        with self.session_factory() as session:
            statement = select(Review).where(Review.id == review_id)
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            if session.bind.dialect.name == "postgresql":
                statement = statement.with_for_update()

            review = session.scalar(statement)
            if review is None:
                raise ValueError(f"Review {review_id} not found in this company.")

            review.analysis_status = "failed"
            review.sync_updated_at = (
                func.clock_timestamp()
                if session.bind.dialect.name == "postgresql"
                else datetime.now(timezone.utc)
            )
            session.commit()

    @staticmethod
    def _result_status(result: dict) -> str:
        return (
            "completed"
            if all(str(result.get(field) or "").strip() for field in REQUIRED_ANALYSIS_FIELDS)
            else "incomplete"
        )

    @staticmethod
    def _rating_only_result(rating: int | None) -> dict:
        if rating is None:
            sentiment = "unknown"
            score = 0.0
            urgency = "unknown"
            summary = "Reviewer tidak menulis komentar dan rating tidak tersedia."
            action = "Tandai sebagai masukan tanpa konteks dan pantau pola serupa."
        elif rating <= 2:
            sentiment = "negative"
            score = 0.85
            urgency = "medium"
            summary = f"Reviewer memberikan rating {rating}/5 tanpa komentar tertulis."
            action = (
                "Tindak lanjuti rating rendah bila identitas reviewer tersedia dan "
                "pantau pola serupa pada lokasi ini."
            )
        elif rating == 3:
            sentiment = "neutral"
            score = 0.75
            urgency = "low"
            summary = "Reviewer memberikan rating 3/5 tanpa komentar tertulis."
            action = "Pantau pola rating dan kumpulkan konteks tambahan bila tersedia."
        else:
            sentiment = "positive"
            score = 0.85
            urgency = "low"
            summary = f"Reviewer memberikan rating {rating}/5 tanpa komentar tertulis."
            action = "Pertahankan mutu layanan dan pantau konsistensi rating."

        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "issue_category": "other",
            "urgency": urgency,
            "summary": summary,
            "recommended_action": action,
            "keywords": [],
            "is_potential_viral": False,
            "is_patient_safety_issue": False,
            "analysis_source": RATING_FALLBACK_MODEL,
        }

    @staticmethod
    def _review_to_dict(review: Review) -> dict:
        return {
            "id": review.id,
            "rating": review.rating,
            "review_text": review.review_text,
            "reviewer_name": review.reviewer_name,
            "review_time": review.review_time,
            "location_id": review.location_id,
        }

    @staticmethod
    def _validate_result(result: dict) -> tuple[dict, bool]:
        """Normalisasi hasil mentah model, DAN tandai kalau ada yang dikoreksi.

        Bendera `corrected` adalah sinyal kualitas baseline (DNGO19-3407):
        model yang sering mengirim bentuk di luar kontrak adalah model yang
        perlu diganti atau prompt-nya diperbaiki — tanpa bendera ini, koreksi
        yang terjadi diam-diam di sini tidak pernah terlihat siapa pun.
        """
        corrected = False

        sentiment = str(result.get("sentiment") or "unknown").lower()
        if sentiment not in ALLOWED_SENTIMENTS:
            corrected = True
            sentiment = "unknown"
        urgency = str(result.get("urgency") or "unknown").lower()
        if urgency not in ALLOWED_URGENCIES:
            corrected = True
            urgency = "unknown"
        category = str(result.get("issue_category") or "other").lower()
        if category not in ALLOWED_CATEGORIES:
            corrected = True
            category = "other"
        try:
            score = float(result.get("sentiment_score", 0))
        except (TypeError, ValueError):
            corrected = True
            score = 0.0
        clamped = max(0.0, min(1.0, score))
        corrected = corrected or clamped != score
        score = clamped
        keywords = result.get("keywords")
        if not isinstance(keywords, list):
            corrected = True
            keywords = []
        cleaned = {
            "sentiment": sentiment,
            "sentiment_score": score,
            "issue_category": category,
            "urgency": urgency,
            "summary": str(result.get("summary") or ""),
            "recommended_action": str(result.get("recommended_action") or ""),
            "keywords": [str(keyword) for keyword in keywords],
            "is_potential_viral": bool(result.get("is_potential_viral", False)),
            "is_patient_safety_issue": bool(
                result.get("is_patient_safety_issue", False)
            ),
        }
        return cleaned, corrected

    def rollback_analyses(
        self, model_name: str, since: datetime | None = None,
    ) -> dict:
        """Prosedur rollback (DNGO19-3407): buang hasil satu model, kembalikan
        review yang terdampak ke jawaban SEBELUMNYA bila ada.

        DIPAKAI KETIKA. Sebuah model (atau versi prompt) ternyata menghasilkan
        analisa yang salah secara sistematis — bukan satu review yang gagal,
        tetapi satu ROLLOUT yang buruk. Yang dibutuhkan operator adalah "buang
        semua yang berasal dari model X, biarkan yang berikutnya menganalisa
        ulang", bukan memperbaiki review satu per satu.

        KENAPA AMAN. ReviewAnalysis bersifat append-only (lihat catatan di
        _store_analysis) — setiap analisa ulang MENAMBAH baris, tidak pernah
        menimpa yang lama. Rollback di sini memakai sifat itu: baris milik
        model_name yang ditarget dihapus, lalu setiap review yang terdampak
        diperiksa apakah masih punya baris analisa LEBIH LAMA dari model lain
        — kalau ada, review itu "kembali" ke jawaban itu (status dihitung
        ulang dari baris tersebut); kalau tidak ada sama sekali, review itu
        kembali menjadi pending dan dianalisa ulang pada run berikutnya.

        model_name WAJIB DIISI dengan sengaja — rollback tanpa target adalah
        cara tercepat menghapus riwayat analisa yang sah tanpa niat.

        @return ringkasan: berapa baris dibuang, berapa review terdampak,
            berapa yang kembali ke jawaban lama vs kembali ke pending.
        """
        model_name = (model_name or "").strip()
        if not model_name:
            raise ValueError(
                "rollback_analyses butuh model_name — rollback tanpa target "
                "akan menghapus riwayat analisa yang sah tanpa niat."
            )

        with self.session_factory() as session:
            statement = select(ReviewAnalysis).where(
                ReviewAnalysis.model_name == model_name
            )
            if since is not None:
                statement = statement.where(ReviewAnalysis.created_at >= since)
            if self.company_id is not None:
                statement = statement.join(
                    Review, Review.id == ReviewAnalysis.review_id
                ).where(Review.company_id == self.company_id)

            bad_rows = list(session.scalars(statement))
            review_ids = sorted({row.review_id for row in bad_rows})
            removed = len(bad_rows)

            for row in bad_rows:
                session.delete(row)
            session.flush()

            reverted_to_prior = 0
            reset_to_pending = 0

            for review_id in review_ids:
                prior = session.scalar(
                    select(ReviewAnalysis)
                    .where(ReviewAnalysis.review_id == review_id)
                    .order_by(ReviewAnalysis.id.desc())
                    .limit(1)
                )
                review = session.get(Review, review_id)
                if review is None:
                    continue

                if prior is not None:
                    review.analysis_status = self._result_status(
                        {
                            "urgency": prior.urgency,
                            "issue_category": prior.issue_category,
                            "summary": prior.summary,
                            "recommended_action": prior.recommended_action,
                        }
                    )
                    reverted_to_prior += 1
                else:
                    review.analysis_status = "pending"
                    reset_to_pending += 1

                review.sync_updated_at = (
                    func.clock_timestamp()
                    if session.bind.dialect.name == "postgresql"
                    else datetime.now(timezone.utc)
                )

            session.commit()

        summary = {
            "model_name": model_name,
            "analyses_removed": removed,
            "reviews_affected": len(review_ids),
            "reverted_to_prior_analysis": reverted_to_prior,
            "reset_to_pending": reset_to_pending,
        }
        logger.warning("analysis.rollback %s", summary)
        return summary

    def quality_summary(self, hours: int = 24) -> dict:
        """Sebaran analysis_status baru-baru ini — sinyal kesehatan murah
        untuk MONITORING (DNGO19-3407).

        Dipakai alerting eksternal: kalau porsi "failed" melonjak dibanding
        biasanya, itu tanda AI-nya bermasalah sebelum ada operator yang lapor.

        Memakai Review.updated_at yang sudah ada di skema, TANPA migrasi baru
        — harganya, kolom itu juga ikut bergerak pada pembaruan review yang
        bukan analisa (mis. hasil scrape ulang), sehingga angkanya adalah
        perkiraan aktivitas terbaru, bukan jejak analisa yang presisi.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=max(0, hours))

        with self.session_factory() as session:
            statement = (
                select(Review.analysis_status, func.count())
                .where(Review.updated_at >= since)
                .group_by(Review.analysis_status)
            )
            if self.company_id is not None:
                statement = statement.where(Review.company_id == self.company_id)
            rows = session.execute(statement).all()

        counts = {status: int(count) for status, count in rows}
        total = sum(counts.values())
        failed = counts.get("failed", 0)

        return {
            "hours": hours,
            "since": since.isoformat(),
            "total": total,
            "by_status": counts,
            "failure_rate": round(failed / total, 4) if total else None,
        }
