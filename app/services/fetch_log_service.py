from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import FetchLog
from app.db.session import get_session_factory
from app.services.fetch_log_repository import FetchLogRepository


class FetchLogService:
    def __init__(
        self,
        company_id: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
        *,
        session: Session | None = None,
    ):
        self.company_id = company_id
        self.session_factory = session_factory or get_session_factory()
        self._session = session

    @contextmanager
    def _read_session(self):
        if self._session is not None:
            yield self._session
        else:
            with self.session_factory() as session:
                yield session

    def start_log(
        self, location_id: int, source: str, metadata: dict | None = None
    ) -> int:
        with self.session_factory() as session:
            log = FetchLog(
                company_id=self.company_id,
                location_id=location_id,
                source=source,
                status="started",
                metadata_json=metadata or {},
                started_at=datetime.now().astimezone(),
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            return log.id

    def finish_log(self, log_id: int, result: dict) -> None:
        with self.session_factory() as session:
            log = session.get(FetchLog, log_id)
            if log is None:
                return
            log.status = result["status"]
            log.total_fetched = result.get("total_fetched", 0)
            log.total_inserted = result.get("total_inserted", 0)
            log.total_duplicate = result.get("total_duplicate", 0)
            log.total_failed = result.get("total_failed", 0)
            log.error_message = result.get("error_message")
            if result.get("metadata"):
                log.metadata_json = result["metadata"]
            log.finished_at = datetime.now().astimezone()
            session.commit()

    def create_dry_run_log(
        self, location_id: int, source: str, total_fetched: int
    ) -> None:
        now = datetime.now().astimezone()
        with self.session_factory() as session:
            session.add(
                FetchLog(
                    company_id=self.company_id,
                    location_id=location_id,
                    source=source,
                    status="dry_run",
                    total_fetched=total_fetched,
                    metadata_json={},
                    started_at=now,
                    finished_at=now,
                )
            )
            session.commit()

    def get_logs(
        self,
        location_id: int | None = None,
        failed_only: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        with self._read_session() as session:
            rows = FetchLogRepository(session, self.company_id).recent(
                location_id=location_id,
                failed_only=failed_only,
                limit=limit,
            )
            return [
                {
                    "id": log.id,
                    "location_id": log.location_id,
                    "location": branch_name,
                    "source": log.source,
                    "status": log.status,
                    "total_fetched": log.total_fetched,
                    "total_inserted": log.total_inserted,
                    "total_duplicate": log.total_duplicate,
                    "total_failed": log.total_failed,
                    "error_message": log.error_message,
                    "metadata": log.metadata_json,
                    "started_at": log.started_at,
                    "finished_at": log.finished_at,
                }
                for log, branch_name in rows
            ]

    def get_last_log(self) -> dict | None:
        logs = self.get_logs(limit=1)
        return logs[0] if logs else None
