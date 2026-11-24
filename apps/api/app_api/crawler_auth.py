"""Shared-token authentication for stateless crawls."""

import hmac

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.services.integration_review_service import IntegrationRequestError

bearer_scheme = HTTPBearer(auto_error=False)


def require_crawler_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected = get_settings().crawler_api_token
    if not expected:
        raise IntegrationRequestError(
            503, "V2_NOT_CONFIGURED", "The v2 crawl API is not configured."
        )
    token = credentials.credentials if credentials else None
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise IntegrationRequestError(
            401, "INVALID_SERVICE_TOKEN", "Invalid service token."
        )
