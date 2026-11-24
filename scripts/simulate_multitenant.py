#!/usr/bin/env python3
"""Watch OneBox drive the real crawler contract using disposable, offline data."""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import re
import shutil
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# No application imports here: even importing app.config normally reads .env.
PREFIX = "/api/integration/v1"
PEPPER = "multitenant-simulation-only-pepper"
PROVISIONING_KEY = "vocprov_" + "simulation-only-" * 3


@dataclass
class Checks:
    passed: int = 0
    failed: int = 0

    def check(self, condition, explanation):
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  [{'PASS' if condition else 'FAIL'}] {explanation}")


@dataclass
class Report:
    scenarios: dict[str, bool] = field(default_factory=dict)
    passed_checks: int = 0
    failed_checks: int = 0
    database_path: str = ""
    engine_paths: list[str] = field(default_factory=list)
    database_removed: bool = False


def table(headers, rows):
    rows = [[str(value) for value in row] for row in rows]
    widths = [max([len(title), *(len(row[i]) for row in rows)]) for i, title in enumerate(headers)]
    print()
    for row in [headers, ["-" * width for width in widths], *rows]:
        print("  " + " | ".join(value.ljust(width) for value, width in zip(row, widths)))


@contextmanager
def isolated_application(database_path, engine_paths):
    """Install guards before app imports; restore process configuration on exit."""
    from sqlalchemy import Engine, event

    safe_env = {
        "DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
        "APP_ENV": "local", "SERVICE_TOKEN_PEPPER": PEPPER,
        "ONEBOX_TENANT_MODE": "managed", "REVIEW_SOURCE_MODE": "mock",
        "AUTO_ANALYZE_ON_CRAWL": "false", "APIFY_API_TOKENS": "",
        "CRAWL_MAX_CONCURRENCY_PER_TENANT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def deny_network(*args, **kwargs):
        raise RuntimeError("Simulation blocked an attempted network call")

    def guard_connect(dialect, connection_record, args, kwargs):
        if dialect.name != "sqlite" or not args or Path(args[0]).resolve() != database_path:
            raise RuntimeError("Simulation blocked a connection outside its temporary database")

    def guard_sql(connection, *args):
        url = connection.engine.url
        if url.get_backend_name() != "sqlite" or Path(url.database).resolve() != database_path:
            raise RuntimeError("Simulation blocked SQL outside its temporary database")
        engine_paths.add(str(Path(url.database).resolve()))

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, safe_env, clear=True))
        stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
        # config.py calls load_dotenv at import time; _EnvSettings itself has no env_file.
        stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
        stack.enter_context(patch("socket.socket.connect", deny_network))
        stack.enter_context(patch("socket.socket.connect_ex", deny_network))
        stack.enter_context(patch("socket.socket.sendto", deny_network))
        stack.enter_context(patch("socket.getaddrinfo", deny_network))
        # Suppress third-party logs; verbose output below uses an explicit field allowlist.
        stack.enter_context(patch("logging.Logger.handle", return_value=None))
        event.listen(Engine, "do_connect", guard_connect)
        event.listen(Engine, "before_cursor_execute", guard_sql)
        stack.callback(event.remove, Engine, "do_connect", guard_connect)
        stack.callback(event.remove, Engine, "before_cursor_execute", guard_sql)

        global Base, ApiClient, Company, Competitor, CrawlBatch, CrawlJob, FetchLog, Location, Review
        global select, delete, CrawlWorker, ApiClientService, FetchLogService
        from sqlalchemy import delete, select
        from app.config import get_settings
        from app.db.base import Base
        from app.db.models import ApiClient, Company, Competitor, CrawlBatch, CrawlJob, FetchLog, Location, Review
        from app.db.session import get_engine, get_session_factory
        from app.services.api_client_service import ApiClientService
        from app.services.crawl_worker import CrawlWorker
        from app.services.fetch_log_service import FetchLogService
        from app.services.tenant_registry_service import provisioning_key_hash

        os.environ["ONEBOX_PROVISIONING_KEY_HASH"] = provisioning_key_hash(PROVISIONING_KEY, PEPPER)
        for getter in (get_settings, get_engine, get_session_factory):
            getter.cache_clear()
            stack.callback(getter.cache_clear)
        settings = get_settings()
        engine = get_engine()
        stack.callback(engine.dispose)
        if (engine.url.get_backend_name() != "sqlite"
                or Path(engine.url.database).resolve() != database_path
                or settings.onebox_site_id is not None or settings.onebox_company_id is not None
                or settings.apify_api_tokens or settings.auto_analyze_on_crawl):
            raise RuntimeError("Unsafe simulation configuration; aborting before schema creation")
        Base.metadata.create_all(engine)
        from fastapi.testclient import TestClient
        from apps.api.main import create_app

        with TestClient(create_app(), base_url="http://simulation.invalid") as client:
            yield settings, engine, get_session_factory(), client


class FakeFetchService:
    """Produce fresh deterministic reviews without an external source or AI."""

    supports_parking = False

    def __init__(self, simulation, company_id):
        self.sim = simulation
        self.company_id = company_id

    def fetch_location(self, location_id, target=None, coverage="delta", budget=None,
                       review_quota_remaining=None, date_from=None, date_to=None,
                       sort_by="newest", on_progress=None):
        limits = [self.sim.reviews_per_location]
        limits.extend(value for value in (target, budget, review_quota_remaining) if value is not None)
        count = max(0, min(limits))
        logs = FetchLogService(self.company_id, self.sim.factory)
        log_id = logs.start_log(location_id, "simulation", {"coverage": coverage})
        rng = random.Random(f"{self.sim.seed}:{self.company_id}:{location_id}:{log_id}")
        now = datetime.now(timezone.utc)
        with self.sim.factory() as session:
            location = session.get(Location, location_id)
            if location is None or location.company_id != self.company_id:
                raise ValueError("Fake fetch target does not belong to tenant")
            for index in range(count):
                identity = f"sim:{self.sim.seed}:{self.company_id}:{location_id}:{log_id}:{index}"
                session.add(Review(
                    company_id=self.company_id, location_id=location_id, source="simulation",
                    external_place_id=location.external_place_id, external_review_id=identity,
                    review_hash=hashlib.sha256(identity.encode()).hexdigest(),
                    review_text=f"Simulated review {index + 1} for {location.branch_name}",
                    reviewer_name=f"Simulated visitor {rng.randrange(10000)}", rating=rng.randint(1, 5),
                    review_time=now, created_at=now, sync_updated_at=now,
                ))
            session.commit()
        result = {
            "status": "success", "total_fetched": count, "total_inserted": count,
            "total_duplicate": 0, "total_failed": 0,
            "metadata": {"coverage": coverage, "reviews_scanned": count,
                         "stop_reason": "quota_exhausted" if review_quota_remaining == count else "target_reached"},
        }
        logs.finish_log(log_id, result)
        self.sim.fetch_calls.append({"company_id": self.company_id, "coverage": coverage,
                                     "fetched": count, "quota": review_quota_remaining})
        if on_progress:
            on_progress(count, count, count)
        if self.sim.on_fetch:
            self.sim.on_fetch()
        return result


class Simulation:
    def __init__(self, settings, engine, factory, client, checks, seed, tenants, verbose, reviews_per_location):
        self.settings, self.engine, self.factory, self.client = settings, engine, factory, client
        self.checks, self.seed, self.tenant_count, self.verbose = checks, seed, tenants, verbose
        self.reviews_per_location = reviews_per_location
        self.fetch_calls = []
        self.on_fetch = None
        self.worker = CrawlWorker(factory, settings, lambda company_id: FakeFetchService(self, company_id))

    def api(self, method, path, token=PROVISIONING_KEY, body=None, expected=200, key=None):
        headers = {"Authorization": f"Bearer {token}"}
        if key:
            headers["Idempotency-Key"] = key
        response = self.client.request(method, PREFIX + path, headers=headers, json=body)
        if self.verbose:
            data = response.json().get("data", response.json().get("error", {}))
            keys = ("code", "status", "site_id", "company_id", "batch_id", "weight",
                    "snapshot_version", "fetched", "upserted", "deactivated")
            summary = {key: data[key] for key in keys if isinstance(data, dict) and key in data}
            sent = {key: body[key] for key in ("snapshot_version", "crawl_mode", "review_quota_remaining")
                    if isinstance(body, dict) and key in body}
            if isinstance(body, dict) and "targets" in body:
                sent["targets"] = len(body["targets"])
            print(f"    {method} {path} -> {response.status_code} sent={sent} result={summary}")
        if response.status_code != expected:
            self.checks.check(False, f"{method} {path}: expected HTTP {expected}, got {response.status_code}")
            raise RuntimeError("Unexpected HTTP status (response omitted to avoid printing secrets)")
        return response.json()

    def register(self, site, name):
        data = self.api("POST", "/tenants", body={"site_id": site, "site_name": name}, expected=201)["data"]
        return {"site": site, "name": name, "company": data["company_id"],
                "token": data["token"]["value"], "label": name.split()[0]}

    def tenants(self, locations=0):
        sites = [169, 177, 201] + list(range(1001, 1001 + self.tenant_count - 3))
        names = ["T1 Alpha Health", "T2 Beta Retail", "T3 Gamma Care"]
        tenants = [self.register(site, names[i] if i < 3 else f"T{i + 1} Extra")
                   for i, site in enumerate(sites)]
        if locations:
            for tenant in tenants:
                self.push(tenant, 1, [item(tenant, i) for i in range(locations)])
        return tenants

    def state(self, tenant):
        return self.api("GET", f"/tenants/{tenant['site']}")["data"]

    def push(self, tenant, version, items, expected=200, token=None):
        return self.api("PUT", "/worklist", token or tenant["token"],
                        {"snapshot_version": version, "items": items, "taxonomies": {}}, expected)["data"]

    def enqueue(self, tenant, key, indices=(0, 1), mode="regular_delta", budget=5, quota=None, expected=202):
        body = {"slot": "manual", "crawl_mode": mode,
                "targets": [{"onebox_location_id": location_number(tenant, index), "budget": budget}
                            for index in indices]}
        if quota is not None:
            body["review_quota_remaining"] = quota
        return self.api("POST", "/crawl-jobs", tenant["token"], body, expected, key)

    def batch(self, tenant, batch):
        return self.api("GET", f"/crawl-jobs/{batch['batch_id']}", tenant["token"])["data"]

    def drain(self):
        for _ in range(1000):
            result = self.worker.execute_next(worker_id="simulation-worker")
            if result is None:
                return
        raise RuntimeError("Simulation drain exceeded its finite job bound")

    def locations(self, tenant):
        with self.factory() as session:
            return list(session.scalars(select(Location).where(Location.company_id == tenant["company"])
                                        .order_by(Location.id)))

    def reviews(self, tenant):
        return self.api("GET", "/reviews?limit=200", tenant["token"])["data"]


def location_number(tenant, index):
    return tenant["site"] * 10000 + index + 1


def item(tenant, index, competitor=False):
    return {"kind": "competitor" if competitor else "location",
            "external_place_id": f"sim-place-{tenant['site']}-{index}",
            "branch_name": f"{tenant['label']} Branch {index + 1}",
            "organization_name": tenant["name"], "onebox_connection_id": tenant["site"],
            "onebox_location_id": location_number(tenant, index),
            "onebox_target_id": location_number(tenant, index),
            "active": True, "crawl_enabled": True, "ingest_reviews": not competitor}


def provisioning(sim):
    """Register sites and demonstrate credential lifetime and platform-only access."""
    tenants = sim.tenants()
    for tenant in tenants:
        repeated = sim.api("POST", "/tenants", body={"site_id": tenant["site"], "site_name": tenant["name"]})["data"]
        state = sim.state(tenant)
        sim.checks.check(repeated["token"] is None and repeated["company_id"] == tenant["company"],
                         f"{tenant['label']}: registration issues a token once; repeat is idempotent")
        sim.checks.check(state["is_active"] and state["weight"] == 1 and "token" not in state
                         and state["usage"]["backfill_fetched_total"] == state["usage"]["operating_fetched_month"] == 0
                         and state["worklist"]["items"] == 0 and state["worklist"]["snapshot_version"] is None,
                         f"{tenant['label']}: GET has default weight, empty worklist, zero usage and no token")
    for tenant, weight in zip(tenants, (1, 2, 1)):
        state = sim.api("PATCH", f"/tenants/{tenant['site']}", body={"weight": weight})["data"]
        sim.checks.check(state["weight"] == weight, f"{tenant['label']}: package weight {weight} persisted")
    a = tenants[0]
    rotated = sim.api("POST", f"/tenants/{a['site']}/token:rotate", body={"overlap_hours": 1})["data"]
    new_token = rotated["token"]["value"]
    old_identity = sim.api("GET", "/whoami", a["token"])
    new_identity = sim.api("GET", "/whoami", new_token)
    with sim.factory() as session:
        old_client = session.scalar(select(ApiClient).where(ApiClient.company_id == a["company"])
                                    .order_by(ApiClient.id))
        expires = old_client.expires_at.replace(tzinfo=timezone.utc)
        overlap_seconds = (expires - datetime.now(timezone.utc)).total_seconds()
        # SETUP: advance just this credential's expiry instead of sleeping an hour.
        old_client.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    sim.checks.check(old_identity["company_id"] == new_identity["company_id"] == a["company"]
                     and 0 < overlap_seconds <= 3600 and new_token != a["token"],
                     "Rotation keeps both tokens valid during a bounded one-hour overlap")
    expired = sim.api("GET", "/whoami", a["token"], expected=401)
    sim.checks.check(expired["error"]["code"] == "INVALID_SERVICE_TOKEN",
                     "Old token fails after simulated expiry (no sleep)")
    a["token"] = new_token
    denied = sim.api("GET", f"/tenants/{a['site']}", a["token"], expected=401)
    sim.checks.check(denied["error"]["code"] == "INVALID_PROVISIONING_KEY", "Tenant token cannot provision tenants")
    table(["site", "company_id", "weight", "active", "token key id"],
          [(t["site"], t["company"], (s := sim.state(t))["weight"], s["is_active"], s["credential"]["key_id"])
           for t in tenants])


def worklist_signature(sim, tenant):
    with sim.factory() as session:
        locations = list(session.execute(select(Location.id, Location.external_place_id, Location.is_active,
                                                Location.crawl_enabled).where(Location.company_id == tenant["company"])))
        competitors = list(session.execute(select(Competitor.id, Competitor.external_place_id, Competitor.is_active)
                                           .where(Competitor.company_id == tenant["company"])))
    state = sim.state(tenant)["worklist"]
    return locations, competitors, state["snapshot_version"], state["items"]


def worklist(sim):
    """Apply atomic versioned snapshots, removals, tenant isolation and scopes."""
    a, b, *_ = sim.tenants()
    rows = []
    initial = [item(a, 0), item(a, 1), item(a, 2, competitor=True)]
    for version, items, outcome in ((1, initial, "applied"), (1, [], "stale"), (2, [initial[0], initial[2]], "applied")):
        before = worklist_signature(sim, a)
        data = sim.push(a, version, items)
        signature = worklist_signature(sim, a)
        expected_counts = (3, 3, 0) if version == 1 else (2, 2, 1)
        counts_ok = ((data["fetched"], data["upserted"], data["deactivated"]) == expected_counts
                     if outcome == "applied" else before == signature and data["upserted"] == 0)
        sim.checks.check(data["status"] == outcome and counts_ok
                         and len(signature[0]) == 2 and len(signature[1]) == 1,
                         f"T1 snapshot v{version}: {outcome}, including correct counts/no-op semantics")
        rows.append(("T1", version, outcome, sim.state(a)["worklist"]["items"]))
    removed = sim.locations(a)[1]
    rejected = sim.enqueue(a, "removed-target", indices=(1,), expected=404)
    sim.checks.check(not removed.is_active and not removed.crawl_enabled
                     and rejected["error"]["code"] == "TARGET_NOT_FOUND", "Removed branch is retained but no longer crawlable")
    before = worklist_signature(sim, a)
    malformed = {**item(a, 9), "external_place_id": ""}
    error = sim.api("PUT", "/worklist", a["token"],
                    {"snapshot_version": 3, "items": [item(a, 8), malformed], "taxonomies": {}}, expected=400)
    sim.checks.check(error["error"]["code"] == "INVALID_SNAPSHOT" and "external_place_id" in error["error"]["message"]
                     and before == worklist_signature(sim, a), "Invalid snapshot is rejected atomically with a contract error")
    rows.append(("T1", 3, "INVALID_SNAPSHOT", sim.state(a)["worklist"]["items"]))
    for version, items in ((1, [item(b, 0)]), (2, [])):
        data = sim.push(b, version, items)
        rows.append(("T2", version, data["status"], sim.state(b)["worklist"]["items"]))
    sim.checks.check(before == worklist_signature(sim, a), "T2 pushes and removals never change T1 items/version")
    # SETUP: a deliberately restricted credential, issued by the real token service.
    read_only = ApiClientService(sim.factory, sim.settings).issue(a["company"], "simulation-read", ["reviews:read"])
    denied = sim.api("PUT", "/worklist", read_only.token, {"snapshot_version": 3, "items": [], "taxonomies": {}}, expected=403)
    sim.checks.check(denied["error"]["code"] == "INSUFFICIENT_SCOPE" and before == worklist_signature(sim, a),
                     "Token without worklist:write gets 403 and changes nothing")
    rows.append(("T1 read-only", 3, "INSUFFICIENT_SCOPE", sim.state(a)["worklist"]["items"]))
    table(["tenant", "version sent", "outcome", "items"], rows)


def leaks_ids(body, protected):
    if isinstance(body, dict):
        return any(leaks_ids(value, protected) for key, value in body.items() if key != "request_id")
    if isinstance(body, list):
        return any(leaks_ids(value, protected) for value in body)
    if isinstance(body, str):
        return any(re.search(r"(?<!\w)" + re.escape(str(value)) + r"(?!\w)", body) for value in protected)
    return body in protected if isinstance(body, int) else False


def isolation(sim):
    """Try real tenant tokens against both owned and foreign resources."""
    a, b, *_ = sim.tenants(locations=2)
    batches = {}
    for tenant in (a, b):
        batches[tenant["site"]] = sim.enqueue(tenant, f"isolation-{tenant['site']}")["data"]
    sim.drain()
    rows = []
    for owner in (a, b):
        own_reviews = sim.reviews(owner)
        own_locations = {location.id for location in sim.locations(owner)}
        sim.checks.check(bool(own_reviews) and all(review["location_id"] in own_locations for review in own_reviews),
                         f"{owner['label']}: unfiltered reviews contain only owned locations")
        for target in (a, b):
            own = owner == target
            location = sim.locations(target)[0]
            batch_id = batches[target["site"]]["batch_id"]
            protected = {target["company"], batch_id}
            for foreign_location in sim.locations(target):
                protected.update((foreign_location.id, foreign_location.onebox_location_id, foreign_location.external_place_id))
            with sim.factory() as session:
                for review in session.scalars(select(Review).where(Review.company_id == target["company"])):
                    protected.update((review.id, review.external_review_id, review.review_hash))
            operations = [
                ("resolve location", "GET", f"/locations/{location.onebox_location_id}", None),
                ("read reviews", "GET", f"/reviews?location_id={location.id}", None),
                ("enqueue", "POST", "/crawl-jobs", {"targets": [{"onebox_location_id": location.onebox_location_id}]}),
                ("read batch", "GET", f"/crawl-jobs/{batch_id}", None),
            ]
            for operation, method, path, body in operations:
                expected = (202 if method == "POST" else 200) if own else 404
                result = sim.api(method, path, owner["token"], body, expected,
                                 f"isolation-{owner['site']}-{target['site']}")
                safe = own or ("error" in result and not leaks_ids(result, protected))
                sim.checks.check(safe, f"{owner['label']} -> {target['label']} {operation}: "
                                 + ("allowed" if own else "denied without foreign IDs"))
                rows.append((owner["label"], target["label"], operation, "allowed" if own else "denied"))
    table(["token owner", "target tenant", "operation", "access"], rows)


def crawl(sim):
    """Drain backfill and delta batches, then reconcile reviews and fetched usage."""
    a, b, *_ = sim.tenants(locations=2)
    before = {t["site"]: sim.state(t)["usage"] for t in (a, b)}
    timeline = []
    for mode, budget in (("initial_backfill", 5), ("regular_delta", 3)):
        key = f"crawl-{mode}"
        batch = sim.enqueue(a, key, mode=mode, budget=budget)["data"]

        def observe():
            state = sim.batch(a, batch)
            timeline.append((mode, state["status"], ",".join(j["status"] for j in state["jobs"]), state["review_counts"]["fetched"]))

        observe()
        sim.on_fetch = observe
        sim.drain()
        sim.on_fetch = None
        observe()
        final = sim.batch(a, batch)
        replay = sim.enqueue(a, key, mode=mode, budget=budget)["data"]
        sim.checks.check(final["status"] == "completed" and final["counts"]["succeeded"] == 2
                         and final["review_counts"]["fetched"] == 2 * budget,
                         f"{mode}: two real worker jobs finish and honour target={budget}")
        sim.checks.check(replay["batch_id"] == batch["batch_id"] and replay["reused_existing_job"],
                         f"{mode}: idempotent HTTP replay returns the same batch")
    after = {t["site"]: sim.state(t)["usage"] for t in (a, b)}
    fetched = Counter()
    for call in sim.fetch_calls:
        fetched[call["coverage"]] += call["fetched"]
    sim.checks.check(after[a["site"]]["backfill_fetched_total"] == fetched["full_backfill"] == 10
                     and after[a["site"]]["operating_fetched_month"] == fetched["delta"] == 6,
                     "HTTP usage exactly matches fake full_backfill and delta fetched counts")
    sim.checks.check(len(sim.reviews(a)) == 16 and sim.reviews(b) == [] and before[b["site"]] == after[b["site"]],
                     "Reviews and usage appear for T1 only")
    sim.checks.check(any(row[1] == "running" for row in timeline), "HTTP polling observes running jobs before completion")
    table(["mode", "batch status", "job statuses", "fetched"], timeline)
    table(["tenant", "when", "backfill fetched", "operating fetched", "UTC month"],
          [(t["label"], when, usage[t["site"]]["backfill_fetched_total"], usage[t["site"]]["operating_fetched_month"],
            usage[t["site"]]["operating_period"]) for t in (a, b) for when, usage in (("before", before), ("after", after))])


def job_counts(sim, tenant):
    with sim.factory() as session:
        return Counter(session.scalars(select(CrawlJob.status).where(CrawlJob.company_id == tenant["company"])))


def deactivation(sim):
    """Cancel waiting work while preserving a running job, reads and other tenants."""
    a, b, *_ = sim.tenants(locations=4)
    sim.enqueue(b, "deactivation-seed")
    sim.drain()
    review_count = len(sim.reviews(b))
    mixed = sim.enqueue(b, "deactivation-mixed", indices=range(4))["data"]
    claimed = sim.worker.claim_next(worker_id="simulation-in-flight")
    if claimed is None or claimed.company_id != b["company"]:
        raise RuntimeError("Expected an in-flight T2 job")
    print("  SETUP: move two queued siblings to retry_wait / awaiting_source; no external run exists.")
    with sim.factory() as session:
        for job, status in zip(mixed["jobs"][2:], ("retry_wait", "awaiting_source")):
            session.get(CrawlJob, job["job_id"]).status = status
        session.commit()
    waiting = sim.enqueue(b, "deactivation-waiting", indices=(0, 1))["data"]
    sim.enqueue(a, "deactivation-other", indices=(0, 1))
    a_before = job_counts(sim, a)
    before = job_counts(sim, b)
    sim.api("PATCH", f"/tenants/{b['site']}", body={"active": False})
    after = job_counts(sim, b)
    waiting_count = sum(before[status] for status in ("queued", "retry_wait", "awaiting_source"))
    sim.checks.check(waiting_count > 0 and after["cancelled"] == waiting_count
                     and all(after[status] == 0 for status in ("queued", "retry_wait", "awaiting_source"))
                     and after["running"] == before["running"] == 1, "Deactivation cancels all waiting states and leaves the running job alone")
    sim.checks.check(sim.batch(b, mixed)["status"] == "running" and sim.batch(b, waiting)["status"] == "cancelled",
                     "Mixed batch stays running; a wholly waiting batch becomes cancelled")
    result = FakeFetchService(sim, b["company"]).fetch_location(claimed.location_id, target=claimed.target_review_count,
                                                               coverage=claimed.coverage)
    sim.worker._finish(claimed, status="succeeded", result=result)
    sim.checks.check(sim.batch(b, mixed)["status"] == "cancelled" and job_counts(sim, b)["running"] == 0,
                     "In-flight job can finish; cancelled siblings make the final mixed batch cancelled")
    denied_enqueue = sim.enqueue(b, "inactive-new-key", expected=409)
    denied_push = sim.api("PUT", "/worklist", b["token"], {"snapshot_version": 2, "items": [], "taxonomies": {}}, expected=409)
    sim.checks.check(denied_enqueue["error"]["code"] == denied_push["error"]["code"] == "TENANT_INACTIVE",
                     "Inactive tenant enqueue and worklist push both answer 409 TENANT_INACTIVE")
    sim.checks.check(len(sim.locations(b)) == 4 and len(sim.reviews(b)) == review_count + result["total_inserted"],
                     "T2 data stays and its token can still read reviews/locations/batches")
    sim.api("GET", f"/locations/{location_number(b, 0)}", b["token"])
    sim.checks.check(job_counts(sim, a) == a_before and sim.state(a)["is_active"]
                     and sim.state(a)["usage"]["operating_fetched_month"] == 0, "T1 jobs, active state and usage are untouched")
    sim.api("PATCH", f"/tenants/{b['site']}", body={"active": True})
    new_batch = sim.enqueue(b, "reactivated-new-key")["data"]
    sim.checks.check(job_counts(sim, b)["cancelled"] == waiting_count and new_batch["status"] == "queued",
                     "Reactivation preserves cancellations; a new enqueue works")
    table(["T2 internal state", "before", "inactive", "reactivated"],
          [(status, before[status], after[status], job_counts(sim, b)[status])
           for status in ("queued", "retry_wait", "awaiting_source", "running", "succeeded", "cancelled")])
    table(["batch", "after deactivation", "after in-flight completion"],
          [("mixed", "running", sim.batch(b, mixed)["status"]), ("waiting only", "cancelled", sim.batch(b, waiting)["status"])])


def clear_queue(sim):
    print("  SETUP: clear disposable jobs/batches between independent claim experiments.")
    with sim.factory() as session:
        session.execute(delete(CrawlJob))
        session.execute(delete(CrawlBatch))
        session.commit()


def fairness(sim):
    """Measure weighted claims, delta priority, live caps and a large-queue neighbour."""
    tenants = sim.tenants()
    weights = list(range(1, len(tenants) + 1))
    sample_size = 10 * sum(weights)
    queue_size = max(10, 10 * max(weights) + 3)
    for tenant, weight in zip(tenants, weights):
        sim.api("PATCH", f"/tenants/{tenant['site']}", body={"weight": weight})
        sim.push(tenant, 1, [item(tenant, i) for i in range(queue_size)])
        sim.enqueue(tenant, f"fair-backfill-{tenant['site']}", range(queue_size), "initial_backfill")
    sim.enqueue(tenants[0], "fair-newer-delta", range(3))
    by_company = {tenant["company"]: tenant for tenant in tenants}
    claims = []
    for _ in range(sample_size):
        claimed = sim.worker.claim_next(worker_id="simulation-fairness")
        if claimed is None:
            break
        claims.append(claimed)
    sequence = [by_company[c.company_id]["label"] for c in claims]
    print("  Claims: " + " ".join(sequence))
    counts = Counter(c.company_id for c in claims)
    sim.checks.check(len(claims) == sample_size and all(abs(counts[t["company"]] - 10 * w) <= 1
                     for t, w in zip(tenants, weights)), "Claim shares follow tenant weights (within one claim)")
    table(["tenant", "weight", "claims", "expected", "actual share", "expected share"],
          [(t["label"], w, counts[t["company"]], 10 * w, f"{counts[t['company']] / sample_size:.1%}",
            f"{w / sum(weights):.1%}") for t, w in zip(tenants, weights)])
    priority_rows = []
    for tenant in tenants:
        positions = [i for i, c in enumerate(claims, 1) if c.company_id == tenant["company"] and c.crawl_mode == "regular_delta"]
        backfills = [i for i, c in enumerate(claims, 1) if c.company_id == tenant["company"] and c.crawl_mode == "initial_backfill"]
        priority_rows.append((tenant["label"], ",".join(map(str, positions)) or "none queued", min(backfills) if backfills else "none"))
        if tenant == tenants[0]:
            sim.checks.check(len(positions) == 3 and bool(backfills) and max(positions) < min(backfills),
                             "T1's three newer delta jobs are claimed before its older backfill jobs")
    table(["tenant", "delta claim positions", "first backfill position"], priority_rows)
    clear_queue(sim)
    for tenant in tenants:
        sim.enqueue(tenant, f"cap-backfill-{tenant['site']}", range(10), "initial_backfill")
    capped = CrawlWorker(sim.factory, sim.settings.model_copy(update={"crawl_max_concurrency_per_tenant": 2}),
                         lambda company_id: FakeFetchService(sim, company_id))
    cap_sequence, peak = [], Counter()
    for _ in range(2 * len(tenants) + 1):
        claimed = capped.claim_next(worker_id="simulation-cap")
        if claimed is None:
            break
        cap_sequence.append(by_company[claimed.company_id]["label"])
        for tenant in tenants:
            peak[tenant["company"]] = max(peak[tenant["company"]], job_counts(sim, tenant)["running"])
    sim.checks.check(all(peak[t["company"]] == 2 for t in tenants) and len(cap_sequence) == 2 * len(tenants)
                     and capped.claim_next(worker_id="simulation-cap-full") is None,
                     "Cap=2 never exceeds two live jobs per tenant; every other tenant is served")
    print("  Cap=2 claims (left running): " + " ".join(cap_sequence))
    table(["tenant", "peak running", "cap", "still waiting"],
          [(t["label"], peak[t["company"]], 2, job_counts(sim, t)["queued"]) for t in tenants])
    clear_queue(sim)
    large, small = tenants[:2]
    for tenant in (large, small):
        sim.api("PATCH", f"/tenants/{tenant['site']}", body={"weight": 1})
    sim.push(large, 2, [item(large, i) for i in range(300)])
    sim.enqueue(large, "huge-backfill-queue", range(300), "initial_backfill")
    sim.enqueue(small, "small-delta-queue", range(5))
    positions, sequence = [], []
    for position in range(1, 16):
        claimed = sim.worker.claim_next(worker_id="simulation-neighbour")
        if claimed is None:
            break
        sequence.append(by_company[claimed.company_id]["label"])
        if claimed.company_id == small["company"]:
            positions.append(position)
        if len(positions) == 5:
            break
    print("  300-vs-5 claims: " + " ".join(sequence))
    sim.checks.check(len(positions) == 5 and positions[0] <= 2 and positions[-1] <= 10,
                     "A 300-job backfill neighbour lets all five small-tenant deltas through within ten claims")
    table(["tenant", "queued at start", "mode", "claim positions"],
          [(large["label"], 300, "initial_backfill", ",".join(str(i) for i, label in enumerate(sequence, 1) if label == large["label"])),
           (small["label"], 5, "regular_delta", ",".join(map(str, positions)))])


def quota_state(used, cap, alert_percent):
    return "pause" if used >= cap else "alert" if used * 100 >= cap * alert_percent else "normal"


def inject_usage(sim, tenant, coverage, fetched, **extra):
    now = datetime.now(timezone.utc)
    with sim.factory() as session:
        session.add(FetchLog(company_id=tenant["company"], location_id=sim.locations(tenant)[0].id,
                             source="simulation-setup", status=extra.pop("status", "success"),
                             total_fetched=fetched, total_inserted=0, metadata_json={"coverage": coverage},
                             started_at=extra.pop("started_at", now), finished_at=now, **extra))
        session.commit()


def quota(sim, location_counts=(10, 100, 310)):
    """Apply OneBox's caps and proposed Jev budget to HTTP-reported crawler usage."""
    tenants = sim.tenants(locations=3)[:3]
    print("  SETUP: inject aggregate fetch_logs (no review rows) for normal, alert and over-cap usage.")
    print("  Jev is an estimate if all shown fetched reviews were analyzed this month; no AI runs.")
    rows = []
    for tenant, locations in zip(tenants, location_counts):
        backfill_cap, operating_cap = max(100000, 2500 * locations), 2000 * locations
        previous_backfill = previous_operating = 0
        # SETUP: prove excluded dry runs, legacy coverage and earlier-month deltas do not inflate usage.
        inject_usage(sim, tenant, "delta", 987, status="dry_run")
        inject_usage(sim, tenant, "legacy", 654)
        inject_usage(sim, tenant, "delta", 321, started_at=datetime.now(timezone.utc).replace(day=1) - timedelta(days=2))
        for stage, backfill_percent, operating_percent in (("normal", 10, 10), ("alert", 81, 51), ("pause", 101, 101)):
            backfill_used, operating_used = backfill_cap * backfill_percent // 100, operating_cap * operating_percent // 100
            # SETUP: backfill is lifetime; an earlier-month backfill must still count.
            inject_usage(sim, tenant, "full_backfill", backfill_used - previous_backfill,
                         started_at=datetime.now(timezone.utc) - timedelta(days=65))
            delta = operating_used - previous_operating
            inject_usage(sim, tenant, "delta", delta // 2)
            inject_usage(sim, tenant, "date_window", delta - delta // 2)
            usage = sim.state(tenant)["usage"]
            bk, op = usage["backfill_fetched_total"], usage["operating_fetched_month"]
            bk_state, op_state = quota_state(bk, backfill_cap, 80), quota_state(op, operating_cap, 50)
            sim.checks.check((bk, op) == (backfill_used, operating_used) and bk_state == op_state == stage
                             and usage["operating_period"] == datetime.now(timezone.utc).strftime("%Y-%m"),
                             f"{tenant['label']} ({locations} locations): HTTP usage -> OneBox {stage}")
            jev_cost = (bk + op) * 1000 * 0.042 / 1000000
            jev_budget = max(10, 0.25 * locations)
            rows.append((tenant["label"], locations, f"{bk:,} / {backfill_cap:,} / {bk / backfill_cap:.0%} / {bk_state}",
                         f"{op:,} / {operating_cap:,} / {op / operating_cap:.0%} / {op_state}", f"${jev_cost:.2f} / ${jev_budget:.2f}"))
            previous_backfill, previous_operating = backfill_used, operating_used
    sim.checks.check(quota_state(50, 100, 50) == "alert" and quota_state(80, 100, 80) == "alert"
                     and quota_state(100, 100, 50) == quota_state(100, 100, 80) == "pause",
                     "OneBox alerts at exactly 50% operating / 80% backfill and pauses at exactly 100%")
    table(["tenant", "locations", "backfill used / cap / percent / state", "operating used / cap / percent / state", "Jev dollars / budget"], rows)
    jev_rows = []
    for percent, expected_state in ((79, "normal"), (80, "alert"), (100, "pause")):
        state = quota_state(percent, 100, 80)
        jev_rows.append((f"{percent}%", state, state != "pause", True))
        sim.checks.check(state == expected_state, f"OneBox Jev policy at {percent}%: {state}; ingestion remains enabled")
    table(["Jev budget used", "state", "analysis allowed", "ingestion allowed"], jev_rows)
    a = tenants[0]
    operating_cap = 2000 * location_counts[0]
    print("\n  SETUP: reset only T1's synthetic operating logs for an independent near-cap batch.")
    with sim.factory() as session:
        session.execute(delete(FetchLog).where(FetchLog.company_id == a["company"],
                        FetchLog.metadata_json["coverage"].as_string().in_(["delta", "date_window"])))
        session.commit()
    inject_usage(sim, a, "delta", operating_cap - 7)
    remaining = operating_cap - sim.state(a)["usage"]["operating_fetched_month"]
    batch = sim.enqueue(a, "quota-final-seven", indices=range(3), quota=remaining)["data"]
    sim.drain()
    final = sim.batch(a, batch)
    calls = sim.fetch_calls
    usage = sim.state(a)["usage"]["operating_fetched_month"]
    sim.checks.check([c["quota"] for c in calls] == [7, 2, 0] and [c["fetched"] for c in calls] == [5, 2, 0]
                     and final["status"] == "completed" and final["review_counts"]["fetched"] == remaining
                     and usage == operating_cap, "Worker passes remaining batch quota 7 -> 2 -> 0; fake stops exactly at the operating cap")
    sim.checks.check(quota_state(usage, operating_cap, 50) == "pause", "OneBox now pauses new operating crawls at 100%")
    table(["job", "target", "quota received", "fetched"], [(i, 5, c["quota"], c["fetched"]) for i, c in enumerate(calls, 1)])


SCENARIOS = {function.__name__: function for function in
             (provisioning, worklist, isolation, crawl, deactivation, fairness, quota)}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, nargs="+", action="extend", help="Run selected scenarios in the given order")
    parser.add_argument("--list", action="store_true", help="List scenarios without loading the application")
    parser.add_argument("--tenants", type=int, default=3, help="Tenants to provision (at least 3); fairness weights are 1..N")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic fake review seed (default: 42)")
    parser.add_argument("--keep-db", action="store_true", help="Retain the temporary SQLite file and print its path")
    parser.add_argument("--verbose", action="store_true", help="Print safe HTTP request/response summaries")
    return parser


def run(args=None, *, reviews_per_location=8):
    """Run selected scenarios and return checks plus evidence of database isolation."""
    args = build_parser().parse_args(args) if not isinstance(args, argparse.Namespace) else args
    if args.list:
        for name, scenario in SCENARIOS.items():
            print(f"{name:14} {scenario.__doc__}")
        return Report()
    if args.tenants < 3:
        raise ValueError("--tenants must be at least 3 for these scenarios")
    if reviews_per_location < 5:
        raise ValueError("Scenarios require reviews_per_location >= 5")
    names = args.scenario or list(SCENARIOS)
    directory = Path(tempfile.mkdtemp(prefix="multitenant-simulation-")).resolve()
    database_path = directory / "simulation.sqlite3"
    report = Report(database_path=str(database_path))
    engine_paths = set()
    checks = Checks()
    print(f"Multi-tenant crawler simulation | seed={args.seed} | tenants={args.tenants}")
    print("Offline TestClient + fake fetch; isolated temporary SQLite; automatic analysis disabled.")
    try:
        with isolated_application(database_path, engine_paths) as (settings, engine, factory, client):
            checks.check(Path(engine.url.database).resolve() == database_path, "Engine verified against the temporary SQLite path before any scenario")
            for name in names:
                print(f"\n=== {name}: {SCENARIOS[name].__doc__} ===")
                Base.metadata.drop_all(engine)
                Base.metadata.create_all(engine)
                previous_failures = checks.failed
                sim = Simulation(settings, engine, factory, client, checks, args.seed, args.tenants, args.verbose, reviews_per_location)
                try:
                    SCENARIOS[name](sim)
                except Exception as exc:
                    checks.check(False, f"{name} aborted ({type(exc).__name__}); inspect the preceding check")
                report.scenarios[name] = checks.failed == previous_failures
    finally:
        if args.keep_db:
            print(f"\nRetained temporary database: {database_path}")
        else:
            shutil.rmtree(directory)
        report.database_removed = not database_path.exists()
        report.engine_paths = sorted(engine_paths)
    report.passed_checks, report.failed_checks = checks.passed, checks.failed
    print(f"\nSummary: {sum(report.scenarios.values())}/{len(names)} scenarios passed; "
          f"{checks.passed} checks passed / {checks.failed} failed.")
    print("Temporary database removed." if report.database_removed else "Temporary database kept for inspection.")
    return report


if __name__ == "__main__":
    sys.exit(1 if run().failed_checks else 0)
