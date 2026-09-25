from __future__ import annotations

from app.integrations.gemini_client import GeminiClientBase


class MockGeminiClient(GeminiClientBase):
    model_name = "mock-gemini-v1"

    def analyze_review(self, review: dict) -> dict:
        text = (review.get("review_text") or "").lower()
        rating = review.get("rating")

        positive_words = {"baik", "ramah", "sigap", "bersih", "nyaman", "memuaskan"}
        negative_words = {
            "lama",
            "kurang",
            "sempit",
            "sulit",
            "gagal",
            "penuh",
            "tidak jelas",
        }
        has_positive = any(word in text for word in positive_words)
        has_negative = any(word in text for word in negative_words)

        if has_positive and has_negative:
            sentiment = "mixed"
            score = 0.72
        elif has_negative or (rating is not None and rating <= 2):
            sentiment = "negative"
            score = 0.86
        elif has_positive or (rating is not None and rating >= 4):
            sentiment = "positive"
            score = 0.9
        else:
            sentiment = "neutral"
            score = 0.62

        category_rules = [
            ("booking_system", ["booking", "aplikasi"]),
            ("waiting_time", ["antrean", "menunggu"]),
            ("administration", ["administrasi", "pendaftaran"]),
            ("pharmacy", ["farmasi", "obat"]),
            ("parking", ["parkir"]),
            ("cleanliness", ["bersih", "toilet"]),
            ("facility", ["gedung", "lift", "ac", "ruang tunggu"]),
            ("doctor_service", ["dokter"]),
            ("nurse_service", ["perawat"]),
        ]
        issue_category = "general_praise" if sentiment == "positive" else "other"
        for candidate, words in category_rules:
            if any(word in text for word in words):
                issue_category = candidate
                break

        safety_words = {
            "salah obat",
            "malpraktik",
            "darurat",
            "nyawa",
            "infeksi",
            "cedera",
            "bahaya",
            "celaka",
            "kecelakaan",
            "keracunan",
            "kebakaran",
        }
        viral_words = {"viral", "sebarkan", "media sosial"}
        patient_safety = any(word in text for word in safety_words)
        potential_viral = any(word in text for word in viral_words)
        if patient_safety:
            urgency = "critical"
        elif potential_viral or (rating == 1 and sentiment == "negative"):
            urgency = "high"
        elif sentiment in {"negative", "mixed"}:
            urgency = "medium"
        else:
            urgency = "low"

        keywords = [
            word
            for word in [
                "dokter",
                "perawat",
                "antrean",
                "administrasi",
                "parkir",
                "farmasi",
                "bersih",
                "lift",
                "booking",
            ]
            if word in text
        ][:5]

        if sentiment == "negative":
            summary = "Pelanggan menyampaikan keluhan yang memerlukan tindak lanjut."
        elif sentiment == "mixed":
            summary = "Pelanggan memberi apresiasi sekaligus menyampaikan kendala."
        elif sentiment == "positive":
            summary = "Pelanggan menyampaikan pengalaman pelayanan yang positif."
        else:
            summary = "Ulasan bersifat netral atau belum cukup spesifik."

        actions = {
            "waiting_time": "Evaluasi alur antrean dan kapasitas petugas pada jam ramai.",
            "administration": "Perjelas informasi dan tingkatkan respons petugas administrasi.",
            "pharmacy": "Tinjau proses antrean dan waktu layanan farmasi.",
            "parking": "Evaluasi kapasitas dan alur parkir pada jam ramai.",
            "booking_system": "Periksa keandalan aplikasi booking dan jalur bantuan pengguna.",
            "facility": "Periksa kapasitas dan pemeliharaan fasilitas yang dikeluhkan.",
        }

        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "issue_category": issue_category,
            "urgency": urgency,
            "summary": summary,
            "recommended_action": actions.get(
                issue_category,
                "Pertahankan mutu layanan dan pantau masukan serupa.",
            ),
            "keywords": keywords,
            "is_potential_viral": potential_viral,
            "is_patient_safety_issue": patient_safety,
        }

