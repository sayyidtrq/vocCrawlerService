from __future__ import annotations

import argparse
import json
import os
import socket
import time

from app.config import get_settings
from app.services.crawl_worker import CrawlWorker


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
    while True:
        result = service.execute_next(worker_id=worker_id)
        if result is not None:
            print(json.dumps(result, default=str, ensure_ascii=False))
        if args.once:
            return 0
        if result is None:
            time.sleep(settings.crawl_worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
