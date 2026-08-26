"""CLI for issuing, rotating, listing, and revoking VOC service tokens."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from app.services.api_client_service import ApiClientService


def _service() -> ApiClientService:
    return ApiClientService()


def _print_token(result) -> None:
    print("Service token (shown once; copy it to the OneBox secret/config store):")
    print(result.token)
    print(f"key_id={result.client.key_id}")
    print(f"company_id={result.client.company_id}")
    print(f"scopes={','.join(result.client.scopes or [])}")


def _issue(args: argparse.Namespace) -> None:
    expires_at = None
    if args.expires_days is not None:
        if args.expires_days <= 0:
            raise SystemExit("--expires-days must be greater than zero")
        expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_days)
    result = _service().issue(
        company_id=args.company_id,
        name=args.name,
        scopes=args.scope,
        expires_at=expires_at,
    )
    _print_token(result)


def _list(args: argparse.Namespace) -> None:
    for client in _service().list_clients(args.company_id):
        print(
            f"key_id={client.key_id} company_id={client.company_id} "
            f"name={client.name!r} scopes={','.join(client.scopes or [])} "
            f"active={client.is_active} expires_at={client.expires_at} "
            f"revoked_at={client.revoked_at}"
        )


def _revoke(args: argparse.Namespace) -> None:
    if not args.yes:
        answer = input(f"Revoke active key {args.key_id}? type 'revoke' to confirm: ")
        if answer != "revoke":
            raise SystemExit("Revoke cancelled")
    client = _service().revoke(args.key_id)
    print(f"revoked key_id={client.key_id}")


def _rotate(args: argparse.Namespace) -> None:
    result = _service().rotate(args.key_id, overlap_hours=args.overlap_hours)
    _print_token(result)
    if args.overlap_hours > 0:
        print(f"Old token remains active for the requested {args.overlap_hours} hour overlap.")
    else:
        print("Old token was revoked immediately.")


def _grant_scope(args: argparse.Namespace) -> None:
    client = _service().grant_scopes(args.key_id, args.scope)
    print(
        f"updated key_id={client.key_id} company_id={client.company_id} "
        f"scopes={','.join(client.scopes or [])}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage VOC service-to-service tokens")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue", help="issue a new token")
    issue.add_argument("--company-id", type=int, required=True)
    issue.add_argument("--name", required=True)
    issue.add_argument("--expires-days", type=int)
    issue.add_argument("--scope", action="append", default=["reviews:read"])
    issue.set_defaults(func=_issue)

    listing = sub.add_parser("list", help="list metadata only; never secrets")
    listing.add_argument("--company-id", type=int)
    listing.set_defaults(func=_list)

    revoke = sub.add_parser("revoke", help="revoke a token")
    revoke.add_argument("--key-id", required=True)
    revoke.add_argument("--yes", action="store_true")
    revoke.set_defaults(func=_revoke)

    rotate = sub.add_parser("rotate", help="issue replacement token")
    rotate.add_argument("--key-id", required=True)
    rotate.add_argument("--overlap-hours", type=int, default=0)
    rotate.set_defaults(func=_rotate)

    grant_scope = sub.add_parser(
        "grant-scope", help="add scopes to an existing token without rotating it"
    )
    grant_scope.add_argument("--key-id", required=True)
    grant_scope.add_argument("--scope", action="append", required=True)
    grant_scope.set_defaults(func=_grant_scope)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
