from __future__ import annotations

from dataclasses import dataclass

from ytdub.models.segments import Segment


@dataclass(frozen=True)
class OpenAITTS:
    api_key: str
    voice: str
    model: str = "gpt-4o-mini-tts"
    name: str = "openai"

    def build_payload(self, segment: Segment) -> dict[str, object]:
        return {
            "model": self.model,
            "voice": self.voice,
            "input": segment.text,
            "format": "mp3",
        }

    def build_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}
