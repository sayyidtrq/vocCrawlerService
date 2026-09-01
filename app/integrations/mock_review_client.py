from __future__ import annotations

from app.db.models import Location
from app.integrations.review_source_client import ReviewSourceClient


class MockReviewClient(ReviewSourceClient):
    def fetch_reviews(self, location: Location, limit: int = 50, **kwargs) -> list[dict]:
        place_id = location.external_place_id
        samples = [
            (
                "Andi Saputra",
                5,
                "Dokternya ramah dan penjelasannya mudah dimengerti.",
            ),
            (
                "Siti Rahma",
                5,
                "Perawat sangat sigap, sabar, dan membantu pasien.",
            ),
            (
                "Budi Santoso",
                2,
                "Antrean pendaftaran terlalu lama, hampir dua jam menunggu.",
            ),
            (
                "Nina Putri",
                2,
                "Petugas administrasi kurang responsif dan informasi tidak jelas.",
            ),
            (
                "Rizky Maulana",
                2,
                "Area parkir sempit dan sulit mendapat tempat saat jam ramai.",
            ),
            (
                "Dewi Lestari",
                3,
                "Pelayanan dokter baik tetapi antrean farmasi cukup lama.",
            ),
            (
                "Fajar Nugraha",
                5,
                "Rumah sakit bersih, toilet terawat, dan ruang tunggu nyaman.",
            ),
            (
                "Maya Kurnia",
                3,
                "Gedungnya bagus dan AC sejuk, tetapi lift sering penuh.",
            ),
            (
                "Agus Pratama",
                1,
                "Aplikasi booking gagal terus sehingga tetap harus daftar manual.",
            ),
            (
                "Lina Wati",
                5,
                "Secara keseluruhan pelayanan Hermina sangat memuaskan.",
            ),
        ]
        reviews = []
        for index, (reviewer, rating, text) in enumerate(samples, start=1):
            review_id = f"{place_id}-mock-{index:03d}"
            payload = {
                "mock": True,
                "id": review_id,
                "author": reviewer,
                "rating": rating,
                "text": text,
            }
            reviews.append(
                {
                    "source": "mock",
                    "external_place_id": place_id,
                    "external_review_id": review_id,
                    "reviewer_name": reviewer,
                    "rating": rating,
                    "review_text": text,
                    "review_time": f"2026-06-{20-index:02d}T09:00:00+07:00",
                    "language": "id",
                    "raw_payload": payload,
                }
            )
        return reviews[: max(0, limit)]
