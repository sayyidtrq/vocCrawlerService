"""Run example reviews through the real reply suggestion and show which preset (or escalation) comes out.

Same call and same decision rules as the /reply-suggestion endpoint: Jev picks one of the industry's prepared
reply presets (the ids and when-to-use lines OneBox offers; copied in scripts/data/industries.json), the
pack's risk flags are asked in the same request, and a critical flag always means escalate. Nothing is written
to the database; each example costs a few hundred AI tokens. Exit code 1 when any expectation fails.

    docker compose exec -T api python -m scripts.try_replies                    # examples of the stored taxonomy's industry
    docker compose exec -T api python -m scripts.try_replies --industry spbu    # another industry (built-in catalog copy if OneBox sent none)
    docker compose exec -T api python -m scripts.try_replies --all-industries
    docker compose exec -T api python -m scripts.try_replies --list
    docker compose exec -T api python -m scripts.try_replies --text "Antre lama sekali" --threshold 0.6
    options: --company-id N  --key kesehatan:0e20266e  --only pujian  --threshold 0.75

Only the Jev provider can answer this (set ANALYSIS_PROVIDER=jev or pass --provider jev).
"""

from __future__ import annotations

import argparse
import sys
import time

from scripts.try_examples import REPLY_EXAMPLES, ReplyExample
from scripts.try_reviews import builtin_industries, resolve_taxonomy

DEFAULT_THRESHOLD = 0.75


def judge(example: ReplyExample, decision: dict) -> list[tuple[bool, str]]:
    """Every expectation of one example against the decision, as (passed, message)."""
    mode = decision.get("mode")
    checks = [(mode == example.mode, f"mode {example.mode} (got {mode})")]
    if example.mode == "preset":
        wanted = " or ".join(example.presets)
        got = decision.get("preset_id")
        checks.append((mode == "preset" and got in example.presets, f"preset {wanted} (got {got})"))
    for flag in example.flags:
        raised = (decision.get("risk_flags") or {}).get(flag) is True
        checks.append((raised, f"risk flag {flag} raised" + ("" if raised else " (it was not)")))
    return checks


def offered_presets(industry: str) -> list[dict]:
    """What OneBox offers the Crawler: the industry's presets without the escalation preset."""
    reply = builtin_industries()[industry]["reply"]
    return [dict(p) for p in reply["presets"] if p["id"] != reply["escalation_preset"]]


def suggest(client, taxonomy, presets: list[dict], text: str, threshold: float) -> tuple[dict, dict, float]:
    from app.services.reply_suggestion_service import decide

    started = time.time()
    answer = client.suggest_reply(text, presets, taxonomy.risk_flags)
    decision = decide(answer, taxonomy, presets, threshold, model=getattr(client, "model_name", None))
    return decision, answer, time.time() - started


def render(index: int, total: int, name: str, text: str, decision: dict, seconds: float, checks: list[tuple[bool, str]], out) -> None:
    out(f"\n== {index}/{total}  {name}")
    out(f'   "{text}"')
    confidence = decision.get("confidence")
    out(f"   decision  : {decision.get('mode')}   preset: {decision.get('preset_id') or '-'}   "
        f"confidence: {'-' if confidence is None else '%.2f' % confidence}   language: {decision.get('language') or '-'}")
    flags = decision.get("risk_flags")
    out("   risk flags: " + ("  ".join(f"{slug}={'YES' if on else 'no'}" for slug, on in flags.items()) if flags else "(none)"))
    for ok, message in checks:
        out(f"   {'ok  ' if ok else 'FAIL'}  {message}")
    out(f"   usage     : {decision.get('tokens_used', '?')} tokens, {seconds:.1f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--company-id", type=int, default=None, help="default: ONEBOX_COMPANY_ID, else any company")
    parser.add_argument("--key", help="taxonomy key, e.g. kesehatan:0e20266e (default: the newest stored)")
    parser.add_argument("--industry", choices=sorted(REPLY_EXAMPLES), help="examples of this industry (built-in catalog copy if OneBox sent none)")
    parser.add_argument("--all-industries", action="store_true", help="run the examples of every industry")
    parser.add_argument("--provider", choices=["jev", "absa", "openai"], default="jev", help="only jev can suggest replies")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="minimum confidence to offer a preset (default 0.75)")
    parser.add_argument("--only", help="run only the examples whose name contains this (case-insensitive)")
    parser.add_argument("--list", action="store_true", help="show the examples and exit")
    parser.add_argument("--text", help="suggest a reply for this one review instead of the examples (no expectations)")
    return parser


def main(argv=None, *, client=None, session_factory=None, out=print) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        for industry, examples in REPLY_EXAMPLES.items():
            out(f"[{industry}]")
            for number, example in enumerate(examples, 1):
                expected = example.mode if example.mode != "preset" else "preset " + "/".join(example.presets)
                out(f"{number}. {example.name}  -> {expected}\n   {example.text}")
        return 0

    if session_factory is None:
        from app.db.session import get_session_factory

        session_factory = get_session_factory()
    company_id = args.company_id
    if company_id is None and client is None:
        from app.config import get_settings

        company_id = get_settings().onebox_company_id

    industries = list(REPLY_EXAMPLES) if args.all_industries else [args.industry]
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
    if not hasattr(client, "suggest_reply"):
        out("Reply suggestion needs the Jev provider (ANALYSIS_PROVIDER=jev or --provider jev).")
        return 2
    out(f"provider: {getattr(client, 'model_name', type(client).__name__)}   threshold: {args.threshold}")

    from app.services.taxonomy_service import Taxonomy

    failed = checked = tokens = reviews = 0
    for key, body, source in plan:
        industry = body.get("industry")
        if industry not in builtin_industries():
            out(f"\n##### {key}: no preset list is known for industry {industry}.")
            return 2
        presets = offered_presets(industry)
        taxonomy = Taxonomy(body)
        examples = [e for e in REPLY_EXAMPLES.get(industry, ()) if not args.only or args.only.lower() in e.name.lower()]
        out(f"\n##### {key} (industry {industry}, {'sent by OneBox' if source == 'stored' else 'built-in catalog copy: OneBox has not sent this industry'}), "
            f"{len(presets)} presets offered")
        if not args.text and not examples:
            out("No example of this industry matches --only." if args.only else f"No built-in examples for {industry}; use --text.")
            if not args.all_industries:
                return 2
            continue
        cases = [("Your text", args.text, None)] if args.text else [(e.name, e.text, e) for e in examples]
        for number, (name, text, example) in enumerate(cases, 1):
            decision, _, seconds = suggest(client, taxonomy, presets, text, args.threshold)
            checks = judge(example, decision) if example else []
            checked += len(checks)
            failed += sum(1 for ok, _ in checks if not ok)
            tokens += int(decision.get("tokens_used") or 0)
            reviews += 1
            render(number, len(cases), name, text, decision, seconds, checks, out)
        if args.text:
            break

    if not args.text:
        out(f"\n{checked - failed}/{checked} expectations met across {reviews} reviews, {tokens} tokens.")
        out("A model can answer differently each run: a lone FAIL is worth a second run before it is worth a fix.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
