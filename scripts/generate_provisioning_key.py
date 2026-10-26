"""Create the key OneBox uses to register tenants, and the hash the crawler stores."""

from __future__ import annotations

from app.config import LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK, get_settings
from app.services.tenant_registry_service import new_provisioning_key, provisioning_key_hash


def main() -> None:
    settings = get_settings()
    if settings.service_token_pepper == LOCAL_SERVICE_TOKEN_PEPPER_FALLBACK:
        print("WARNING: SERVICE_TOKEN_PEPPER is the local fallback; set the real one first,")
        print("because the hash below is only valid with the pepper it was made with.\n")
    key = new_provisioning_key()
    print("Give this key to OneBox. It is shown once and is not stored here:")
    print(f"  {key}\n")
    print("Put this in the crawler environment (.env):")
    print(f"  ONEBOX_PROVISIONING_KEY_HASH={provisioning_key_hash(key, settings.service_token_pepper)}")


if __name__ == "__main__":
    main()
