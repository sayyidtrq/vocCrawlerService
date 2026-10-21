"""Score a taxonomy on hand-labelled reviews (Phase 5 packs, multi-label tagging).

Input CSV columns: ``review_text``, ``expected_slug`` and optionally ``expected_tags``
(slugs joined by ``|``) and ``rating``. The snapshot is one OneBox taxonomy body, or the
golden worklist fixture plus ``--key``. Prints per-aspect precision/recall, the share of
``lainnya``, the corrected rate and, when tags are labelled, the tag metrics that set the
per-aspect thresholds.

    python -m scripts.eval_taxonomy labelled.csv --taxonomy snapshot.json --provider jev
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_snapshot(path: str, key: str | None = None) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "taxonomies" in data:
        if key is None:
            raise SystemExit("--key is required when the file holds several taxonomies.")
        return data["taxonomies"][key]
    return data


def read_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            tags = {t for t in (raw.get("expected_tags") or "").split("|") if t.strip()}
            rating = (raw.get("rating") or "").strip()
            rows.append(
                {
                    "review_text": raw["review_text"],
                    "expected_slug": raw["expected_slug"].strip(),
                    "expected_tags": tags,
                    "rating": int(rating) if rating.isdigit() else None,
                }
            )
        return rows


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def per_aspect(pairs: list[tuple[set, set]]) -> dict:
    """pairs: (expected slugs, predicted slugs) per review -> precision/recall per slug."""
    tp: Counter = Counter()
    predicted: Counter = Counter()
    expected: Counter = Counter()
    for want, got in pairs:
        for slug in want:
            expected[slug] += 1
        for slug in got:
            predicted[slug] += 1
        for slug in want & got:
            tp[slug] += 1
    return {
        slug: {
            "support": expected[slug],
            "predicted": predicted[slug],
            "precision": _ratio(tp[slug], predicted[slug]),
            "recall": _ratio(tp[slug], expected[slug]),
        }
        for slug in sorted(set(expected) | set(predicted))
    }


def evaluate(results: list[dict], fallback: str = "lainnya") -> dict:
    """results: one dict per review with expected_slug, expected_tags, predicted_slug,
    predicted_tags (ranked list of slugs) and corrected."""
    total = len(results)
    primary = per_aspect([({r["expected_slug"]}, {r["predicted_slug"]}) for r in results])
    report = {
        "reviews": total,
        "primary_accuracy": _ratio(sum(r["expected_slug"] == r["predicted_slug"] for r in results), total),
        "fallback_share": _ratio(sum(r["predicted_slug"] == fallback for r in results), total),
        "corrected_rate": _ratio(sum(bool(r["corrected"]) for r in results), total),
        "per_aspect": primary,
    }
    labelled = [r for r in results if r["expected_tags"]]
    if labelled:
        over = [max(0, len(r["predicted_tags"]) - len(r["expected_tags"])) for r in labelled]
        report["tags"] = {
            "labelled": len(labelled),
            "per_aspect": per_aspect([(r["expected_tags"], set(r["predicted_tags"])) for r in labelled]),
            "over_tag_rate": round(sum(over) / len(labelled), 4),
            # how often the single-choice category is also the most likely tag
            "primary_is_top_tag": _ratio(
                sum(bool(r["predicted_tags"]) and r["predicted_tags"][0] == r["predicted_slug"] for r in labelled),
                len(labelled),
            ),
        }
    return report


def run(args: argparse.Namespace) -> dict:
    from app.config import get_settings
    from app.integrations.analysis_client import create_analysis_client
    from app.services.analysis_service import AnalysisService
    from app.services.taxonomy_service import Taxonomy

    snapshot = load_snapshot(args.taxonomy, args.key)
    if args.tagging:
        snapshot = {**snapshot, "tagging": {"enabled": True, "max_tags": args.max_tags, "thresholds": {}}}
    taxonomy = Taxonomy(snapshot)
    client = create_analysis_client(get_settings(), args.provider)

    results = []
    for row in read_rows(args.csv):
        raw = client.analyze_review(
            {"review_text": row["review_text"], "rating": row["rating"], "taxonomy": snapshot}
        )
        cleaned, corrected = AnalysisService._validate_result(raw, taxonomy)
        results.append(
            {
                **row,
                "predicted_slug": cleaned["issue_category"],
                "predicted_tags": [t["slug"] for t in cleaned.get("tags") or []],
                "corrected": corrected,
            }
        )
    return evaluate(results, taxonomy.fallback)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("csv", help="labelled reviews")
    parser.add_argument("--taxonomy", required=True, help="snapshot JSON (or worklist fixture with --key)")
    parser.add_argument("--key", help="taxonomy key inside a worklist fixture")
    parser.add_argument("--provider", choices=["jev", "openai", "absa"], default=None)
    parser.add_argument("--tagging", action="store_true", help="also score multi-label tags")
    parser.add_argument("--max-tags", type=int, default=5)
    return parser


def main() -> None:
    print(json.dumps(run(build_parser().parse_args()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
