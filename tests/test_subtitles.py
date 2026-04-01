from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ytdub.media.ffmpeg import ExternalCommandError, run_ffmpeg
from ytdub.media.subtitles import (
    build_subtitles_filter,
    parse_subtitle_file,
    render_srt,
    reshape_subtitle_segments,
)
from ytdub.models.segments import Segment


def test_srt_render_preserves_segment_order() -> None:
    srt = render_srt(
        [
            Segment(start_ms=0, end_ms=1200, text="hello"),
            Segment(start_ms=1500, end_ms=2400, text="world"),
        ]
    )

    assert "1\n00:00:00,000 --> 00:00:01,200\nhello" in srt
    assert "2\n00:00:01,500 --> 00:00:02,400\nworld" in srt


def test_render_srt_wraps_long_lines_to_two_rows() -> None:
    srt = render_srt(
        [
            Segment(
                start_ms=0,
                end_ms=2000,
                text="This subtitle should wrap into two readable lines for display",
            )
        ]
    )

    assert (
        "This subtitle should wrap into\n"
        "two readable lines for display"
    ) in srt


def test_run_ffmpeg_wraps_command_failures(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=["ffmpeg", "-version"],
            stderr="broken",
        )

    monkeypatch.setattr("ytdub.media.ffmpeg.run", fake_run)

    with pytest.raises(ExternalCommandError, match="ffmpeg"):
        run_ffmpeg(["-version"])


def test_build_subtitles_filter_escapes_windows_drive_separator(tmp_path: Path) -> None:
    path = tmp_path / "final-subtitles.srt"

    filter_arg = build_subtitles_filter(path)

    assert filter_arg.startswith("subtitles='")
    assert str(path.resolve().as_posix()).replace(":", r"\:") in filter_arg


def test_parse_srt_file_into_segments(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "source.en.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,200\nHello world\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\nSecond line\n",
        encoding="utf-8",
    )

    segments = parse_subtitle_file(subtitle_path)

    assert segments == [
        Segment(start_ms=0, end_ms=1200, text="Hello world"),
        Segment(start_ms=1500, end_ms=3000, text="Second line"),
    ]


def test_parse_vtt_file_into_segments(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "source.en.vtt"
    subtitle_path.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.200\n"
        "<c.colorE5E5E5>Hello world</c>\n\n"
        "00:00:01.500 --> 00:00:03.000\n"
        "Second line\n",
        encoding="utf-8",
    )

    segments = parse_subtitle_file(subtitle_path)

    assert segments == [
        Segment(start_ms=0, end_ms=1200, text="Hello world"),
        Segment(start_ms=1500, end_ms=3000, text="Second line"),
    ]


def test_parse_subtitle_file_merges_incremental_youtube_captions(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "source.en-orig.srt"
    subtitle_path.write_text(
        "1\n00:00:02,950 --> 00:00:02,960\n[music]\n\n"
        "2\n00:00:02,960 --> 00:00:05,749\n[music] I found something\n\n"
        "3\n00:00:05,749 --> 00:00:05,759\nI found something\n\n"
        "4\n00:00:05,759 --> 00:00:07,670\nI found something >> in the store.\n\n"
        "5\n00:00:07,680 --> 00:00:10,070\n>> in the store. >> Okay.\n",
        encoding="utf-8",
    )

    segments = parse_subtitle_file(subtitle_path)

    assert segments == [
        Segment(start_ms=2960, end_ms=10070, text="I found something in the store. Okay."),
    ]


def test_reshape_subtitle_segments_splits_long_punctuated_text() -> None:
    segments = reshape_subtitle_segments(
        [
            Segment(
                start_ms=0,
                end_ms=6000,
                text="First we check the shelves, then we check the back room, and finally we call the manager.",
            )
        ],
        language="en",
    )

    assert len(segments) == 3
    assert [segment.text for segment in segments] == [
        "First we check the shelves,",
        "then we check the back room,",
        "and finally we call the manager.",
    ]
    assert segments[0].start_ms == 0
    assert segments[-1].end_ms == 6000
    assert all(current.end_ms <= following.start_ms for current, following in zip(segments, segments[1:]))


def test_reshape_subtitle_segments_falls_back_to_word_splitting() -> None:
    segments = reshape_subtitle_segments(
        [
            Segment(
                start_ms=1000,
                end_ms=5000,
                text="This subtitle has no punctuation and still needs readable chunks for viewers",
            )
        ],
        language="en",
    )

    assert len(segments) >= 2
    assert segments[0].start_ms == 1000
    assert segments[-1].end_ms == 5000
    assert " ".join(segment.text for segment in segments).replace("  ", " ") == (
        "This subtitle has no punctuation and still needs readable chunks for viewers"
    )
