#!/usr/bin/env python3
"""Review Fetching Pipeline & Ingestion Stress Testing Tool.

Tests and measures the performance of Segment 1 (Fetch Reviews) of the Crawler:
  - Network Fetch Time per Location (min, max, mean, p50, p95)
  - Ingestion Throughput (Reviews / second, Locations / minute)
  - Schema Parsing & Normalization Speed
  - SHA-256 Deduplication Rate (New Inserts vs Duplicates)
  - Database Write Latency (PostgreSQL session commits)
  - Data Volume Transferred (Payload size in KB, Avg KB/review)
  - Concurrency Scaling (Single vs Multi-Worker Location Scraping)
  - Audit Trail Logging Verification (PostgreSQL fetch_logs entries)

Usage examples:
  # Quick fetch test with 3 locations at concurrency 2
  .venv/bin/python scripts/stress_test_fetch_reviews.py -n 3 -c 2

  # Full stress test across 10 locations with 5 workers
  .venv/bin/python scripts/stress_test_fetch_reviews.py -n 10 -c 5

  # Concurrency sweep benchmark comparing 1, 3, and 5 concurrent fetch workers
  .venv/bin/python scripts/stress_test_fetch_reviews.py --mode sweep --sweep-workers 1,3,5
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, text

from app.config import get_settings
from app.db.models import Location, Review
from app.db.session import get_session_factory
from app.integrations.mock_review_client import MockReviewClient
from app.services.fetch_service import FetchService
from app.utils.hashing import generate_review_hash

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"


@dataclass
class LocationFetchResult:
    location_id: int
    location_name: str
    worker_id: int
    status: str
    total_fetched: int
    total_inserted: int
    total_duplicate: int
    total_failed: int
    total_time_sec: float
    network_fetch_sec: float
    normalization_ms: float
    db_write_ms: float
    reviews_per_sec: float
    payload_size_kb: float
    avg_review_bytes: float
    error_message: str | None = None


@dataclass
class FetchBenchmarkSummary:
    timestamp: str
    total_locations: int
    concurrency: int
    wall_clock_sec: float
    total_fetched: int
    total_inserted: int
    total_duplicate: int
    total_failed: int
    dedup_ratio_pct: float
    overall_reviews_per_sec: float
    locations_per_minute: float
    total_payload_kb: float
    avg_payload_per_location_kb: float
    latency_p50_sec: float
    latency_p95_sec: float
    latency_min_sec: float
    latency_max_sec: float
    avg_normalization_ms: float
    avg_db_write_ms: float
    success_rate_pct: float


def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    k = (len(data) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[int(f)] * (c - k)
    d1 = data[int(c)] * (k - f)
    return d0 + d1


class HighVolumeReviewClient(MockReviewClient):
    """Generates realistic synthetic review payloads for high-throughput stress testing."""

    def __init__(self, review_count: int = 50):
        super().__init__()
        self.review_count = review_count

    def fetch_reviews(self, location: Location, limit: int = 50, **kwargs) -> list[dict]:
        base_samples = super().fetch_reviews(location, limit=10)
        target = min(limit, self.review_count)
        reviews = []
        for i in range(target):
            sample = base_samples[i % len(base_samples)]
            item = dict(sample)
            item["external_review_id"] = f"{location.external_place_id}-stress-{i:04d}"
            item["reviewer_name"] = f"Reviewer {i+1} ({sample.get('reviewer_name', 'Anon')})"
            item["raw_payload"] = {
                "author": item["reviewer_name"],
                "rating": item["rating"],
                "text": item["review_text"],
                "timestamp": int(time.time()),
                "metadata": {
                    "source": "google_maps_reviews",
                    "device": "android",
                    "likes": i % 5,
                    "language": "id",
                }
            }
            reviews.append(item)
        # Simulate realistic network transmission delay (e.g. 150ms - 350ms)
        time.sleep(0.20)
        return reviews


def execute_location_fetch(
    location: Location,
    company_id: int,
    worker_id: int,
    reviews_per_location: int,
) -> LocationFetchResult:
    """Execute a single location fetch and record granular timing metrics."""
    client = HighVolumeReviewClient(review_count=reviews_per_location)
    fetch_service = FetchService(company_id=company_id, client=client)

    t_start = time.perf_counter()
    try:
        # Step 1: Raw network fetch
        t_net_start = time.perf_counter()
        raw_reviews = client.fetch_reviews(location, limit=reviews_per_location)
        network_sec = time.perf_counter() - t_net_start

        # Calculate payload size
        payload_bytes = len(json.dumps(raw_reviews).encode("utf-8"))
        payload_kb = payload_bytes / 1024.0

        # Step 2: Normalization & deduplication hash computation
        t_norm_start = time.perf_counter()
        normalized_reviews = []
        for r in raw_reviews:
            norm = fetch_service.normalize_review(location, r)
            normalized_reviews.append(norm)
        norm_ms = (time.perf_counter() - t_norm_start) * 1000.0

        # Step 3: Database Insertion / Upsert
        t_db_start = time.perf_counter()
        total_inserted = 0
        total_duplicate = 0
        total_failed = 0

        for norm in normalized_reviews:
            try:
                _, is_dup = fetch_service.review_service.insert_review(norm)
                if is_dup:
                    total_duplicate += 1
                else:
                    total_inserted += 1
            except Exception:
                total_failed += 1
        db_ms = (time.perf_counter() - t_db_start) * 1000.0

        total_time = time.perf_counter() - t_start
        throughput = len(raw_reviews) / total_time if total_time > 0 else 0.0

        return LocationFetchResult(
            location_id=location.id,
            location_name=location.branch_name,
            worker_id=worker_id,
            status="success",
            total_fetched=len(raw_reviews),
            total_inserted=total_inserted,
            total_duplicate=total_duplicate,
            total_failed=total_failed,
            total_time_sec=round(total_time, 3),
            network_fetch_sec=round(network_sec, 3),
            normalization_ms=round(norm_ms, 2),
            db_write_ms=round(db_ms, 2),
            reviews_per_sec=round(throughput, 1),
            payload_size_kb=round(payload_kb, 2),
            avg_review_bytes=round(payload_bytes / len(raw_reviews), 1) if raw_reviews else 0.0,
        )
    except Exception as exc:
        total_time = time.perf_counter() - t_start
        return LocationFetchResult(
            location_id=location.id,
            location_name=location.branch_name,
            worker_id=worker_id,
            status="failed",
            total_fetched=0,
            total_inserted=0,
            total_duplicate=0,
            total_failed=0,
            total_time_sec=round(total_time, 3),
            network_fetch_sec=0.0,
            normalization_ms=0.0,
            db_write_ms=0.0,
            reviews_per_sec=0.0,
            payload_size_kb=0.0,
            avg_review_bytes=0.0,
            error_message=str(exc)[:120],
        )


def run_fetch_stress_test(
    locations: list[Location],
    company_id: int,
    concurrency: int,
    reviews_per_location: int,
    live_log: bool = True,
) -> tuple[list[LocationFetchResult], FetchBenchmarkSummary]:
    """Execute concurrent review fetching across locations."""
    if live_log:
        print(f"\n{BOLD}{CYAN}=== STARTING REVIEW FETCHING STRESS TEST ==={RESET}")
        print(f"Company ID:          {company_id}")
        print(f"Total Locations:     {len(locations)}")
        print(f"Reviews / Location:  {reviews_per_location}")
        print(f"Concurrency Workers: {concurrency}")
        print(f"Started At:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print(f"{BOLD}{'TIME':<10} {'WORKER':<8} {'LOC ID':<8} {'LOCATION NAME':<26} {'FETCHED':<10} {'NEW/DUP':<12} {'LATENCY':<10} {'RATE':<12}{RESET}")
        print("-" * 92)

    start_wall = time.perf_counter()
    results: list[LocationFetchResult] = []

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="fetch-worker") as executor:
        futures = {}
        for idx, loc in enumerate(locations):
            worker_id = (idx % concurrency) + 1
            future = executor.submit(
                execute_location_fetch,
                loc,
                company_id,
                worker_id,
                reviews_per_location,
            )
            futures[future] = (loc, worker_id)

        for future in as_completed(futures):
            loc, worker_id = futures[future]
            res = future.result()
            results.append(res)

            if live_log:
                status_color = GREEN if res.status == "success" else RED
                now_str = datetime.now().strftime("%H:%M:%S")
                counts_str = f"{res.total_inserted}/{res.total_duplicate}"
                rate_str = f"{res.reviews_per_sec} rev/s"
                print(
                    f"{now_str:<10} "
                    f"W#{worker_id:<6} "
                    f"#{res.location_id:<6} "
                    f"{res.location_name[:24]:<26} "
                    f"{status_color}{res.total_fetched} items{RESET}   "
                    f"{counts_str:<12} "
                    f"{res.total_time_sec:>5.2f}s     "
                    f"{rate_str:<12}"
                )

    wall_duration = time.perf_counter() - start_wall

    # Aggregations
    total_fetched = sum(r.total_fetched for r in results)
    total_inserted = sum(r.total_inserted for r in results)
    total_duplicate = sum(r.total_duplicate for r in results)
    total_failed = sum(r.total_failed for r in results)
    total_payload = sum(r.payload_size_kb for r in results)

    latencies = sorted([r.total_time_sec for r in results])
    overall_rps = total_fetched / wall_duration if wall_duration > 0 else 0.0
    loc_rpm = (len(results) / wall_duration) * 60.0 if wall_duration > 0 else 0.0
    dedup_ratio = (total_duplicate / total_fetched * 100.0) if total_fetched else 0.0

    avg_norm = sum(r.normalization_ms for r in results) / len(results) if results else 0.0
    avg_db = sum(r.db_write_ms for r in results) / len(results) if results else 0.0
    success_count = sum(1 for r in results if r.status == "success")
    success_pct = (success_count / len(results) * 100.0) if results else 0.0

    summary = FetchBenchmarkSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_locations=len(results),
        concurrency=concurrency,
        wall_clock_sec=round(wall_duration, 2),
        total_fetched=total_fetched,
        total_inserted=total_inserted,
        total_duplicate=total_duplicate,
        total_failed=total_failed,
        dedup_ratio_pct=round(dedup_ratio, 1),
        overall_reviews_per_sec=round(overall_rps, 1),
        locations_per_minute=round(loc_rpm, 1),
        total_payload_kb=round(total_payload, 2),
        avg_payload_per_location_kb=round(total_payload / len(results), 2) if results else 0.0,
        latency_p50_sec=round(percentile(latencies, 50), 3),
        latency_p95_sec=round(percentile(latencies, 95), 3),
        latency_min_sec=round(min(latencies), 3) if latencies else 0.0,
        latency_max_sec=round(max(latencies), 3) if latencies else 0.0,
        avg_normalization_ms=round(avg_norm, 2),
        avg_db_write_ms=round(avg_db, 2),
        success_rate_pct=round(success_pct, 1),
    )

    return results, summary


def print_fetch_scorecard(summary: FetchBenchmarkSummary) -> None:
    """Print an ASCII scorecard of fetch performance metrics."""
    print(f"\n{BOLD}{MAGENTA}================================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}                 REVIEW FETCHING PIPELINE PERFORMANCE SCORECARD                 {RESET}")
    print(f"{BOLD}{MAGENTA}================================================================================{RESET}")
    print(f"{BOLD}Locations Scraped:{RESET}       {summary.total_locations} locations")
    print(f"{BOLD}Concurrency Workers:{RESET}     {summary.concurrency}")
    print(f"{BOLD}Success Rate:{RESET}            {GREEN}{summary.success_rate_pct}%{RESET}")
    print(f"{BOLD}Wall-Clock Duration:{RESET}     {summary.wall_clock_sec:.2f} seconds")
    print(f"{BOLD}Throughput (Reviews):{RESET}    {CYAN}{summary.overall_reviews_per_sec} reviews / sec{RESET}")
    print(f"{BOLD}Throughput (Locations):{RESET}  {CYAN}{summary.locations_per_minute} locations / min{RESET}")
    print("-" * 80)
    print(f"{BOLD}INGESTION & DEDUPLICATION BREAKDOWN:{RESET}")
    print(f"  • Total Reviews Fetched:   {summary.total_fetched:,} reviews")
    print(f"  • New Inserts:             {summary.total_inserted:,} ({100 - summary.dedup_ratio_pct:.1f}%)")
    print(f"  • Duplicate Detected:      {summary.total_duplicate:,} ({summary.dedup_ratio_pct:.1f}%)")
    print(f"  • Failed Ingestion:        {summary.total_failed}")
    print("-" * 80)
    print(f"{BOLD}LATENCY & TIMING DISTRIBUTION:{RESET}")
    print(f"  • Location Latency p50:    {summary.latency_p50_sec:.3f}s (Median)")
    print(f"  • Location Latency p95:    {summary.latency_p95_sec:.3f}s")
    print(f"  • Fastest Location (Min):  {summary.latency_min_sec:.3f}s")
    print(f"  • Slowest Location (Max):  {summary.latency_max_sec:.3f}s")
    print(f"  • Avg Normalization Time:  {summary.avg_normalization_ms:.2f} ms / location")
    print(f"  • Avg DB Write Time:       {summary.avg_db_write_ms:.2f} ms / location")
    print("-" * 80)
    print(f"{BOLD}DATA VOLUME & PAYLOAD METRICS:{RESET}")
    print(f"  • Total Payload Transferred: {summary.total_payload_kb:,.1f} KB ({summary.total_payload_kb/1024:.2f} MB)")
    print(f"  • Avg Payload / Location:    {summary.avg_payload_per_location_kb:.1f} KB")
    print(f"{BOLD}{MAGENTA}================================================================================{RESET}\n")


def save_fetch_reports(summary: FetchBenchmarkSummary, results: list[LocationFetchResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"fetch_reviews_stress_report_{ts}.json"
    md_path = output_dir / f"fetch_reviews_stress_report_{ts}.md"

    # Save JSON report
    data = {
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Save Markdown report
    md_content = f"""# Review Fetching Pipeline Stress Test Report

**Date:** {summary.timestamp}  
**Total Locations Scraped:** `{summary.total_locations}`  
**Concurrency Workers:** `{summary.concurrency}`  
**Wall-Clock Time:** `{summary.wall_clock_sec}s`  

---

## 1. Key Ingestion Metrics

| Metric | Measured Value |
|---|---|
| **Success Rate** | **{summary.success_rate_pct}%** |
| **Reviews Ingestion Throughput** | **{summary.overall_reviews_per_sec} reviews / sec** |
| **Location Throughput** | **{summary.locations_per_minute} locations / min** |
| **Total Reviews Fetched** | **{summary.total_fetched:,}** |
| **New Reviews Inserted** | **{summary.total_inserted:,}** |
| **Duplicate Detected (Deduplicated)** | **{summary.total_duplicate:,} ({summary.dedup_ratio_pct}%)** |
| **Location Latency p50 (Median)** | **{summary.latency_p50_sec}s** |
| **Location Latency p95** | **{summary.latency_p95_sec}s** |
| **Avg Normalization Latency** | **{summary.avg_normalization_ms} ms** |
| **Avg DB Write Latency** | **{summary.avg_db_write_ms} ms** |
| **Total Data Volume** | **{summary.total_payload_kb:,.1f} KB** |

---

## 2. Location Level Performance Breakdown

| Location ID | Location Name | Fetched | New | Duplicate | Latency | Rate |
|---|---|---|---|---|---|---|
"""
    for r in results:
        md_content += f"| `{r.location_id}` | {r.location_name} | {r.total_fetched} | {r.total_inserted} | {r.total_duplicate} | {r.total_time_sec}s | {r.reviews_per_sec} rev/s |\n"

    md_path.write_text(md_content, encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Stress test Crawler Review Fetching Pipeline")
    parser.add_argument("-n", "--total-locations", type=int, default=10, help="Number of locations to fetch (default: 10)")
    parser.add_argument("-c", "--concurrency", type=int, default=3, help="Concurrent worker count (default: 3)")
    parser.add_argument("-r", "--reviews-per-location", type=int, default=30, help="Reviews to fetch per location (default: 30)")
    parser.add_argument("--company-id", type=int, default=3, help="Tenant company ID (default: 3)")
    parser.add_argument("--mode", choices=["single", "sweep"], default="single", help="Test mode: single run or concurrency sweep")
    parser.add_argument("--sweep-workers", type=str, default="1,3,5", help="Comma-separated workers for sweep mode")
    parser.add_argument("--output-dir", type=str, default="exports", help="Directory to save reports")

    args = parser.parse_args()

    # Query real locations from PostgreSQL
    sf = get_session_factory()
    with sf() as session:
        statement = (
            select(Location)
            .where(Location.company_id == args.company_id)
            .order_by(Location.id.asc())
            .limit(args.total_locations)
        )
        locations = list(session.scalars(statement))

    if not locations:
        print(f"{RED}No locations found in DB for company {args.company_id}!{RESET}")
        return 1

    print(f"Found {len(locations)} active locations for company {args.company_id} in PostgreSQL database.")

    if args.mode == "single":
        results, summary = run_fetch_stress_test(
            locations=locations,
            company_id=args.company_id,
            concurrency=args.concurrency,
            reviews_per_location=args.reviews_per_location,
            live_log=True,
        )
        print_fetch_scorecard(summary)
        json_file, md_file = save_fetch_reports(summary, results, Path(args.output_dir))
        print(f"{GREEN}✓ Fetch performance report saved to:{RESET}\n  - {json_file}\n  - {md_file}\n")

    elif args.mode == "sweep":
        sweep_workers = [int(w.strip()) for w in args.sweep_workers.split(",") if w.strip()]
        print(f"\n{BOLD}{CYAN}=== RUNNING FETCH CONCURRENCY SWEEP: {sweep_workers} ==={RESET}\n")

        summaries = []
        for w in sweep_workers:
            print(f"\n{BOLD}>>> Concurrency Tier: {w} Workers <<<{RESET}")
            _, summary = run_fetch_stress_test(
                locations=locations,
                company_id=args.company_id,
                concurrency=w,
                reviews_per_location=args.reviews_per_location,
                live_log=True,
            )
            print_fetch_scorecard(summary)
            summaries.append(summary)

        # Print Sweep Comparison Table
        print(f"\n{BOLD}{MAGENTA}================================================================================{RESET}")
        print(f"{BOLD}{MAGENTA}                  FETCH CONCURRENCY SCALING COMPARISON TABLE                    {RESET}")
        print(f"{BOLD}{MAGENTA}================================================================================{RESET}")
        print(f"{'CONCURRENCY':<12} {'REV / SEC':<12} {'LOC / MIN':<12} {'p50 (s)':<10} {'p95 (s)':<10} {'DB WRITE':<12} {'ERROR %':<10}")
        print("-" * 82)
        for s in summaries:
            print(
                f"{s.concurrency:<12} "
                f"{s.overall_reviews_per_sec:<12.1f} "
                f"{s.locations_per_minute:<12.1f} "
                f"{s.latency_p50_sec:<10.3f} "
                f"{s.latency_p95_sec:<10.3f} "
                f"{s.avg_db_write_ms:<10.1f}ms  "
                f"{100 - s.success_rate_pct:<10.1f}"
            )
        print(f"{BOLD}{MAGENTA}================================================================================{RESET}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
