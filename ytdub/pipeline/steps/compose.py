from __future__ import annotations

import json
from pathlib import Path

from ytdub.media.ffmpeg import run_ffmpeg
from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.media.subtitles import render_srt
from ytdub.pipeline.runner import StepResult


class ComposeStep:
    name = "compose"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        source_video = Path(job.artifacts["download"])
        translation_path = Path(job.artifacts["translate"])
        synthesize_path = Path(job.artifacts["synthesize"])
        video_artifact = work_dir / "final-video.mp4"
        srt_artifact = work_dir / "final-subtitles.srt"
        merged_audio = work_dir / "merged-dub.mp3"
        concat_manifest = work_dir / "concat.txt"

        translation_payload = json.loads(translation_path.read_text(encoding="utf-8"))
        synthesize_payload = json.loads(synthesize_path.read_text(encoding="utf-8"))
        segments = [
            Segment(
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                text=str(segment["text"]),
            )
            for segment in translation_payload.get("segments", [])
        ]
        concat_manifest.write_text(
            "\n".join(
                f"file '{clip['audio_path']}'"
                for clip in synthesize_payload.get("clips", [])
            )
            + ("\n" if synthesize_payload.get("clips") else ""),
            encoding="utf-8",
        )

        if synthesize_payload.get("clips"):
            run_ffmpeg(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_manifest),
                    "-c",
                    "copy",
                    str(merged_audio),
                ]
            )
            run_ffmpeg(
                [
                    "-i",
                    str(source_video),
                    "-i",
                    str(merged_audio),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-shortest",
                    str(video_artifact),
                ]
            )
        else:
            video_artifact.write_text(f"{job.job_id}:final", encoding="utf-8")

        srt_artifact.write_text(
            render_srt(segments),
            encoding="utf-8",
        )
        return StepResult(
            artifacts={
                self.name: str(video_artifact),
                "compose_srt": str(srt_artifact),
            }
        )
