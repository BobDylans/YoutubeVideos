from __future__ import annotations

import json
from pathlib import Path

from ytdub.media.ffmpeg import run_ffmpeg
from ytdub.media.subtitles import build_subtitles_filter, render_srt
from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.pipeline.runner import StepResult


class ComposeStep:
    name = "compose"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        source_video = Path(job.artifacts["download"])
        translation_path = Path(job.artifacts["translate"])
        video_artifact = work_dir / "final-video.mp4"
        srt_artifact = work_dir / "final-subtitles.srt"

        translation_payload = json.loads(translation_path.read_text(encoding="utf-8"))
        segments = [
            Segment(
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                text=str(segment["text"]),
            )
            for segment in translation_payload.get("segments", [])
        ]

        srt_artifact.write_text(
            render_srt(segments),
            encoding="utf-8",
        )
        run_ffmpeg(
            [
                "-i",
                str(source_video),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-vf",
                build_subtitles_filter(srt_artifact),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(video_artifact),
            ]
        )
        return StepResult(
            artifacts={
                self.name: str(video_artifact),
                "compose_srt": str(srt_artifact),
            }
        )
