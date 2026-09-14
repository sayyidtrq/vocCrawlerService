from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.utils.date_parser import format_datetime
from app.utils.formatter import print_table, truncate


def print_heading(title: str) -> None:
    print(f"\n{title}\n")


def pause() -> None:
    input("\nPress Enter to continue...")


def parse_int(value: str, field_name: str = "Value") -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    value = input(f"{prompt} {suffix}: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def show_locations(locations: list) -> None:
    if not locations:
        print("No Hermina locations found.")
        print("Please add a location first.")
        return
    print_table(
        ["ID", "Hospital", "Branch", "City", "Source", "Active"],
        [
            [
                item.id,
                item.hospital_name,
                item.branch_name,
                item.city or "-",
                item.source,
                "Yes" if item.is_active else "No",
            ]
            for item in locations
        ],
    )


def show_reviews(items: list[dict], page: int = 1, total_pages: int = 1) -> None:
    print_table(
        [
            "ID",
            "Location",
            "Rating",
            "Reviewer",
            "Review Preview",
            "Time",
            "Analyzed",
        ],
        [
            [
                item["id"],
                item["location"],
                item["rating"] if item["rating"] is not None else "-",
                truncate(item["reviewer_name"], 18),
                truncate(item["review_text"], 42),
                format_datetime(item["review_time"], include_time=False),
                "Yes" if item["analyzed"] else "No",
            ]
            for item in items
        ],
    )
    print(f"\nPage {page} of {total_pages}")


def show_analysis_result(result: dict) -> None:
    print("\nAnalysis completed.\n")
    print(f"Total reviews        : {result['total']}")
    print(f"Successfully analyzed: {result['success']}")
    print(f"Failed               : {result['failed']}")
    print("\nSentiment Result:")
    for sentiment in ["positive", "neutral", "negative", "mixed", "unknown"]:
        print(f"{sentiment.title():<9}: {result['sentiments'][sentiment]}")
    if result["errors"]:
        print("\nErrors:")
        for error in result["errors"][:10]:
            print(f"- Review {error['review_id']}: {error['error']}")


def show_fetch_result(result: dict) -> None:
    if result["status"] == "failed":
        print("\nFetch failed.\n")
        print(f"Location : {result['location_name']}")
        print(f"Source   : {result['source']}")
        print(f"Error    : {result['error_message']}")
        return
    print()
    print(f"Source          : {result['source']}")
    print(f"Location        : {result['location_name']}")
    print(f"Total fetched   : {result['total_fetched']}")
    print(f"Inserted        : {result['total_inserted']}")
    print(f"Duplicate       : {result['total_duplicate']}")
    print(f"Failed          : {result['total_failed']}")
    print(f"Status          : {result['status'].replace('_', ' ').title()}")
    if result["total_inserted"] == 0 and result["total_duplicate"] > 0:
        print("\nNo new reviews found.")


def show_apify_fetch_result(result: dict) -> None:
    if result["status"] == "failed":
        print("\nApify fetch failed.\n")
        print(f"Location : {result['location_name']}")
        print(f"Error    : {result['error_message']}")
        return
    metadata = result.get("metadata") or {}
    heading = (
        "Apify fetch completed."
        if result["status"] == "success"
        else "Apify fetch completed with partial result."
    )
    print(f"\n{heading}\n")
    print(f"Location          : {result['location_name']}")
    print(f"Target requested  : {result['target_review_count']}")
    print(f"Reviews fetched   : {result['total_fetched']}")
    print(f"Inserted          : {result['total_inserted']}")
    print(f"Duplicate         : {result['total_duplicate']}")
    print(f"Failed            : {result['total_failed']}")
    print(f"Status            : {result['status'].replace('_', ' ').title()}")
    if metadata.get("stopped_reason") not in {None, "target_reached"}:
        print(f"Reason            : {metadata['stopped_reason']}")


def handle_menu_error(exc: Exception) -> None:
    if isinstance(exc, SQLAlchemyError):
        print("\nDatabase error occurred.")
    else:
        print()
    print(f"Error: {exc}")
