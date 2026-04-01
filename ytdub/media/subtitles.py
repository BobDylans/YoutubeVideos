from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ytdub.models.segments import Segment

_COMPACT_LANGUAGE_PREFIXES = ("zh", "ja", "ko", "th")
_COMPACT_PUNCTUATION = "，。！？；：、"
_COMPACT_CONNECTORS = (
    "但是",
    "不过",
    "然后",
    "最后",
    "因此",
    "所以",
    "于是",
    "并且",
    "而且",
    "如果",
    "虽然",
    "因为",
    "同时",
    "另外",
    "此外",
    "接着",
    "随后",
)
_COMPACT_PUNCT_TRANSLATION = str.maketrans(
    {
        ",": "，",
        ".": "。",
        "!": "！",
        "?": "？",
        ";": "；",
        ":": "：",
    }
)
_COMPACT_TRAILING_UNIT_CHARS = frozenset("年月日号点个次秒分时天周万亿%％")


@dataclass(frozen=True)
class SubtitleLayout:
    max_segment_units: int
    max_line_units: int


def render_srt(segments: list[Segment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_timestamp(segment.start_ms)} --> {_format_timestamp(segment.end_ms)}",
                    _wrap_subtitle_text(segment.text),
                ]
            )
        )

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def build_subtitles_filter(path: Path) -> str:
    escaped_path = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{escaped_path}'"


def reshape_subtitle_segments(segments: list[Segment], language: str) -> list[Segment]:
    reshaped: list[Segment] = []

    for segment in segments:
        compact = _should_use_compact_layout(language, segment.text)
        layout = _layout_for_compact(compact)
        reshaped.extend(_reshape_segment(segment, compact=compact, layout=layout))

    return reshaped


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


def _reshape_segment(segment: Segment, *, compact: bool, layout: SubtitleLayout) -> list[Segment]:
    cleaned_text = _prepare_subtitle_text(segment.text, compact=compact)
    if not cleaned_text:
        return []

    if _display_units(cleaned_text, compact=compact) <= layout.max_segment_units:
        return [Segment(start_ms=segment.start_ms, end_ms=segment.end_ms, text=cleaned_text)]

    chunks = _chunk_text(cleaned_text, compact=compact, layout=layout)
    if len(chunks) <= 1:
        return [Segment(start_ms=segment.start_ms, end_ms=segment.end_ms, text=cleaned_text)]

    ranges = _allocate_time_ranges(segment.start_ms, segment.end_ms, chunks, compact=compact)
    return [
        Segment(start_ms=start_ms, end_ms=end_ms, text=chunk)
        for (start_ms, end_ms), chunk in zip(ranges, chunks)
    ]


def _chunk_text(text: str, *, compact: bool, layout: SubtitleLayout) -> list[str]:
    if compact:
        return _chunk_compact_text(text, layout)

    phrase_chunks = _pack_chunks(
        _split_phrases(text, compact=compact),
        compact=compact,
        max_units=layout.max_segment_units,
    )
    if len(phrase_chunks) > 1:
        return phrase_chunks
    return _fallback_chunks(text, compact=compact, max_units=layout.max_segment_units)


def _pack_chunks(parts: list[str], *, compact: bool, max_units: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    for part in parts:
        normalized = _clean_subtitle_text(part)
        if not normalized:
            continue

        if _display_units(normalized, compact=compact) > max_units:
            if current:
                chunks.append(_join_parts(current, compact=compact))
                current = []
            chunks.extend(_fallback_chunks(normalized, compact=compact, max_units=max_units))
            continue

        candidate_parts = [*current, normalized]
        candidate = _join_parts(candidate_parts, compact=compact)
        if current and _display_units(candidate, compact=compact) > max_units:
            chunks.append(_join_parts(current, compact=compact))
            current = [normalized]
            continue

        current = candidate_parts

    if current:
        chunks.append(_join_parts(current, compact=compact))

    return chunks


def _split_phrases(text: str, *, compact: bool) -> list[str]:
    if compact:
        pattern = rf"[^{re.escape(_COMPACT_PUNCTUATION)}\s]+[{re.escape(_COMPACT_PUNCTUATION)}]*"
        matches = [match.group(0).strip() for match in re.finditer(pattern, text) if match.group(0).strip()]
        return matches or [text]

    parts = [part.strip() for part in re.split(r"(?<=[,;:.!?])\s+", text) if part.strip()]
    return parts or [text]


def _fallback_chunks(text: str, *, compact: bool, max_units: int) -> list[str]:
    if compact:
        characters = [char for char in text if not char.isspace()]
        if not characters:
            return []
        return ["".join(characters[index : index + max_units]) for index in range(0, len(characters), max_units)]

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and _display_units(candidate, compact=False) > max_units:
            chunks.append(" ".join(current))
            current = [word]
            continue
        current.append(word)

    if current:
        chunks.append(" ".join(current))

    return chunks


def _allocate_time_ranges(start_ms: int, end_ms: int, chunks: list[str], *, compact: bool) -> list[tuple[int, int]]:
    if not chunks:
        return []

    total_duration = max(end_ms - start_ms, len(chunks))
    weights = [max(_display_units(chunk, compact=compact), 1) for chunk in chunks]
    total_weight = sum(weights)
    ranges: list[tuple[int, int]] = []
    current_start = start_ms

    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            ranges.append((current_start, end_ms))
            continue

        remaining_chunks = len(weights) - index - 1
        proportional = round(total_duration * weight / total_weight)
        candidate_end = current_start + max(proportional, 1)
        latest_allowed_end = end_ms - remaining_chunks
        candidate_end = min(candidate_end, latest_allowed_end)
        if candidate_end <= current_start:
            candidate_end = current_start + 1
        ranges.append((current_start, candidate_end))
        current_start = candidate_end

    return ranges


def _wrap_subtitle_text(text: str) -> str:
    compact = _is_compact_text(text)
    normalized = _prepare_subtitle_text(text, compact=compact)
    if not normalized:
        return ""

    layout = _layout_for_compact(compact)
    if _display_units(normalized, compact=compact) <= layout.max_line_units:
        return normalized

    if compact:
        clauses = _split_compact_clauses(normalized)
        if len(clauses) == 1 and _display_units(normalized, compact=True) <= _compact_single_line_limit(layout):
            return normalized
        return _wrap_compact_text(normalized)

    return _balanced_two_line_wrap(normalized, compact=compact)


def _layout_for_compact(compact: bool) -> SubtitleLayout:
    if compact:
        return SubtitleLayout(max_segment_units=16, max_line_units=11)
    return SubtitleLayout(max_segment_units=48, max_line_units=24)


def _is_compact_language(language: str) -> bool:
    normalized = language.lower().replace("_", "-")
    return normalized.startswith(_COMPACT_LANGUAGE_PREFIXES)


def _is_compact_text(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff" or "\uac00" <= char <= "\ud7af" for char in text)


def _should_use_compact_layout(language: str, text: str) -> bool:
    if _is_compact_text(text):
        return True
    if " " in text:
        return False
    return _is_compact_language(language)


def _join_parts(parts: list[str], *, compact: bool) -> str:
    separator = "" if compact else " "
    return _prepare_subtitle_text(separator.join(parts), compact=compact)


def _prepare_subtitle_text(text: str, *, compact: bool) -> str:
    normalized = _clean_subtitle_text(text)
    if not compact:
        return normalized

    normalized = normalized.translate(_COMPACT_PUNCT_TRANSLATION)
    normalized = re.sub(r"\s*([，。！？；：、])\s*", r"\1", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", normalized)
    if normalized and _is_compact_text(normalized) and normalized[-1] not in _COMPACT_PUNCTUATION:
        normalized += "。"
    return normalized


def _chunk_compact_text(text: str, layout: SubtitleLayout) -> list[str]:
    clauses = _split_compact_clauses(text)
    if not clauses:
        return []

    if len(clauses) == 1 and _display_units(text, compact=True) <= _compact_single_line_limit(layout):
        return [text]

    if _display_units(text, compact=True) > layout.max_segment_units and len(clauses) > 1:
        return clauses

    phrase_chunks = _pack_chunks(clauses, compact=True, max_units=layout.max_segment_units)
    if len(phrase_chunks) > 1:
        return phrase_chunks
    return _fallback_chunks(text, compact=True, max_units=layout.max_segment_units)


def _split_compact_clauses(text: str) -> list[str]:
    clauses = [match.group(0) for match in re.finditer(r"[^，。！？；：、]+[，。！？；：、]?", text) if match.group(0)]
    if len(clauses) > 1:
        return _ensure_compact_clause_punctuation(clauses)

    positions = sorted(
        {
            index
            for marker in _COMPACT_CONNECTORS
            for index in _find_all_occurrences(text, marker)
            if 0 < index < len(text)
        }
    )
    if not positions:
        return [text]

    clauses = []
    start = 0
    for index in positions:
        if index - start < 4:
            continue
        clauses.append(text[start:index])
        start = index
    if start < len(text):
        clauses.append(text[start:])
    return _ensure_compact_clause_punctuation([clause for clause in clauses if clause])


def _ensure_compact_clause_punctuation(clauses: list[str]) -> list[str]:
    normalized: list[str] = []
    for index, clause in enumerate(clauses):
        cleaned = clause.strip()
        if not cleaned:
            continue
        if cleaned[-1] not in _COMPACT_PUNCTUATION:
            cleaned += "。" if index == len(clauses) - 1 else "，"
        normalized.append(cleaned)
    return normalized


def _find_all_occurrences(text: str, marker: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(marker, start)
        if index == -1:
            return positions
        positions.append(index)
        start = index + len(marker)


def _wrap_compact_text(text: str) -> str:
    clauses = _split_compact_clauses(text)
    if len(clauses) >= 2:
        best_index = 1
        best_score: tuple[int, int] | None = None
        for index in range(1, len(clauses)):
            left = "".join(clauses[:index])
            right = "".join(clauses[index:])
            score = (
                abs(_display_units(left, compact=True) - _display_units(right, compact=True)),
                max(_display_units(left, compact=True), _display_units(right, compact=True)),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_index = index
        return "\n".join(["".join(clauses[:best_index]), "".join(clauses[best_index:])])

    return _balanced_compact_token_wrap(text)


def _balanced_two_line_wrap(text: str, *, compact: bool) -> str:
    if compact:
        return _balanced_compact_token_wrap(text)

    words = text.split()
    if len(words) <= 1:
        return text

    best_index = 1
    best_score: tuple[int, int] | None = None
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        score = (abs(len(left) - len(right)), max(len(left), len(right)))
        if best_score is None or score < best_score:
            best_score = score
            best_index = index

    return "\n".join([" ".join(words[:best_index]), " ".join(words[best_index:])])


def _display_units(text: str, *, compact: bool) -> int:
    if compact:
        return sum(1 for char in text if not char.isspace())
    return len(text)


def _compact_single_line_limit(layout: SubtitleLayout) -> int:
    return layout.max_line_units * 2


def _balanced_compact_token_wrap(text: str) -> str:
    tokens = _tokenize_compact_text(text)
    if len(tokens) <= 1:
        return text

    best_index = 1
    best_score: tuple[int, int] | None = None
    for index in range(1, len(tokens)):
        left = "".join(tokens[:index])
        right = "".join(tokens[index:])
        if not left or not right:
            continue
        score = (
            max(_display_units(left, compact=True), _display_units(right, compact=True)),
            abs(_display_units(left, compact=True) - _display_units(right, compact=True)),
        )
        if best_score is None or score < best_score:
            best_score = score
            best_index = index

    return "\n".join(["".join(tokens[:best_index]), "".join(tokens[best_index:])])


def _tokenize_compact_text(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0

    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue

        if char in _COMPACT_PUNCTUATION:
            if tokens:
                tokens[-1] += char
            else:
                tokens.append(char)
            index += 1
            continue

        if _is_ascii_token_char(char):
            start = index
            index += 1
            while index < len(text) and _is_ascii_token_char(text[index]):
                index += 1

            token = text[start:index]
            while index < len(text) and text[index] in _COMPACT_TRAILING_UNIT_CHARS:
                token += text[index]
                index += 1
            tokens.append(token)
            continue

        tokens.append(char)
        index += 1

    return tokens


def _is_ascii_token_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in {".", "/", "-", "_", "+", "#"})


def _clean_subtitle_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

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
