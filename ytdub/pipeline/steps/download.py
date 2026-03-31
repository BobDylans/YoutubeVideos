from __future__ import annotations

from pathlib import Path

from ytdub.media.ytdlp import run_ytdlp
from ytdub.models.job import JobRecord
from ytdub.pipeline.runner import StepResult


class DownloadStep:
    name = "download"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        output_template = work_dir / "source.%(ext)s"
        run_ytdlp(
            [
                "--no-progress",
                "--output",
                str(output_template),
                job.url,
            ]
        )

        matches = sorted(work_dir.glob("source.*"))
        if not matches:
            raise FileNotFoundError(f"yt-dlp did not produce a file in {work_dir}")

        return StepResult(artifacts={self.name: str(matches[0])})
