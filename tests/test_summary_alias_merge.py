from __future__ import annotations

from app.db.models import Company, Location, Review, ReviewAnalysis
from app.services.summary_repository import SummaryRepository
from app.services.taxonomy_service import upsert_snapshots


def seed(session_factory, company_id, categories):
    with session_factory() as session:
        location = Location(
            company_id=company_id, hospital_name="Org", branch_name="Cabang", source="onebox", external_place_id="p"
        )
        session.add(location)
        session.flush()
        for n, category in enumerate(categories):
            review = Review(
                company_id=company_id, location_id=location.id, source="google_maps",
                review_hash=f"h{n}", review_text="x", rating=3,
            )
            session.add(review)
            session.flush()
            session.add(ReviewAnalysis(review_id=review.id, sentiment="negative", issue_category=category))
        session.commit()
        return location.id


def test_legacy_and_canonical_slugs_add_up(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        upsert_snapshots(session, tx_company_id, tx_fixture["taxonomies"])
        session.commit()
    location_id = seed(
        tx_session_factory, tx_company_id,
        ["doctor_service", "doctor_service", "pelayanan_dokter", "waiting_time", "kebersihan"],
    )

    with tx_session_factory() as session:
        repo = SummaryRepository(session, tx_company_id)
        overall = dict(repo.top_issues())
        per_location = dict(repo.location_top_issues(location_id))

    assert overall["pelayanan_dokter"] == 3 and "doctor_service" not in overall
    assert overall["waktu_tunggu"] == 1 and overall["kebersihan"] == 1
    assert per_location == overall


def test_without_snapshots_the_counts_are_untouched(tx_session_factory, tx_company_id):
    seed(tx_session_factory, tx_company_id, ["doctor_service", "pelayanan_dokter", "doctor_service"])

    with tx_session_factory() as session:
        counts = dict(SummaryRepository(session, tx_company_id).top_issues())

    assert counts == {"doctor_service": 2, "pelayanan_dokter": 1}


def test_other_tenants_aliases_do_not_leak(tx_session_factory, tx_company_id, tx_fixture):
    with tx_session_factory() as session:
        other = Company(name="Other", ai_enable_flag=True)
        session.add(other)
        session.commit()
        upsert_snapshots(session, other.id, tx_fixture["taxonomies"])
        session.commit()
    seed(tx_session_factory, tx_company_id, ["doctor_service", "pelayanan_dokter"])

    with tx_session_factory() as session:
        counts = dict(SummaryRepository(session, tx_company_id).top_issues())

    assert counts == {"doctor_service": 1, "pelayanan_dokter": 1}
