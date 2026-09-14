from __future__ import annotations

from app.services.apify_fetch_service import ApifyFetchService
from app.services.fetch_log_service import FetchLogService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.terminal.common import (
    handle_menu_error,
    parse_int,
    pause,
    print_heading,
    show_fetch_result,
    show_apify_fetch_result,
    show_locations,
)
from app.utils.date_parser import format_datetime


def run_fetch_menu() -> None:
    service = FetchService()
    locations = LocationService()
    log_service = FetchLogService()
    apify_service = ApifyFetchService()
    while True:
        print_heading("Fetch / Sync Reviews")
        print("1. Fetch Reviews for One Location")
        print("2. Fetch Reviews for All Active Locations")
        print("3. Dry Run Fetch for One Location")
        print("4. Apify Fetch from Review URL")
        print("5. View Last Fetch Result")
        print("0. Back to Main Menu")
        choice = input("\nSelect menu: ").strip()
        try:
            if choice == "1":
                location_id = _select_active_location(locations)
                if location_id is not None:
                    location = locations.get_location(location_id)
                    print(f"\nFetching reviews for {location.branch_name}...")
                    show_fetch_result(service.fetch_location(location_id))
                    pause()
            elif choice == "2":
                _fetch_all(service)
            elif choice == "3":
                location_id = _select_active_location(locations)
                if location_id is not None:
                    _dry_run(service, location_id)
            elif choice == "4":
                location_id = _select_active_location(locations)
                if location_id is not None:
                    target = _select_apify_target(apify_service)
                    location = locations.get_location(location_id)
                    print("\nStarting Apify review fetch...\n")
                    print(f"Location      : {location.branch_name}")
                    print(f"Target review : {target}")
                    print("Source        : apify_google_maps")
                    result = apify_service.fetch_location(location_id, target)
                    show_apify_fetch_result(result)
                    pause()
            elif choice == "5":
                _show_last_log(log_service)
            elif choice == "0":
                return
            else:
                print("Invalid menu selection. Please try again.")
        except Exception as exc:
            handle_menu_error(exc)
            pause()


def _select_active_location(service: LocationService) -> int | None:
    active = service.get_all_locations(active_only=True)
    show_locations(active)
    if not active:
        print("Please add or activate location first.")
        pause()
        return None
    return parse_int(input("\nLocation ID: ").strip(), "Location ID")


def _fetch_all(service: FetchService) -> None:
    print("\nFetching reviews for all active locations...")
    summary = service.fetch_all_active_locations()
    if summary["total_locations"] == 0:
        print("No active Hermina locations found.")
        print("Please add or activate location first.")
        pause()
        return
    print("\nSync completed.\n")
    print(f"Total locations processed : {summary['total_locations']}")
    print(f"Success                   : {summary['success']}")
    print(f"Failed                    : {summary['failed']}")
    print(f"Total reviews fetched     : {summary['total_fetched']}")
    print(f"Total inserted            : {summary['total_inserted']}")
    print(f"Total duplicate           : {summary['total_duplicate']}")
    pause()


def _dry_run(service: FetchService, location_id: int) -> None:
    result = service.dry_run_location(location_id)
    print_heading("Dry Run Result")
    print(f"Location      : {result['location_name']}")
    print(f"Source        : {result['source']}")
    print(f"Total fetched : {result['total_fetched']}")
    print("\nSample Reviews:")
    for index, review in enumerate(result["samples"], start=1):
        print(
            f"{index}. Rating {review['rating'] or '-'} - "
            f"{review['review_text']}"
        )
    print("\nNo data was inserted.")
    pause()


def _show_last_log(service: FetchLogService) -> None:
    log = service.get_last_log()
    if log is None:
        print("No fetch logs found.")
    else:
        print_heading("Last Fetch Result")
        print(f"Location  : {log['location']}")
        print(f"Source    : {log['source']}")
        print(f"Status    : {log['status']}")
        print(f"Fetched   : {log['total_fetched']}")
        print(f"Inserted  : {log['total_inserted']}")
        print(f"Duplicate : {log['total_duplicate']}")
        print(f"Failed    : {log['total_failed']}")
        print(f"Started   : {format_datetime(log['started_at'])}")
        print(f"Finished  : {format_datetime(log['finished_at'])}")
        if log["error_message"]:
            print(f"Error     : {log['error_message']}")
    pause()


def _select_apify_target(service: ApifyFetchService) -> int:
    print("\nTarget reviews to fetch:")
    print("1. 100 reviews")
    print("2. 150 reviews")
    print("3. 200 reviews")
    print("4. Custom number")
    choice = input("\nSelect target: ").strip()
    presets = {"1": 100, "2": 150, "3": 200}
    if choice in presets:
        return presets[choice]
    if choice == "4":
        custom = parse_int(
            input("Custom target review count: ").strip(),
            "Target review count",
        )
        return service.validate_target(custom)
    raise ValueError("Invalid target selection.")
