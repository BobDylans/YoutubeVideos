from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


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

    def synthesize_segment(
        self,
        segment: Segment,
        output_path: Path,
        transport: HttpTransport | None = None,
    ) -> Path:
        response = (transport or UrllibTransport()).send(
            HttpRequest(
                method="POST",
                url="https://api.openai.com/v1/audio/speech",
                headers={
                    **self.build_headers(),
                    "Accept": "audio/mpeg",
                },
                json_body=self.build_payload(segment),
            )
        )
        output_path.write_bytes(response.content)
        return output_path
