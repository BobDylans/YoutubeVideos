from __future__ import annotations

from pathlib import Path
import re

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


def build_subtitles_filter(path: Path) -> str:
    escaped_path = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{escaped_path}'"


def parse_subtitle_file(path: Path) -> list[Segment]:
    content = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\r?\n+", content)
    segments: list[Segment] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT":
            continue

        timestamp_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timestamp_index is None:
            continue

        start_ms, end_ms = _parse_timestamp_range(lines[timestamp_index])
        text_lines = [_strip_subtitle_markup(line) for line in lines[timestamp_index + 1 :]]
        text = " ".join(line for line in text_lines if line).strip()
        if not text:
            continue

        segments.append(Segment(start_ms=start_ms, end_ms=end_ms, text=text))

    return _merge_incremental_segments(segments)


def _format_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def _parse_timestamp_range(line: str) -> tuple[int, int]:
    start_text, end_text = [part.strip().split(" ", 1)[0] for part in line.split("-->", 1)]
    return _parse_timestamp(start_text), _parse_timestamp(end_text)


def _parse_timestamp(value: str) -> int:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        raise ValueError(f"Unsupported subtitle timestamp: {value}")

    total_ms = int(round(((hours * 3600) + (minutes * 60) + seconds) * 1000))
    return total_ms


def _strip_subtitle_markup(line: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", line)
    return re.sub(r"\s+", " ", without_tags).strip()


def _merge_incremental_segments(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        normalized_text = _normalize_subtitle_text(segment.text)
        if not normalized_text:
            continue

        normalized_segment = Segment(
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=normalized_text,
        )
        if not merged:
            merged.append(normalized_segment)
            continue

        previous = merged[-1]
        if _contains_text(previous.text, normalized_segment.text):
            merged[-1] = Segment(
                start_ms=previous.start_ms,
                end_ms=max(previous.end_ms, normalized_segment.end_ms),
                text=previous.text,
            )
            continue

        if _contains_text(normalized_segment.text, previous.text):
            merged[-1] = Segment(
                start_ms=previous.start_ms,
                end_ms=max(previous.end_ms, normalized_segment.end_ms),
                text=normalized_segment.text,
            )
            continue

        overlap_words = _find_word_overlap(previous.text, normalized_segment.text)
        if overlap_words > 0:
            merged_words = previous.text.split() + normalized_segment.text.split()[overlap_words:]
            merged[-1] = Segment(
                start_ms=previous.start_ms,
                end_ms=max(previous.end_ms, normalized_segment.end_ms),
                text=" ".join(merged_words),
            )
            continue

        merged.append(normalized_segment)

    return merged


def _normalize_subtitle_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", " ", text)
    cleaned = cleaned.replace(">>", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _contains_text(haystack: str, needle: str) -> bool:
    haystack_words = [_normalize_word(word) for word in haystack.split()]
    needle_words = [_normalize_word(word) for word in needle.split()]
    if not haystack_words or not needle_words or len(needle_words) > len(haystack_words):
        return False

    for index in range(len(haystack_words) - len(needle_words) + 1):
        if haystack_words[index : index + len(needle_words)] == needle_words:
            return True

    return False


def _find_word_overlap(previous: str, current: str) -> int:
    previous_words = previous.split()
    current_words = current.split()
    max_overlap = min(len(previous_words), len(current_words))
    for overlap in range(max_overlap, 0, -1):
        if [
            _normalize_word(word) for word in previous_words[-overlap:]
        ] == [_normalize_word(word) for word in current_words[:overlap]]:
            return overlap
    return 0


def _normalize_word(word: str) -> str:
    return re.sub(r"[^\w']+", "", word).lower()
