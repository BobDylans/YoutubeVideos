from __future__ import annotations

from dataclasses import dataclass

from ytdub.models.segments import Segment


@dataclass(frozen=True)
class ElevenLabsTTS:
    api_key: str
    voice_id: str
    model_id: str = "eleven_multilingual_v2"
    name: str = "elevenlabs"

    def build_request(self, segment: Segment) -> dict[str, object]:
        return {
            "url": f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            "headers": {"xi-api-key": self.api_key},
            "json": {
                "text": segment.text,
                "model_id": self.model_id,
            },
        }
