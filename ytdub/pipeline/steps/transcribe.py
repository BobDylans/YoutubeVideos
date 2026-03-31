from __future__ import annotations

import json
from pathlib import Path

from ytdub.media.ffmpeg import run_ffmpeg
from ytdub.models.job import JobRecord
from ytdub.pipeline.runner import StepResult


class TranscribeStep:
    name = "transcribe"

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        source_video = Path(job.artifacts["download"])
        extracted_audio = work_dir / "source.wav"
        transcript_path = work_dir / "transcript.json"

        run_ffmpeg(
            [
                "-i",
                str(source_video),
                "-vn",
                "-acodec",
                "pcm_s16le",
                str(extracted_audio),
            ]
        )

        transcript_path.write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "source_video": str(source_video),
                    "extracted_audio": str(extracted_audio),
                    "segments": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return StepResult(
            artifacts={
                self.name: str(transcript_path),
                "transcribe_audio": str(extracted_audio),
            }
        )
