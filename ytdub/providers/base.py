from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpTransport


@dataclass(frozen=True)
class ProviderBase:
    name: str


class Transcriber(Protocol):
    name: str

    def build_request(self, audio_path: Path) -> dict[str, object]: ...
    def transcribe(self, audio_path: Path, transport: HttpTransport | None = None) -> list[Segment]: ...


class Translator(Protocol):
    name: str

    def build_payload(
        self,
        segments: list[Segment],
        target_language: str,
    ) -> dict[str, object]: ...
    def translate_segments(
        self,
        segments: list[Segment],
        target_language: str,
        transport: HttpTransport | None = None,
    ) -> list[Segment]: ...


class SpeechSynthesizer(Protocol):
    name: str

    def build_payload(self, segment: Segment) -> dict[str, object]: ...
    def synthesize_segment(
        self,
        segment: Segment,
        output_path: Path,
        transport: HttpTransport | None = None,
    ) -> Path: ...
