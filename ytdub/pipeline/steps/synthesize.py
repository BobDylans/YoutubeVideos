from __future__ import annotations

from pathlib import Path

from ytdub.models.job import JobRecord
from ytdub.pipeline.runner import StepResult


class SynthesizeStep:
    name = "synthesize"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        artifact = work_dir / "dubbed-audio.txt"
        artifact.write_text(f"{job.job_id}:dubbed", encoding="utf-8")
        return StepResult(artifacts={self.name: str(artifact)})
