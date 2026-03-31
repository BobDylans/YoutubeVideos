from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str
