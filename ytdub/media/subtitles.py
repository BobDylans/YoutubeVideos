from __future__ import annotations

from ytdub.models.segments import Segment


def render_srt(segments: list[Segment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_timestamp(segment.start_ms)} --> {_format_timestamp(segment.end_ms)}",
                    segment.text,
                ]
            )
        )

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _format_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"
