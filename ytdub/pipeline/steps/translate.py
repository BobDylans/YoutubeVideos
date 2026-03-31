from __future__ import annotations

from pathlib import Path

from ytdub.models.job import JobRecord
from ytdub.pipeline.runner import StepResult


class TranslateStep:
    name = "translate"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        artifact = work_dir / "translation.json"
        artifact.write_text(f'{{"job_id": "{job.job_id}", "status": "stub"}}', encoding="utf-8")
        return StepResult(artifacts={self.name: str(artifact)})
