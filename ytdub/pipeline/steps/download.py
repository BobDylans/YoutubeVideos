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
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                "en.*",
                "--convert-subs",
                "srt",
                "--output",
                str(output_template),
                job.url,
            ]
        )

        matches = sorted(work_dir.glob("source.*"))
        video_matches = [path for path in matches if path.suffix.lower() not in {".srt", ".vtt", ".ass"}]
        if not video_matches:
            raise FileNotFoundError(f"yt-dlp did not produce a file in {work_dir}")

        artifacts = {self.name: str(video_matches[0])}
        subtitle_matches = sorted(path for path in matches if path.suffix.lower() in {".srt", ".vtt"})
        if subtitle_matches:
            artifacts["download_subtitles"] = str(subtitle_matches[0])

        return StepResult(artifacts=artifacts)
