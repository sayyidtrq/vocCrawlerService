from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlBatch, CrawlJob
from app.services.crawl_result import (
    matched_count,
    rating_snapshot,
    scanned_count,
    stop_reason,
)


def serialize_batch(
    session: Session, batch: CrawlBatch, include_jobs: bool = True
) -> dict:
    jobs = list(
        session.scalars(
            select(CrawlJob)
            .where(CrawlJob.batch_id == batch.id)
            .order_by(CrawlJob.id)
        )
    )
    counts = {
        status: 0
        for status in (
            "queued",
            "running",
            "retry_wait",
            "succeeded",
            "partial_success",
            "skipped",
            "failed",
        )
    }
    review_counts = {
        "target": 0,
        "scanned": 0,
        "fetched": 0,
        "matched": 0,
        "out_of_range": 0,
        "out_of_range_newer": 0,
        "out_of_range_older": 0,
        "inserted": 0,
        "duplicate": 0,
        "failed": 0,
    }
    for job in jobs:
        counts[job.status] = counts.get(job.status, 0) + 1
        review_counts["target"] += job.target_review_count
        result = job.result_json or {}
        # Job yang masih berjalan belum punya total_fetched; yang ada baru
        # progress_fetched dari loop gulir. Dipakai supaya layar bisa
        # menampilkan "n dari target" selagi crawl berlangsung.
        review_counts["fetched"] += int(
            result.get("total_fetched") or result.get("progress_fetched") or 0
        )
        metadata = result.get("metadata") or {}
        out_of_range_count = int(result.get("total_skipped_out_of_range") or 0)
        review_counts["scanned"] += scanned_count(result)
        review_counts["matched"] += matched_count(result)
        review_counts["out_of_range"] += out_of_range_count
        review_counts["out_of_range_newer"] += int(
            metadata.get("out_of_range_newer") or 0
        )
        review_counts["out_of_range_older"] += int(
            metadata.get("out_of_range_older") or 0
        )
        review_counts["inserted"] += int(result.get("total_inserted") or 0)
        review_counts["duplicate"] += int(result.get("total_duplicate") or 0)
        review_counts["failed"] += int(result.get("total_failed") or 0)
    batch_stop_reason, stop_reasons = batch_stop_reasons(jobs)
    limits = {
        "max_reviews_to_collect": review_counts["target"],
        "scan_limit": sum(
            int(((job.result_json or {}).get("request") or {}).get("scan_limit") or 0)
            for job in jobs
        ),
    }
    data = {
        "batch_id": batch.public_id,
        "status": batch.status,
        "slot": batch.slot,
        "job_count": len(jobs),
        "counts": counts,
        "review_counts": review_counts,
        "created_at": batch.created_at,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
        "stop_reason": batch_stop_reason,
        "stop_reasons": stop_reasons,
        # Jobs sudah dimuat di atas, jadi ini tidak menambah query.
        # Disertakan juga saat include_jobs False: daftar batch tanpa
        # penyebut cabang memaksa OneBox memanggil detail tiap batch.
        "targets": [
            job.onebox_location_id
            for job in jobs
            if job.onebox_location_id is not None
        ],
        # Jenis batch, supaya daftar riwayat bisa dipisah tanpa memanggil
        # detail tiap batch. Tanpa ini pemanggil hanya bisa menebak dari
        # targets yang kosong, dan batch cabang yang gagal total akan
        # tertukar dengan batch kompetitor.
        "kind": batch_kind(jobs),
        "competitors": [
            job.competitor_id for job in jobs if job.competitor_id is not None
        ],
        "reused_existing_job": False,
        "limits": limits,
    }
    if include_jobs:
        data["jobs"] = [
            {
                "job_id": job.id,
                "onebox_location_id": job.onebox_location_id,
                "competitor_id": job.competitor_id,
                "kind": (
                    "competitor"
                    if job.competitor_id is not None
                    else "location"
                ),
                "target_review_count": job.target_review_count,
                "max_reviews_to_collect": (
                    ((job.result_json or {}).get("request") or {}).get(
                        "max_reviews_to_collect"
                    )
                    or job.target_review_count
                ),
                "scan_limit": ((job.result_json or {}).get("request") or {}).get(
                    "scan_limit"
                ),
                "crawl_mode": ((job.result_json or {}).get("request") or {}).get(
                    "crawl_mode"
                ),
                "stop_reason": stop_reason(job.result_json or {}),
                "rating_snapshot": rating_snapshot(job.result_json or {}),
                "status": job.status,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "result": job.result_json,
                "error": (
                    {"code": job.last_error_code, "message": job.last_error}
                    if job.last_error_code
                    else None
                ),
                "started_at": job.started_at,
                "finished_at": job.finished_at,
            }
            for job in jobs
        ]
    return data


def batch_kind(jobs) -> str:
    """location | competitor | mixed.

    Batch kosong dianggap location: itu bentuk lama, dan menyebutnya apa pun
    selain itu akan membuat batch lawas berpindah layar.
    """
    jenis = {
        "competitor" if job.competitor_id is not None else "location"
        for job in jobs
    }
    if len(jenis) == 1:
        return jenis.pop()
    return "mixed" if jenis else "location"


def batch_stop_reasons(jobs) -> tuple[str | None, dict[str, int]]:
    counts: dict[str, int] = {}
    for job in jobs:
        reason = stop_reason(job.result_json or {})
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    if not counts:
        return None, {}
    if len(counts) == 1:
        return next(iter(counts)), counts
    return "mixed", counts

