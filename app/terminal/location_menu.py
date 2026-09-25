from __future__ import annotations

from app.services.location_service import LocationService
from app.terminal.common import (
    ask_yes_no,
    handle_menu_error,
    parse_int,
    pause,
    print_heading,
    show_locations,
)


FIELDS = [
    "hospital_name",
    "branch_name",
    "city",
    "address",
    "latitude",
    "longitude",
    "source",
    "external_place_id",
    "google_maps_url",
    "google_reviews_url",
    "target_review_count",
    "is_active",
]


def run_location_menu() -> None:
    service = LocationService()
    while True:
        print_heading("Manage Locations")
        print("1. Add New Location")
        print("2. View All Locations")
        print("3. View Active Locations")
        print("4. Update Location")
        print("5. Activate / Deactivate Location")
        print("6. Delete Location")
        print("0. Back to Main Menu")
        choice = input("\nSelect menu: ").strip()
        try:
            if choice == "1":
                _add_location(service)
            elif choice == "2":
                show_locations(service.get_all_locations())
                pause()
            elif choice == "3":
                show_locations(service.get_all_locations(active_only=True))
                pause()
            elif choice == "4":
                _update_location(service)
            elif choice == "5":
                _toggle_location(service)
            elif choice == "6":
                _delete_location(service)
            elif choice == "0":
                return
            else:
                print("Invalid menu selection. Please try again.")
        except Exception as exc:
            handle_menu_error(exc)
            pause()


def _add_location(service: LocationService) -> None:
    print_heading("Add New Location")
    hospital_name = input("Company / Brand / Hospital Name: ").strip() or "Company"
    branch_name = input("Branch Name: ").strip()
    city = input("City: ").strip()
    address = input("Address: ").strip()
    latitude = input("Latitude: ").strip()
    longitude = input("Longitude: ").strip()
    source = input("Source [default: google_places]: ").strip() or "google_places"
    external_place_id = input("External Place ID: ").strip()
    google_maps_url = input("Google Maps URL [optional]: ").strip()
    google_reviews_url = input("Google Reviews URL [optional]: ").strip()
    target_review_count = (
        input("Target Review Count [default: 100]: ").strip() or "100"
    )
    is_active = ask_yes_no("Is Active?", default=True)
    location = service.add_location(
        hospital_name=hospital_name,
        branch_name=branch_name,
        city=city,
        address=address,
        latitude=latitude,
        longitude=longitude,
        source=source,
        external_place_id=external_place_id,
        google_maps_url=google_maps_url,
        google_reviews_url=google_reviews_url,
        target_review_count=target_review_count,
        is_active=is_active,
    )
    print(f"\nLocation {location.branch_name} was added successfully.")
    pause()


def _update_location(service: LocationService) -> None:
    print_heading("Update Location")
    locations = service.get_all_locations()
    show_locations(locations)
    if not locations:
        pause()
        return
    location_id = parse_int(input("\nLocation ID: ").strip(), "Location ID")
    location = service.get_location(location_id)
    if location is None:
        raise ValueError("Location not found.")
    print(f"\nCurrent location: {location.branch_name}")
    for index, field in enumerate(FIELDS, start=1):
        print(f"{index}. {field}")
    field_choice = parse_int(input("Field to update: ").strip(), "Field selection")
    if not 1 <= field_choice <= len(FIELDS):
        raise ValueError("Invalid field selection.")
    field = FIELDS[field_choice - 1]
    current = getattr(location, field)
    value = input(f"New value [{current}]: ").strip()
    if value == "":
        print("No change made.")
        pause()
        return
    updated = service.update_location(location_id, field, value)
    print(f"Location {updated.branch_name} was updated successfully.")
    pause()


def _toggle_location(service: LocationService) -> None:
    print_heading("Activate / Deactivate Location")
    locations = service.get_all_locations()
    show_locations(locations)
    if not locations:
        pause()
        return
    location_id = parse_int(input("\nLocation ID: ").strip(), "Location ID")
    updated = service.toggle_active(location_id)
    status = "activated" if updated.is_active else "deactivated"
    print(f"Location {updated.branch_name} has been {status}.")
    pause()


def _delete_location(service: LocationService) -> None:
    print_heading("Delete Location")
    locations = service.get_all_locations()
    show_locations(locations)
    if not locations:
        pause()
        return
    location_id = parse_int(input("\nLocation ID: ").strip(), "Location ID")
    location = service.get_location(location_id)
    if location is None:
        raise ValueError("Location not found.")
    if not ask_yes_no(
        f"Delete {location.branch_name} and all related data?", default=False
    ):
        print("Delete cancelled.")
        pause()
        return
    branch_name = service.delete_location(location_id)
    print(f"Location {branch_name} was deleted.")
    pause()
