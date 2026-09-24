#!/usr/bin/env python3
"""Comprehensive Benchmark Runner for Fetching Pipeline and PostgreSQL Database Performance.

Measures:
  1. Fetch Pipeline: Network Latency, Payload Size, Schema Normalization, SHA-256 Hash Generation.
  2. Concurrency Scalability: Multi-worker location ingestion throughput.
  3. Database Read Performance: Keyset pagination, Index scan deduplication, Location queries.
  4. Database Write Performance: Baseline (Single Commit) vs Optimized (Bulk Chunk Commit).
  5. Storage & Capacity Projections: Relation sizes, TOAST, Indexes, 10K to 1M scale projections.

Usage:
  .venv/bin/python scripts/benchmark_fetch_and_db.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import func, or_, select, text

from app.config import get_settings
from app.db.models import Company, Location, Review
from app.db.session import get_session_factory
from app.integrations.mock_review_client import MockReviewClient
from app.services.fetch_service import FetchService
from app.services.location_service import LocationService
from app.services.review_service import ReviewService
from app.utils.hashing import generate_review_hash

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")


def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return d0 + d1


# ---------------------------------------------------------
# Part 1: High Volume Review Generator
# ---------------------------------------------------------
class RealisticStressClient(MockReviewClient):
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
            item["external_review_id"] = f"{location.external_place_id}-bench-{i:04d}"
            item["reviewer_name"] = f"Pengulas {i+1} ({sample.get('reviewer_name', 'Anon')})"
            item["raw_payload"] = {
                "author": item["reviewer_name"],
                "rating": item["rating"],
                "text": item["review_text"],
                "timestamp": int(time.time()),
                "source": "google_maps_reviews",
                "device": "mobile",
                "likes": i % 7,
            }
            reviews.append(item)
        # Simulate realistic WAN latency (180ms - 220ms)
        time.sleep(0.20)
        return reviews


# ---------------------------------------------------------
# Part 2: Database Read Benchmark
# ---------------------------------------------------------
def benchmark_db_reads(session_factory, iterations: int = 50) -> dict:
    """Benchmark typical queries against PostgreSQL."""
    print("  -> Benchmarking Database Read Latencies...")
    
    with session_factory() as session:
        # Sample an existing hash
        sample_hash = session.execute(
            select(Review.review_hash).where(Review.review_hash.isnot(None)).limit(1)
        ).scalar()
        
        # Sample an existing location_id
        sample_loc_id = session.execute(
            select(Review.location_id).limit(1)
        ).scalar()

    # 1. Deduplication Hash Index Lookup
    hash_latencies = []
    if sample_hash:
        for _ in range(iterations):
            t0 = time.perf_counter()
            with session_factory() as session:
                session.execute(
                    text("SELECT id FROM reviews WHERE review_hash = :h"),
                    {"h": sample_hash}
                ).first()
            hash_latencies.append((time.perf_counter() - t0) * 1000.0)

    # 2. Keyset pagination query for pending AI reviews
    pending_latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        with session_factory() as session:
            session.execute(
                text("SELECT id, review_text, rating FROM reviews WHERE analysis_status = 'pending' ORDER BY id ASC LIMIT 50")
            ).fetchall()
        pending_latencies.append((time.perf_counter() - t0) * 1000.0)

    # 3. Location-based review retrieval (OneBox UI detail view)
    loc_latencies = []
    if sample_loc_id:
        for _ in range(iterations):
            t0 = time.perf_counter()
            with session_factory() as session:
                session.execute(
                    text("SELECT id, reviewer_name, rating, review_text FROM reviews WHERE location_id = :loc ORDER BY review_time DESC LIMIT 25"),
                    {"loc": sample_loc_id}
                ).fetchall()
            loc_latencies.append((time.perf_counter() - t0) * 1000.0)

    # 4. Aggregation query (Dashboard Metrics)
    agg_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        with session_factory() as session:
            session.execute(
                text("SELECT rating, count(*) FROM reviews GROUP BY rating")
            ).fetchall()
        agg_latencies.append((time.perf_counter() - t0) * 1000.0)

    return {
        "dedup_hash_index_lookup": {
            "p50_ms": round(percentile(hash_latencies, 50), 2),
            "p95_ms": round(percentile(hash_latencies, 95), 2),
            "mean_ms": round(sum(hash_latencies) / len(hash_latencies), 2) if hash_latencies else 0.0,
            "min_ms": round(min(hash_latencies), 2) if hash_latencies else 0.0,
            "max_ms": round(max(hash_latencies), 2) if hash_latencies else 0.0,
        },
        "pending_reviews_keyset_query": {
            "p50_ms": round(percentile(pending_latencies, 50), 2),
            "p95_ms": round(percentile(pending_latencies, 95), 2),
            "mean_ms": round(sum(pending_latencies) / len(pending_latencies), 2) if pending_latencies else 0.0,
        },
        "location_review_history_query": {
            "p50_ms": round(percentile(loc_latencies, 50), 2),
            "p95_ms": round(percentile(loc_latencies, 95), 2),
            "mean_ms": round(sum(loc_latencies) / len(loc_latencies), 2) if loc_latencies else 0.0,
        },
        "rating_aggregation_dashboard_query": {
            "p50_ms": round(percentile(agg_latencies, 50), 2),
            "p95_ms": round(percentile(agg_latencies, 95), 2),
            "mean_ms": round(sum(agg_latencies) / len(agg_latencies), 2) if agg_latencies else 0.0,
        }
    }


# ---------------------------------------------------------
# Part 3: Database Write Benchmark (Single Commit vs Bulk)
# ---------------------------------------------------------
def benchmark_db_writes(location: Location, company_id: int, num_items: int = 30) -> dict:
    """Compare single-row commit (baseline) vs bulk chunk commit (optimized)."""
    print(f"  -> Benchmarking Database Write Performance ({num_items} test reviews)...")
    client = RealisticStressClient(review_count=num_items)
    fetch_service = FetchService(company_id=company_id, client=client)
    review_service = fetch_service.review_service

    raw_items = client.fetch_reviews(location, limit=num_items)
    normalized_items = [fetch_service.normalize_review(location, r) for r in raw_items]

    # Prepare unique test batches using ephemeral review hashes to avoid collision
    batch_single = []
    ts = int(time.time() * 1000)
    for i, it in enumerate(normalized_items):
        item = dict(it)
        item["external_review_id"] = f"test-single-{ts}-{i:04d}"
        item["review_hash"] = f"hash-single-{ts}-{i:04d}"
        item["review_text"] = f"Test ulasan performa database write baseline #{i+1}"
        batch_single.append(item)

    batch_bulk = []
    for i, it in enumerate(normalized_items):
        item = dict(it)
        item["external_review_id"] = f"test-bulk-{ts}-{i:04d}"
        item["review_hash"] = f"hash-bulk-{ts}-{i:04d}"
        item["review_text"] = f"Test ulasan performa database write bulk #{i+1}"
        batch_bulk.append(item)

    # 1. Single Commit Baseline
    t0 = time.perf_counter()
    single_success = 0
    single_item_latencies = []
    for item in batch_single:
        t_item = time.perf_counter()
        review_service.insert_review(item)
        single_item_latencies.append((time.perf_counter() - t_item) * 1000.0)
        single_success += 1
    t_single_total = time.perf_counter() - t0
    single_throughput = single_success / t_single_total if t_single_total > 0 else 0.0

    # 2. Bulk Chunk Commit Optimized
    t0 = time.perf_counter()
    bulk_results = review_service.insert_reviews_bulk(batch_bulk, batch_size=num_items)
    t_bulk_total = time.perf_counter() - t0
    bulk_success = len(bulk_results)
    bulk_throughput = bulk_success / t_bulk_total if t_bulk_total > 0 else 0.0

    # Cleanup test rows to keep DB clean
    session_factory = get_session_factory()
    with session_factory() as session:
        session.execute(
            text("DELETE FROM reviews WHERE external_review_id LIKE :prefix"),
            {"prefix": f"test-%-{ts}-%"}
        )
        session.commit()

    speedup = bulk_throughput / single_throughput if single_throughput > 0 else 1.0

    return {
        "items_tested": num_items,
        "single_row_commit": {
            "total_time_sec": round(t_single_total, 3),
            "throughput_rev_sec": round(single_throughput, 2),
            "avg_latency_per_item_ms": round(sum(single_item_latencies) / len(single_item_latencies), 2),
            "p50_item_ms": round(percentile(single_item_latencies, 50), 2),
            "p95_item_ms": round(percentile(single_item_latencies, 95), 2),
        },
        "bulk_chunk_commit": {
            "total_time_sec": round(t_bulk_total, 3),
            "throughput_rev_sec": round(bulk_throughput, 2),
            "effective_latency_per_item_ms": round((t_bulk_total * 1000.0) / num_items, 2),
        },
        "speedup_factor": round(speedup, 1),
    }


# ---------------------------------------------------------
# Part 4: Concurrency Sweep for Fetch Pipeline
# ---------------------------------------------------------
def benchmark_fetch_concurrency(locations: list[Location], company_id: int, workers_list: list[int] = [1, 3, 5]) -> list[dict]:
    """Test fetching pipeline across varying worker counts."""
    print("  -> Benchmarking Fetch Pipeline Concurrency Sweep...")
    results = []

    for workers in workers_list:
        sample_locs = locations[:min(len(locations), workers * 2)]
        t0 = time.perf_counter()
        
        loc_latencies = []
        total_reviews = 0
        total_bytes = 0
        total_norm_ms = 0.0

        def fetch_task(loc: Location):
            client = RealisticStressClient(review_count=25)
            fetch_svc = FetchService(company_id=company_id, client=client)
            
            t_loc0 = time.perf_counter()
            raw = client.fetch_reviews(loc, limit=25)
            payload_str = json.dumps(raw)
            raw_bytes = len(payload_str.encode("utf-8"))

            t_n0 = time.perf_counter()
            normalized = [fetch_svc.normalize_review(loc, r) for r in raw]
            norm_ms = (time.perf_counter() - t_n0) * 1000.0

            # Test deduplication check against DB
            with get_session_factory()() as session:
                hashes = [n["review_hash"] for n in normalized]
                session.execute(
                    select(Review.id).where(Review.review_hash.in_(hashes))
                ).fetchall()

            dur = time.perf_counter() - t_loc0
            return dur, len(raw), raw_bytes, norm_ms

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch_task, loc) for loc in sample_locs]
            for fut in as_completed(futures):
                dur, rev_count, raw_bytes, norm_ms = fut.result()
                loc_latencies.append(dur)
                total_reviews += rev_count
                total_bytes += raw_bytes
                total_norm_ms += norm_ms

        wall_sec = time.perf_counter() - t0
        throughput = total_reviews / wall_sec if wall_sec > 0 else 0.0
        loc_per_min = (len(sample_locs) / wall_sec) * 60.0 if wall_sec > 0 else 0.0

        results.append({
            "workers": workers,
            "total_locations": len(sample_locs),
            "total_reviews": total_reviews,
            "wall_clock_sec": round(wall_sec, 2),
            "throughput_rev_sec": round(throughput, 2),
            "locations_per_min": round(loc_per_min, 1),
            "latency_p50_sec": round(percentile(loc_latencies, 50), 3),
            "latency_p95_sec": round(percentile(loc_latencies, 95), 3),
            "avg_payload_kb_per_loc": round((total_bytes / len(sample_locs)) / 1024.0, 2),
            "avg_bytes_per_review": round(total_bytes / total_reviews, 1) if total_reviews else 0.0,
            "avg_normalization_ms_per_loc": round(total_norm_ms / len(sample_locs), 2),
        })

    return results


# ---------------------------------------------------------
# Part 5: PostgreSQL Storage & Capacity Projections
# ---------------------------------------------------------
def get_db_storage_metrics(session_factory) -> dict:
    """Retrieve exact table and index sizes from PostgreSQL."""
    print("  -> Retrieving PostgreSQL Storage & Capacity Metrics...")
    with session_factory() as session:
        # Table sizes in bytes
        tot_bytes = session.execute(text("SELECT pg_total_relation_size('reviews')")).scalar() or 0
        tbl_bytes = session.execute(text("SELECT pg_relation_size('reviews')")).scalar() or 0
        idx_bytes = session.execute(text("SELECT pg_indexes_size('reviews')")).scalar() or 0
        toast_bytes = session.execute(text("SELECT pg_total_relation_size(reltoastrelid) FROM pg_class WHERE relname = 'reviews'")).scalar() or 0

        total_rows = session.execute(text("SELECT count(*) FROM reviews")).scalar() or 1
        active_locs = session.execute(text("SELECT count(*) FROM locations WHERE is_active = true")).scalar() or 0

        # Cache hit ratio
        cache_hit = session.execute(text("""
            SELECT coalesce(sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100, 100.0)
            FROM pg_statio_user_tables WHERE relname = 'reviews'
        """)).scalar() or 100.0

    bytes_per_row = tot_bytes / total_rows if total_rows > 0 else 2600.0

    # Scale Projections
    scales = [10_000, 50_000, 100_000, 500_000, 1_000_000]
    projections = []
    # AWS RDS gp3 price reference: $0.115 per GB-month at Kurs Rp 17.500 = Rp 2.012,50 / GB-month
    STORAGE_COST_PER_GB_IDR = 0.115 * 17500.0

    for n in scales:
        proj_bytes = n * bytes_per_row
        proj_mb = proj_bytes / (1024 * 1024)
        proj_gb = proj_bytes / (1024 * 1024 * 1024)
        cost_monthly_idr = proj_gb * STORAGE_COST_PER_GB_IDR

        # Estimated RAM working set (25% of table + 100% of index)
        ram_needed_mb = (proj_mb * 0.4) + (n * (idx_bytes / total_rows) / (1024 * 1024))

        projections.append({
            "review_count": n,
            "projected_total_mb": round(proj_mb, 1),
            "projected_total_gb": round(proj_gb, 3),
            "estimated_ram_working_set_mb": round(ram_needed_mb, 1),
            "storage_cost_per_month_idr": round(cost_monthly_idr, 2),
        })

    return {
        "current_stats": {
            "total_reviews": total_rows,
            "total_locations": active_locs,
            "total_size_mb": round(tot_bytes / (1024 * 1024), 2),
            "table_heap_size_mb": round(tbl_bytes / (1024 * 1024), 2),
            "indexes_size_mb": round(idx_bytes / (1024 * 1024), 2),
            "toast_payload_size_mb": round(toast_bytes / (1024 * 1024), 2),
            "avg_bytes_per_review": round(bytes_per_row, 1),
            "cache_hit_ratio_pct": round(float(cache_hit), 2),
        },
        "projections": projections,
    }


def main():
    print("================================================================================")
    print("  BENCHMARK PENGUJIAN PERFORMA FETCHING & DATABASE POSTGRESQL MULTI-TENANT")
    print("================================================================================")

    session_factory = get_session_factory()
    with session_factory() as session:
        locations = session.scalars(
            select(Location).where(Location.is_active.is_(True)).order_by(Location.id.asc())
        ).all()
        company = session.scalars(select(Company).limit(1)).first()
        company_id = company.id if company else 1

    if not locations:
        print("ERROR: Tidak ada data lokasi aktif di database!")
        sys.exit(1)

    print(f"Data Lokasi Ditemukan: {len(locations)} cabang aktif. Menggunakan Company ID: {company_id}")

    # 1. DB Reads
    read_metrics = benchmark_db_reads(session_factory, iterations=40)

    # 2. DB Writes (Single vs Bulk)
    write_metrics = benchmark_db_writes(locations[0], company_id=company_id, num_items=25)

    # 3. Fetch Pipeline Concurrency
    concurrency_metrics = benchmark_fetch_concurrency(locations, company_id=company_id, workers_list=[1, 3, 5])

    # 4. Storage & Capacity
    storage_metrics = get_db_storage_metrics(session_factory)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    export_payload = {
        "report_title": "Laporan Evaluasi Performa Pipeline Penarikan (Fetch) & Database PostgreSQL",
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
        "database_engine": "PostgreSQL (Remote Cluster)",
        "read_performance": read_metrics,
        "write_performance": write_metrics,
        "fetch_concurrency_sweep": concurrency_metrics,
        "storage_and_projections": storage_metrics,
    }

    out_dir = REPO_ROOT / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"fetch_and_db_benchmark_{timestamp_str}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("  RINGKASAN HASIL BENCHMARK")
    print("="*80)
    print(f"1. Database Read Latency (Hash Index Scan) : {read_metrics['dedup_hash_index_lookup']['p50_ms']} ms")
    print(f"2. Keyset Query Latency (Pending 50 rows)  : {read_metrics['pending_reviews_keyset_query']['p50_ms']} ms")
    print(f"3. DB Write Throughput (Baseline Single)   : {write_metrics['single_row_commit']['throughput_rev_sec']} ulasan/detik")
    print(f"4. DB Write Throughput (Optimized Bulk)    : {write_metrics['bulk_chunk_commit']['throughput_rev_sec']} ulasan/detik (Peningkatan {write_metrics['speedup_factor']}x!)")
    print(f"5. Fetch Throughput (5 Workers)            : {concurrency_metrics[-1]['throughput_rev_sec']} ulasan/detik ({concurrency_metrics[-1]['locations_per_min']} lokasi/menit)")
    print(f"6. Database Storage Per Review             : {storage_metrics['current_stats']['avg_bytes_per_review']} bytes (~{round(storage_metrics['current_stats']['avg_bytes_per_review']/1024, 2)} KB)")
    print(f"7. Hasil pengujian lengkap tersimpan di   : {out_file}")
    print("="*80)


if __name__ == "__main__":
    main()
