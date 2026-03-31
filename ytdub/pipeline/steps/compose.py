from __future__ import annotations

from pathlib import Path

from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.media.subtitles import render_srt
from ytdub.pipeline.runner import StepResult


class ComposeStep:
    name = "compose"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        video_artifact = work_dir / "final-video.mp4"
        srt_artifact = work_dir / "final-subtitles.srt"
        video_artifact.write_text(f"{job.job_id}:final", encoding="utf-8")
        srt_artifact.write_text(
            render_srt(
                [
                    Segment(
                        start_ms=0,
                        end_ms=1000,
                        text=f"Dubbed output for {job.job_id}",
                    )
                ]
            ),
            encoding="utf-8",
        )
        return StepResult(
            artifacts={
                self.name: str(video_artifact),
                "compose_srt": str(srt_artifact),
            }
        )
