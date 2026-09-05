from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.models import Competitor
from app.db.session import get_session_factory
from app.integrations.selenium_google_maps_client import (
    SeleniumGoogleMapsReviewClient,
)
from app.services.competitor_review_service import CompetitorReviewService
from app.services.crawl_result import CrawlFetchResult
from app.services.entitlement_service import EntitlementService
from app.services.fetch_log_service import FetchLogService
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.date_parser import is_within_date_range


logger = logging.getLogger(__name__)


class _CompetitorAsLocation:
    """Bungkus kompetitor agar bisa melewati scraper dan normalizer yang sama
    persis dengan cabang.

    Scraper hanya membaca empat atribut — external_place_id, branch_name,
    google_reviews_url, google_maps_url — dan normalizer hanya menambah `id`.
    Dengan menyediakannya di sini, dukungan kompetitor tidak menuntut satu baris
    pun perubahan di jalur cabang yang sudah berjalan.
    """

    __slots__ = (
        "id",
        "branch_name",
        "hospital_name",
        "external_place_id",
        "google_maps_url",
        "google_reviews_url",
        "target_review_count",
        "source",
    )

    def __init__(self, competitor):
        self.id = competitor.id
        self.branch_name = competitor.name
        self.hospital_name = competitor.name
        self.external_place_id = competitor.external_place_id
        self.google_maps_url = competitor.google_maps_url
        self.google_reviews_url = competitor.google_reviews_url
        self.target_review_count = competitor.target_review_count
        self.source = competitor.source


class SeleniumFetchService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
        client: SeleniumGoogleMapsReviewClient | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()
        self.location_service = LocationService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.review_service = ReviewService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.fetch_log_service = FetchLogService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.competitor_review_service = CompetitorReviewService(
            company_id=company_id, session_factory=self.session_factory
        )
        self.client = client or SeleniumGoogleMapsReviewClient(self.settings)
        self.normalizer = FetchService(
            company_id=company_id,
            session_factory=self.session_factory,
            settings=self.settings,
            client=self.client,
        )

    def fetch_location(
        self,
        location_id: int,
        target: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
        scan_limit: int | None = None,
        time_limit_seconds: int = 600,
    ) -> CrawlFetchResult:
        location = self.location_service.get_location(location_id)
        if location is None:
            raise ValueError("Location not found.")

        # Google Maps TIDAK punya penyaring tanggal — hanya empat urutan.
        # Rentang tanggal karena itu hanya bisa dicapai dengan mengurutkan dari
        # yang terbaru lalu berhenti begitu melewati batas bawah. Urutan lain
        # tidak kronologis, sehingga berhenti-awal di atasnya akan membuang
        # ulasan yang cocok tanpa ada yang tahu. Maka rentang tanggal memaksa
        # 'newest', dan alasannya dicatat supaya layar bisa menjelaskannya.
        sort_dipaksa = False
        if (date_from is not None or date_to is not None) and sort_by != "newest":
            sort_dipaksa = True
            sort_by = "newest"
        requested_target = self.validate_target(
            target or location.target_review_count
        )
        requested_scan_limit = self.validate_scan_limit(
            scan_limit, requested_target
        )
        result: CrawlFetchResult = {
            "location_id": location.id,
            "location_name": location.branch_name,
            "source": self.client.source_name,
            "status": "failed",
            "target_review_count": requested_target,
            "total_fetched": 0,
            "total_inserted": 0,
            "total_duplicate": 0,
            "total_failed": 0,
            "total_skipped_out_of_range": 0,
            "error_message": None,
            "metadata": {
                "target_review_count": requested_target,
                "max_reviews_to_collect": requested_target,
                "scan_limit": requested_scan_limit,
                "headless": self.settings.selenium_headless,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }
        log_id = self.fetch_log_service.start_log(
            location.id, self.client.source_name, result["metadata"]
        )
        logger.info(
            "Selenium fetch started for %s with target %s",
            location.branch_name,
            requested_target,
        )
        try:
            # Penyaringan tanggal harus ikut menentukan KAPAN BERHENTI
            # menggulir, bukan cuma membuang hasil di akhir. Google Maps
            # mengurutkan ulasan terbaru lebih dulu, jadi permintaan rentang ke
            # periode lampau akan menghabiskan seluruh jatah target pada ulasan
            # terbaru dan menyisakan nol — berapa kali pun diulang.
            def _nilai_rentang(raw_review):
                if date_from is None and date_to is None:
                    return "keep"
                try:
                    waktu = self.normalizer.normalize_review(
                        location, raw_review
                    ).get("review_time")
                except Exception:
                    # Kartu rusak diserahkan ke jalur normal di bawah, yang
                    # sudah menghitungnya sebagai gagal.
                    return "keep"
                if is_within_date_range(waktu, date_from, date_to):
                    return "keep"
                # Sudah lebih tua dari batas bawah: karena urutannya
                # terbaru-dulu, sisanya pasti lebih tua lagi.
                try:
                    if date_from is not None and waktu is not None and waktu < date_from:
                        return "stop"
                except TypeError:
                    # Beda kesadaran zona waktu — jangan sampai menghentikan
                    # crawl hanya karena perbandingan tidak bisa dilakukan.
                    return "skip"
                return "skip"

            raw_reviews = self.client.fetch_reviews(
                location,
                limit=requested_target,
                on_progress=on_progress,
                keep_check=_nilai_rentang,
                sort_by=sort_by,
                scan_limit=requested_scan_limit,
                time_limit_seconds=time_limit_seconds,
            )
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"]["date_from"] = date_from.isoformat() if date_from else None
            result["metadata"]["date_to"] = date_to.isoformat() if date_to else None
            result["metadata"]["sort_forced_to_newest"] = sort_dipaksa
            result["metadata"]["max_reviews_to_collect"] = requested_target
            result["metadata"]["scan_limit"] = requested_scan_limit

            # Peringatan yang HARUS sampai ke layar: kalau urutan gagal
            # dipasang sementara rentang tanggal diminta, hasilnya tidak bisa
            # dijamin lengkap — daftar Google mengikuti urutan 'paling relevan'
            # yang tidak kronologis.
            if (date_from is not None or date_to is not None) and not result[
                "metadata"
            ].get("sort_applied", False):
                result["metadata"]["range_warning"] = (
                    "Urutan terbaru gagal dipasang, sehingga hasil rentang "
                    "tanggal tidak dijamin lengkap."
                )
                logger.warning(
                    "Rentang tanggal diminta tetapi urutan newest gagal "
                    "dipasang untuk %s",
                    location.branch_name,
                )
            result["total_fetched"] = len(raw_reviews)
            result["total_failed"] = int(
                result["metadata"].get("failed_review_cards", 0)
            )
            for raw_review in raw_reviews:
                try:
                    normalized = self.normalizer.normalize_review(
                        location, raw_review
                    )
                    if not is_within_date_range(normalized["review_time"], date_from, date_to):
                        result["total_skipped_out_of_range"] += 1
                        if self._is_older_than_range(
                            normalized["review_time"], date_from
                        ):
                            result["metadata"]["out_of_range_older"] = (
                                int(result["metadata"].get("out_of_range_older") or 0)
                                + 1
                            )
                        else:
                            result["metadata"]["out_of_range_newer"] = (
                                int(result["metadata"].get("out_of_range_newer") or 0)
                                + 1
                            )
                        continue
                    _, duplicate = self.review_service.insert_review(normalized)
                    if duplicate:
                        result["total_duplicate"] += 1
                    else:
                        result["total_inserted"] += 1
                except Exception as exc:
                    result["total_failed"] += 1
                    logger.exception(
                        "Failed to store one Selenium review: %s", exc
                    )
            # Ulasan yang dibuang karena di luar rentang BUKAN kegagalan —
            # itu justru penyaring bekerja. Menghitungnya sebagai partial
            # membuat setiap penarikan berentang tanggal tampak setengah gagal.
            tersimpan = result["total_inserted"] + result["total_duplicate"]
            partial = (
                (tersimpan < requested_target
                 and result["total_skipped_out_of_range"] == 0)
                or result["total_failed"] > 0
            )
            result["status"] = "partial_success" if partial else "success"
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.exception("Selenium fetch failed for %s", location.branch_name)
        finally:
            self.fetch_log_service.finish_log(log_id, result)
        return result

    def fetch_competitor(
        self,
        competitor_id: int,
        target: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        on_progress=None,
        sort_by: str = "newest",
        scan_limit: int | None = None,
        time_limit_seconds: int = 600,
    ) -> CrawlFetchResult:
        """Tarik ulasan satu kompetitor ke tabel competitor_reviews.

        Sengaja tidak menulis fetch_logs: kolom location_id di tabel itu
        menunjuk ke locations, dan memasukkan id kompetitor ke sana akan
        menautkannya ke cabang yang tidak ada hubungannya.
        """
        with self.session_factory() as session:
            statement = select(Competitor).where(Competitor.id == competitor_id)
            if self.company_id is not None:
                statement = statement.where(
                    Competitor.company_id == self.company_id
                )
            competitor = session.scalar(statement)
            if competitor is None:
                raise ValueError("Competitor not found.")
            sasaran = _CompetitorAsLocation(competitor)

        # Alasan pemaksaan urutan ini sama dengan jalur cabang: Google Maps
        # tidak punya penyaring tanggal, jadi rentang hanya bisa dikerjakan
        # dengan mengurutkan terbaru lalu berhenti di batas bawah.
        sort_dipaksa = False
        if (date_from is not None or date_to is not None) and sort_by != "newest":
            sort_dipaksa = True
            sort_by = "newest"
        requested_target = self.validate_target(
            target or sasaran.target_review_count
        )
        requested_scan_limit = self.validate_scan_limit(
            scan_limit, requested_target
        )
        result: CrawlFetchResult = {
            "competitor_id": sasaran.id,
            "competitor_name": sasaran.branch_name,
            "source": self.client.source_name,
            "status": "failed",
            "target_review_count": requested_target,
            "total_fetched": 0,
            "total_inserted": 0,
            "total_duplicate": 0,
            "total_failed": 0,
            "total_skipped_out_of_range": 0,
            "error_message": None,
            "metadata": {
                "target_review_count": requested_target,
                "max_reviews_to_collect": requested_target,
                "scan_limit": requested_scan_limit,
                "headless": self.settings.selenium_headless,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }
        logger.info(
            "Selenium competitor fetch started for %s with target %s",
            sasaran.branch_name,
            requested_target,
        )
        try:

            def _nilai_rentang(raw_review):
                if date_from is None and date_to is None:
                    return "keep"
                try:
                    waktu = self.normalizer.normalize_review(
                        sasaran, raw_review
                    ).get("review_time")
                except Exception:
                    return "keep"
                if is_within_date_range(waktu, date_from, date_to):
                    return "keep"
                try:
                    if (
                        date_from is not None
                        and waktu is not None
                        and waktu < date_from
                    ):
                        return "stop"
                except TypeError:
                    return "skip"
                return "skip"

            raw_reviews = self.client.fetch_reviews(
                sasaran,
                limit=requested_target,
                on_progress=on_progress,
                keep_check=_nilai_rentang,
                sort_by=sort_by,
                scan_limit=requested_scan_limit,
                time_limit_seconds=time_limit_seconds,
            )
            result["metadata"] = dict(self.client.last_metadata)
            result["metadata"]["date_from"] = (
                date_from.isoformat() if date_from else None
            )
            result["metadata"]["date_to"] = date_to.isoformat() if date_to else None
            result["metadata"]["sort_forced_to_newest"] = sort_dipaksa
            result["metadata"]["max_reviews_to_collect"] = requested_target
            result["metadata"]["scan_limit"] = requested_scan_limit
            if (date_from is not None or date_to is not None) and not result[
                "metadata"
            ].get("sort_applied", False):
                result["metadata"]["range_warning"] = (
                    "Urutan terbaru gagal dipasang, sehingga hasil rentang "
                    "tanggal tidak dijamin lengkap."
                )
            result["total_fetched"] = len(raw_reviews)
            result["total_failed"] = int(
                result["metadata"].get("failed_review_cards", 0)
            )
            for raw_review in raw_reviews:
                try:
                    normalized = self.normalizer.normalize_review(
                        sasaran, raw_review
                    )
                    if not is_within_date_range(
                        normalized["review_time"], date_from, date_to
                    ):
                        result["total_skipped_out_of_range"] += 1
                        if self._is_older_than_range(
                            normalized["review_time"], date_from
                        ):
                            result["metadata"]["out_of_range_older"] = (
                                int(result["metadata"].get("out_of_range_older") or 0)
                                + 1
                            )
                        else:
                            result["metadata"]["out_of_range_newer"] = (
                                int(result["metadata"].get("out_of_range_newer") or 0)
                                + 1
                            )
                        continue
                    _, duplicate = self.competitor_review_service.insert_review(
                        sasaran.id, normalized
                    )
                    if duplicate:
                        result["total_duplicate"] += 1
                    else:
                        result["total_inserted"] += 1
                except Exception as exc:
                    result["total_failed"] += 1
                    logger.exception(
                        "Failed to store one competitor review: %s", exc
                    )
            tersimpan = result["total_inserted"] + result["total_duplicate"]
            partial = (
                (
                    tersimpan < requested_target
                    and result["total_skipped_out_of_range"] == 0
                )
                or result["total_failed"] > 0
            )
            result["status"] = "partial_success" if partial else "success"
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            logger.exception(
                "Selenium competitor fetch failed for %s", sasaran.branch_name
            )
        return result

    def validate_target(self, target: object) -> int:
        try:
            value = int(target)
        except (TypeError, ValueError) as exc:
            raise ValueError("Target review count must be numeric.") from exc
        maximum = min(self.settings.selenium_max_target_reviews, 300)
        if self.company_id is not None:
            quota = EntitlementService(self.company_id, self.session_factory).review_quota()
            if quota > 0:
                maximum = min(maximum, quota)
        if not 1 <= value <= maximum:
            raise ValueError(
                f"Target review count must be between 1 and {maximum}."
            )
        return value

    @staticmethod
    def _is_older_than_range(
        review_time: datetime | None, date_from: datetime | None
    ) -> bool:
        if review_time is None or date_from is None:
            return False
        try:
            return review_time < date_from
        except TypeError:
            return False

    @staticmethod
    def validate_scan_limit(scan_limit: object, target: int) -> int:
        if scan_limit is None:
            return target
        try:
            value = int(scan_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("Scan limit must be numeric.") from exc
        if value < target:
            return target
        return min(value, 5000)
