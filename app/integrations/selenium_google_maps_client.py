from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    JavascriptException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from app.config import Settings
from app.db.models import Location
from app.integrations import google_maps_selectors as selectors
from app.integrations.review_source_client import ReviewSourceClient, ReviewSourceError
from app.utils.rating_parser import parse_compact_count, parse_rating


logger = logging.getLogger(__name__)


class SeleniumGoogleMapsReviewClient(ReviewSourceClient):
    source_name = "selenium_google_maps"
    max_no_new_scroll_attempts = 5

    def __init__(self, settings: Settings, driver_factory=None):
        self.settings = settings
        self.driver_factory = driver_factory or self._create_driver
        self.last_metadata: dict = {}

    def fetch_reviews(
        self,
        location: Location,
        limit: int = 50,
        on_progress=None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        target = min(
            max(1, int(limit)),
            self.settings.selenium_max_target_reviews,
            300,
        )
        url = self._resolve_url(location)
        self._validate_url(url)
        driver = None
        started_at = datetime.now().astimezone()
        try:
            driver = self.driver_factory()
            driver.get(url)
            self._accept_consent_if_present(driver)
            cards = self._wait_for_review_cards_or_open_panel(driver)
            container = self._find_scroll_container(driver, cards[0])
            sort_applied = self._sort_newest_if_possible(driver)
            time.sleep(1)
            cards = self._find_review_cards(driver)
            if cards:
                container = self._find_scroll_container(driver, cards[0])
            range_requested = date_from is not None or date_to is not None
            if range_requested and not sort_applied:
                warning = (
                    "Date-range crawling requires Google Maps newest sorting. "
                    "Sorting was unavailable, so the crawl stopped early to "
                    "avoid scanning stale reviews."
                )
                self.last_metadata = {
                    "target_review_count": target,
                    "loaded_review_cards": len(cards),
                    "reviews_scanned": 0,
                    "scraped_review_cards": 0,
                    "matched_review_cards": 0,
                    "failed_review_cards": 0,
                    "scroll_attempts": 0,
                    "headless": self.settings.selenium_headless,
                    "url": url,
                    "final_url": driver.current_url,
                    "stopped_reason": "sort_unavailable",
                    "sort_applied": False,
                    "range_warning": warning,
                }
                return []
            max_scanned = max(50, target * 10) if range_requested else None
            (
                reviews,
                scanned_review_cards,
                failed_cards,
                scroll_attempts,
                stopped_reason,
            ) = self._collect_reviews(
                driver=driver,
                container=container,
                target=target,
                source_url=url,
                scraped_at=started_at,
                on_progress=on_progress,
                max_scanned=max_scanned,
            )
            if not reviews:
                raise ReviewSourceError(
                    "No reviews were loaded. Please check the review URL "
                    "or try non-headless mode."
                )

            self.last_metadata = {
                "target_review_count": target,
                "loaded_review_cards": scanned_review_cards,
                "reviews_scanned": scanned_review_cards,
                "scraped_review_cards": len(reviews),
                "matched_review_cards": len(reviews),
                "failed_review_cards": failed_cards,
                "scroll_attempts": scroll_attempts,
                "headless": self.settings.selenium_headless,
                "url": url,
                "final_url": driver.current_url,
                "stopped_reason": stopped_reason,
                "sort_applied": sort_applied,
                "max_scanned": max_scanned,
            }
            return reviews
        except ReviewSourceError:
            raise
        except WebDriverException as exc:
            raise ReviewSourceError(
                "Selenium browser failed or Google Maps could not be loaded. "
                f"Details: {exc}"
            ) from exc
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except WebDriverException:
                    logger.warning("Selenium browser could not close cleanly.")

    def _create_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--lang=id-ID")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        browser_path = (
            shutil.which("google-chrome")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
        )
        if browser_path:
            options.binary_location = browser_path
        if self.settings.selenium_user_data_dir:
            self.settings.selenium_user_data_dir.mkdir(
                parents=True, exist_ok=True
            )
            options.add_argument(
                f"--user-data-dir={self.settings.selenium_user_data_dir}"
            )
        if self.settings.selenium_headless:
            options.add_argument("--headless=new")
        driver_path = shutil.which("chromedriver")
        service = (
            ChromeService(executable_path=driver_path)
            if driver_path
            else ChromeService()
        )
        try:
            return webdriver.Chrome(service=service, options=options)
        except WebDriverException as exc:
            raise ReviewSourceError(
                "Selenium browser failed to start. Please check Chrome and "
                "ChromeDriver installation."
            ) from exc

    @staticmethod
    def _resolve_url(location: Location) -> str:
        if location.google_reviews_url:
            return location.google_reviews_url.strip()
        if location.google_maps_url:
            return location.google_maps_url.strip()
        if location.external_place_id:
            query = quote_plus(location.branch_name or "Hermina")
            place_id = quote_plus(location.external_place_id)
            return (
                "https://www.google.com/maps/search/?api=1"
                f"&query={query}&query_place_id={place_id}&hl=id"
            )
        raise ReviewSourceError(
            "Invalid Google review URL. Please update location "
            "google_reviews_url."
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme not in {"http", "https"}
            or "google." not in hostname
            or "/maps" not in parsed.path
        ):
            raise ReviewSourceError(
                "Invalid Google review URL. Please update location "
                "google_reviews_url."
            )

    def _wait_for_review_cards_or_open_panel(self, driver) -> list[WebElement]:
        wait = WebDriverWait(
            driver, self.settings.selenium_wait_timeout_seconds
        )
        try:
            cards = wait.until(
                lambda current: (
                    self._find_review_cards(current)
                    or (
                        [self._find_review_open_button(current)]
                        if self._find_review_open_button(current)
                        else []
                    )
                )
            )
        except TimeoutException:
            cards = []

        button = self._find_review_open_button(driver)
        if button is not None:
            self._safe_click(driver, button)
            try:
                return wait.until(
                    lambda current: (
                        self._find_review_cards(current)
                        if self._find_first(
                            current, selectors.SCROLL_CONTAINER_SELECTORS
                        )
                        else []
                    )
                )
            except TimeoutException as exc:
                raise ReviewSourceError(
                    "No reviews were loaded. Please check the review URL "
                    "or try non-headless mode."
                ) from exc
        if cards and isinstance(cards[0], WebElement):
            return cards

        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except WebDriverException:
            body_text = ""
        if "tampilan terbatas" in body_text or "limited view" in body_text:
            raise ReviewSourceError(
                "Google Maps is showing a limited view. Open the dedicated "
                "Selenium browser profile and sign in manually once, then "
                "retry. Login automation is intentionally not supported."
            )
        raise ReviewSourceError(
            "Review container was not found. Google Maps layout may have "
            "changed or the URL is invalid."
        )

    def _collect_reviews(
        self,
        driver,
        container,
        target: int,
        source_url: str,
        scraped_at: datetime,
        on_progress=None,
        max_scanned: int | None = None,
    ):
        reviews: list[dict] = []
        review_keys: set[str] = set()
        seen_card_ids: set[str] = set()
        failed_card_ids: set[str] = set()
        no_new_attempts = 0
        scroll_attempts = 0
        stopped_reason = "target_reached"

        while (
            len(reviews) < target
            and scroll_attempts < self.settings.selenium_max_scroll_attempts
            and no_new_attempts < self.max_no_new_scroll_attempts
            and (max_scanned is None or len(seen_card_ids) < max_scanned)
        ):
            count_before = len(reviews)
            if on_progress is not None:
                # Dilaporkan tiap putaran gulir, bukan tiap kartu: menulis ke
                # database sesering kartu akan lebih mahal daripada crawl-nya.
                try:
                    on_progress(len(reviews), target)
                except Exception:  # laporan kemajuan tidak boleh menggagalkan crawl
                    logger.debug('on_progress gagal', exc_info=True)
            cards = self._find_review_cards(driver)
            for card in cards:
                if len(reviews) >= target:
                    break
                if max_scanned is not None and len(seen_card_ids) >= max_scanned:
                    break
                card_id = self._card_identity(card)
                if card_id in seen_card_ids:
                    continue
                seen_card_ids.add(card_id)
                try:
                    self._expand_review(card, driver)
                    review = self._extract_review(
                        card=card,
                        source_url=driver.current_url or source_url,
                        scraped_at=scraped_at,
                    )
                    review_key = "|".join(
                        [
                            str(review.get("external_review_id") or ""),
                            str(review.get("reviewer_name") or ""),
                            str(review.get("rating") or ""),
                            str(review.get("review_text") or ""),
                            str(review.get("review_relative_time") or ""),
                        ]
                    )
                    if review_key not in review_keys:
                        review_keys.add(review_key)
                        reviews.append(review)
                except StaleElementReferenceException:
                    seen_card_ids.discard(card_id)
                except Exception as exc:
                    failed_card_ids.add(card_id)
                    logger.warning("Failed to extract one review card: %s", exc)

            if len(reviews) >= target:
                break
            if max_scanned is not None and len(seen_card_ids) >= max_scanned:
                break
            if len(reviews) == count_before:
                no_new_attempts += 1
            else:
                no_new_attempts = 0

            try:
                driver.execute_script(
                    "arguments[0].scrollTop += "
                    "Math.max(400, arguments[0].clientHeight * 0.85);",
                    container,
                )
            except (JavascriptException, StaleElementReferenceException):
                current_cards = self._find_review_cards(driver)
                if not current_cards:
                    raise ReviewSourceError(
                        "Review container could not be scrolled."
                    )
                container = self._find_scroll_container(
                    driver, current_cards[0]
                )
            scroll_attempts += 1
            time.sleep(self.settings.selenium_scroll_delay_seconds)

        if len(reviews) < target:
            if max_scanned is not None and len(seen_card_ids) >= max_scanned:
                stopped_reason = "max_scanned_reached"
            elif no_new_attempts >= self.max_no_new_scroll_attempts:
                stopped_reason = "no_new_review_cards"
            elif scroll_attempts >= self.settings.selenium_max_scroll_attempts:
                stopped_reason = "max_scroll_attempts"
        return (
            reviews,
            len(seen_card_ids),
            len(failed_card_ids),
            scroll_attempts,
            stopped_reason,
        )

    def _find_scroll_container(self, driver, first_card: WebElement):
        container = self._find_first(driver, selectors.SCROLL_CONTAINER_SELECTORS)
        if container is not None:
            return container
        try:
            return first_card.find_element(By.XPATH, "./ancestor::div[@role='feed'][1]")
        except NoSuchElementException:
            pass
        try:
            container = driver.execute_script(
                """
                let element = arguments[0].parentElement;
                while (element) {
                  const style = window.getComputedStyle(element);
                  if (/(auto|scroll)/.test(style.overflowY) &&
                      element.scrollHeight > element.clientHeight) {
                    return element;
                  }
                  element = element.parentElement;
                }
                return null;
                """,
                first_card,
            )
        except JavascriptException:
            container = None
        if container is None:
            raise ReviewSourceError(
                "Review container was not found. Google Maps layout may "
                "have changed or the URL is invalid."
            )
        return container

    def _extract_review(
        self, card: WebElement, source_url: str, scraped_at: datetime
    ) -> dict:
        reviewer_name = self._element_text(
            self._find_first(card, selectors.REVIEWER_NAME_SELECTORS)
        ) or "Anonymous"
        rating_element = self._find_first(card, selectors.RATING_SELECTORS)
        rating_value = None
        if rating_element is not None:
            rating_value = (
                rating_element.get_attribute("aria-label")
                or rating_element.get_attribute("data-tooltip")
                or rating_element.text
            )
        review_text = self._element_text(
            self._find_first(card, selectors.REVIEW_TEXT_SELECTORS)
        )
        relative_time = self._element_text(
            self._find_first(card, selectors.REVIEW_TIME_SELECTORS)
        )
        profile_element = self._find_first(
            card, selectors.PROFILE_LINK_SELECTORS
        )
        profile_url = None
        if profile_element is not None:
            profile_url = profile_element.get_attribute("href")
        photo_element = self._find_first(card, selectors.PHOTO_SELECTORS)
        photo_url = (
            photo_element.get_attribute("src") if photo_element is not None else None
        )
        reviewer_meta = self._element_text(
            self._find_first(card, selectors.REVIEWER_META_SELECTORS)
        )
        local_guide = (
            "Local Guide"
            if "local guide" in reviewer_meta.lower()
            or "pemandu lokal" in reviewer_meta.lower()
            else None
        )
        total_reviews = self._parse_reviewer_total_reviews(reviewer_meta)
        like_element = self._find_first(card, selectors.LIKE_BUTTON_SELECTORS)
        like_value = ""
        if like_element is not None:
            like_value = (
                like_element.text
                or like_element.get_attribute("aria-label")
                or like_element.get_attribute("data-tooltip")
                or ""
            )
        owner_container = self._find_first(
            card, selectors.OWNER_RESPONSE_CONTAINER_SELECTORS
        )
        owner_text = None
        owner_time = None
        if owner_container is not None:
            owner_text = self._element_text(
                self._find_first(
                    owner_container, selectors.OWNER_RESPONSE_TEXT_SELECTORS
                )
            )
            owner_time = self._element_text(
                self._find_first(
                    owner_container, selectors.OWNER_RESPONSE_TIME_SELECTORS
                )
            )
        review_id = (
            card.get_attribute("data-review-id")
            or card.get_attribute("data-reviewid")
            or None
        )
        raw_payload = {
            "review_id": review_id,
            "reviewer_name": reviewer_name,
            "reviewer_meta": reviewer_meta,
            "rating_label": rating_value,
            "review_text": review_text,
            "review_relative_time": relative_time,
            "like_label": like_value,
            "owner_response_text": owner_text,
            "owner_response_relative_time": owner_time,
            "source_url": source_url,
        }
        return {
            "source": self.source_name,
            "external_review_id": review_id,
            "reviewer_name": reviewer_name,
            "reviewer_profile_url": profile_url,
            "reviewer_photo_url": photo_url,
            "reviewer_local_guide_level": local_guide,
            "reviewer_total_reviews": total_reviews,
            "rating": parse_rating(rating_value),
            "review_text": review_text,
            "review_relative_time": relative_time or None,
            "review_time": None,
            "review_language": "unknown",
            "language": "unknown",
            "like_count": parse_compact_count(like_value),
            "owner_response_text": owner_text or None,
            "owner_response_time": None,
            "scraped_at": scraped_at.isoformat(),
            "raw_payload": raw_payload,
        }

    def _expand_review(self, card: WebElement, driver) -> None:
        for selector in selectors.MORE_BUTTON_SELECTORS:
            for button in card.find_elements(By.CSS_SELECTOR, selector):
                if button.is_displayed():
                    self._safe_click(driver, button)

    @staticmethod
    def _card_identity(card: WebElement) -> str:
        try:
            return (
                card.get_attribute("data-review-id")
                or card.get_attribute("data-reviewid")
                or card.id
            )
        except WebDriverException:
            return card.id

    def _sort_newest_if_possible(self, driver) -> bool:
        sort_button = self._find_first(driver, selectors.SORT_BUTTON_SELECTORS)
        if sort_button is None:
            return False
        try:
            self._safe_click(driver, sort_button)
            options = driver.find_elements(
                By.XPATH,
                "//*[self::div or self::li][@role='menuitemradio' or "
                "@role='menuitem'][contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                "'newest') or contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                "'terbaru')]",
            )
            for option in options:
                if option.is_displayed():
                    self._safe_click(driver, option)
                    time.sleep(1)
                    return True
        except WebDriverException:
            logger.info("Review sorting was unavailable; using current order.")
        return False

    @staticmethod
    def _accept_consent_if_present(driver) -> None:
        xpaths = [
            "//button[.//*[normalize-space()='Accept all']]",
            "//button[normalize-space()='Accept all']",
            "//button[.//*[normalize-space()='Terima semua']]",
            "//button[normalize-space()='Terima semua']",
        ]
        for xpath in xpaths:
            for button in driver.find_elements(By.XPATH, xpath):
                if button.is_displayed():
                    try:
                        button.click()
                        time.sleep(1)
                        return
                    except WebDriverException:
                        continue

    @staticmethod
    def _safe_click(driver, element: WebElement) -> None:
        try:
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)

    @staticmethod
    def _find_first(root, selector_list: list[str]) -> WebElement | None:
        for selector in selector_list:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, selector)
            except WebDriverException:
                continue
            for element in elements:
                try:
                    if element.is_displayed():
                        return element
                except WebDriverException:
                    continue
        return None

    @staticmethod
    def _find_review_open_button(root) -> WebElement | None:
        for selector in selectors.REVIEW_BUTTON_SELECTORS:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, selector)
            except WebDriverException:
                continue
            for element in elements:
                try:
                    label = " ".join(
                        [
                            element.text or "",
                            element.get_attribute("aria-label") or "",
                        ]
                    ).lower()
                    if "tulis ulasan" in label or "write a review" in label:
                        continue
                    if element.is_displayed():
                        return element
                except WebDriverException:
                    continue
        return None

    @staticmethod
    def _find_review_cards(root) -> list[WebElement]:
        seen: set[str] = set()
        output: list[WebElement] = []
        for selector in selectors.REVIEW_CARD_SELECTORS:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, selector)
            except WebDriverException:
                continue
            for element in elements:
                try:
                    key = (
                        element.get_attribute("data-review-id")
                        or element.get_attribute("data-reviewid")
                        or element.id
                    )
                except WebDriverException:
                    continue
                if key not in seen:
                    seen.add(key)
                    output.append(element)
        return output

    @staticmethod
    def _element_text(element: WebElement | None) -> str:
        if element is None:
            return ""
        try:
            return " ".join(element.text.split())
        except WebDriverException:
            return ""

    @staticmethod
    def _parse_reviewer_total_reviews(value: str) -> int | None:
        match = re.search(
            r"(\d[\d.,]*)\s+(?:reviews?|ulasan)", value, flags=re.IGNORECASE
        )
        if not match:
            return None
        return parse_compact_count(match.group(1), default=0)
