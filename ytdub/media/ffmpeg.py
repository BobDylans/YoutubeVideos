from __future__ import annotations

from dataclasses import dataclass
from subprocess import CalledProcessError, CompletedProcess, run


@dataclass(frozen=True)
class ExternalCommandError(RuntimeError):
    command: str
    exit_code: int
    stderr: str

    def __str__(self) -> str:
        return f"{self.command} failed with exit code {self.exit_code}: {self.stderr}"


def run_ffmpeg(args: list[str]) -> CompletedProcess[str]:
    return _run_command("ffmpeg", args)


def run_ffprobe(args: list[str]) -> CompletedProcess[str]:
    return _run_command("ffprobe", args)


def _run_command(command: str, args: list[str]) -> CompletedProcess[str]:
    try:
        return run(
            [command, *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except CalledProcessError as exc:
        raise ExternalCommandError(
            command=command,
            exit_code=exc.returncode,
            stderr=exc.stderr or "",
        ) from exc
