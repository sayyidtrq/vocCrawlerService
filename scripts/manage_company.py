"""CLI for creating and listing crawler companies."""

from __future__ import annotations

import argparse

from app.services.company_service import CompanyService


def _service() -> CompanyService:
    return CompanyService()


def _create(args: argparse.Namespace) -> None:
    company = _service().create(
        args.name,
        ai_enable_flag=args.ai_enable,
        analyze_competitor_flag=args.analyze_competitor,
        total_enable_review=args.total_enable_review,
    )
    print(f"company_id={company.id} name={company.name}")


def _list(_: argparse.Namespace) -> None:
    for company in _service().list_companies():
        print(
            f"company_id={company.id} name={company.name} "
            f"created_at={company.created_at}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage crawler companies")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a company")
    create.add_argument("--name", required=True)
    create.add_argument("--ai-enable", action="store_true")
    create.add_argument("--analyze-competitor", action="store_true")
    create.add_argument("--total-enable-review", type=int, default=0)
    create.set_defaults(func=_create)

    listing = sub.add_parser("list", help="list companies")
    listing.set_defaults(func=_list)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
