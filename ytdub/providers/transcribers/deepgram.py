from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


@dataclass(frozen=True)
class DeepgramTranscriber:
    api_key: str
    model: str = "nova-3"
    name: str = "deepgram"

    def build_request(self, audio_path: Path) -> dict[str, object]:
        return {
            "url": "https://api.deepgram.com/v1/listen",
            "headers": {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",
            },
            "params": {
                "model": self.model,
                "smart_format": "true",
            },
            "body": audio_path.read_bytes(),
        }

    def transcribe(self, audio_path: Path, transport: HttpTransport | None = None) -> list[Segment]:
        request_data = self.build_request(audio_path)
        response = (transport or UrllibTransport()).send(
            HttpRequest(
                method="POST",
                url=str(request_data["url"]),
                headers=dict(request_data["headers"]),
                params=dict(request_data["params"]),
                content=bytes(request_data["body"]),
            )
        )
        payload = response.json()
        paragraphs = (
            payload.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("paragraphs", {})
            .get("paragraphs", [])
        )
        segments: list[Segment] = []
        for paragraph in paragraphs:
            text = " ".join(
                sentence.get("text", "").strip()
                for sentence in paragraph.get("sentences", [])
                if sentence.get("text")
            ).strip()
            if not text:
                continue
            segments.append(
                Segment(
                    start_ms=int(float(paragraph["start"]) * 1000),
                    end_ms=int(float(paragraph["end"]) * 1000),
                    text=text,
                )
            )
        return segments
