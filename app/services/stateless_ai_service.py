"""Request-only AI decisions with best-effort audit history."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.config import Settings
from app.db.audit_models import AuditAnalysis
from app.db.session import get_session_factory
from app.integrations.analysis_client import create_analysis_client
from app.services.analysis_service import AnalysisService, RATING_FALLBACK_MODEL
from app.services.integration_review_service import IntegrationRequestError
from app.services.reply_suggestion_service import DEFAULT_PRESET_THRESHOLD, decide
from app.services.taxonomy_service import Taxonomy, validate_body

logger = logging.getLogger(__name__)
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _usage(values=None) -> dict:
    return {key: int((values or {}).get(key) or 0) for key in TOKEN_FIELDS}


def _taxonomy(body: dict | None, fallback_key: str | None) -> Taxonomy | None:
    if body is None:
        return None
    key = body.get("key") or fallback_key or ""
    if not isinstance(key, str) or len(key) > 80:
        return None
    try:
        validated = validate_body(key, body)
        if validated is None:
            return None
        taxonomy = Taxonomy(validated)
        # validate_body checks aspects; also reject unusable flag/alias structures.
        flags = taxonomy.flags({})
        taxonomy.category(None)
        taxonomy.is_safety(flags)
        taxonomy.is_viral(flags)
        return taxonomy
    except (TypeError, ValueError, KeyError, AttributeError):
        return None


class StatelessAiService:
    def __init__(
        self, settings: Settings, *, client_factory=create_analysis_client,
        session_factory=None,
    ):
        self.settings = settings
        self.client_factory = client_factory
        self.session_factory = session_factory if session_factory is not None else lambda: get_session_factory()()

    def analyze(self, params: dict) -> dict:
        provider = params.get("provider") or self.settings.analysis_provider
        taxonomy = _taxonomy(params.get("taxonomy"), params.get("taxonomy_key"))
        if params.get("taxonomy") is not None and taxonomy is None:
            raise IntegrationRequestError(400, "INVALID_TAXONOMY", "The taxonomy is not usable.")
        # Local to this request: concurrent requests may select different providers.
        worker = threading.local()

        def run(review: dict) -> tuple[dict, dict, str | None]:
            usage = _usage()
            result = {
                "id": review["id"], "review_hash": review.get("review_hash"),
                "status": "rating_fallback", "corrected": False, "analysis": None, "error": None,
            }
            if not review["text"].strip():
                raw = AnalysisService._rating_only_result(review.get("rating"), taxonomy)
                result["analysis"], result["corrected"] = AnalysisService._validate_result(raw, taxonomy)
                return result, usage, RATING_FALLBACK_MODEL

            if not hasattr(worker, "client"):
                try:
                    worker.client = self.client_factory(self.settings, provider)
                except Exception as exc:
                    raise IntegrationRequestError(
                        503, "PROVIDER_NOT_CONFIGURED", "The AI provider is not configured."
                    ) from exc
            client = worker.client
            llm_review = {
                "id": review["id"], "rating": review.get("rating"), "review_text": review["text"],
                "reviewer_name": review.get("reviewer_name"), "review_time": None, "location_id": None,
            }
            if taxonomy is not None:
                llm_review["taxonomy"] = taxonomy.body
            try:
                raw = self._call_llm_with_retry(client, llm_review, usage)
                result["analysis"], result["corrected"] = AnalysisService._validate_result(raw, taxonomy)
                result["status"] = "analyzed"
            except Exception:
                result["status"] = "failed"
                result["error"] = {"code": "ANALYSIS_FAILED", "message": "Analysis failed."}
            return result, usage, getattr(client, "model_name", None)

        reviews = params["reviews"]
        concurrency = min(len(reviews), max(1, int(self.settings.analysis_llm_concurrency or 1)))
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="v2-analysis") as executor:
            outcomes = list(executor.map(run, reviews))
        data = {
            "provider": provider,
            "model": next(
                (model for result, _, model in outcomes if result["status"] != "rating_fallback"),
                RATING_FALLBACK_MODEL,
            ),
            "summary": {
                status: sum(result["status"] == status for result, _, _ in outcomes)
                for status in ("analyzed", "rating_fallback", "failed")
            },
            "usage": {key: sum(usage[key] for _, usage, _ in outcomes) for key in TOKEN_FIELDS},
            "results": [result for result, _, _ in outcomes],
        }
        self._write_audit([
            AuditAnalysis(
                site_id=params.get("site_id", 0), review_ref=result["id"], review_hash=result["review_hash"],
                kind="analysis", provider=provider, model=model,
                taxonomy_key=(taxonomy.key or None) if taxonomy is not None else None,
                status=result["status"], result=result["analysis"] if result["analysis"] is not None else result["error"],
                **usage,
            )
            for result, usage, model in outcomes
        ])
        return data

    def _call_llm_with_retry(self, client, review: dict, usage: dict) -> dict:
        max_retries = max(0, int(self.settings.analysis_llm_max_retries or 0))
        base = max(0.0, float(self.settings.analysis_llm_retry_backoff_seconds or 0))
        retries_done = 0
        while True:
            # A failed call must not reuse the preceding review's usage.
            client.last_usage = {}
            try:
                return client.analyze_review(review)
            except Exception:
                if retries_done >= max_retries:
                    raise
                delay = min(8.0, base * (2**retries_done)) if base > 0 else 0.0
                retries_done += 1
                logger.warning("V2 analysis call failed; retry %s/%s in %.1fs", retries_done, max_retries, delay)
                if delay > 0:
                    time.sleep(delay)
            finally:
                for key, value in _usage(getattr(client, "last_usage", None)).items():
                    usage[key] += value

    def suggest_reply(self, params: dict) -> dict:
        taxonomy = _taxonomy(params["taxonomy"], params.get("taxonomy_key"))
        text = params["text"].strip()
        presets = params["presets"]
        usage, model = _usage(), None
        none = {"mode": "none", "tokens_used": 0}
        error = None
        if taxonomy is None:
            data = {**none, "reason": "taxonomy_unavailable"}
        elif not text:
            data = {**none, "reason": "no_text"}
        elif not presets:
            data = {**none, "reason": "no_presets"}
        else:
            try:
                client = self.client_factory(self.settings, "jev")
                model = getattr(client, "model_name", None)
                answer = client.suggest_reply(text, presets, taxonomy.risk_flags)
                usage = _usage(getattr(client, "last_usage", None))
                data = decide(
                    answer, taxonomy, presets,
                    params.get("thresholds", {}).get("preset", DEFAULT_PRESET_THRESHOLD), model=model,
                )
            except Exception:
                error = IntegrationRequestError(
                    502, "SUGGESTION_FAILED", "The AI provider could not suggest a reply."
                )
                data = {"code": error.code, "message": error.message}
        review_hash = params.get("review_hash")
        self._write_audit([AuditAnalysis(
            site_id=params.get("site_id", 0), review_ref=(review_hash or "")[:64], review_hash=review_hash,
            kind="reply_suggestion", provider="jev", model=model,
            taxonomy_key=(taxonomy.key or None) if taxonomy is not None else None,
            status="failed" if error else data["mode"], result=data, **usage,
        )])
        if error is not None:
            raise error
        return data

    def _write_audit(self, rows: list[AuditAnalysis]) -> None:
        try:
            with self.session_factory() as session:
                session.add_all(rows)
                session.commit()
        except Exception as exc:
            logger.warning("V2 AI audit write failed: %s", exc)
