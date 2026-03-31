from __future__ import annotations

from subprocess import CompletedProcess

from ytdub.media.ffmpeg import _run_command


def run_ytdlp(args: list[str]) -> CompletedProcess[str]:
    return _run_command("yt-dlp", args)
