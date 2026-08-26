from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db.session import get_engine

logger = logging.getLogger(__name__)


def mask_secret(secret: str | None) -> str:
    if not secret:
        return "NOT FOUND"
    suffix = secret[-4:] if len(secret) >= 4 else secret
    return f"{'*' * 12}{suffix}"


class SettingsService:
    def __init__(self, settings: Settings | None = None, engine=None):
        self.settings = settings or get_settings()
        self.engine = engine or get_engine()

    def check_database_connection(self) -> dict:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            inspector = inspect(self.engine)
            required_tables = {
                "locations",
                "reviews",
                "review_analysis",
                "fetch_logs",
            }
            missing_tables = sorted(
                table for table in required_tables if not inspector.has_table(table)
            )
            if missing_tables:
                return {
                    "ok": False,
                    "message": (
                        "Database schema is not ready. Run `alembic upgrade head`. "
                        f"Missing tables: {', '.join(missing_tables)}"
                    ),
                }
            logger.info("Database connection check succeeded")
            return {"ok": True, "message": "OK"}
        except SQLAlchemyError as exc:
            logger.error("Database connection check failed: %s", exc)
            return {"ok": False, "message": str(exc)}

    def check_local_llm_key(self) -> dict:
        return {
            "found": bool(self.settings.local_llm_api_key),
            "masked": mask_secret(self.settings.local_llm_api_key) if self.settings.local_llm_api_key else None,
        }

    def check_review_source_key(self) -> dict:
        return {
            "found": bool(self.settings.google_maps_api_key),
            "masked": mask_secret(self.settings.google_maps_api_key),
        }

    def public_configuration(self) -> dict:
        return {
            "APP_ENV": self.settings.app_env,
            "APP_NAME": self.settings.app_name,
            "LOG_LEVEL": self.settings.log_level,
            "EXPORT_DIR": str(self.settings.export_dir),
            "DATABASE_URL": self._masked_database_url(),
            "REVIEW_SOURCE_MODE": self.settings.review_source_mode,
            "GOOGLE_PLACES_LANGUAGE_CODE": (
                self.settings.google_places_language_code
            ),
            "GOOGLE_PLACES_REGION_CODE": self.settings.google_places_region_code,
            "GEMINI_MODE": self.settings.gemini_mode,
            "GEMINI_MODEL": self.settings.gemini_model,
            "FETCH_LIMIT_PER_LOCATION": self.settings.fetch_limit_per_location,
            "FETCH_TIMEOUT_SECONDS": self.settings.fetch_timeout_seconds,
            "FETCH_MAX_RETRY": self.settings.fetch_max_retry,
            "SELENIUM_HEADLESS": self.settings.selenium_headless,
            "SELENIUM_DEFAULT_TARGET_REVIEWS": (
                self.settings.selenium_default_target_reviews
            ),
            "SELENIUM_MAX_TARGET_REVIEWS": (
                self.settings.selenium_max_target_reviews
            ),
            "SELENIUM_SCROLL_DELAY_SECONDS": (
                self.settings.selenium_scroll_delay_seconds
            ),
            "SELENIUM_MAX_SCROLL_ATTEMPTS": (
                self.settings.selenium_max_scroll_attempts
            ),
            "SELENIUM_WAIT_TIMEOUT_SECONDS": (
                self.settings.selenium_wait_timeout_seconds
            ),
            "SELENIUM_USER_DATA_DIR": (
                str(self.settings.selenium_user_data_dir)
                if self.settings.selenium_user_data_dir
                else ""
            ),
            "ANALYSIS_BATCH_SIZE": self.settings.analysis_batch_size,
            "ANALYSIS_LLM_CONCURRENCY": self.settings.analysis_llm_concurrency,
            "PROMPT_VERSION": self.settings.prompt_version,
            "PAGE_SIZE": self.settings.page_size,
            "SHOW_RAW_PAYLOAD": self.settings.show_raw_payload,
        }

    def _masked_database_url(self) -> str:
        value = self.settings.database_url
        if "@" not in value or "://" not in value:
            return "configured"
        scheme, remainder = value.split("://", 1)
        credentials, host = remainder.rsplit("@", 1)
        username = credentials.split(":", 1)[0]
        return f"{scheme}://{username}:********@{host}"
