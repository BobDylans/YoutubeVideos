from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytdub.models.job import JobRecord
from ytdub.pipeline.steps.compose import ComposeStep
from ytdub.pipeline.steps.download import DownloadStep
from ytdub.pipeline.steps.transcribe import TranscribeStep
from ytdub.pipeline.runner import PipelineRunner, StepResult
from ytdub.storage.jobs import JobStore


@dataclass
class FakeStep:
    name: str

    def run(self, job, work_dir: Path) -> StepResult:
        artifact_path = work_dir / f"{self.name}.txt"
        artifact_path.write_text(f"{job.job_id}:{self.name}", encoding="utf-8")
        return StepResult(artifacts={self.name: str(artifact_path)})


def build_runner(tmp_path: Path) -> tuple[PipelineRunner, JobStore]:
    jobs_dir = tmp_path / "jobs"
    store = JobStore(jobs_dir)
    steps = {name: FakeStep(name) for name in ("download", "transcribe", "translate", "synthesize", "compose")}
    return PipelineRunner(store=store, steps=steps), store


def test_runner_skips_completed_steps(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)
    job = store.create(url="https://youtube.com/watch?v=abc")
    store.update_step(job.job_id, "download", "completed")

    result = runner.resume(job.job_id)
    loaded = store.load(job.job_id)

    assert "download" not in result.executed_steps
    assert result.executed_steps == ["transcribe", "translate", "synthesize", "compose"]
    assert loaded.steps["compose"].status == "completed"


def test_rerun_invalidates_selected_step_and_downstream(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)
    result = runner.run("https://youtube.com/watch?v=abc")

    rerun_result = runner.rerun(result.job.job_id, from_step="translate")
    loaded = store.load(result.job.job_id)

    assert rerun_result.executed_steps == ["translate", "synthesize", "compose"]
    assert loaded.steps["download"].status == "completed"
    assert loaded.steps["translate"].status == "completed"
    assert loaded.current_step == "compose"


def test_runner_registers_artifacts_and_step_directories(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)

    result = runner.run("https://youtube.com/watch?v=abc")
    loaded = store.load(result.job.job_id)
    job_root = tmp_path / "jobs" / result.job.job_id

    assert (job_root / "download").is_dir()
    assert (job_root / "compose").is_dir()
    assert loaded.artifacts["compose"].endswith("compose/compose.txt")


def test_compose_step_writes_final_artifacts(tmp_path: Path) -> None:
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc")
    step = ComposeStep()

    result = step.run(job, tmp_path)

    assert result.artifacts["compose"].endswith(".mp4")
    assert result.artifacts["compose_srt"].endswith(".srt")
    assert Path(result.artifacts["compose"]).exists()
    assert Path(result.artifacts["compose_srt"]).exists()


def test_download_step_uses_ytdlp_and_returns_downloaded_file(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run_ytdlp(args: list[str]):
        captured["args"] = args
        (tmp_path / "source.mp4").write_text("video", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.download.run_ytdlp", fake_run_ytdlp)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc")
    step = DownloadStep()

    result = step.run(job, tmp_path)

    assert "--output" in captured["args"]
    assert "https://youtube.com/watch?v=abc" in captured["args"]
    assert result.artifacts["download"].endswith("source.mp4")


def test_transcribe_step_extracts_audio_and_writes_transcript(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list[str]] = {}
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video", encoding="utf-8")

    def fake_run_ffmpeg(args: list[str]):
        captured["args"] = args
        (tmp_path / "source.wav").write_text("audio", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.transcribe.run_ffmpeg", fake_run_ffmpeg)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {"download": str(source_video)}
    )
    step = TranscribeStep()

    result = step.run(job, tmp_path)

    assert captured["args"][0] == "-i"
    assert str(source_video) in captured["args"]
    assert result.artifacts["transcribe"].endswith("transcript.json")
