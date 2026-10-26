"""Score reply suggestion on hand-labelled reviews: preset precision/coverage and safety recall.

Input CSV columns: ``review_text``, ``expected_preset`` (a preset id, or ``none``) and
``critical`` (``1`` when the review must be escalated, e.g. a medical error). Presets come
from a JSON list of ``{id, when_to_use}``; the pack's risk flags from the taxonomy snapshot.
Targets from the plan: precision >= 0.90 at the chosen threshold and safety recall = 1.0
(a single missed critical review blocks the generated path).

    python -m scripts.eval_reply labelled.csv --taxonomy snapshot.json --presets presets.json --threshold 0.75
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.eval_taxonomy import load_snapshot


def read_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [
            {
                "review_text": raw["review_text"],
                "expected_preset": raw["expected_preset"].strip() or "none",
                "critical": (raw.get("critical") or "").strip() in {"1", "true", "yes"},
            }
            for raw in csv.DictReader(handle)
        ]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def evaluate(results: list[dict]) -> dict:
    """results: expected_preset, critical, mode, preset_id, tokens_used per review."""
    answered = [r for r in results if r["mode"] == "preset"]
    labelled = [r for r in results if r["expected_preset"] != "none" and not r["critical"]]
    critical = [r for r in results if r["critical"]]
    return {
        "reviews": len(results),
        # of the replies we would offer, how many were the right preset
        "preset_precision": _ratio(sum(r["preset_id"] == r["expected_preset"] for r in answered), len(answered)),
        # of the reviews that have a right preset, how many we answered correctly
        "coverage": _ratio(sum(r["mode"] == "preset" and r["preset_id"] == r["expected_preset"] for r in labelled), len(labelled)),
        "answered_share": _ratio(len(answered), len(results)),
        "safety_recall": _ratio(sum(r["mode"] == "escalate" for r in critical), len(critical)),
        # an offered preset on a review labelled "none"/critical is the costly mistake
        "wrongly_offered": sum(
            r["mode"] == "preset" and (r["critical"] or r["expected_preset"] == "none") for r in results
        ),
        "tokens_total": sum(int(r.get("tokens_used") or 0) for r in results),
    }


def run(args: argparse.Namespace) -> dict:
    from app.config import get_settings
    from app.integrations.analysis_client import create_analysis_client
    from app.services.reply_suggestion_service import decide
    from app.services.taxonomy_service import Taxonomy

    taxonomy = Taxonomy(load_snapshot(args.taxonomy, args.key))
    presets = json.loads(Path(args.presets).read_text(encoding="utf-8"))
    client = create_analysis_client(get_settings(), "jev")

    results = []
    for row in read_rows(args.csv):
        answer = client.suggest_reply(row["review_text"], presets, taxonomy.risk_flags)
        out = decide(answer, taxonomy, presets, args.threshold, model=getattr(client, "model_name", None))
        results.append({**row, "mode": out["mode"], "preset_id": out.get("preset_id"), "tokens_used": out["tokens_used"]})
    return evaluate(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("csv", help="labelled reviews")
    parser.add_argument("--taxonomy", required=True, help="snapshot JSON (or worklist fixture with --key)")
    parser.add_argument("--key", help="taxonomy key inside a worklist fixture")
    parser.add_argument("--presets", required=True, help="JSON list of {id, when_to_use}")
    parser.add_argument("--threshold", type=float, default=0.75)
    return parser


def main() -> None:
    print(json.dumps(run(build_parser().parse_args()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
