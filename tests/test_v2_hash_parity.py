"""A v2 crawl must give a review the same review_hash v1 gave it, or OneBox would import duplicates on the switch."""

from types import SimpleNamespace

import pytest

from app.integrations.apify_review_parser import ApifyReviewParser
from app.services.fetch_service import FetchService
from app.services.stateless_crawl_service import StatelessCrawlService
from tests.test_v2_crawls import actor_item

PLACE = "ChIJparity"
CASES = {
    "iso time and owner reply": {},
    "relative time only": {"reviewed_at_date": None, "reviewed_at": "3 weeks ago"},
    "no text and no name": {"content": "", "reviewer_name": None},
    "rating as a string": {"rating": "4"},
    "time with an offset": {"reviewed_at_date": "2026-10-02T07:00:00+07:00"},
    "edited review": {"edited_at": "2026-10-05T01:00:00Z", "is_edited": True},
    "unicode and odd spaces": {"content": "Antre   lama sekali  \U0001F621"},
}


@pytest.mark.parametrize("changes", CASES.values(), ids=CASES.keys())
def test_v2_review_hash_equals_the_v1_review_hash(changes):
    item = actor_item(1, **changes)
    v1_self = SimpleNamespace(
        settings=SimpleNamespace(review_source_mode="apify_google_maps"),
        _resolve_review_time=FetchService._resolve_review_time,
    )
    v1 = FetchService.normalize_review(
        v1_self, SimpleNamespace(id=1, external_place_id=PLACE), ApifyReviewParser.parse_review(item)
    )
    v2 = StatelessCrawlService._normalize_review(item, PLACE)
    assert v1["review_hash"] == v2["review_hash"]
