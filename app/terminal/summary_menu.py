from __future__ import annotations

from app.db.session import get_session_factory
from app.services.location_service import LocationService
from app.services.summary_service import SummaryService
from app.terminal.common import (
    handle_menu_error,
    parse_int,
    pause,
    print_heading,
    show_locations,
)
from app.utils.date_parser import format_datetime
from app.utils.formatter import print_table, truncate


def run_summary_menu() -> None:
    session_factory = get_session_factory()
    locations = LocationService()
    while True:
        print_heading("View Analysis Summary")
        print("1. Summary for All Locations")
        print("2. Summary by Location")
        print("3. Negative Review Summary")
        print("4. Critical Issue Summary")
        print("5. Top Issue Categories")
        print("6. Sentiment Distribution")
        print("0. Back to Main Menu")
        choice = input("\nSelect menu: ").strip()
        try:
            if choice == "1":
                with session_factory() as session:
                    _overall(SummaryService(session=session).overall_summary())
            elif choice == "2":
                all_locations = locations.get_all_locations()
                show_locations(all_locations)
                if not all_locations:
                    pause()
                    continue
                location_id = parse_int(
                    input("\nLocation ID: ").strip(), "Location ID"
                )
                with session_factory() as session:
                    _location(
                        SummaryService(session=session).location_summary(location_id)
                    )
            elif choice == "3":
                with session_factory() as session:
                    _negative(SummaryService(session=session).negative_reviews())
            elif choice == "4":
                with session_factory() as session:
                    _critical(SummaryService(session=session).critical_issues())
            elif choice == "5":
                with session_factory() as session:
                    _top_issues(
                        SummaryService(session=session).overall_summary()["top_issues"]
                    )
            elif choice == "6":
                with session_factory() as session:
                    _sentiments(
                        SummaryService(session=session).overall_summary()["sentiments"]
                    )
            elif choice == "0":
                return
            else:
                print("Invalid menu selection. Please try again.")
                continue
            pause()
        except Exception as exc:
            handle_menu_error(exc)
            pause()


def _overall(summary: dict) -> None:
    print_heading("Overall Review Summary")
    print(f"Total Locations        : {summary['total_locations']}")
    print(f"Total Reviews          : {summary['total_reviews']}")
    print(f"Analyzed Reviews       : {summary['analyzed_reviews']}")
    print(f"Pending Analysis       : {summary['pending_analysis']}")
    _sentiments(summary["sentiments"], heading=False)
    _top_issues(summary["top_issues"], heading=False)
    print(f"\nCritical Issues        : {summary['critical_issues']}")
    print(f"Latest Fetch           : {format_datetime(summary['latest_fetch'])}")


def _location(summary: dict) -> None:
    print_heading(f"Location Summary: {summary['location_name']}")
    print(f"Total Reviews    : {summary['total_reviews']}")
    print(f"Average Rating   : {summary['average_rating'] or '-'}")
    print(f"Negative Reviews : {summary['sentiments']['negative']}")
    print(f"Critical Issues  : {summary['critical_issues']}")
    _top_issues(summary["top_issues"], heading=False)
    if summary["negative_examples"]:
        print("\nNegative Review Examples:")
        for text in summary["negative_examples"]:
            print(f"- {truncate(text, 100)}")
    print("\nManagement Focus:")
    if summary["management_focus"]:
        for action in summary["management_focus"]:
            print(f"- {action}")
    else:
        print("- No analyzed issues yet.")


def _negative(items: list[dict]) -> None:
    print_heading("Negative Review Summary")
    print_table(
        ["Location", "Rating", "Review", "Category", "Urgency"],
        [
            [
                item["location"],
                item["rating"] or "-",
                truncate(item["review_text"], 55),
                item["issue_category"],
                item["urgency"],
            ]
            for item in items
        ],
    )


def _critical(items: list[dict]) -> None:
    print_heading("Critical Issue Summary")
    print_table(
        ["Location", "Rating", "Review", "Category", "Urgency", "Action"],
        [
            [
                item["location"],
                item["rating"] or "-",
                truncate(item["review_text"], 40),
                item["issue_category"],
                item["urgency"],
                truncate(item["recommended_action"], 50),
            ]
            for item in items
        ],
    )


def _top_issues(items, heading: bool = True) -> None:
    if heading:
        print_heading("Top Issue Categories")
    else:
        print("\nTop Issues:")
    if not items:
        print("(no analyzed issues)")
        return
    for index, (category, count) in enumerate(items, start=1):
        print(f"{index}. {str(category).replace('_', ' ').title():<24}: {count}")


def _sentiments(sentiments: dict, heading: bool = True) -> None:
    if heading:
        print_heading("Sentiment Distribution")
    else:
        print("\nSentiment:")
    for name in ["positive", "neutral", "negative", "mixed", "unknown"]:
        print(f"{name.title():<10}: {sentiments.get(name, 0)}")
