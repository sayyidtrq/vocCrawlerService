"""Run example positive, negative and mixed reviews through the real analysis and show what comes out.

Uses the taxonomy OneBox sent (the newest snapshot of the company) and the provider the server is
configured with, exactly as the worker would. Nothing is written to the database; every example costs
a few thousand AI tokens. Exit code 1 when any expectation fails (it is a smoke test: models vary).

    docker compose exec -T api python -m scripts.try_reviews                  # examples of the stored taxonomy's industry
    docker compose exec -T api python -m scripts.try_reviews --industry spbu  # another industry (built-in catalog copy if OneBox sent none)
    docker compose exec -T api python -m scripts.try_reviews --all-industries # every industry's examples (about 30 reviews)
    docker compose exec -T api python -m scripts.try_reviews --list           # names only, no AI call
    docker compose exec -T api python -m scripts.try_reviews --only campuran  # examples whose name matches
    docker compose exec -T api python -m scripts.try_reviews --text "Dokter ramah tapi parkir penuh" --rating 3
    options: --company-id N  --key kesehatan:0e20266e  --provider jev|absa|openai  --tagging (force multi-tag on)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from scripts.try_examples import REVIEW_EXAMPLES, Example, ReplyExample  # noqa: F401  (re-exported for the tests)

EXAMPLES = REVIEW_EXAMPLES["kesehatan"]
DATA = Path(__file__).resolve().parent / "data" / "industries.json"


def builtin_industries() -> dict:
    """OneBox's industry catalog as of the last copy (scripts/data/industries.json): snapshot + reply presets."""
    return json.loads(DATA.read_text(encoding="utf-8"))["industries"]


def judge(example: Example, cleaned: dict, check_tags: bool = True) -> list[tuple[bool, str]]:
    """Every expectation of one example against the analysis, as (passed, message).

    check_tags=False (multi-tag is off, so no tags can exist) skips the tag expectations only."""
    checks = []
    sentiment = cleaned.get("sentiment")
    checks.append((sentiment in example.sentiment, f"overall sentiment {' or '.join(example.sentiment)} (got {sentiment})"))
    tags = {tag["slug"]: tag.get("sentiment") for tag in cleaned.get("tags") or []}
    for slugs, want in example.tags if check_tags else ():
        hit = [(slug, tags[slug]) for slug in slugs if slug in tags]
        label = "/".join(slugs)
        if not hit:
            checks.append((False, f"{label} = {want} (got: not tagged; tags are {', '.join(tags) or 'none'})"))
        else:
            ok = any(got == want for _, got in hit)
            actual = ", ".join("%s=%s" % pair for pair in hit)
            checks.append((ok, f"{label} = {want}" + ("" if ok else f" (got {actual})")))
    for flag in example.flags:
        raised = (cleaned.get("risk_flags") or {}).get(flag) is True
        checks.append((raised, f"risk flag {flag} raised" + ("" if raised else " (it was not)")))
    if example.none_negative and check_tags:
        negative = [slug for slug, got in tags.items() if got == "negative"]
        checks.append((not negative, "no negative tag on a compliment" + (f" (got {', '.join(negative)})" if negative else "")))
    return checks


def pick_snapshot(session_factory, company_id: int | None, key: str | None, industry: str | None = None):
    """Newest stored taxonomy (optionally of one company / key / industry) as (key, body), or None."""
    from sqlalchemy import select

    from app.db.models import TaxonomySnapshot

    statement = select(TaxonomySnapshot).order_by(TaxonomySnapshot.received_at.desc(), TaxonomySnapshot.id.desc())
    if company_id is not None:
        statement = statement.where(TaxonomySnapshot.company_id == company_id)
    if key:
        statement = statement.where(TaxonomySnapshot.key == key)
    with session_factory() as session:
        for row in session.scalars(statement):
            if industry is None or (row.body or {}).get("industry") == industry:
                return row.key, dict(row.body)
    return None


def resolve_taxonomy(session_factory, company_id, explicit_company: bool, key, industry):
    """(key, body, source) from what OneBox sent, else the built-in catalog copy for a named industry; or None."""
    stored = pick_snapshot(session_factory, company_id, key, industry) or (
        None if explicit_company else pick_snapshot(session_factory, None, key, industry)
    )
    if stored:
        return stored[0], stored[1], "stored"
    built = builtin_industries().get(industry) if industry and not key else None
    return (built["snapshot"]["key"], dict(built["snapshot"]), "built-in") if built else None


def with_tagging(body: dict, force: bool) -> dict:
    if not force:
        return body
    return {**body, "tagging": {"enabled": True, "max_tags": (body.get("tagging") or {}).get("max_tags") or 5, "thresholds": {}}}


def analyse(client, body: dict, rating: int | None, text: str) -> tuple[dict, dict, float]:
    """The raw model answer cleaned the way AnalysisService stores it, plus token usage and seconds."""
    from app.services.analysis_service import AnalysisService
    from app.services.taxonomy_service import Taxonomy

    started = time.time()
    raw = client.analyze_review({"review_text": text, "rating": rating, "taxonomy": body})
    cleaned, _ = AnalysisService._validate_result(raw, Taxonomy(body))
    return cleaned, dict(getattr(client, "last_usage", None) or {}), time.time() - started


def _tag_text(tag: dict) -> str:
    probability = "" if tag.get("p") is None else " (%.2f)" % tag["p"]
    return "%s%s %s" % (tag["slug"], probability, tag.get("sentiment"))


def render(index: int, total: int, name: str, rating: int | None, text: str, cleaned: dict, usage: dict, seconds: float,
           checks: list[tuple[bool, str]], out) -> None:
    out(f"\n== {index}/{total}  {name}   (rating {rating if rating is not None else '-'})")
    out(f'   "{text}"')
    out(f"   sentiment : {cleaned.get('sentiment')} ({cleaned.get('sentiment_score'):.2f})   category: {cleaned.get('issue_category')}   urgency: {cleaned.get('urgency')}")
    flags = cleaned.get("risk_flags")
    out("   risk flags: " + ("  ".join(f"{slug}={'YES' if on else 'no'}" for slug, on in flags.items()) if flags else "(none in this taxonomy)"))
    tags = cleaned.get("tags")
    if tags is None:
        out("   tags      : (multi-tag is off for this taxonomy)")
    else:
        out("   tags      : " + " | ".join(_tag_text(tag) for tag in tags))
    for ok, message in checks:
        out(f"   {'ok  ' if ok else 'FAIL'}  {message}")
    out(f"   usage     : {usage.get('total_tokens', '?')} tokens, {seconds:.1f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--company-id", type=int, default=None, help="default: ONEBOX_COMPANY_ID, else any company")
    parser.add_argument("--key", help="taxonomy key, e.g. kesehatan:0e20266e (default: the newest stored)")
    parser.add_argument("--industry", choices=sorted(REVIEW_EXAMPLES), help="examples of this industry (built-in catalog copy if OneBox sent none)")
    parser.add_argument("--all-industries", action="store_true", help="run the examples of every industry")
    parser.add_argument("--provider", choices=["jev", "absa", "openai"], default=None, help="default: the server's ANALYSIS_PROVIDER")
    parser.add_argument("--tagging", action="store_true", help="force multi-tag on even if OneBox has it off")
    parser.add_argument("--only", help="run only the examples whose name contains this (case-insensitive)")
    parser.add_argument("--list", action="store_true", help="show the examples and exit")
    parser.add_argument("--text", help="analyse this one review instead of the examples (no expectations)")
    parser.add_argument("--rating", type=int, default=None, help="rating for --text")
    return parser


def run_set(client, body: dict, examples, text, rating, out, header: str) -> tuple[int, int, int]:
    """Analyse one taxonomy's examples (or one free text). Returns (failed, checked, tokens)."""
    out(header)
    tagging_on = bool((body.get("tagging") or {}).get("enabled"))
    if not tagging_on and not text:
        out("multi-tag is off, so tag expectations are skipped (sentiment and risk flags are still checked); add --tagging to check tags too.")
    cases = [("Your text", rating, text, None)] if text else [(e.name, e.rating, e.text, e) for e in examples]
    failed = checked = tokens = 0
    for number, (name, case_rating, case_text, example) in enumerate(cases, 1):
        cleaned, usage, seconds = analyse(client, body, case_rating, case_text)
        checks = judge(example, cleaned, check_tags=tagging_on) if example else []
        checked += len(checks)
        failed += sum(1 for ok, _ in checks if not ok)
        tokens += int(usage.get("total_tokens") or 0)
        render(number, len(cases), name, case_rating, case_text, cleaned, usage, seconds, checks, out)
    return failed, checked, tokens


def main(argv=None, *, client=None, session_factory=None, out=print) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        for industry, examples in REVIEW_EXAMPLES.items():
            out(f"[{industry}]")
            for number, example in enumerate(examples, 1):
                out(f"{number}. {example.name}  (rating {example.rating})\n   {example.text}")
        return 0

    if session_factory is None:
        from app.db.session import get_session_factory

        session_factory = get_session_factory()
    company_id = args.company_id
    if company_id is None and client is None:
        from app.config import get_settings

        company_id = get_settings().onebox_company_id

    industries = list(REVIEW_EXAMPLES) if args.all_industries else [args.industry]
    plan = []
    for industry in industries:
        resolved = resolve_taxonomy(session_factory, company_id, args.company_id is not None, args.key, industry)
        if resolved is None:
            out(f"No taxonomy found{f' for industry {industry}' if industry else ''}. In OneBox turn on 'Taksonomi industri aktif' "
                "(Setup Parameter > Alur Tindak Lanjut > Industri Site), Simpan, then run: python -m scripts.refresh_worklist --company-id N")
            return 2
        plan.append(resolved)

    if client is None:
        from app.config import get_settings
        from app.integrations.analysis_client import create_analysis_client

        client = create_analysis_client(get_settings(), args.provider)
    out(f"provider: {getattr(client, 'model_name', type(client).__name__)}")

    failed = checked = tokens = reviews = 0
    for key, body, source in plan:
        body = with_tagging(body, args.tagging or source == "built-in")
        tagging_on = bool((body.get("tagging") or {}).get("enabled"))
        industry = body.get("industry")
        examples = [e for e in REVIEW_EXAMPLES.get(industry, ()) if not args.only or args.only.lower() in e.name.lower()]
        header = (f"\n##### {key} (industry {industry}, {'sent by OneBox' if source == 'stored' else 'built-in catalog copy: OneBox has not sent this industry'}), "
                  f"multi-tag {'ON' if tagging_on else 'OFF (use --tagging to force it on)'}")
        if not args.text and not examples:
            out(header + ("\nNo example of this industry matches --only." if args.only else f"\nNo built-in examples for {industry}; use --text."))
            if not args.all_industries:
                return 2
            continue
        f, c, t = run_set(client, body, examples, args.text, args.rating, out, header)
        failed, checked, tokens, reviews = failed + f, checked + c, tokens + t, reviews + (1 if args.text else len(examples))
        if args.text:
            break

    if not args.text:
        out(f"\n{checked - failed}/{checked} expectations met across {reviews} reviews, {tokens} tokens.")
        out("A model can answer differently each run: a lone FAIL is worth a second run before it is worth a fix.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
