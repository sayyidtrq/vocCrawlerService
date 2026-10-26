"""HTTP authentication for OneBox service-to-service integration calls."""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.services.api_client_service import ApiClientService, InvalidServiceToken
from app.services.integration_review_service import IntegrationRequestError
from app.services.tenant_registry_service import provisioning_key_hash

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServicePrincipal:
    client_id: int
    key_id: str
    company_id: int
    scopes: frozenset[str]


bearer_scheme = HTTPBearer(auto_error=False)


def require_service_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ServicePrincipal:
    """Verify a bearer token without ever accepting company_id from the request."""

    token = (
        credentials.credentials
        if credentials and credentials.scheme.lower() == "bearer"
        else None
    )
    if not token:
        raise IntegrationRequestError(
            401, "INVALID_SERVICE_TOKEN", "Invalid service token."
        )

    try:
        client = ApiClientService().verify(token)
    except InvalidServiceToken:
        raise IntegrationRequestError(
            401, "INVALID_SERVICE_TOKEN", "Invalid service token."
        )

    principal = ServicePrincipal(
        client_id=client.id,
        key_id=client.key_id,
        company_id=client.company_id,
        scopes=frozenset(client.scopes or []),
    )
    request.state.service_principal = principal
    logger.info(
        "service_auth.success",
        extra={"key_id": principal.key_id, "company_id": principal.company_id},
    )
    return principal


def require_provisioning_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """Gate tenant provisioning behind the platform key OneBox holds.

    Not a ServicePrincipal: the key is not tied to any company, and it cannot
    read or write any tenant's data - it can only register and switch tenants.
    Only its HMAC is configured here (ONEBOX_PROVISIONING_KEY_HASH).
    """

    settings = get_settings()
    expected = settings.onebox_provisioning_key_hash
    if not expected:
        raise IntegrationRequestError(
            503, "PROVISIONING_NOT_CONFIGURED", "Tenant provisioning is not configured."
        )

    key = (
        credentials.credentials
        if credentials and credentials.scheme.lower() == "bearer"
        else None
    )
    supplied = provisioning_key_hash(key, settings.service_token_pepper) if key else ""
    if not key or not hmac.compare_digest(supplied.encode(), expected.encode()):
        logger.warning("provisioning_auth.rejected")
        raise IntegrationRequestError(
            401, "INVALID_PROVISIONING_KEY", "Invalid provisioning key."
        )

    if not settings.onebox_managed:
        raise IntegrationRequestError(
            409,
            "TENANT_MODE_NOT_MANAGED",
            "Tenant provisioning needs ONEBOX_TENANT_MODE=managed.",
        )
