from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Only ever reachable when APP_ENV=local; Settings refuses to validate without a
# real INTEGRATION_CURSOR_SECRET anywhere else.
LOCAL_CURSOR_SECRET_FALLBACK = "local-only-cursor-secret-never-deploy-this"
LOCAL_JWT_SECRET_FALLBACK = "local-only-jwt-secret-never-deploy-this"
LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK = (
    "local-only-service-token-pepper-never-deploy-this"
)
DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost.onebox.co.id",
)
REVIEW_SOURCE_MODES = {
    "mock",
    "google_places",
    "google_business_profile",
    "third_party",
    "selenium",
}

# Fields that go through the old _as_int/_as_bool/_as_float/_as_optional_int/
# _as_list helpers, all of which treat a blank env value as absent (use the
# default). Fields using plain os.getenv(name, default) with no such guard
# (app_name, log_level, review_source_mode, etc.) are deliberately NOT in
# this list - a blank value there stays blank, exactly like before.
_BLANK_USES_DEFAULT_FIELDS = (
    "export_dir",
    "google_maps_api_key",
    "gemini_api_key",
    "onebox_base_url",
    "onebox_service_email",
    "onebox_service_password",
    "fetch_limit_per_location",
    "fetch_timeout_seconds",
    "fetch_max_retry",
    "selenium_headless",
    "selenium_default_target_reviews",
    "selenium_max_target_reviews",
    "selenium_scroll_delay_seconds",
    "selenium_max_scroll_attempts",
    "selenium_wait_timeout_seconds",
    "analysis_batch_size",
    "page_size",
    "show_raw_payload",
    "onebox_site_id",
    "onebox_company_id",
    "onebox_worklist_path",
    "onebox_timeout_seconds",
    "onebox_max_retry",
    "onebox_cache_stale_after_seconds",
    "crawl_worker_lease_seconds",
    "crawl_worker_max_attempts",
    "crawl_worker_poll_seconds",
    "crawl_worker_retry_base_seconds",
    "analysis_llm_max_retries",
    "analysis_llm_retry_backoff_seconds",
    "analysis_circuit_breaker_threshold",
    "analysis_llm_concurrency",
)

# Fields whose value floors at a fixed minimum (clamped, never rejected -
# matches every max(N, _as_int(...)) call the old get_settings() made).
_INT_FLOORS = {
    "onebox_timeout_seconds": 1,
    "onebox_max_retry": 0,
    "onebox_cache_stale_after_seconds": 0,
    "crawl_worker_lease_seconds": 60,
    "crawl_worker_max_attempts": 1,
    "crawl_worker_poll_seconds": 1,
    "crawl_worker_retry_base_seconds": 1,
    "analysis_llm_max_retries": 0,
    "analysis_circuit_breaker_threshold": 0,
}


class Settings(BaseModel):
    """Plain, environment-blind value object - constructing Settings(...)
    directly (as tests do) only ever uses what you pass plus the field
    defaults below, exactly like the dataclass this replaced. It never
    reads os.environ. Only _EnvSettings (used solely by get_settings())
    does that."""

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        validate_default=True,
    )

    app_env: str = "local"
    app_name: str = "Review System"
    log_level: str = "INFO"
    export_dir: Path = Path("exports")
    database_url: str
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        DEFAULT_CORS_ALLOWED_ORIGINS
    )
    review_source_mode: str = "mock"
    google_maps_api_key: str | None = None
    google_places_language_code: str = "id"
    google_places_region_code: str = "ID"
    local_llm_base_url: str = "http://192.168.1.115:11434/v1/"
    local_llm_api_key: str | None = "ollama"
    local_llm_model: str = "qwen2.5:7b"
    fetch_limit_per_location: int = 50
    fetch_timeout_seconds: int = 30
    fetch_max_retry: int = 3
    selenium_headless: bool = False
    selenium_default_target_reviews: int = 100
    selenium_max_target_reviews: int = 300
    selenium_scroll_delay_seconds: float = 1.0
    selenium_max_scroll_attempts: int = 400
    selenium_wait_timeout_seconds: int = 20
    selenium_user_data_dir: Path | None = Path(".selenium-profile")
    analysis_batch_size: int = 20
    prompt_version: str = "v1"
    page_size: int = 20
    show_raw_payload: bool = False
    gemini_mode: str = "real"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    integration_cursor_secret: str = LOCAL_CURSOR_SECRET_FALLBACK
    jwt_secret_key: str = LOCAL_JWT_SECRET_FALLBACK
    service_token_pepper: str = LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK
    onebox_base_url: str | None = None
    # Env var abbreviates "service" to "svc" - the field name doesn't, so the
    # default FIELD_NAME.upper() alias would miss it without this.
    onebox_service_email: str | None = Field(
        default=None, validation_alias="ONEBOX_SVC_EMAIL"
    )
    onebox_service_password: str | None = Field(
        default=None, validation_alias="ONEBOX_SVC_PASSWORD"
    )
    onebox_site_id: int | None = None
    onebox_company_id: int | None = None
    onebox_worklist_path: str = "/api/VocWorklist"
    onebox_timeout_seconds: int = 30
    onebox_max_retry: int = 3
    # Env var carries a "WORKLIST_" segment the field name dropped.
    onebox_cache_stale_after_seconds: int = Field(
        default=86400, validation_alias="ONEBOX_WORKLIST_CACHE_STALE_AFTER_SECONDS"
    )
    crawl_worker_lease_seconds: int = 900
    crawl_worker_max_attempts: int = 3
    crawl_worker_poll_seconds: int = 5
    crawl_worker_retry_base_seconds: int = 60
    # DNGO19-3407: retry sesuai permintaan PBI. Backoff sama polanya dengan
    # OneBoxWorklistClient._backoff (min(8.0, base * 2**attempt)).
    analysis_llm_max_retries: int = 2
    analysis_llm_retry_backoff_seconds: float = 1.0
    # Fallback: berhenti setelah N kegagalan LLM beruntun dalam satu run.
    # 0 = mati (perilaku lama).
    analysis_circuit_breaker_threshold: int = 5
    # Bounded parallelism for network-bound LLM calls. Database writes remain
    # serialized by AnalysisService so append-only history/watermarks stay
    # safe. This default (4, clamped to [1, 16]) is what get_settings() has
    # always actually produced in production; the pre-pydantic dataclass
    # field itself defaulted to 1, but that value was only ever reachable by
    # constructing Settings() directly and skipping get_settings() entirely.
    # Normalized to the one that's live, not silently kept split two ways.
    analysis_llm_concurrency: int = 4

    def ensure_export_dir(self) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        return self.export_dir


class _EnvSettings(Settings, BaseSettings):
    """The only env/.env-reading entry point - inherits every field from
    Settings unchanged and adds the environment source plus every
    normalization/clamping/validation rule the old get_settings() applied.

    All of that validation lives here, not on Settings, on purpose: the old
    frozen dataclass ran zero validation on direct construction (no
    __post_init__) - only get_settings() enforced blank-handling, clamps,
    and the "real secrets outside local/test" rule. Settings(...) built
    directly (as tests do throughout the suite) must keep behaving that way.
    Used exclusively by get_settings(); nothing else should reference this
    class directly."""

    model_config = SettingsConfigDict(case_sensitive=False)

    @field_validator(*_BLANK_USES_DEFAULT_FIELDS, mode="before")
    @classmethod
    def _blank_uses_default(cls, value: Any, info) -> Any:
        """A source value of "" (or whitespace) means unset, not "set to
        blank" - matches every old _as_int/_as_bool/_as_float/_as_list/
        _as_optional_int helper and every plain `os.getenv(x) or None`
        field, all of which treated blank as absent."""
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            if not value.strip():
                return DEFAULT_CORS_ALLOWED_ORIGINS
            items = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(items) if items else DEFAULT_CORS_ALLOWED_ORIGINS
        return value

    @field_validator("local_llm_api_key", mode="before")
    @classmethod
    def _blank_local_llm_api_key_is_none(cls, value: Any) -> Any:
        # Absent -> default "ollama" (handled by the field default, this
        # validator isn't even called). Explicitly blank -> None, matching
        # the old os.getenv(..., "ollama") or None.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("selenium_user_data_dir", mode="before")
    @classmethod
    def _blank_selenium_profile_is_none(cls, value: Any) -> Any:
        # Absent -> default ".selenium-profile". Explicitly blank -> None
        # (profile dir disabled), matching Path(value) if value else None.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "app_name",
        "google_places_language_code",
        "google_places_region_code",
        "local_llm_base_url",
        "local_llm_model",
        "prompt_version",
        mode="after",
    )
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("log_level", mode="after")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("gemini_mode", mode="after")
    @classmethod
    def _normalize_gemini_mode(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("gemini_model", mode="after")
    @classmethod
    def _strip_gemini_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("review_source_mode", mode="after")
    @classmethod
    def _validate_review_source_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in REVIEW_SOURCE_MODES:
            raise ValueError(
                "REVIEW_SOURCE_MODE must be mock, google_places, "
                "google_business_profile, third_party, or selenium."
            )
        return normalized

    @field_validator("export_dir", mode="after")
    @classmethod
    def _resolve_export_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else BASE_DIR / value

    @field_validator("selenium_user_data_dir", mode="after")
    @classmethod
    def _resolve_selenium_user_data_dir(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        return value if value.is_absolute() else BASE_DIR / value

    @field_validator("selenium_scroll_delay_seconds", mode="after")
    @classmethod
    def _floor_scroll_delay(cls, value: float) -> float:
        # Lantai 0.5 detik, bukan 2. Nol tidak diizinkan: kartu perlu waktu
        # dimuat setelah digulir, dan menggulir lebih cepat dari itu justru
        # menghasilkan lebih sedikit ulasan.
        return max(0.5, value)

    @field_validator("selenium_max_scroll_attempts", mode="after")
    @classmethod
    def _clamp_max_scroll_attempts(cls, value: int) -> int:
        # Plafon 1000, bukan 100. Rentang tanggal ke periode lampau harus
        # menembus ratusan ulasan yang lebih baru sebelum sampai ke
        # jendelanya; dengan plafon 100 crawl berhenti jauh sebelum itu.
        return min(1000, max(1, value))

    @field_validator("analysis_llm_retry_backoff_seconds", mode="after")
    @classmethod
    def _floor_backoff_seconds(cls, value: float) -> float:
        return max(0.0, value)

    @field_validator("analysis_llm_concurrency", mode="after")
    @classmethod
    def _clamp_llm_concurrency(cls, value: int) -> int:
        return min(16, max(1, value))

    @field_validator("onebox_worklist_path", mode="after")
    @classmethod
    def _normalize_worklist_path(cls, value: str) -> str:
        return value.strip() or "/api/VocWorklist"

    @field_validator(*_INT_FLOORS, mode="after")
    @classmethod
    def _floor_int(cls, value: int, info) -> int:
        return max(_INT_FLOORS[info.field_name], value)

    @model_validator(mode="after")
    def _validate_secrets_outside_local(self) -> _EnvSettings:
        if self.app_env.lower() not in {"local", "test"}:
            missing = [
                name
                for name, value in (
                    ("JWT_SECRET_KEY", self.jwt_secret_key),
                    ("SERVICE_TOKEN_PEPPER", self.service_token_pepper),
                )
                if not value or value.startswith("change-me")
            ]
            if missing:
                raise ValueError(
                    ", ".join(missing)
                    + " must be set to a unique secret outside local/test."
                )
        # This secret signs the pagination cursors. A shared or guessable
        # value lets a caller forge a cursor for another tenant, so anywhere
        # with real data must refuse to boot without its own. Only "local"
        # is exempt here - "test" is not, unlike the jwt/pepper check above.
        if (
            self.integration_cursor_secret == LOCAL_CURSOR_SECRET_FALLBACK
            and self.app_env.lower() != "local"
        ):
            raise ValueError(
                "INTEGRATION_CURSOR_SECRET is required when APP_ENV is not "
                "local. Generate a unique value per environment."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _EnvSettings()
