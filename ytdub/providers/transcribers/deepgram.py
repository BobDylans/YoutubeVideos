from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
