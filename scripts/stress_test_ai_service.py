#!/usr/bin/env python3
"""Reproducible AI Analysis Service & API Stress Testing Tool.

Tests the Crawler service AI analysis pipeline under concurrent load using real
review data directly from the PostgreSQL database. Measures:
  - Latency (min, max, mean, p50, p90, p95, p99, stddev)
  - Throughput (requests/sec, reviews/min)
  - Token consumption (prompt, completion, total, per-review)
  - Cost / pricing calculation (USD and IDR)
  - Error rates & HTTP status codes
  - Concurrency scaling performance

Usage examples:
  # Quick test with 10 reviews and 3 workers (Jev AI)
  .venv/bin/python scripts/stress_test_ai_service.py -n 10 -c 3

  # Full stress test with 30 reviews at concurrency 5
  .venv/bin/python scripts/stress_test_ai_service.py -n 30 -c 5 --provider jev

  # Concurrency sweep benchmark comparing 1, 5, and 10 workers
  .venv/bin/python scripts/stress_test_ai_service.py --mode sweep -n 30 --sweep-workers 1,5,10

  # Batch pending endpoint stress test
  .venv/bin/python scripts/stress_test_ai_service.py --mode pending -n 50
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from app.db.session import get_session_factory
from app.services.api_client_service import ApiClientService

# ANSI Color codes for clean real-time console display
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

# Price reference (per 1M tokens or per request)
# Jev AI via OpenRouter: ~$0.0000319 per query or ~$0.035 / 1M prompt, $0.14 / 1M completion
# Gemini 2.5 Flash Lite: $0.075 / 1M prompt, $0.30 / 1M completion
USD_TO_IDR = 17_500.0


@dataclass
class RequestResult:
    review_id: int
    worker_id: int
    status_code: int
    latency_sec: float
    success: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    sentiment: str = "unknown"
    category: str = "unknown"
    urgency: str = "unknown"
    is_viral: bool = False
    is_safety: bool = False
    error_message: str | None = None
    llm_inference_ms: float = 0.0
    model_name: str = ""


@dataclass
class BenchmarkSummary:
    timestamp: str
    provider: str
    model_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate_pct: float
    concurrency: int
    wall_clock_duration_sec: float
    requests_per_second: float
    reviews_per_minute: float
    latency_min_sec: float
    latency_max_sec: float
    latency_mean_sec: float
    latency_p50_sec: float
    latency_p90_sec: float
    latency_p95_sec: float
    latency_p99_sec: float
    latency_stddev_sec: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_tokens_per_review: float
    tokens_per_second: float
    total_cost_usd: float
    total_cost_idr: float
    avg_cost_per_review_usd: float
    avg_cost_per_review_idr: float
    projected_cost_1k_reviews_idr: float
    sentiments: dict[str, int] = field(default_factory=dict)
    categories: dict[str, int] = field(default_factory=dict)
    viral_risks_detected: int = 0
    safety_issues_detected: int = 0


def calculate_cost(provider: str, prompt_tokens: int, completion_tokens: int, raw_cost: float = 0.0) -> float:
    """Calculate estimated cost in USD."""
    if raw_cost > 0.0:
        return raw_cost
    if provider == "jev":
        # TypeSafe Jev: ~$0.035 / 1M prompt, ~$0.14 / 1M completion
        return (prompt_tokens * 0.035 / 1_000_000.0) + (completion_tokens * 0.14 / 1_000_000.0)
    elif provider == "openai":
        # Gemini 2.5 Flash Lite or GPT-4o-mini
        return (prompt_tokens * 0.075 / 1_000_000.0) + (completion_tokens * 0.30 / 1_000_000.0)
    elif provider == "absa":
        # Self-hosted ABSA: inference cost is infrastructure-based ($0 external API cost)
        return 0.0
    return (prompt_tokens * 0.05 / 1_000_000.0) + (completion_tokens * 0.20 / 1_000_000.0)


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


def compute_stddev(data: list[float], mean: float) -> float:
    if len(data) <= 1:
        return 0.0
    variance = sum((x - mean) ** 2 for x in data) / (len(data) - 1)
    return math.sqrt(variance)


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


class LocalServerManager:
    """Manages an in-process FastAPI server if no live server is currently listening."""

    def __init__(self, port: int = 8998):
        self.port = port
        self.host = "127.0.0.1"
        self.server = None
        self.thread = None

    def start(self) -> str:
        if is_port_open(self.host, self.port):
            return f"http://{self.host}:{self.port}"

        import uvicorn
        from apps.api.main import create_app

        app = create_app()
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        # Wait for server to bind
        for _ in range(30):
            time.sleep(0.1)
            if is_port_open(self.host, self.port):
                break
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self.server:
            self.server.should_exit = True
            if self.thread:
                self.thread.join(timeout=2)


def fetch_test_reviews(company_id: int, limit: int, location_id: int | None = None) -> list[dict]:
    """Fetch real reviews from PostgreSQL database."""
    sf = get_session_factory()
    with sf() as session:
        query = """
            SELECT r.id, r.company_id, r.location_id, r.reviewer_name, r.rating, r.review_text
            FROM reviews r
            WHERE r.company_id = :company_id
              AND r.review_text IS NOT NULL
              AND length(trim(r.review_text)) > 15
        """
        params: dict[str, Any] = {"company_id": company_id, "limit": limit}
        if location_id:
            query += " AND r.location_id = :location_id"
            params["location_id"] = location_id

        # Prioritize reviews not yet analyzed to test real-world ingestion, then fallback to recent
        query += """
            ORDER BY (
                SELECT count(*) FROM review_analysis a WHERE a.review_id = r.id
            ) ASC, r.id DESC
            LIMIT :limit
        """
        rows = session.execute(text(query), params).fetchall()
        return [
            {
                "id": r.id,
                "company_id": r.company_id,
                "location_id": r.location_id,
                "reviewer_name": r.reviewer_name,
                "rating": r.rating,
                "review_text": r.review_text,
            }
            for r in rows
        ]


def get_or_create_service_token(company_id: int) -> str:
    """Issue a valid service token for testing."""
    svc = ApiClientService()
    issued = svc.issue(
        company_id=company_id,
        name="stress-test-runner",
        scopes=["analysis:write", "reviews:read"],
    )
    return issued.token


def execute_single_review_rerun(
    client: httpx.Client,
    base_url: str,
    token: str,
    provider: str,
    review: dict,
    worker_id: int,
) -> RequestResult:
    """Execute a single-review rerun request against Crawler API."""
    url = f"{base_url}/api/integration/v1/analysis/reviews/{review['id']}/rerun"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": f"stress-{worker_id}-{review['id']}-{int(time.time()*1000)}",
    }
    params = {"provider": provider}

    t0 = time.perf_counter()
    try:
        resp = client.post(url, headers=headers, params=params, timeout=120.0)
        latency = time.perf_counter() - t0

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            token_usage = data.get("token_usage", {})
            prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
            comp_tokens = int(token_usage.get("completion_tokens") or 0)
            total_tokens = int(token_usage.get("total_tokens") or (prompt_tokens + comp_tokens))
            llm_call_ms = float(data.get("llm_call_ms_total") or 0.0)

            # Extract sentiments & quality if present
            sentiments_dict = data.get("sentiments", {})
            sentiment = "positive" if sentiments_dict.get("positive") else \
                        "negative" if sentiments_dict.get("negative") else \
                        "neutral" if sentiments_dict.get("neutral") else "mixed"

            # Check DB or raw response if available
            cost = calculate_cost(provider, prompt_tokens, comp_tokens)

            return RequestResult(
                review_id=review["id"],
                worker_id=worker_id,
                status_code=resp.status_code,
                latency_sec=latency,
                success=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
                sentiment=sentiment,
                llm_inference_ms=llm_call_ms,
            )
        else:
            return RequestResult(
                review_id=review["id"],
                worker_id=worker_id,
                status_code=resp.status_code,
                latency_sec=latency,
                success=False,
                error_message=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
    except Exception as exc:
        latency = time.perf_counter() - t0
        return RequestResult(
            review_id=review["id"],
            worker_id=worker_id,
            status_code=0,
            latency_sec=latency,
            success=False,
            error_message=str(exc)[:120],
        )


def run_concurrent_stress_test(
    base_url: str,
    token: str,
    provider: str,
    reviews: list[dict],
    concurrency: int,
    live_log: bool = True,
) -> tuple[list[RequestResult], BenchmarkSummary]:
    """Execute concurrent AI analysis requests and stream real-time metrics."""
    results: list[RequestResult] = []
    total_reviews = len(reviews)

    if live_log:
        print(f"\n{BOLD}{CYAN}=== STARTING STRESS TEST RUN ==={RESET}")
        print(f"Target:       {base_url}/api/integration/v1/analysis")
        print(f"Provider:     {provider.upper()}")
        print(f"Total Items:  {total_reviews} reviews from database")
        print(f"Concurrency:  {concurrency} concurrent workers")
        print(f"Started at:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print(f"{BOLD}{'TIME':<10} {'WORKER':<8} {'REVIEW':<10} {'STATUS':<10} {'LATENCY':<10} {'TOKENS':<14} {'EST. COST (IDR)':<16} {'SENTIMENT':<12}{RESET}")
        print("-" * 84)

    start_wall_clock = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="stress-worker") as executor:
        # Create separate HTTP client per worker for authentic connection pooling
        clients = [httpx.Client(timeout=120.0) for _ in range(concurrency)]

        futures = {}
        for idx, review in enumerate(reviews):
            worker_id = (idx % concurrency) + 1
            client = clients[worker_id - 1]
            future = executor.submit(
                execute_single_review_rerun,
                client,
                base_url,
                token,
                provider,
                review,
                worker_id,
            )
            futures[future] = (idx, review, worker_id)

        completed_count = 0
        for future in as_completed(futures):
            idx, review, worker_id = futures[future]
            res = future.result()
            results.append(res)
            completed_count += 1

            if live_log:
                status_color = GREEN if res.success else RED
                cost_idr = res.estimated_cost_usd * USD_TO_IDR
                now_str = datetime.now().strftime("%H:%M:%S")
                token_str = f"{res.total_tokens} ({res.prompt_tokens}p/{res.completion_tokens}c)" if res.total_tokens else "-"
                cost_str = f"Rp {cost_idr:.2f}" if cost_idr > 0 else "-"

                status_text = f"HTTP {res.status_code}" if res.status_code else "ERROR"
                print(
                    f"{now_str:<10} "
                    f"W#{worker_id:<6} "
                    f"#{res.review_id:<8} "
                    f"{status_color}{status_text:<10}{RESET} "
                    f"{res.latency_sec:>6.2f}s    "
                    f"{token_str:<14} "
                    f"{cost_str:<16} "
                    f"{res.sentiment:<12}"
                )

        for c in clients:
            c.close()

    wall_duration = time.perf_counter() - start_wall_clock

    # Compute metrics
    latencies = sorted([r.latency_sec for r in results])
    successful = [r for r in results if r.success]
    success_count = len(successful)
    fail_count = len(results) - success_count
    error_rate = (fail_count / len(results) * 100.0) if results else 0.0

    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
    rps = len(results) / wall_duration if wall_duration > 0 else 0.0
    rpm = rps * 60.0

    total_prompt = sum(r.prompt_tokens for r in results)
    total_comp = sum(r.completion_tokens for r in results)
    total_tokens = sum(r.total_tokens for r in results)
    tokens_per_sec = total_tokens / wall_duration if wall_duration > 0 else 0.0
    avg_tokens_review = total_tokens / len(results) if results else 0.0

    total_cost_usd = sum(r.estimated_cost_usd for r in results)
    total_cost_idr = total_cost_usd * USD_TO_IDR
    avg_cost_usd = total_cost_usd / len(results) if results else 0.0
    avg_cost_idr = total_cost_idr / len(results) if results else 0.0
    cost_1k_idr = avg_cost_idr * 1000.0

    sentiments: dict[str, int] = {}
    for r in results:
        sentiments[r.sentiment] = sentiments.get(r.sentiment, 0) + 1

    summary = BenchmarkSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=provider,
        model_name="~typesafe/jev-latest" if provider == "jev" else "gemini-2.5-flash-lite",
        total_requests=len(results),
        successful_requests=success_count,
        failed_requests=fail_count,
        error_rate_pct=round(error_rate, 2),
        concurrency=concurrency,
        wall_clock_duration_sec=round(wall_duration, 2),
        requests_per_second=round(rps, 2),
        reviews_per_minute=round(rpm, 1),
        latency_min_sec=round(min(latencies), 3) if latencies else 0.0,
        latency_max_sec=round(max(latencies), 3) if latencies else 0.0,
        latency_mean_sec=round(mean_lat, 3),
        latency_p50_sec=round(percentile(latencies, 50), 3),
        latency_p90_sec=round(percentile(latencies, 90), 3),
        latency_p95_sec=round(percentile(latencies, 95), 3),
        latency_p99_sec=round(percentile(latencies, 99), 3),
        latency_stddev_sec=round(compute_stddev(latencies, mean_lat), 3),
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_comp,
        total_tokens=total_tokens,
        avg_tokens_per_review=round(avg_tokens_review, 1),
        tokens_per_second=round(tokens_per_sec, 1),
        total_cost_usd=round(total_cost_usd, 6),
        total_cost_idr=round(total_cost_idr, 2),
        avg_cost_per_review_usd=round(avg_cost_usd, 6),
        avg_cost_per_review_idr=round(avg_cost_idr, 2),
        projected_cost_1k_reviews_idr=round(cost_1k_idr, 2),
        sentiments=sentiments,
    )

    return results, summary


def print_scorecard(summary: BenchmarkSummary) -> None:
    """Print a rich ASCII scorecard of the performance benchmark."""
    print(f"\n{BOLD}{MAGENTA}================================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}                       AI SERVICE PERFORMANCE SCORECARD                         {RESET}")
    print(f"{BOLD}{MAGENTA}================================================================================{RESET}")
    print(f"{BOLD}Provider / Model:{RESET}        {summary.provider.upper()} ({summary.model_name})")
    print(f"{BOLD}Concurrency Workers:{RESET}     {summary.concurrency}")
    print(f"{BOLD}Total Processed:{RESET}         {summary.total_requests} reviews")
    print(f"{BOLD}Success / Failed:{RESET}        {GREEN}{summary.successful_requests} ok{RESET} / {RED}{summary.failed_requests} failed{RESET} (Error rate: {summary.error_rate_pct}%)")
    print(f"{BOLD}Wall-Clock Time:{RESET}         {summary.wall_clock_duration_sec:.2f} seconds")
    print(f"{BOLD}Throughput:{RESET}              {CYAN}{summary.requests_per_second} req/sec{RESET} ({summary.reviews_per_minute} reviews/min)")
    print("-" * 80)
    print(f"{BOLD}LATENCY DISTRIBUTION:{RESET}")
    print(f"  • Min:    {summary.latency_min_sec:.3f}s")
    print(f"  • Mean:   {summary.latency_mean_sec:.3f}s (± {summary.latency_stddev_sec:.3f}s)")
    print(f"  • p50:    {summary.latency_p50_sec:.3f}s  (Median)")
    print(f"  • p90:    {summary.latency_p90_sec:.3f}s")
    print(f"  • p95:    {summary.latency_p95_sec:.3f}s")
    print(f"  • p99:    {summary.latency_p99_sec:.3f}s")
    print(f"  • Max:    {summary.latency_max_sec:.3f}s")
    print("-" * 80)
    print(f"{BOLD}TOKEN CONSUMPTION:{RESET}")
    print(f"  • Total Tokens:         {summary.total_tokens:,}")
    print(f"  • Prompt (Input):       {summary.total_prompt_tokens:,}")
    print(f"  • Completion (Output):  {summary.total_completion_tokens:,}")
    print(f"  • Avg Tokens / Review:  {summary.avg_tokens_per_review:.1f} tokens")
    print(f"  • Token Processing:     {summary.tokens_per_second:.1f} tokens/sec")
    print("-" * 80)
    print(f"{BOLD}COST & PRICING ANALYSIS:{RESET}")
    print(f"  • Total Cost (USD):     ${summary.total_cost_usd:.6f}")
    print(f"  • Total Cost (IDR):     Rp {summary.total_cost_idr:,.2f}")
    print(f"  • Avg Cost / Review:    ${summary.avg_cost_per_review_usd:.6f} (Rp {summary.avg_cost_per_review_idr:.2f})")
    print(f"  • Projected / 1K Reviews: Rp {summary.projected_cost_1k_reviews_idr:,.2f} (~${summary.projected_cost_1k_reviews_idr/USD_TO_IDR:.2f})")
    print(f"  • Projected / 10K Reviews: Rp {summary.projected_cost_1k_reviews_idr*10:,.2f} (~${(summary.projected_cost_1k_reviews_idr*10)/USD_TO_IDR:.2f})")
    print("-" * 80)
    print(f"{BOLD}CLASSIFICATION SUMMARY:{RESET}")
    for s_name, count in summary.sentiments.items():
        pct = (count / summary.total_requests * 100) if summary.total_requests else 0
        print(f"  • Sentiment '{s_name}': {count} ({pct:.1f}%)")
    print(f"{BOLD}{MAGENTA}================================================================================{RESET}\n")


def save_reports(summary: BenchmarkSummary, results: list[RequestResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"ai_stress_test_report_{summary.provider}_{ts}.json"
    md_path = output_dir / f"ai_stress_test_report_{summary.provider}_{ts}.md"

    # Save JSON report
    data = {
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Save Markdown report
    md_content = f"""# AI Service Stress Test & Performance Report

**Date:** {summary.timestamp}  
**Provider:** `{summary.provider}` (`{summary.model_name}`)  
**Concurrency:** `{summary.concurrency}` workers  
**Total Reviews Tested:** `{summary.total_requests}`  

---

## 1. Executive Summary

| Metric | Measured Value |
|---|---|
| **Success Rate** | **{100 - summary.error_rate_pct:.1f}%** ({summary.successful_requests}/{summary.total_requests}) |
| **Throughput** | **{summary.requests_per_second} req/sec** ({summary.reviews_per_minute} reviews/min) |
| **Latency p50 (Median)** | **{summary.latency_p50_sec}s** |
| **Latency p95** | **{summary.latency_p95_sec}s** |
| **Latency p99** | **{summary.latency_p99_sec}s** |
| **Avg Tokens / Review** | **{summary.avg_tokens_per_review:.1f} tokens** |
| **Avg Cost / Review** | **${summary.avg_cost_per_review_usd:.6f}** (Rp {summary.avg_cost_per_review_idr:.2f}) |
| **Projected Cost / 1,000 Reviews** | **Rp {summary.projected_cost_1k_reviews_idr:,.2f}** (~${summary.projected_cost_1k_reviews_idr/USD_TO_IDR:.2f}) |

---

## 2. Latency Metrics

- **Minimum:** `{summary.latency_min_sec}s`
- **Mean:** `{summary.latency_mean_sec}s` (StdDev: `{summary.latency_stddev_sec}s`)
- **Median (p50):** `{summary.latency_p50_sec}s`
- **p90:** `{summary.latency_p90_sec}s`
- **p95:** `{summary.latency_p95_sec}s`
- **p99:** `{summary.latency_p99_sec}s`
- **Maximum:** `{summary.latency_max_sec}s`

---

## 3. Token Consumption & Pricing

- **Total Prompt Tokens:** `{summary.total_prompt_tokens:,}`
- **Total Completion Tokens:** `{summary.total_completion_tokens:,}`
- **Total Tokens:** `{summary.total_tokens:,}`
- **Token Processing Speed:** `{summary.tokens_per_second:.1f} tokens/sec`
- **Total Test Cost:** `${summary.total_cost_usd:.6f}` (Rp {summary.total_cost_idr:,.2f})
- **Projected 10,000 Reviews Cost:** `Rp {summary.projected_cost_1k_reviews_idr * 10:,.2f}`

---

## 4. Sentiment Distribution

| Sentiment | Count | Percentage |
|---|---|---|
"""
    for s_name, count in summary.sentiments.items():
        pct = (count / summary.total_requests * 100) if summary.total_requests else 0
        md_content += f"| `{s_name}` | {count} | {pct:.1f}% |\n"

    md_path.write_text(md_content, encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Stress test Crawler AI Analysis Service")
    parser.add_argument("-n", "--total-reviews", type=int, default=20, help="Total reviews to test from DB (default: 20)")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Concurrent worker count (default: 5)")
    parser.add_argument("-p", "--provider", choices=["jev", "openai", "absa"], default="jev", help="AI provider (default: jev)")
    parser.add_argument("--company-id", type=int, default=3, help="Tenant company ID (default: 3)")
    parser.add_argument("--location-id", type=int, default=None, help="Filter reviews by location ID")
    parser.add_argument("--base-url", type=str, default=None, help="Base URL of Crawler service (auto-starts if omitted)")
    parser.add_argument("--mode", choices=["single", "sweep", "pending"], default="single", help="Test mode (single rerun, sweep benchmark, or pending batch)")
    parser.add_argument("--sweep-workers", type=str, default="1,3,5,10", help="Comma-separated worker counts for sweep mode")
    parser.add_argument("--output-dir", type=str, default="exports", help="Directory to save performance reports")

    args = parser.parse_args()

    # Ensure JEV_API_KEY is available in environment
    settings = get_settings()
    if not os.getenv("JEV_API_KEY") and settings.jev_api_key:
        os.environ["JEV_API_KEY"] = settings.jev_api_key

    # Manage local server if needed
    server_mgr = None
    base_url = args.base_url
    if not base_url:
        if is_port_open("127.0.0.1", 8000):
            base_url = "http://127.0.0.1:8000"
        else:
            print(f"{CYAN}Starting local API server on 127.0.0.1:8998 for testing...{RESET}")
            server_mgr = LocalServerManager(port=8998)
            base_url = server_mgr.start()
            print(f"{GREEN}Local API server listening at {base_url}{RESET}")

    try:
        # Issue or obtain service token
        token = get_or_create_service_token(args.company_id)

        # Fetch reviews from database
        print(f"Fetching {args.total_reviews} real reviews from PostgreSQL database (Company {args.company_id})...")
        reviews = fetch_test_reviews(args.company_id, args.total_reviews, args.location_id)
        if not reviews:
            print(f"{RED}No eligible reviews found in DB for company {args.company_id}!{RESET}")
            return 1
        print(f"Fetched {len(reviews)} reviews successfully.")

        if args.mode == "single":
            results, summary = run_concurrent_stress_test(
                base_url=base_url,
                token=token,
                provider=args.provider,
                reviews=reviews,
                concurrency=args.concurrency,
                live_log=True,
            )
            print_scorecard(summary)
            json_file, md_file = save_reports(summary, results, Path(args.output_dir))
            print(f"{GREEN}✓ Performance report saved to:{RESET}\n  - {json_file}\n  - {md_file}\n")

        elif args.mode == "sweep":
            sweep_concurrencies = [int(x.strip()) for x in args.sweep_workers.split(",") if x.strip()]
            print(f"\n{BOLD}{CYAN}=== RUNNING CONCURRENCY SCALING SWEEP: {sweep_concurrencies} ==={RESET}\n")

            sweep_summaries: list[BenchmarkSummary] = []
            for c in sweep_concurrencies:
                print(f"\n{BOLD}>>> Concurrency Tier: {c} Workers <<<{RESET}")
                # Slice or reuse reviews
                sample_slice = reviews[:min(len(reviews), args.total_reviews)]
                _, summary = run_concurrent_stress_test(
                    base_url=base_url,
                    token=token,
                    provider=args.provider,
                    reviews=sample_slice,
                    concurrency=c,
                    live_log=True,
                )
                print_scorecard(summary)
                sweep_summaries.append(summary)

            # Print Sweep Comparison Table
            print(f"\n{BOLD}{MAGENTA}================================================================================{RESET}")
            print(f"{BOLD}{MAGENTA}                     CONCURRENCY SWEEP COMPARISON TABLE                         {RESET}")
            print(f"{BOLD}{MAGENTA}================================================================================{RESET}")
            print(f"{'CONCURRENCY':<12} {'RPS':<10} {'RPM':<12} {'p50 (s)':<10} {'p95 (s)':<10} {'p99 (s)':<10} {'TOK/SEC':<10} {'ERROR %':<10}")
            print("-" * 84)
            for s in sweep_summaries:
                print(
                    f"{s.concurrency:<12} "
                    f"{s.requests_per_second:<10} "
                    f"{s.reviews_per_minute:<12} "
                    f"{s.latency_p50_sec:<10.2f} "
                    f"{s.latency_p95_sec:<10.2f} "
                    f"{s.latency_p99_sec:<10.2f} "
                    f"{s.tokens_per_second:<10.1f} "
                    f"{s.error_rate_pct:<10.1f}"
                )
            print(f"{BOLD}{MAGENTA}================================================================================{RESET}\n")

        elif args.mode == "pending":
            print(f"\n{BOLD}{CYAN}=== RUNNING BATCH PENDING ENDPOINT TEST ==={RESET}\n")
            url = f"{base_url}/api/integration/v1/analysis/pending"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {"provider": args.provider, "location_id": args.location_id}

            print(f"Calling POST {url} with provider={args.provider}...")
            t0 = time.perf_counter()
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(url, headers=headers, json=payload)
            duration = time.perf_counter() - t0

            print(f"Status: {resp.status_code}")
            print(f"Total Duration: {duration:.2f}s")
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                print("Batch Result Data:")
                print(json.dumps(data, indent=2))
            else:
                print("Error Response:", resp.text)

    finally:
        if server_mgr:
            server_mgr.stop()


if __name__ == "__main__":
    sys.exit(main() or 0)
