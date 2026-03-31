from __future__ import annotations

import subprocess

import pytest

from ytdub.media.ffmpeg import ExternalCommandError, run_ffmpeg
from ytdub.media.subtitles import render_srt
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
