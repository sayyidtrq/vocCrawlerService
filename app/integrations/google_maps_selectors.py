"""Google Maps selectors kept in one place for easy maintenance."""

REVIEW_CARD_SELECTORS = [
    "div[data-review-id]",
    "div.jftiEf",
    "div[data-reviewid]",
]

# Kontrol yang membuka daftar ulasan penuh dari panel tempat. Google Maps
# menghapus div[role='feed']; panel Ringkasan dan daftar ulasan kini berbagi
# kelas kontainer gulir yang sama, jadi 3-6 kartu pratinjau di Ringkasan BUKAN
# daftar ulasan. Satu-satunya pembeda yang bisa dipercaya adalah tab yang aktif,
# maka tab "Ulasan" didahulukan di sini. jsaction tombol kini berprefiks dinamis
# (pane.wfvdleNN...) sehingga hanya bentuk *= yang bertahan.
REVIEW_BUTTON_SELECTORS = [
    "button[role='tab'][aria-label^='Ulasan' i]",
    "button[role='tab'][aria-label^='Reviews' i]",
    "button[aria-label^='Ulasan lainnya' i]",
    "button[aria-label^='More reviews' i]",
    "button.uj73Ce",
    "button[role='tab'][aria-label*='ulasan' i]",
    "button[role='tab'][aria-label*='review' i]",
    "button[jsaction*='moreReviews']",
    "[role='button'][jsaction*='moreReviews']",
    "button[aria-label*='reviews' i]",
    "button[aria-label*='ulasan' i]",
    "[role='button'][aria-label*='reviews' i]",
    "[role='button'][aria-label*='ulasan' i]",
]

SCROLL_CONTAINER_SELECTORS = [
    "div[role='feed']",
    "div.m6QErb.DxyBCb.kA9KIf.dS8AEf",
    "div.m6QErb.DxyBCb.kA9KIf",
]

REVIEWER_NAME_SELECTORS = [
    ".d4r55",
    "button.WEBjve div",
    "[class*='d4r55']",
]

RATING_SELECTORS = [
    "span.kvMYJc",
    "span[role='img'][aria-label*='star' i]",
    "span[role='img'][aria-label*='bintang' i]",
]

REVIEW_TEXT_SELECTORS = [
    "span.wiI7pd",
    "div.MyEned span",
    "[data-expandable-section] span",
]

REVIEW_TIME_SELECTORS = [
    "span.rsqaWe",
    ".DU9Pgb span",
]

MORE_BUTTON_SELECTORS = [
    "button.w8nwRe",
    "button[jsaction*='expandReview']",
]

PROFILE_LINK_SELECTORS = [
    "a[href*='/maps/contrib/']",
    "button.WEBjve",
]

PHOTO_SELECTORS = [
    "img.NBa7we",
    "img[src*='googleusercontent']",
]

REVIEWER_META_SELECTORS = [
    "div.RfnDt",
    "div.TSUbDb",
]

LIKE_BUTTON_SELECTORS = [
    "button[jsaction*='review.vote']",
    "button[aria-label*='helpful' i]",
    "button[aria-label*='membantu' i]",
]

OWNER_RESPONSE_CONTAINER_SELECTORS = [
    "div.CDe7pd",
    "div.d6xFrb",
]

OWNER_RESPONSE_TEXT_SELECTORS = [
    "div.wiI7pd",
    "span.wiI7pd",
]

OWNER_RESPONSE_TIME_SELECTORS = [
    "span.DZSIDd",
    "span.rsqaWe",
]

SORT_BUTTON_SELECTORS = [
    "button[aria-label*='Urutkan ulasan' i]",
    "button[aria-label*='Sort reviews' i]",
    "button[data-value='Urutkan']",
    "button[data-value='Sort']",
]

PLACE_RATING_SNAPSHOT_SELECTORS = [
    "div.F7nice",
    "div.fontDisplayLarge",
    "button[jsaction*='pane.reviewChart.moreReviews']",
    "button[aria-label*='reviews' i]",
    "button[aria-label*='ulasan' i]",
]
