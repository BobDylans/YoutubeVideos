from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ytdub.media.subtitles import reshape_subtitle_segments
from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.pipeline.runner import StepResult
from ytdub.providers.base import Translator
from ytdub.providers.registry import ProviderRegistry


@dataclass
class TranslateStep:
    name = "translate"
    translator: Translator | None = None
    registry: ProviderRegistry | None = None

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        transcript_path = Path(job.artifacts["transcribe"])
        artifact = work_dir / "translation.json"
        transcript_payload = json.loads(transcript_path.read_text(encoding="utf-8"))
        source_segments = [
            Segment(
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                text=str(segment["text"]),
            )
            for segment in transcript_payload.get("segments", [])
        ]
        provider = self._resolve_translator(job)
        translated_segments = (
            provider.translate_segments(
                source_segments,
                target_language=job.settings.target_language,
            )
            if provider is not None
            else []
        )
        translated_segments = reshape_subtitle_segments(
            translated_segments,
            language=job.settings.target_language,
        )
        artifact.write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "provider": job.settings.translator,
                    "target_language": job.settings.target_language,
                    "source_transcript": str(transcript_path),
                    "segments": [
                        {
                            "start_ms": segment.start_ms,
                            "end_ms": segment.end_ms,
                            "text": segment.text,
                        }
                        for segment in translated_segments
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return StepResult(artifacts={self.name: str(artifact)})

    def _resolve_translator(self, job: JobRecord) -> Translator | None:
        if self.translator is not None:
            return self.translator
        if self.registry is None:
            return None
        return self.registry.get_translator(job.settings.translator)
