from __future__ import annotations

from pathlib import Path

from ytdub.media.ffmpeg import ExternalCommandError
from ytdub.media.ytdlp import run_ytdlp
from ytdub.models.job import JobRecord
from ytdub.pipeline.runner import StepResult


class DownloadStep:
    name = "download"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        output_template = work_dir / "source.%(ext)s"
        base_args = [
            "--no-progress",
            "--output",
            str(output_template),
            job.url,
        ]
        subtitle_args = [
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "en.*",
            "--convert-subs",
            "srt",
        ]
        subtitle_download_succeeded = True
        try:
            run_ytdlp([*subtitle_args, *base_args])
        except ExternalCommandError as exc:
            if not _is_subtitle_download_failure(exc):
                raise
            subtitle_download_succeeded = False
            run_ytdlp(base_args)

        matches = sorted(work_dir.glob("source.*"))
        video_matches = [path for path in matches if path.suffix.lower() not in {".srt", ".vtt", ".ass"}]
        if not video_matches:
            raise FileNotFoundError(f"yt-dlp did not produce a file in {work_dir}")

        artifacts = {self.name: str(video_matches[0])}
        subtitle_matches = (
            sorted(path for path in matches if path.suffix.lower() in {".srt", ".vtt"})
            if subtitle_download_succeeded
            else []
        )
        if subtitle_matches:
            artifacts["download_subtitles"] = str(subtitle_matches[0])

        return StepResult(artifacts=artifacts)


def _is_subtitle_download_failure(error: ExternalCommandError) -> bool:
    stderr = error.stderr.lower()
    return "unable to download video subtitles" in stderr or "video subtitles" in stderr
