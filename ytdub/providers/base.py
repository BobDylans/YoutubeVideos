from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ytdub.models.segments import Segment


@dataclass(frozen=True)
class ProviderBase:
    name: str


class Transcriber(Protocol):
    name: str

    def build_request(self, audio_path: Path) -> dict[str, object]: ...


class Translator(Protocol):
    name: str

    def build_payload(
        self,
        segments: list[Segment],
        target_language: str,
    ) -> dict[str, object]: ...


class SpeechSynthesizer(Protocol):
    name: str

    def build_payload(self, segment: Segment) -> dict[str, object]: ...
