from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import time

from app.config import get_settings
from app.services.crawl_worker import CrawlWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("crawl_worker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drain durable Voice of Customer crawl jobs."
    )
    parser.add_argument(
        "--once", action="store_true", help="Process at most one due job and exit."
    )
    parser.add_argument(
        "--worker-id", help="Stable worker identity used by the job lease."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    worker_id = args.worker_id or f"{socket.gethostname()}:{os.getpid()}"
    service = CrawlWorker(settings=settings)
    logger.info("Crawl worker started with worker_id=%s", worker_id)
    while True:
        try:
            result = service.execute_next(worker_id=worker_id)
            if result is not None:
                logger.info(
                    "Job batch processed: status=%s, batch_id=%s",
                    result.get("status"),
                    result.get("batch_id"),
                )
        except Exception:
            logger.exception("Error in crawl worker loop")
            result = None
        if args.once:
            return 0
        if result is None:
            time.sleep(settings.crawl_worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

