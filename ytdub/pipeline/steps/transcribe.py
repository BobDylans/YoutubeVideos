from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ytdub.media.ffmpeg import run_ffmpeg
from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.pipeline.runner import StepResult
from ytdub.providers.base import Transcriber
from ytdub.providers.registry import ProviderRegistry


@dataclass
class TranscribeStep:
    name = "transcribe"
    transcriber: Transcriber | None = None
    registry: ProviderRegistry | None = None

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

        provider = self._resolve_transcriber(job)
        raw_segments = provider.transcribe(extracted_audio) if provider is not None else []
        segments = [
            {
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
            }
            for segment in raw_segments
        ]

        transcript_path.write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "provider": job.settings.transcriber,
                    "source_video": str(source_video),
                    "extracted_audio": str(extracted_audio),
                    "segments": segments,
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

    def _resolve_transcriber(self, job: JobRecord) -> Transcriber | None:
        if self.transcriber is not None:
            return self.transcriber
        if self.registry is None:
            return None
        return self.registry.get_transcriber(job.settings.transcriber)
