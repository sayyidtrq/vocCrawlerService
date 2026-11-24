from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import Location, TaxonomySnapshot
from app.services.worklist_sync_service import WorklistSyncService


class FakeWorklistClient:
    def __init__(self, payload):
        self.payload = payload

    def get_worklist(self):
        return self.payload


def onebox_settings(settings, company_id):
    return settings.model_copy(
        update={
            "onebox_base_url": "http://onebox.test",
            "onebox_service_email": "voc@test.invalid",
            "onebox_service_password": "secret",
            "onebox_site_id": 169,
            "onebox_company_id": company_id,
        }
    )


def worklist(fixture, *, with_taxonomy=True):
    """The golden OneBox worklist made syncable: the fixture carries only the taxonomy fields."""
    items = []
    for item in fixture["data"]:
        full = {
            "kind": "location",
            "external_place_id": f"place-{item['onebox_location_id']}",
            "branch_name": f"Cabang {item['onebox_location_id']}",
            "active": True,
            "crawl_enabled": True,
            "ingest_reviews": True,
            **item,
        }
        if not with_taxonomy:
            full.pop("taxonomy_key", None)
        items.append(full)
    payload = {"meta": {"site_id": 169}, "data": items}
    if with_taxonomy:
        payload["taxonomies"] = fixture["taxonomies"]
    return payload


def sync(session_factory, settings, company_id, payload):
    service = WorklistSyncService(
        company_id=company_id,
        session_factory=session_factory,
        settings=onebox_settings(settings, company_id),
        client=FakeWorklistClient(payload),
    )
    assert service.refresh().status == "synced"


def locations(session_factory):
    with session_factory() as session:
        return {loc.onebox_location_id: loc for loc in session.scalars(select(Location))}


def test_worklist_with_taxonomies_sets_location_fields_and_stores_snapshots(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    sync(tx_session_factory, tx_settings, tx_company_id, worklist(tx_fixture))

    by_id = locations(tx_session_factory)
    assert by_id[11].taxonomy_key == "kesehatan:0e20266e" and by_id[11].taxonomy_version == "0e20266e"
    assert by_id[21].taxonomy_key == "spbu:6285c2fa" and by_id[21].taxonomy_version == "6285c2fa"
    with tx_session_factory() as session:
        assert session.scalar(select(func.count(TaxonomySnapshot.id))) == 2


def test_worklist_without_taxonomy_fields_changes_nothing(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    """An older OneBox (or a site with the flag off) sends neither key nor map."""
    sync(tx_session_factory, tx_settings, tx_company_id, worklist(tx_fixture, with_taxonomy=False))

    assert {loc.taxonomy_key for loc in locations(tx_session_factory).values()} == {None}
    with tx_session_factory() as session:
        assert session.scalar(select(func.count(TaxonomySnapshot.id))) == 0


def test_turning_the_flag_off_returns_locations_to_legacy_but_keeps_the_cache(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    sync(tx_session_factory, tx_settings, tx_company_id, worklist(tx_fixture))
    sync(tx_session_factory, tx_settings, tx_company_id, worklist(tx_fixture, with_taxonomy=False))

    loc = locations(tx_session_factory)[21]
    assert loc.taxonomy_key is None and loc.taxonomy_version is None
    with tx_session_factory() as session:
        assert session.scalar(select(func.count(TaxonomySnapshot.id))) == 2


def test_an_invalid_snapshot_never_fails_the_sync(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture
):
    payload = worklist(tx_fixture)
    payload["taxonomies"]["spbu:6285c2fa"] = {"aspects": []}

    sync(tx_session_factory, tx_settings, tx_company_id, payload)

    with tx_session_factory() as session:
        keys = set(session.scalars(select(TaxonomySnapshot.key)))
    assert keys == {"kesehatan:0e20266e"}
    # the location still names the key: analysis finds no snapshot and stays legacy
    assert locations(tx_session_factory)[21].taxonomy_key == "spbu:6285c2fa"


def test_a_resync_refreshes_the_snapshot_body(
    tx_session_factory, tx_settings, tx_company_id, tx_fixture, tx_tagged
):
    sync(tx_session_factory, tx_settings, tx_company_id, worklist(tx_fixture))
    payload = worklist(tx_fixture)
    payload["taxonomies"]["spbu:6285c2fa"] = tx_tagged(payload["taxonomies"]["spbu:6285c2fa"])

    sync(tx_session_factory, tx_settings, tx_company_id, payload)

    with tx_session_factory() as session:
        row = session.scalar(select(TaxonomySnapshot).where(TaxonomySnapshot.key == "spbu:6285c2fa"))
    assert row.body["tagging"]["enabled"] is True
