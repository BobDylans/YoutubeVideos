from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ytdub.models.job import JobRecord
from ytdub.models.segments import Segment
from ytdub.pipeline.runner import StepResult
from ytdub.providers.base import SpeechSynthesizer
from ytdub.providers.registry import ProviderRegistry


@dataclass
class SynthesizeStep:
    name = "synthesize"
    synthesizer: SpeechSynthesizer | None = None
    registry: ProviderRegistry | None = None

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        translation_path = Path(job.artifacts["translate"])
        translation_payload = json.loads(translation_path.read_text(encoding="utf-8"))
        translated_segments = [
            Segment(
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                text=str(segment["text"]),
            )
            for segment in translation_payload.get("segments", [])
        ]
        artifact = work_dir / "dubbed-audio.json"
        clips = []
        synthesizer = self._resolve_synthesizer(job)
        if synthesizer is not None:
            for index, segment in enumerate(translated_segments, start=1):
                output_path = work_dir / f"segment-{index:04d}.mp3"
                written_path = synthesizer.synthesize_segment(segment, output_path)
                clips.append(
                    {
                        "start_ms": segment.start_ms,
                        "end_ms": segment.end_ms,
                        "text": segment.text,
                        "audio_path": str(written_path),
                    }
                )
        artifact.write_text(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "provider": job.settings.tts,
                    "target_language": job.settings.target_language,
                    "source_translation": str(translation_path),
                    "clips": clips,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return StepResult(artifacts={self.name: str(artifact)})

    def _resolve_synthesizer(self, job: JobRecord) -> SpeechSynthesizer | None:
        if self.synthesizer is not None:
            return self.synthesizer
        if self.registry is None:
            return None
        return self.registry.get_tts(job.settings.tts)
