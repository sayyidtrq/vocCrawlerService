from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.services.settings_service import SettingsService
from apps.api.app_api.serializers import to_jsonable
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal


router = APIRouter(tags=["settings"])


@router.get(
    "/settings",
    summary="Konfigurasi runtime (non-rahasia)",
    description="Mengembalikan konfigurasi publik aplikasi dan status ketersediaan API key (nilai key selalu di-masking).",
    responses={200: {"content": {"application/json": {"example": {"app_env": "local", "app_name": "Review System", "review_source_mode": "selenium", "page_size": 20, "google_maps_api_key": "****", "google_maps_api_key_configured": True}}}}},
)
def get_public_settings(principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    settings = get_settings()
    service = SettingsService(settings)
    review_source_key = service.check_review_source_key()
    local_llm_key = service.check_local_llm_key()
    return to_jsonable(
        {
            "app_env": settings.app_env,
            "app_name": settings.app_name,
            "log_level": settings.log_level,
            "export_dir": settings.export_dir,
            "review_source_mode": settings.review_source_mode,
            "google_places_language_code": settings.google_places_language_code,
            "google_places_region_code": settings.google_places_region_code,
            "local_llm_model": settings.local_llm_model,
            "fetch_limit_per_location": settings.fetch_limit_per_location,
            "fetch_timeout_seconds": settings.fetch_timeout_seconds,
            "fetch_max_retry": settings.fetch_max_retry,
            "selenium_headless": settings.selenium_headless,
            "selenium_default_target_reviews": (
                settings.selenium_default_target_reviews
            ),
            "selenium_max_target_reviews": settings.selenium_max_target_reviews,
            "selenium_scroll_delay_seconds": settings.selenium_scroll_delay_seconds,
            "selenium_max_scroll_attempts": settings.selenium_max_scroll_attempts,
            "selenium_wait_timeout_seconds": (
                settings.selenium_wait_timeout_seconds
            ),
            "selenium_user_data_dir": settings.selenium_user_data_dir,
            "analysis_batch_size": settings.analysis_batch_size,
            "prompt_version": settings.prompt_version,
            "page_size": settings.page_size,
            "show_raw_payload": settings.show_raw_payload,
            "google_maps_api_key": review_source_key["masked"],
            "local_llm_api_key": local_llm_key["masked"],
            "google_maps_api_key_configured": review_source_key["found"],
            "local_llm_api_key_configured": local_llm_key["found"],
        }
    )


@router.get(
    "/settings/database-check",
    summary="Cek koneksi database",
    description="Memeriksa apakah koneksi ke PostgreSQL berhasil.",
    responses={200: {"content": {"application/json": {"example": {"ok": True, "message": "Database connection successful."}}}}},
)
def check_database_connection(principal: ServicePrincipal = Depends(require_service_principal)) -> dict:
    return to_jsonable(SettingsService().check_database_connection())
