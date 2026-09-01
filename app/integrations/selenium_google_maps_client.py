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
        self, location: Location, limit: int = 50, on_progress=None,
        keep_check=None, sort_by: str = "newest", scan_limit: int | None = None,
        time_limit_seconds: int = 0,
    ) -> list[dict]:
        target = min(
            max(1, int(limit)),
            self.settings.selenium_max_target_reviews,
            300,
        )
        max_scan = max(target, min(int(scan_limit or target), 5000))
        url, url_strategy = self._resolve_url_with_source(location)
        self._validate_url(url)
        fallback_from_url = None
        driver = None
        started_at = datetime.now().astimezone()
        try:
            driver = self.driver_factory()
            try:
                cards = self._open_review_panel(driver, url)
            except ReviewSourceError as exc:
                # Place ID dari master data kadang berbentuk valid, tetapi tidak
                # lagi dikenali Google. Maps lalu membuka peta kosong tanpa
                # panel ulasan. Dalam kasus itu, pencarian nama cabang adalah
                # fallback satu kali yang lebih aman daripada mengulang Place
                # ID rusak sampai retry habis.
                fallback_url = self._name_search_url(location)
                if (
                    url_strategy != "external_place_id"
                    or not self._can_try_name_search_fallback(exc)
                    or fallback_url == url
                ):
                    raise
                logger.warning(
                    "Google Place ID tidak membuka panel ulasan untuk %s; "
                    "mencoba pencarian nama cabang.",
                    location.branch_name,
                )
                fallback_from_url = url
                url = fallback_url
                url_strategy = "branch_name_fallback"
                cards = self._open_review_panel(driver, url)
            container = self._find_scroll_container(driver, cards[0])
            sort_applied = self._apply_sort(driver, sort_by)
            time.sleep(1)

            # Berhenti-awal berbasis tanggal HANYA sah pada daftar kronologis.
            # Kalau urutan gagal dipasang, Google memakai urutan bawaannya
            # ('paling relevan') yang tidak berurutan waktu — memotong daftar
            # itu akan membuang ulasan yang sebenarnya cocok, diam-diam. Maka
            # putusan 'stop' diturunkan menjadi 'skip': penyaringan tetap
            # berjalan, hanya berhentinya yang tidak lagi dipercepat.
            if keep_check is not None and not sort_applied:
                _asli = keep_check

                def keep_check(review, _f=_asli):
                    putusan = _f(review)
                    return 'skip' if putusan == 'stop' else putusan
            cards = self._find_review_cards(driver)
            if cards:
                container = self._find_scroll_container(driver, cards[0])
            (
                reviews,
                loaded_review_cards,
                failed_cards,
                scroll_attempts,
                stopped_reason,
                total_seen,
            ) = self._collect_reviews(
                driver=driver,
                container=container,
                target=target,
                source_url=url,
                scraped_at=started_at,
                on_progress=on_progress,
                keep_check=keep_check,
                scan_limit=max_scan,
                time_limit_seconds=time_limit_seconds,
            )
            if not reviews:
                raise ReviewSourceError(
                    "No reviews were loaded. Please check the review URL "
                    "or try non-headless mode."
                )

            self.last_metadata = {
                "target_review_count": target,
                "max_reviews_to_collect": target,
                "scan_limit": max_scan,
                "loaded_review_cards": loaded_review_cards,
                "scraped_review_cards": len(reviews),
                "failed_review_cards": failed_cards,
                "scroll_attempts": scroll_attempts,
                "headless": self.settings.selenium_headless,
                "url": url,
                "final_url": driver.current_url,
                "url_strategy": url_strategy,
                "fallback_from_url": fallback_from_url,
                "stopped_reason": stopped_reason,
                "sort_by": sort_by,
                # Penting bagi pemanggil: berhenti-awal berbasis tanggal HANYA
                # sah bila urutannya benar-benar terpasang. Bila False, daftar
                # mengikuti urutan bawaan Google yang tidak kronologis.
                "sort_applied": sort_applied,
                "time_limit_seconds": time_limit_seconds,
                "reviews_scanned": total_seen,
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
    def _place_id_url(location: Location) -> str | None:
        """URL pencarian dari Place ID — bentuk yang selalu sah."""
        if not location.external_place_id:
            return None
        query = quote_plus(location.branch_name or "Hermina")
        place_id = quote_plus(location.external_place_id)
        return (
            "https://www.google.com/maps/search/?api=1"
            f"&query={query}&query_place_id={place_id}&hl=id"
        )

    @staticmethod
    def _name_search_url(location: Location) -> str | None:
        """Google Maps search URL without Place ID as a recovery path."""
        query = (location.branch_name or location.hospital_name or "").strip()
        if not query:
            return None
        return (
            "https://www.google.com/maps/search/?api=1"
            f"&query={quote_plus(query)}&hl=id"
        )

    @classmethod
    def _resolve_url_with_source(cls, location: Location) -> tuple[str, str]:
        """Resolve a usable URL and retain its provenance for recovery."""
        candidates = [
            ("google_reviews_url", (location.google_reviews_url or "").strip()),
            ("google_maps_url", (location.google_maps_url or "").strip()),
            ("external_place_id", cls._place_id_url(location) or ""),
        ]
        rejected = []
        for source, url in candidates:
            if not url:
                continue
            try:
                cls._validate_url(url)
                if rejected:
                    logger.warning(
                        "URL dari %s tidak sah (%s); memakai %s sebagai gantinya",
                        ", ".join(rejected),
                        location.branch_name,
                        source,
                    )
                return url, source
            except ReviewSourceError:
                rejected.append(source)

        if rejected:
            raise ReviewSourceError(
                "URL ulasan Google tidak sah pada "
                + ", ".join(rejected)
                + ". Perbaiki kolom itu, atau isi external_place_id agar URL "
                "bisa dibentuk otomatis. Tautan pendek maps.app.goo.gl tidak "
                "didukung - pakai tautan lengkap google.com/maps."
            )
        raise ReviewSourceError(
            "Lokasi ini belum punya URL ulasan Google maupun external_place_id."
        )

    @classmethod
    def _resolve_url(cls, location: Location) -> str:
        """Kandidat pertama yang SAH, bukan kandidat pertama yang terisi.

        google_reviews_url dan google_maps_url adalah kolom opsional yang diisi
        manusia, jadi bisa salah bentuk — tautan pendek maps.app.goo.gl adalah
        yang paling sering. external_place_id sebaliknya berasal dari sistem dan
        selalu menghasilkan URL yang sah.

        Menyerah pada kandidat pertama yang terisi membuat satu kolom opsional
        yang salah mengalahkan identitas yang benar: Eka Hospital Margonda gagal
        crawl tiga kali berturut-turut karena tautan pendek, sementara cabang
        lain yang kolomnya kosong sama sekali justru berhasil lewat Place ID.
        """
        return cls._resolve_url_with_source(location)[0]

    def _open_review_panel(self, driver, url: str) -> list[WebElement]:
        driver.get(url)
        self._accept_consent_if_present(driver)
        return self._wait_for_review_cards_or_open_panel(driver)

    @staticmethod
    def _can_try_name_search_fallback(error: ReviewSourceError) -> bool:
        message = str(error)
        return (
            "Review container was not found" in message
            or "No reviews were loaded" in message
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
        keep_check=None,
        scan_limit: int | None = None,
        time_limit_seconds: int = 0,
    ):
        reviews: list[dict] = []
        review_keys: set[str] = set()
        seen_card_ids: set[str] = set()
        failed_card_ids: set[str] = set()
        no_new_attempts = 0
        scroll_attempts = 0
        stopped_reason = "target_reached"

        # Jumlah ulasan yang LOLOS saringan pemanggil. Target dihitung dari
        # angka ini, bukan dari jumlah kartu yang terbaca: Google menampilkan
        # ulasan terbaru lebih dulu, jadi permintaan rentang ke periode lampau
        # harus boleh menggulir melewati ulasan-ulasan baru tanpa menghabiskan
        # jatahnya. Tanpa keep_check, angka ini sama dengan jumlah kartu dan
        # perilakunya persis seperti sebelumnya.
        kept = 0
        habis_jendela = False
        max_scan = max(target, int(scan_limit or target))
        scan_limit_tercapai = False

        # Batas waktu. Rentang tanggal ke periode lampau menuntut menelusuri
        # ratusan ulasan yang lebih baru lebih dulu, dan tanpa batas satu job
        # bisa menahan worker sangat lama sementara cabang lain mengantre.
        # Kehabisan waktu BUKAN kegagalan — yang sudah terkumpul tetap dipakai
        # dan alasannya dilaporkan apa adanya.
        batas_waktu = None
        if time_limit_seconds and time_limit_seconds > 0:
            batas_waktu = time.monotonic() + time_limit_seconds
        kehabisan_waktu = False

        while (
            kept < target
            and len(reviews) < max_scan
            and scroll_attempts < self.settings.selenium_max_scroll_attempts
            and no_new_attempts < self.max_no_new_scroll_attempts
        ):
            if batas_waktu is not None and time.monotonic() >= batas_waktu:
                kehabisan_waktu = True
                break

            count_before = len(reviews)
            if on_progress is not None:
                # Dilaporkan tiap putaran gulir, bukan tiap kartu: menulis ke
                # database sesering kartu akan lebih mahal daripada crawl-nya.
                #
                # Dua angka: berapa yang cocok dan berapa yang sudah
                # ditelusuri. Melaporkan yang cocok saja membuat layar diam di
                # nol selama menggulir melewati ulasan di luar rentang — tidak
                # bisa dibedakan dari macet.
                try:
                    on_progress(kept, target, len(reviews))
                except Exception:  # laporan kemajuan tidak boleh menggagalkan crawl
                    logger.debug('on_progress gagal', exc_info=True)
            cards = self._find_review_cards(driver)
            for card in cards:
                if kept >= target or habis_jendela or len(reviews) >= max_scan:
                    if len(reviews) >= max_scan and kept < target:
                        scan_limit_tercapai = True
                    break
                if batas_waktu is not None and time.monotonic() >= batas_waktu:
                    kehabisan_waktu = True
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

                        # Kartu tetap dikembalikan seluruhnya supaya service
                        # bisa menghitung berapa yang terbaca dan berapa yang
                        # dibuang; keputusan di sini hanya menyangkut kapan
                        # berhenti menggulir.
                        putusan = "keep"
                        if keep_check is not None:
                            try:
                                putusan = keep_check(review) or "keep"
                            except Exception:
                                logger.debug(
                                    "keep_check gagal, ulasan dianggap lolos",
                                    exc_info=True,
                                )
                                putusan = "keep"

                        if putusan == "stop":
                            # Sudah melewati batas bawah jendela. Karena
                            # urutannya terbaru-dulu, sisanya pasti lebih tua.
                            habis_jendela = True
                            break

                        if putusan == "keep":
                            kept += 1
                        if len(reviews) >= max_scan and kept < target:
                            scan_limit_tercapai = True
                            break
                except StaleElementReferenceException:
                    seen_card_ids.discard(card_id)
                except Exception as exc:
                    failed_card_ids.add(card_id)
                    logger.warning("Failed to extract one review card: %s", exc)

            if kept >= target or habis_jendela or kehabisan_waktu or scan_limit_tercapai:
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

        if kehabisan_waktu:
            stopped_reason = "time_limit"
        elif scan_limit_tercapai or (len(reviews) >= max_scan and kept < target):
            stopped_reason = "scan_limit_reached"
        elif habis_jendela:
            stopped_reason = "out_of_range"
        elif kept < target:
            if no_new_attempts >= self.max_no_new_scroll_attempts:
                stopped_reason = "no_new_review_cards"
            elif scroll_attempts >= self.settings.selenium_max_scroll_attempts:
                stopped_reason = "max_scroll_attempts"
        return (
            reviews,
            len(seen_card_ids),

            len(failed_card_ids),
            scroll_attempts,
            stopped_reason,
            len(reviews),
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

    # Kata kunci menu urutan Google Maps, Inggris dan Indonesia. Google tidak
    # menyediakan penyaring tanggal sama sekali — hanya empat urutan ini — jadi
    # rentang tanggal hanya bisa dicapai lewat 'newest' ditambah berhenti awal.
    SORT_KEYWORDS = {
        "newest": ("newest", "terbaru"),
        "most_relevant": ("most relevant", "paling relevan", "relevance"),
        "highest_rating": ("highest rating", "peringkat tertinggi", "rating tertinggi"),
        "lowest_rating": ("lowest rating", "peringkat terendah", "rating terendah"),
    }

    def _apply_sort(self, driver, sort_by: str = "newest") -> bool:
        """Terapkan urutan pada panel ulasan.

        Mengembalikan True HANYA bila urutannya benar-benar terpasang.
        Pemanggil wajib memeriksa nilai ini sebelum mengandalkan urutan:
        berhenti-awal berbasis tanggal hanya sah pada daftar kronologis, dan
        urutan bawaan Google ('paling relevan') tidak kronologis. Memotong
        daftar seperti itu akan membuang ulasan yang sebenarnya cocok, diam-diam.
        """
        kata = self.SORT_KEYWORDS.get(sort_by) or self.SORT_KEYWORDS["newest"]

        sort_button = self._find_first(driver, selectors.SORT_BUTTON_SELECTORS)
        if sort_button is None:
            logger.info("Tombol urutan tidak ditemukan; memakai urutan bawaan.")
            return False

        try:
            self._safe_click(driver, sort_button)

            syarat = " or ".join(
                "contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                f"'{k}')"
                for k in kata
            )
            options = driver.find_elements(
                By.XPATH,
                "//*[self::div or self::li][@role='menuitemradio' or "
                f"@role='menuitem'][{syarat}]",
            )
            for option in options:
                if option.is_displayed():
                    self._safe_click(driver, option)
                    time.sleep(1)
                    return True

            logger.info("Pilihan urutan '%s' tidak ada di menu.", sort_by)
            return False
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
