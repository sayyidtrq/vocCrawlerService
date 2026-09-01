from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Only ever reachable when APP_ENV=local; get_settings refuses to start without a
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


def _as_float(name: str, default: float) -> float:
    """Baca setelan pecahan; jeda gulir kini boleh di bawah satu detik."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == '':
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _as_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer when set.") from exc


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_name: str
    log_level: str
    export_dir: Path
    database_url: str
    cors_allowed_origins: tuple[str, ...]
    review_source_mode: str
    google_maps_api_key: str | None
    google_places_language_code: str
    google_places_region_code: str
    local_llm_base_url: str
    local_llm_api_key: str | None
    local_llm_model: str
    fetch_limit_per_location: int
    fetch_timeout_seconds: int
    fetch_max_retry: int
    selenium_headless: bool
    selenium_default_target_reviews: int
    selenium_max_target_reviews: int
    selenium_scroll_delay_seconds: float
    selenium_max_scroll_attempts: int
    selenium_wait_timeout_seconds: int
    selenium_user_data_dir: Path | None
    analysis_batch_size: int
    prompt_version: str
    page_size: int
    show_raw_payload: bool
    gemini_mode: str = "real"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    # Default is for tests that build Settings directly; get_settings() still
    # refuses to boot outside local without a real INTEGRATION_CURSOR_SECRET.
    integration_cursor_secret: str = LOCAL_CURSOR_SECRET_FALLBACK
    jwt_secret_key: str = LOCAL_JWT_SECRET_FALLBACK
    service_token_pepper: str = LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK
    onebox_base_url: str | None = None
    onebox_service_email: str | None = None
    onebox_service_password: str | None = None
    onebox_site_id: int | None = None
    onebox_company_id: int | None = None
    onebox_worklist_path: str = "/api/VocWorklist"
    onebox_timeout_seconds: int = 30
    onebox_max_retry: int = 3
    onebox_cache_stale_after_seconds: int = 86400
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
    # serialized by AnalysisService so append-only history/watermarks stay safe.
    analysis_llm_concurrency: int = 1

    def ensure_export_dir(self) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        return self.export_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    review_mode = os.getenv("REVIEW_SOURCE_MODE", "mock").strip().lower()
    if review_mode not in {
        "mock",
        "google_places",
        "google_business_profile",
        "third_party",
        "selenium",
    }:
        raise ValueError(
            "REVIEW_SOURCE_MODE must be mock, google_places, "
            "google_business_profile, third_party, or selenium."
        )

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is required in .env.")

    app_env = os.getenv("APP_ENV", "local").strip()
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
    service_token_pepper = os.getenv("SERVICE_TOKEN_PEPPER", "").strip()
    if app_env.lower() not in {"local", "test"}:
        missing = [
            name
            for name, value in (
                ("JWT_SECRET_KEY", jwt_secret_key),
                ("SERVICE_TOKEN_PEPPER", service_token_pepper),
            )
            if not value or value.startswith("change-me")
        ]
        if missing:
            raise ValueError(
                ", ".join(missing)
                + " must be set to a unique secret outside local/test."
            )
    jwt_secret_key = jwt_secret_key or LOCAL_JWT_SECRET_FALLBACK
    service_token_pepper = service_token_pepper or LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK

    integration_cursor_secret = os.getenv("INTEGRATION_CURSOR_SECRET", "").strip()
    if not integration_cursor_secret:
        # This secret signs the pagination cursors. A shared or guessable value
        # lets a caller forge a cursor for another tenant, so anywhere with real
        # data must refuse to boot without its own.
        if app_env.lower() != "local":
            raise ValueError(
                "INTEGRATION_CURSOR_SECRET is required when APP_ENV is not local. "
                "Generate a unique value per environment."
            )
        integration_cursor_secret = LOCAL_CURSOR_SECRET_FALLBACK

    export_value = os.getenv("EXPORT_DIR", "exports").strip() or "exports"
    export_dir = Path(export_value)
    if not export_dir.is_absolute():
        export_dir = BASE_DIR / export_dir

    selenium_profile_value = os.getenv(
        "SELENIUM_USER_DATA_DIR", ".selenium-profile"
    ).strip()
    selenium_user_data_dir = (
        Path(selenium_profile_value) if selenium_profile_value else None
    )
    if selenium_user_data_dir and not selenium_user_data_dir.is_absolute():
        selenium_user_data_dir = BASE_DIR / selenium_user_data_dir

    return Settings(
        app_env=app_env,
        app_name=os.getenv("APP_NAME", "Review System").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        export_dir=export_dir,
        database_url=database_url,
        cors_allowed_origins=tuple(
            _as_list(
                "CORS_ALLOWED_ORIGINS",
                list(DEFAULT_CORS_ALLOWED_ORIGINS),
            )
        ),
        review_source_mode=review_mode,
        google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY") or None,
        google_places_language_code=os.getenv(
            "GOOGLE_PLACES_LANGUAGE_CODE", "id"
        ).strip(),
        google_places_region_code=os.getenv("GOOGLE_PLACES_REGION_CODE", "ID").strip(),
        gemini_mode=os.getenv("GEMINI_MODE", "real").strip().lower(),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        local_llm_base_url=os.getenv(
            "LOCAL_LLM_BASE_URL", "http://192.168.1.115:11434/v1/"
        ).strip(),
        local_llm_api_key=os.getenv("LOCAL_LLM_API_KEY", "ollama") or None,
        local_llm_model=os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b").strip(),
        fetch_limit_per_location=_as_int("FETCH_LIMIT_PER_LOCATION", 50),
        fetch_timeout_seconds=_as_int("FETCH_TIMEOUT_SECONDS", 30),
        fetch_max_retry=_as_int("FETCH_MAX_RETRY", 3),
        selenium_headless=_as_bool("SELENIUM_HEADLESS", False),
        selenium_default_target_reviews=_as_int("SELENIUM_DEFAULT_TARGET_REVIEWS", 100),
        selenium_max_target_reviews=_as_int("SELENIUM_MAX_TARGET_REVIEWS", 300),
        # Lantai 0.5 detik, bukan 2. Nol tidak diizinkan: kartu perlu waktu
        # dimuat setelah digulir, dan menggulir lebih cepat dari itu justru
        # menghasilkan lebih sedikit ulasan.
        selenium_scroll_delay_seconds=max(
            0.5, _as_float("SELENIUM_SCROLL_DELAY_SECONDS", 1.0)
        ),
        # Plafon 1000, bukan 100. Rentang tanggal ke periode lampau harus
        # menembus ratusan ulasan yang lebih baru sebelum sampai ke jendelanya;
        # dengan plafon 100 crawl berhenti jauh sebelum itu. Batas waktu per
        # job yang sekarang menjaga durasinya, bukan lagi jumlah gulir.
        selenium_max_scroll_attempts=min(
            1000, max(1, _as_int("SELENIUM_MAX_SCROLL_ATTEMPTS", 400))
        ),
        selenium_wait_timeout_seconds=_as_int("SELENIUM_WAIT_TIMEOUT_SECONDS", 20),
        selenium_user_data_dir=selenium_user_data_dir,
        analysis_batch_size=_as_int("ANALYSIS_BATCH_SIZE", 20),
        analysis_llm_max_retries=max(0, _as_int("ANALYSIS_LLM_MAX_RETRIES", 2)),
        analysis_llm_retry_backoff_seconds=max(
            0.0, _as_float("ANALYSIS_LLM_RETRY_BACKOFF_SECONDS", 1.0)
        ),
        analysis_circuit_breaker_threshold=max(
            0, _as_int("ANALYSIS_CIRCUIT_BREAKER_THRESHOLD", 5)
        ),
        analysis_llm_concurrency=min(
            16, max(1, _as_int("ANALYSIS_LLM_CONCURRENCY", 4))
        ),
        prompt_version=os.getenv("PROMPT_VERSION", "v1").strip(),
        page_size=_as_int("PAGE_SIZE", 20),
        show_raw_payload=_as_bool("SHOW_RAW_PAYLOAD", False),
        integration_cursor_secret=integration_cursor_secret,
        jwt_secret_key=jwt_secret_key,
        service_token_pepper=service_token_pepper,
        onebox_base_url=os.getenv("ONEBOX_BASE_URL") or None,
        onebox_service_email=os.getenv("ONEBOX_SVC_EMAIL") or None,
        onebox_service_password=os.getenv("ONEBOX_SVC_PASSWORD") or None,
        onebox_site_id=_as_optional_int("ONEBOX_SITE_ID"),
        onebox_company_id=_as_optional_int("ONEBOX_COMPANY_ID"),
        onebox_worklist_path=(
            os.getenv("ONEBOX_WORKLIST_PATH", "/api/VocWorklist").strip()
            or "/api/VocWorklist"
        ),
        onebox_timeout_seconds=max(1, _as_int("ONEBOX_TIMEOUT_SECONDS", 30)),
        onebox_max_retry=max(0, _as_int("ONEBOX_MAX_RETRY", 3)),
        onebox_cache_stale_after_seconds=max(
            0, _as_int("ONEBOX_WORKLIST_CACHE_STALE_AFTER_SECONDS", 86400)
        ),
        crawl_worker_lease_seconds=max(60, _as_int("CRAWL_WORKER_LEASE_SECONDS", 900)),
        crawl_worker_max_attempts=max(1, _as_int("CRAWL_WORKER_MAX_ATTEMPTS", 3)),
        crawl_worker_poll_seconds=max(1, _as_int("CRAWL_WORKER_POLL_SECONDS", 5)),
        crawl_worker_retry_base_seconds=max(
            1, _as_int("CRAWL_WORKER_RETRY_BASE_SECONDS", 60)
        ),
    )
