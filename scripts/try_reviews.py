"""Run example positive, negative and mixed reviews through the real analysis and show what comes out.

Uses the taxonomy OneBox sent (the newest snapshot of the company) and the provider the server is
configured with, exactly as the worker would. Nothing is written to the database; every example costs
a few thousand AI tokens. Exit code 1 when any expectation fails (it is a smoke test: models vary).

    docker compose exec -T api python -m scripts.try_reviews                  # all examples
    docker compose exec -T api python -m scripts.try_reviews --list           # names only, no AI call
    docker compose exec -T api python -m scripts.try_reviews --only campuran  # examples whose name matches
    docker compose exec -T api python -m scripts.try_reviews --text "Dokter ramah tapi parkir penuh" --rating 3
    options: --company-id N  --key kesehatan:0e20266e  --provider jev|absa|openai  --tagging (force multi-tag on)
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    """One review and what a good analysis says about it. Tags are matched by any of the listed slugs."""

    name: str
    rating: int
    text: str
    sentiment: tuple[str, ...]  # acceptable overall sentiments
    tags: tuple[tuple[tuple[str, ...], str], ...] = ()  # ((acceptable slugs), sentiment about that aspect)
    flags: tuple[str, ...] = ()  # risk flags that must be raised
    none_negative: bool = False  # a pure compliment must not carry a negative tag


# Written for the Kesehatan pack (hospital reviews); use --text for other industries.
EXAMPLES: tuple[Example, ...] = (
    Example(
        "Positif: dokter, perawat, kebersihan", 5,
        "Dokternya ramah dan menjelaskan dengan sangat jelas, perawatnya sigap dan sabar, ruangannya bersih sekali. Terima kasih RS Hermina!",
        ("positive",),
        ((("pelayanan_dokter",), "positive"), (("pelayanan_perawat",), "positive"), (("kebersihan",), "positive")),
        none_negative=True,
    ),
    Example(
        "Positif: pujian singkat", 5,
        "Pelayanan memuaskan, terima kasih.",
        ("positive",),
        ((("pujian_umum", "kualitas_layanan", "pelayanan_petugas"), "positive"),),
        none_negative=True,
    ),
    Example(
        "Negatif: antre, administrasi, parkir", 1,
        "Antre pendaftaran lebih dari dua jam, petugas administrasinya judes, dan parkirnya penuh. Sangat mengecewakan.",
        ("negative",),
        ((("waktu_tunggu",), "negative"), (("administrasi", "pelayanan_petugas"), "negative"), (("parkir",), "negative")),
    ),
    Example(
        "Campuran: dokter bagus, parkir buruk", 3,
        "Dokternya bagus dan sabar menjelaskan, tapi parkirnya penuh dan harus muter lama cari tempat.",
        ("mixed",),
        ((("pelayanan_dokter",), "positive"), (("parkir",), "negative")),
    ),
    Example(
        "Campuran: apotek cepat, tagihan keliru", 2,
        "Obat di apotek lengkap dan cepat, tapi tagihan kamar tidak sesuai estimasi dan kasirnya tidak ramah.",
        ("mixed",),
        ((("farmasi",), "positive"), (("tagihan_pembayaran",), "negative")),
    ),
    Example(
        "Negatif berat: salah obat, mau viral", 1,
        "Anak saya salah diberi obat oleh perawat dan hampir celaka. Akan saya viralkan di media sosial!",
        ("negative",),
        ((("pelayanan_perawat", "farmasi", "keamanan"), "negative"),),
        flags=("keselamatan_pasien", "risiko_viral"),
    ),
    Example(
        "Campuran (English): IGD lama, perawat baik", 3,
        "The ER wait was very long, but the nurses were kind and caring.",
        ("mixed",),
        ((("igd", "waktu_tunggu"), "negative"), (("pelayanan_perawat",), "positive")),
    ),
)


def judge(example: Example, cleaned: dict) -> list[tuple[bool, str]]:
    """Every expectation of one example against the analysis, as (passed, message)."""
    checks = []
    sentiment = cleaned.get("sentiment")
    checks.append((sentiment in example.sentiment, f"overall sentiment {' or '.join(example.sentiment)} (got {sentiment})"))
    tags = {tag["slug"]: tag.get("sentiment") for tag in cleaned.get("tags") or []}
    for slugs, want in example.tags:
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
    if example.none_negative:
        negative = [slug for slug, got in tags.items() if got == "negative"]
        checks.append((not negative, "no negative tag on a compliment" + (f" (got {', '.join(negative)})" if negative else "")))
    return checks


def pick_snapshot(session_factory, company_id: int | None, key: str | None):
    """Newest stored taxonomy (optionally of one company / one key) as (key, body), or None."""
    from sqlalchemy import select

    from app.db.models import TaxonomySnapshot

    statement = select(TaxonomySnapshot).order_by(TaxonomySnapshot.received_at.desc(), TaxonomySnapshot.id.desc())
    if company_id is not None:
        statement = statement.where(TaxonomySnapshot.company_id == company_id)
    if key:
        statement = statement.where(TaxonomySnapshot.key == key)
    with session_factory() as session:
        row = session.scalars(statement.limit(1)).first()
        return (row.key, dict(row.body)) if row else None


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
    parser.add_argument("--provider", choices=["jev", "absa", "openai"], default=None, help="default: the server's ANALYSIS_PROVIDER")
    parser.add_argument("--tagging", action="store_true", help="force multi-tag on even if OneBox has it off")
    parser.add_argument("--only", help="run only the examples whose name contains this (case-insensitive)")
    parser.add_argument("--list", action="store_true", help="show the examples and exit")
    parser.add_argument("--text", help="analyse this one review instead of the examples (no expectations)")
    parser.add_argument("--rating", type=int, default=None, help="rating for --text")
    return parser


def main(argv=None, *, client=None, session_factory=None, out=print) -> int:
    args = build_parser().parse_args(argv)
    examples = [e for e in EXAMPLES if not args.only or args.only.lower() in e.name.lower()]
    if args.list:
        for number, example in enumerate(EXAMPLES, 1):
            out(f"{number}. {example.name}  (rating {example.rating})\n   {example.text}")
        return 0
    if not args.text and not examples:
        out(f"No example matches --only {args.only!r}. Use --list.")
        return 2

    if session_factory is None:
        from app.db.session import get_session_factory

        session_factory = get_session_factory()
    company_id = args.company_id
    if company_id is None and client is None:
        from app.config import get_settings

        company_id = get_settings().onebox_company_id
    picked = pick_snapshot(session_factory, company_id, args.key) or (
        pick_snapshot(session_factory, None, args.key) if args.company_id is None else None
    )
    if picked is None:
        out("No taxonomy is stored for that company/key. In OneBox turn on 'Taksonomi industri aktif' (Setup Parameter > "
            "Alur Tindak Lanjut > Industri Site), Simpan, then run: python -m scripts.refresh_worklist --company-id N")
        return 2
    key, body = picked
    if args.tagging:
        body = {**body, "tagging": {"enabled": True, "max_tags": (body.get("tagging") or {}).get("max_tags") or 5, "thresholds": {}}}
    tagging_on = bool((body.get("tagging") or {}).get("enabled"))
    out(f"taxonomy {key} (industry {body.get('industry')}), multi-tag {'ON' if tagging_on else 'OFF (use --tagging to force it on)'}")
    if body.get("industry") != "kesehatan" and not args.text:
        out("note: the built-in examples are hospital reviews; for this industry try --text.")

    if client is None:
        from app.config import get_settings
        from app.integrations.analysis_client import create_analysis_client

        client = create_analysis_client(get_settings(), args.provider)
    out(f"provider: {getattr(client, 'model_name', type(client).__name__)}")

    failed = checked = total_tokens = 0
    cases = [("Your text", args.rating, args.text, None)] if args.text else [(e.name, e.rating, e.text, e) for e in examples]
    for number, (name, rating, text, example) in enumerate(cases, 1):
        cleaned, usage, seconds = analyse(client, body, rating, text)
        checks = judge(example, cleaned) if example else []
        checked += len(checks)
        failed += sum(1 for ok, _ in checks if not ok)
        total_tokens += int(usage.get("total_tokens") or 0)
        render(number, len(cases), name, rating, text, cleaned, usage, seconds, checks, out)

    if not args.text:
        out(f"\n{checked - failed}/{checked} expectations met across {len(cases)} reviews, {total_tokens} tokens.")
        out("A model can answer differently each run: a lone FAIL is worth a second run before it is worth a fix.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
