from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from ytdub.models.job import JobRecord, JobSettings


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, url: str, settings: JobSettings | None = None) -> JobRecord:
        job = JobRecord.create(job_id=uuid4().hex[:12], url=url, settings=settings)
        self.save(job)
        return job

    def load(self, job_id: str) -> JobRecord:
        payload = json.loads(self._job_file(job_id).read_text(encoding="utf-8"))
        return JobRecord.from_dict(payload)

    def save(self, job: JobRecord) -> JobRecord:
        self._write(job)
        return job

    def update_step(self, job_id: str, step_name: str, status: str) -> JobRecord:
        job = self.load(job_id)
        return self.save(job.with_step_status(step_name, status))

    def list_jobs(self) -> list[JobRecord]:
        jobs = [self.load(job_dir.name) for job_dir in self.root.iterdir() if job_dir.is_dir()]
        return sorted(jobs, key=lambda job: (job.created_at, job.job_id))

    def _write(self, job: JobRecord) -> None:
        job_dir = self.root / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        self._job_file(job.job_id).write_text(
            json.dumps(job.to_dict(), indent=2),
            encoding="utf-8",
        )

    def _job_file(self, job_id: str) -> Path:
        return self.root / job_id / "job.json"

    def write_log(self, job_id: str, step_name: str, content: str) -> Path:
        log_dir = self.root / job_id / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{step_name}.log"
        log_path.write_text(content, encoding="utf-8")
        return log_path
