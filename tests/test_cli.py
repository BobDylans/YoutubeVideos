from __future__ import annotations

import json
import os
from pathlib import Path
from subprocess import run


def invoke_cli(args: list[str], tmp_path: Path):
    env = {
        **os.environ,
        "YTDUB_JOBS_DIR": str(tmp_path / "jobs"),
        "YTDUB_OUTPUTS_DIR": str(tmp_path / "outputs"),
        "YTDUB_USE_STUB_STEPS": "1",
    }
    return run(
        ["python", "-m", "ytdub.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_cli_shows_help() -> None:
    result = run(["python", "-m", "ytdub.cli", "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "run" in result.stdout


def test_run_command_accepts_url(tmp_path: Path) -> None:
    result = invoke_cli(["run", "https://youtube.com/watch?v=abc"], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["job_id"]
    assert payload["executed_steps"] == ["download", "transcribe", "translate", "synthesize", "compose"]


def test_show_job_command_prints_saved_job(tmp_path: Path) -> None:
    run_result = invoke_cli(["run", "https://youtube.com/watch?v=abc"], tmp_path)
    job_id = json.loads(run_result.stdout)["job_id"]

    result = invoke_cli(["show-job", job_id], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["job_id"] == job_id
    assert payload["url"] == "https://youtube.com/watch?v=abc"


def test_resume_command_handles_existing_job(tmp_path: Path) -> None:
    run_result = invoke_cli(["run", "https://youtube.com/watch?v=abc"], tmp_path)
    job_id = json.loads(run_result.stdout)["job_id"]

    result = invoke_cli(["resume", job_id], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["job_id"] == job_id
    assert payload["executed_steps"] == []


def test_batch_run_reads_url_file(tmp_path: Path) -> None:
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://youtube.com/watch?v=1\nhttps://youtube.com/watch?v=2\n", encoding="utf-8")

    result = invoke_cli(["batch-run", str(url_file)], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 2
    assert payload[0]["url"] == "https://youtube.com/watch?v=1"
    assert payload[1]["url"] == "https://youtube.com/watch?v=2"


def test_list_jobs_returns_saved_jobs(tmp_path: Path) -> None:
    invoke_cli(["run", "https://youtube.com/watch?v=abc"], tmp_path)
    invoke_cli(["run", "https://youtube.com/watch?v=xyz"], tmp_path)

    result = invoke_cli(["list-jobs"], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [job["url"] for job in payload] == [
        "https://youtube.com/watch?v=abc",
        "https://youtube.com/watch?v=xyz",
    ]
