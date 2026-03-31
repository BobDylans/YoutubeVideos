from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


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

    def synthesize_segment(
        self,
        segment: Segment,
        output_path: Path,
        transport: HttpTransport | None = None,
    ) -> Path:
        request_data = self.build_request(segment)
        response = (transport or UrllibTransport()).send(
            HttpRequest(
                method="POST",
                url=f"{request_data['url']}?output_format=mp3_44100_128",
                headers={
                    **dict(request_data["headers"]),
                    "Accept": "audio/mpeg",
                },
                json_body=dict(request_data["json"]),
            )
        )
        output_path.write_bytes(response.content)
        return output_path
