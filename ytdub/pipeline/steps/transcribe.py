from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ytdub.media.ffmpeg import run_ffmpeg
from ytdub.media.subtitles import parse_subtitle_file
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

        subtitle_path = _resolve_downloaded_subtitles(job)
        if subtitle_path is not None:
            if extracted_audio.exists():
                extracted_audio.unlink()
            raw_segments = parse_subtitle_file(subtitle_path)
            provider_name = "youtube_subtitles"
        else:
            run_ffmpeg(
                [
                    "-i",
                    str(source_video),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-acodec",
                    "pcm_s16le",
                    str(extracted_audio),
                ]
            )

            provider = self._resolve_transcriber(job)
            raw_segments = provider.transcribe(extracted_audio) if provider is not None else []
            provider_name = job.settings.transcriber
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
                    "provider": provider_name,
                    "source_video": str(source_video),
                    "extracted_audio": str(extracted_audio) if extracted_audio.exists() else None,
                    "source_subtitles": str(subtitle_path) if subtitle_path is not None else None,
                    "segments": segments,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        artifacts = {self.name: str(transcript_path)}
        if extracted_audio.exists():
            artifacts["transcribe_audio"] = str(extracted_audio)
        return StepResult(artifacts=artifacts)

    def _resolve_transcriber(self, job: JobRecord) -> Transcriber | None:
        if self.transcriber is not None:
            return self.transcriber
        if self.registry is None:
            return None
        return self.registry.get_transcriber(job.settings.transcriber)


def _resolve_downloaded_subtitles(job: JobRecord) -> Path | None:
    subtitle_artifact = job.artifacts.get("download_subtitles")
    if not subtitle_artifact:
        return None

    subtitle_path = Path(subtitle_artifact)
    if not subtitle_path.exists():
        return None

    return subtitle_path
