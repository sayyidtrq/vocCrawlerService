"""Inspect the live Google Maps review DOM without writing review data."""

from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.keys import Keys

from app.config import get_settings
from app.integrations.selenium_google_maps_client import (
    SeleniumGoogleMapsReviewClient,
)


def _attribute(element, name: str):
    try:
        value = element.get_attribute(name)
    except Exception:
        return None
    return value[:300] if value else None


def _snapshot(client, driver, label: str) -> dict:
    cards = client._find_review_cards(driver)
    controls = []
    for element in driver.find_elements(
        By.CSS_SELECTOR, "button,[role='button'],[role='tab']"
    ):
        aria = _attribute(element, "aria-label")
        role = _attribute(element, "role")
        jsaction = _attribute(element, "jsaction")
        value = _attribute(element, "data-value")
        visible_text = (element.text or "").strip()[:160]
        searchable = " ".join(
            str(item or "")
            for item in (aria, role, jsaction, value, visible_text)
        ).lower()
        if not any(
            keyword in searchable
            for keyword in ("ulas", "review", "urut", "sort", "lain", "more")
        ):
            continue
        controls.append(
            {
                "tag": element.tag_name,
                "aria_label": aria,
                "role": role,
                "aria_selected": _attribute(element, "aria-selected"),
                "jsaction": jsaction,
                "data_value": value,
                "text": visible_text,
                "displayed": element.is_displayed(),
            }
        )

    scrollables = driver.execute_script(
        """
        return Array.from(document.querySelectorAll('div')).map((element, index) => {
          const style = getComputedStyle(element);
          return {
            index,
            role: element.getAttribute('role'),
            class_name: String(element.className || '').slice(0, 180),
            aria_label: element.getAttribute('aria-label'),
            overflow_y: style.overflowY,
            scroll_top: element.scrollTop,
            scroll_height: element.scrollHeight,
            client_height: element.clientHeight
          };
        }).filter(item =>
          item.scroll_height > item.client_height + 5 &&
          ['auto', 'scroll'].includes(item.overflow_y)
        ).sort((left, right) =>
          (right.scroll_height - right.client_height) -
          (left.scroll_height - left.client_height)
        ).slice(0, 12);
        """
    )
    return {
        "label": label,
        "card_count": len(cards),
        "card_ids": [client._card_identity(card) for card in cards[:12]],
        "controls": controls[:40],
        "scrollables": scrollables,
    }


def run_probe(url: str, advances: int, wait_seconds: float, screenshot: Path) -> dict:
    client = SeleniumGoogleMapsReviewClient(get_settings())
    driver = None
    report = {"url": url, "snapshots": []}
    try:
        driver = client._create_driver()
        driver.get(url)
        client._accept_consent_if_present(driver)
        client._wait_for_review_cards_or_open_panel(driver)
        report.update(
            {
                "navigator_webdriver": driver.execute_script(
                    "return navigator.webdriver"
                ),
                "title": driver.title,
                "final_url": driver.current_url,
            }
        )
        report["snapshots"].append(_snapshot(client, driver, "panel_open"))
        report["sort_applied"] = client._apply_sort(driver, "newest")
        report["snapshots"].append(_snapshot(client, driver, "after_sort"))

        cards = client._find_review_cards(driver)
        container = client._find_scroll_container(driver, cards[0])
        for attempt in range(1, advances + 1):
            container = client._advance_review_list(driver, container)
            time.sleep(wait_seconds)
            report["snapshots"].append(
                _snapshot(client, driver, f"advance_{attempt}")
            )

        origin = ScrollOrigin.from_element(container)
        ActionChains(driver).scroll_from_origin(origin, 0, 1200).perform()
        time.sleep(wait_seconds)
        report["snapshots"].append(_snapshot(client, driver, "trusted_wheel"))

        container.send_keys(Keys.END)
        time.sleep(wait_seconds)
        report["snapshots"].append(_snapshot(client, driver, "end_key"))
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(screenshot))
        report["screenshot"] = str(screenshot)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe Google Maps review controls and pagination read-only."
    )
    parser.add_argument("url", help="Full google.com/maps URL to inspect")
    parser.add_argument("--advances", type=int, default=3)
    parser.add_argument("--wait-seconds", type=float, default=3.0)
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=Path("/tmp/google-maps-runtime-probe.png"),
    )
    args = parser.parse_args()
    report = run_probe(
        args.url,
        max(0, args.advances),
        max(0.0, args.wait_seconds),
        args.screenshot,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
