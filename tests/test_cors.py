from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import DEFAULT_CORS_ALLOWED_ORIGINS
from apps.api import main as api_main


def test_default_cors_allows_all_local_onebox_feature_pages(monkeypatch):
    assert "https://localhost.onebox.co.id" in DEFAULT_CORS_ALLOWED_ORIGINS
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(cors_allowed_origins=DEFAULT_CORS_ALLOWED_ORIGINS),
    )

    response = TestClient(api_main.create_app()).options(
        "/api/health",
        headers={
            "Origin": "https://localhost.onebox.co.id",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://localhost.onebox.co.id"
    )


def test_default_cors_does_not_allow_unlisted_origin(monkeypatch):
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(cors_allowed_origins=DEFAULT_CORS_ALLOWED_ORIGINS),
    )

    response = TestClient(api_main.create_app()).options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
