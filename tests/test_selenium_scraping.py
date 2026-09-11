from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from selenium.common.exceptions import StaleElementReferenceException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.models import Company, CompetitorReview, FetchLog, Review
from app.integrations.review_source_client import ReviewSourceError
from app.integrations.selenium_google_maps_client import (
    SeleniumGoogleMapsReviewClient,
)
from app.services.competitor_service import CompetitorService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.services.selenium_fetch_service import SeleniumFetchService
from app.utils.hashing import generate_selenium_review_hash
from app.utils.rating_parser import parse_compact_count, parse_rating


def make_settings(tmp_path):
    return Settings(
        app_env="test",
        app_name="Review System",
        log_level="INFO",
        export_dir=tmp_path / "exports",
        database_url="sqlite+pysqlite:///:memory:",
        cors_allowed_origins=("http://localhost:3000",),
        review_source_mode="selenium",
        google_maps_api_key=None,
        google_places_language_code="id",
        google_places_region_code="ID",
        local_llm_base_url="http://localhost:11434/v1/",
        local_llm_api_key="test",
        local_llm_model="mock",
        fetch_limit_per_location=50,
        fetch_timeout_seconds=1,
        fetch_max_retry=0,
        selenium_headless=True,
        selenium_default_target_reviews=100,
        selenium_max_target_reviews=300,
        selenium_scroll_delay_seconds=2,
        selenium_max_scroll_attempts=100,
        selenium_wait_timeout_seconds=20,
        selenium_user_data_dir=None,
        analysis_batch_size=20,
        prompt_version="v1",
        page_size=20,
        show_raw_payload=False,
    )


class FakeSeleniumClient:
    source_name = "selenium_google_maps"

    def __init__(self):
        self.last_metadata = {}

    def fetch_reviews(
        self,
        location,
        limit=50,
        on_progress=None,
        keep_check=None,
        sort_by="newest",
        scan_limit=None,
        time_limit_seconds=0,
    ):
        self.last_metadata = {
            "target_review_count": limit,
            "max_reviews_to_collect": limit,
            "scan_limit": scan_limit or limit,
            "loaded_review_cards": 2,
            "reviews_scanned": 2,
            "matched_review_cards": 0 if keep_check is not None else 2,
            "scraped_review_cards": 2,
            "failed_review_cards": 0,
            "scroll_attempts": 3,
            "headless": True,
            "url": location.google_reviews_url,
            "stopped_reason": "no_new_review_cards",
            "sort_applied": True,
            "place_rating": 4.3,
            "place_review_count": 9422,
            "rating_snapshot_at": "2026-09-01T06:00:00+00:00",
            "rating_snapshot": {
                "source": "google_maps",
                "place_rating": 4.3,
                "place_review_count": 9422,
                "snapshot_at": "2026-09-01T06:00:00+00:00",
            },
        }
        scraped_at = datetime.now().astimezone().isoformat()
        if on_progress is not None:
            on_progress(2, limit)
        return [
            {
                "source": self.source_name,
                "external_review_id": f"review-{index}",
                "reviewer_name": name,
                "reviewer_profile_url": f"https://google.com/maps/contrib/{index}",
                "reviewer_photo_url": None,
                "reviewer_local_guide_level": (
                    "Local Guide" if index == 1 else None
                ),
                "reviewer_total_reviews": 37 if index == 1 else None,
                "rating": rating,
                "review_text": text,
                "review_relative_time": "2 minggu lalu",
                "review_time": None,
                "review_language": "id",
                "language": "id",
                "like_count": index,
                "owner_response_text": None,
                "owner_response_time": None,
                "scraped_at": scraped_at,
                "raw_payload": {"test": True},
            }
            for index, (name, rating, text) in enumerate(
                [
                    ("Andi", 5, "Pelayanan baik."),
                    ("Budi", 2, "Antrean lama."),
                ],
                start=1,
            )
        ]


class SortUnavailableSeleniumClient:
    source_name = "selenium_google_maps"

    def __init__(self):
        self.last_metadata = {}

    def fetch_reviews(
        self,
        location,
        limit=50,
        on_progress=None,
        keep_check=None,
        sort_by="newest",
        scan_limit=None,
        time_limit_seconds=0,
    ):
        self.last_metadata = {
            "target_review_count": limit,
            "max_reviews_to_collect": limit,
            "scan_limit": scan_limit or limit,
            "loaded_review_cards": 4,
            "reviews_scanned": 0,
            "scraped_review_cards": 0,
            "matched_review_cards": 0,
            "failed_review_cards": 0,
            "scroll_attempts": 0,
            "headless": True,
            "url": location.google_reviews_url,
            "stopped_reason": "sort_unavailable",
            "sort_applied": False,
            "range_warning": "Date-range crawling requires newest sorting.",
        }
        return []


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed_location(session_factory, target_review_count=2):
    with session_factory() as session:
        company = Company(
            name="Test Company",
            ai_enable_flag=True,
            total_enable_review=100,
            analyze_competitor_flag=False,
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        company_id = company.id
    location = LocationService(
        company_id=company_id, session_factory=session_factory
    ).add_location(
        hospital_name="Hermina",
        branch_name="Hermina Bekasi",
        city="Bekasi",
        source="google_places",
        external_place_id="place-bekasi",
        google_reviews_url="https://www.google.com/maps/place/example/reviews",
        target_review_count=target_review_count,
        is_active=True,
    )
    return company_id, location


def seed_competitor(session_factory, target_review_count=2):
    with session_factory() as session:
        company = Company(
            name="Test Company",
            ai_enable_flag=True,
            total_enable_review=100,
            analyze_competitor_flag=False,
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        company_id = company.id
    competitor = CompetitorService(
        company_id=company_id, session_factory=session_factory
    ).add_competitor(
        name="RS Pesaing Bekasi",
        city="Bekasi",
        source="google_places",
        external_place_id="place-pesaing-bekasi",
        google_reviews_url="https://www.google.com/maps/place/competitor/reviews",
        target_review_count=target_review_count,
        is_active=True,
    )
    return company_id, competitor


def test_rating_and_count_parsers():
    assert parse_rating("5 bintang") == 5
    assert parse_rating("Rating 4.0") == 4
    assert parse_rating("unknown") is None
    assert parse_compact_count("1,2k orang merasa terbantu") == 1200
    assert parse_compact_count("37 ulasan") == 37


def test_selenium_driver_uses_container_browser_and_safe_flags(
    monkeypatch, tmp_path
):
    settings = make_settings(tmp_path)
    captured = {}

    def fake_which(binary):
        return {
            "chromium": "/usr/bin/chromium",
            "chromedriver": "/usr/bin/chromedriver",
        }.get(binary)

    class _FakeChromeDriver:
        def execute_cdp_cmd(self, cmd, params):
            captured["cdp_cmd"] = cmd
            captured["cdp_params"] = params

    def fake_chrome(*, service, options):
        captured["service"] = service
        captured["options"] = options
        return _FakeChromeDriver()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        fake_which,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    result = SeleniumGoogleMapsReviewClient(settings)._create_driver()

    assert result is not None
    assert captured["options"].binary_location == "/usr/bin/chromium"
    assert "--headless=new" in captured["options"].arguments
    assert "--no-sandbox" in captured["options"].arguments
    assert "--disable-dev-shm-usage" in captured["options"].arguments
    assert captured["service"].path == "/usr/bin/chromedriver"


def test_selenium_driver_hides_automation_fingerprint(monkeypatch, tmp_path):
    # Google Maps membatasi pagination ulasan untuk browser yang terdeteksi
    # otomasi (navigator.webdriver bawaan Selenium). Pastikan flag penyamar
    # dan patch CDP-nya benar-benar terpasang, bukan cuma niat di komentar.
    settings = make_settings(tmp_path)
    captured = {}

    class _FakeChromeDriver:
        def execute_cdp_cmd(self, cmd, params):
            captured["cdp_cmd"] = cmd
            captured["cdp_params"] = params

    def fake_chrome(*, service, options):
        captured["options"] = options
        return _FakeChromeDriver()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        lambda _binary: None,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    SeleniumGoogleMapsReviewClient(settings)._create_driver()

    options = captured["options"]
    assert "--disable-blink-features=AutomationControlled" in options.arguments
    assert options.experimental_options["excludeSwitches"] == ["enable-automation"]
    assert options.experimental_options["useAutomationExtension"] is False
    assert captured["cdp_cmd"] == "Page.addScriptToEvaluateOnNewDocument"
    assert "navigator" in captured["cdp_params"]["source"]
    assert "webdriver" in captured["cdp_params"]["source"]


def test_selenium_driver_applies_proxy_when_configured(monkeypatch, tmp_path):
    settings = make_settings(tmp_path).model_copy(
        update={"selenium_proxy_url": "http://203.0.113.10:8080"}
    )
    captured = {}

    class _FakeChromeDriver:
        def execute_cdp_cmd(self, cmd, params):
            pass

    def fake_chrome(*, service, options):
        captured["options"] = options
        return _FakeChromeDriver()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        lambda _binary: None,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    SeleniumGoogleMapsReviewClient(settings)._create_driver()

    # selenium_authenticated_proxy strips the scheme when building
    # --proxy-server (Chrome accepts a bare host:port).
    assert "--proxy-server=203.0.113.10:8080" in captured["options"].arguments


def test_selenium_driver_proxy_with_credentials_loads_auth_extension(
    monkeypatch, tmp_path
):
    # Webshare's free tier (and most proxy providers) authenticate by
    # username/password, not IP whitelist. Chrome's --proxy-server flag has
    # no credential field, so selenium_authenticated_proxy answers the proxy
    # auth challenge via a generated Chrome extension instead.
    settings = make_settings(tmp_path).model_copy(
        update={"selenium_proxy_url": "http://demo_user:demo_pass@203.0.113.10:8080"}
    )
    captured = {}

    class _FakeChromeDriver:
        def execute_cdp_cmd(self, cmd, params):
            pass

    def fake_chrome(*, service, options):
        captured["options"] = options
        return _FakeChromeDriver()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        lambda _binary: None,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    SeleniumGoogleMapsReviewClient(settings)._create_driver()

    options = captured["options"]
    assert "--proxy-server=203.0.113.10:8080" in options.arguments
    # Credentials never leak into a bare Chrome flag; they're baked into the
    # generated extension instead (asserted by presence of either path).
    assert options.extensions or any(
        a.startswith("--load-extension=") for a in options.arguments
    )


def test_selenium_driver_skips_proxy_flag_when_unset(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    captured = {}

    class _FakeChromeDriver:
        def execute_cdp_cmd(self, cmd, params):
            pass

    def fake_chrome(*, service, options):
        captured["options"] = options
        return _FakeChromeDriver()

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.shutil.which",
        lambda _binary: None,
    )
    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.webdriver.Chrome",
        fake_chrome,
    )

    SeleniumGoogleMapsReviewClient(settings)._create_driver()

    assert not any(
        a.startswith("--proxy-server=") for a in captured["options"].arguments
    )


def test_place_id_resolution_keeps_source_and_has_name_search_fallback(tmp_path):
    session_factory = make_session_factory()
    _, location = seed_location(session_factory)
    client = SeleniumGoogleMapsReviewClient(make_settings(tmp_path))

    url, source = client._resolve_url_with_source(location)

    assert source == "google_reviews_url"
    assert url == location.google_reviews_url

    location.google_reviews_url = None
    url, source = client._resolve_url_with_source(location)

    assert source == "external_place_id"
    assert "query_place_id=place-bekasi" in url
    assert (
        client._name_search_url(location)
        == "https://www.google.com/maps/search/?api=1&query=Hermina+Bekasi&hl=id"
    )


def test_selenium_hash_uses_scraping_identity_fields():
    review = {
        "source": "selenium_google_maps",
        "location_id": 1,
        "external_review_id": "review-1",
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Pelayanan baik.",
        "review_relative_time": "2 minggu lalu",
        "reviewer_profile_url": "https://google.com/maps/contrib/1",
    }
    updated_relative_time = dict(review, review_relative_time="3 minggu lalu")
    assert generate_selenium_review_hash(review) == generate_selenium_review_hash(
        updated_relative_time
    )


def test_selenium_hash_fallback_does_not_use_relative_time():
    review = {
        "source": "selenium_google_maps",
        "location_id": 1,
        "external_review_id": None,
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Pelayanan baik.",
        "review_time": None,
        "review_relative_time": "2 minggu lalu",
        "reviewer_profile_url": "https://google.com/maps/contrib/1",
    }
    updated_relative_time = dict(review, review_relative_time="3 minggu lalu")

    assert generate_selenium_review_hash(review) == generate_selenium_review_hash(
        updated_relative_time
    )


def test_review_insert_deduplicates_legacy_hash_by_external_review_id(tmp_path):
    session_factory = make_session_factory()
    company_id, location = seed_location(session_factory)
    service = ReviewService(company_id=company_id, session_factory=session_factory)
    base_review = {
        "company_id": company_id,
        "location_id": location.id,
        "source": "selenium_google_maps",
        "external_place_id": location.external_place_id,
        "external_review_id": "stable-google-review-id",
        "reviewer_name": "Andi",
        "rating": 5,
        "review_text": "Pelayanan baik.",
        "review_relative_time": "2 minggu lalu",
        "review_language": "id",
        "language": "id",
        "like_count": 0,
        "raw_payload": {},
        "review_hash": "legacy-relative-time-hash",
    }
    inserted, duplicate = service.insert_review(dict(base_review))

    assert duplicate is False
    assert inserted is not None

    next_review = dict(
        base_review,
        review_relative_time="3 minggu lalu",
        review_hash=generate_selenium_review_hash(base_review),
    )
    inserted_again, duplicate_again = service.insert_review(next_review)

    assert inserted_again is None
    assert duplicate_again is True


def test_selenium_fetch_stores_metadata_and_deduplicates(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    first = service.fetch_location(location.id, target=2)
    second = service.fetch_location(location.id, target=2)

    assert first["status"] == "success"
    assert first["total_inserted"] == 2
    assert second["total_duplicate"] == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(Review.id))) == 2
        latest_log = session.scalar(
            select(FetchLog).order_by(FetchLog.id.desc()).limit(1)
        )
        assert latest_log.source == "selenium_google_maps"
        assert latest_log.metadata_json["scroll_attempts"] == 3
        assert latest_log.metadata_json["rating_snapshot"] == {
            "source": "google_maps",
            "place_rating": 4.3,
            "place_review_count": 9422,
            "snapshot_at": "2026-09-01T06:00:00+00:00",
        }


def test_selenium_competitor_fetch_stores_reviews_without_fetch_log(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, competitor = seed_competitor(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    first = service.fetch_competitor(competitor.id, target=2)
    second = service.fetch_competitor(competitor.id, target=2)

    assert first["status"] == "success"
    assert first["total_inserted"] == 2
    assert second["status"] == "success"
    assert second["total_duplicate"] == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(CompetitorReview.id))) == 2
        assert session.scalar(select(func.count(FetchLog.id))) == 0


def test_selenium_competitor_fetch_result_uses_competitor_keys(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, competitor = seed_competitor(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    result = service.fetch_competitor(competitor.id, target=2)

    assert result["competitor_id"] == competitor.id
    assert result["competitor_name"] == competitor.name
    assert "location_id" not in result
    assert "location_name" not in result


def test_date_range_stops_honestly_when_sort_is_unavailable(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory, target_review_count=5)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=SortUnavailableSeleniumClient(),
    )

    result = service.fetch_location(
        location.id,
        target=5,
        date_from=datetime.now().astimezone() - timedelta(days=7),
    )

    assert result["status"] == "partial_success"
    assert result["total_inserted"] == 0
    assert result["total_fetched"] == 0
    assert result["metadata"]["stopped_reason"] == "sort_unavailable"
    assert result["metadata"]["reviews_scanned"] == 0
    assert result["error_message"] is None
    assert result["metadata"]["range_warning"] == (
        "Urutan terbaru gagal dipasang, sehingga hasil rentang tanggal "
        "tidak dijamin lengkap."
    )


def test_date_range_with_only_out_of_range_reviews_is_partial(tmp_path):
    session_factory = make_session_factory()
    settings = make_settings(tmp_path)
    company_id, location = seed_location(session_factory)
    service = SeleniumFetchService(
        company_id=company_id,
        session_factory=session_factory,
        settings=settings,
        client=FakeSeleniumClient(),
    )

    result = service.fetch_location(
        location.id,
        target=2,
        date_from=datetime.now().astimezone() - timedelta(days=1),
    )

    assert result["status"] == "success"
    assert result["total_fetched"] == 2
    assert result["total_inserted"] == 0
    assert result["total_skipped_out_of_range"] == 2
    assert result["metadata"]["matched_review_cards"] == 0


class _FakeEl:
    def __init__(self, attrs=None, text=""):
        self._attrs = attrs or {}
        self.text = text
        self.id = f"el-{id(self)}"
        self.clicks = 0

    def get_attribute(self, name):
        return self._attrs.get(name)

    def is_displayed(self):
        return True

    def click(self):
        self.clicks += 1
        callback = getattr(self, "on_click", None)
        if callback is not None:
            callback()

    def find_elements(self, _by, _selector):
        return []


class _FakeDriver:
    """Minimal DOM: find_elements answers from a {selector: [elements]} map."""

    def __init__(self, registry, body_text=""):
        self._registry = registry
        self._body = _FakeEl(text=body_text)
        self.current_url = "https://www.google.com/maps/place/x/reviews"

    def find_elements(self, _by, selector):
        return list(self._registry.get(selector, []))

    def find_element(self, _by, _selector):
        return self._body

    def execute_script(self, *_a, **_k):
        return None


def _client_with_short_wait(tmp_path):
    settings = make_settings(tmp_path).model_copy(
        update={
            "selenium_wait_timeout_seconds": 0,
            "selenium_scroll_delay_seconds": 0,
        }
    )
    return SeleniumGoogleMapsReviewClient(settings)


def test_advance_review_list_clicks_load_more_and_adds_cards(tmp_path):
    initial_cards = [_FakeEl({"data-review-id": f"r{i}"}) for i in range(5)]
    more_cards = [_FakeEl({"data-review-id": f"r{i}"}) for i in range(5, 10)]
    button = _FakeEl()
    registry = {
        "div[data-review-id]": initial_cards,
        "button[aria-label^='Lihat ulasan lainnya' i]": [button],
    }
    button.on_click = lambda: registry["div[data-review-id]"].extend(more_cards)
    client = _client_with_short_wait(tmp_path)
    driver = _FakeDriver(registry)

    client._advance_review_list(driver, _FakeEl())

    assert button.clicks == 1
    assert len(client._find_review_cards(driver)) == 10


def test_advance_review_list_without_load_more_is_safe(tmp_path):
    # Tanpa tombol "load more", fungsi tetap harus melakukan scroll biasa -
    # bukan diam saja - supaya daftar yang benar-benar infinite-scroll masih
    # maju.
    client = _client_with_short_wait(tmp_path)
    scroll_calls = []

    class _RecordingDriver(_FakeDriver):
        def execute_script(self, _script, *args, **_kwargs):
            scroll_calls.append(args)

    container = _FakeEl()
    result = client._advance_review_list(_RecordingDriver({}), container)

    assert scroll_calls == [(container,)]
    assert result is container


def test_advance_review_list_swallows_stale_button_click(tmp_path):
    # Tombol "load more" bisa hilang/berganti tepat saat diklik (AJAX
    # menukar markup-nya). Itu bukan kegagalan crawl - harus tetap lanjut ke
    # scroll, bukan meledak sampai ke fetch_reviews dan membuang ulasan yang
    # sudah terkumpul.
    class _StaleButton(_FakeEl):
        def click(self):
            raise StaleElementReferenceException("gone")

    button = _StaleButton()
    registry = {"button[aria-label^='Lihat ulasan lainnya' i]": [button]}
    client = _client_with_short_wait(tmp_path)

    result = client._advance_review_list(_FakeDriver(registry), _FakeEl())

    assert result is not None  # did not raise


def test_apply_sort_waits_for_option_after_click(tmp_path, monkeypatch):
    # Opsi menu muncul setelah beberapa kali polling, bukan seketika saat
    # diklik - kalau _apply_sort membaca sekali saja (perilaku lama), ini
    # akan gagal.
    sort_button = _FakeEl()
    option = _FakeEl()
    client = _client_with_short_wait(tmp_path)
    option_xpath = client._sort_menu_option_xpath(client.SORT_KEYWORDS["newest"])
    registry = {"button[aria-label*='Urutkan ulasan' i]": [sort_button]}
    polls = {"count": 0}

    class _DelayedMenuDriver(_FakeDriver):
        def find_elements(self, by, selector):
            if selector == option_xpath:
                polls["count"] += 1
                return [option] if polls["count"] >= 3 else []
            return super().find_elements(by, selector)

    monkeypatch.setattr(
        "app.integrations.selenium_google_maps_client.time.sleep", lambda _seconds: None
    )

    assert client._apply_sort(_DelayedMenuDriver(registry), "newest") is True
    assert option.clicks == 1
    assert polls["count"] >= 3


def test_overview_only_panel_raises_instead_of_returning_preview_cards(tmp_path):
    # Panel Ringkasan: tab "Ulasan" ADA tapi tidak aktif, hanya 3 kartu
    # pratinjau, tidak ada div[role='feed']. Meng-klik tab tidak mengubah
    # apa pun (DOM statis). Scraper harus gagal keras, bukan mengembalikan 3.
    overview_tab = _FakeEl({"role": "tab", "aria-selected": "true",
                            "aria-label": "Ringkasan RS Contoh"})
    reviews_tab = _FakeEl({"role": "tab", "aria-selected": "false",
                           "aria-label": "Ulasan untuk RS Contoh"})
    registry = {
        "[role='tab']": [overview_tab, reviews_tab],
        "button[role='tab'][aria-label^='Ulasan' i]": [reviews_tab],
        "div[data-review-id]": [_FakeEl({"data-review-id": f"r{i}"})
                                for i in range(3)],
    }
    client = _client_with_short_wait(tmp_path)

    with pytest.raises(ReviewSourceError, match="Review container was not found"):
        client._wait_for_review_cards_or_open_panel(_FakeDriver(registry))
    assert reviews_tab.clicks == 1  # it did try to open the list


def test_get_with_proxy_retry_survives_transient_407(tmp_path):
    # selenium_authenticated_proxy's extension listener can lose the race
    # against the very first navigation. That request comes back as Chrome's
    # own "HTTP ERROR 407" page - retrying (not failing outright) is the fix.
    client = _client_with_short_wait(tmp_path)
    get_calls = []

    class _FlakyProxyDriver(_FakeDriver):
        def get(self, url):
            get_calls.append(url)
            self._body.text = (
                "This page isn't working\nHTTP ERROR 407"
                if len(get_calls) == 1
                else "Graha Asuransi Astra"
            )

    driver = _FlakyProxyDriver({})
    client._get_with_proxy_retry(driver, "https://example.com/maps")

    assert get_calls == ["https://example.com/maps"] * 2
    assert "407" not in driver.find_element(None, None).text


def test_get_with_proxy_retry_gives_up_after_max_attempts(tmp_path):
    client = _client_with_short_wait(tmp_path)
    get_calls = []

    class _AlwaysFlakyDriver(_FakeDriver):
        def get(self, url):
            get_calls.append(url)
            self._body.text = "This page isn't working\nHTTP ERROR 407"

    driver = _AlwaysFlakyDriver({})
    client._get_with_proxy_retry(driver, "https://example.com/maps", attempts=3)

    assert len(get_calls) == 3  # stops retrying, doesn't hang forever


def test_click_opens_reviews_list(tmp_path):
    # Dari panel Ringkasan, klik tab "Ulasan": tab jadi aktif dan panel
    # menampilkan daftar ulasan penuh. Kartu itulah yang dikembalikan.
    overview_tab = _FakeEl({"role": "tab", "aria-selected": "true",
                            "aria-label": "Ringkasan RS Contoh"})
    reviews_tab = _FakeEl({"role": "tab", "aria-selected": "false",
                           "aria-label": "Ulasan untuk RS Contoh"})
    preview = [_FakeEl({"data-review-id": f"p{i}"}) for i in range(3)]
    full = [_FakeEl({"data-review-id": f"r{i}"}) for i in range(12)]
    registry = {
        "[role='tab']": [overview_tab, reviews_tab],
        "button[role='tab'][aria-label^='Ulasan' i]": [reviews_tab],
        "div[data-review-id]": preview,
    }

    def _open_reviews_list():
        overview_tab._attrs["aria-selected"] = "false"
        reviews_tab._attrs["aria-selected"] = "true"
        registry["div[data-review-id]"] = full

    reviews_tab.on_click = _open_reviews_list
    client = _client_with_short_wait(tmp_path)

    result = client._wait_for_review_cards_or_open_panel(_FakeDriver(registry))

    assert result == full


def test_click_then_only_preview_count_cards_raises(tmp_path):
    # Setelah klik, tab "Ulasan" aktif tapi yang terbaca cuma 3 kartu — tak
    # bisa dibedakan dari pratinjau Ringkasan (`_find_review_cards` tidak
    # terlingkup ke daftar). Gagal keras, bukan mengembalikannya sebagai 3.
    overview_tab = _FakeEl({"role": "tab", "aria-selected": "true",
                            "aria-label": "Ringkasan RS Contoh"})
    reviews_tab = _FakeEl({"role": "tab", "aria-selected": "false",
                           "aria-label": "Ulasan untuk RS Contoh"})
    preview = [_FakeEl({"data-review-id": f"p{i}"}) for i in range(3)]
    registry = {
        "[role='tab']": [overview_tab, reviews_tab],
        "button[role='tab'][aria-label^='Ulasan' i]": [reviews_tab],
        "div[data-review-id]": preview,
    }

    def _flip_selected_only():
        overview_tab._attrs["aria-selected"] = "false"
        reviews_tab._attrs["aria-selected"] = "true"
        # daftar ulasan tak kunjung render — tetap 3 kartu pratinjau

    reviews_tab.on_click = _flip_selected_only
    client = _client_with_short_wait(tmp_path)

    with pytest.raises(ReviewSourceError, match="Review container was not found"):
        client._wait_for_review_cards_or_open_panel(_FakeDriver(registry))


def test_reviews_tab_active_returns_cards(tmp_path):
    reviews_tab = _FakeEl({"role": "tab", "aria-selected": "true",
                           "aria-label": "Ulasan untuk RS Contoh"})
    cards = [_FakeEl({"data-review-id": f"r{i}"}) for i in range(3)]
    registry = {"[role='tab']": [reviews_tab], "div[data-review-id]": cards}
    client = _client_with_short_wait(tmp_path)

    result = client._wait_for_review_cards_or_open_panel(_FakeDriver(registry))

    assert result == cards


def test_unconfirmed_reviews_surface_raises_even_with_visible_cards(tmp_path):
    # Tidak ada tab, tidak ada kontrol pembuka daftar — kartu yang terlihat
    # tidak bisa dibuktikan sebagai daftar ulasan lengkap (bisa jadi pratinjau
    # Ringkasan, atau kontrolnya lambat render). Harus gagal keras, bukan
    # mengembalikan kartu yang belum terkonfirmasi.
    cards = [_FakeEl({"data-review-id": f"r{i}"}) for i in range(2)]
    registry = {"[role='tab']": [], "div[data-review-id]": cards}
    client = _client_with_short_wait(tmp_path)

    with pytest.raises(ReviewSourceError, match="Review container was not found"):
        client._wait_for_review_cards_or_open_panel(_FakeDriver(registry))
