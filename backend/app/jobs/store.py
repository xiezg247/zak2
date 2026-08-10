from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class JobRecord:
    id: str
    kind: str
    status: str  # pending | running | success | failed
    progress: float = 0.0
    error: str | None = None
    result_ref: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(self, kind: str, *, meta: dict[str, Any] | None = None) -> JobRecord:
        now = datetime.now(UTC).isoformat()
        job = JobRecord(
            id=str(uuid4()),
            kind=kind,
            status="pending",
            meta=meta or {},
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, *, limit: int = 50) -> list[JobRecord]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        error: str | None = None,
        result_ref: str | None = None,
    ) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if error is not None:
                job.error = error
            if result_ref is not None:
                job.result_ref = result_ref
            job.updated_at = datetime.now(UTC).isoformat()
            return job


job_store = JobStore()
