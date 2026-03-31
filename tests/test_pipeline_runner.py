from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ytdub.models.job import JobRecord, JobSettings
from ytdub.models.segments import Segment
from ytdub.pipeline.steps.compose import ComposeStep
from ytdub.pipeline.steps.download import DownloadStep
from ytdub.pipeline.steps.synthesize import SynthesizeStep
from ytdub.pipeline.steps.transcribe import TranscribeStep
from ytdub.pipeline.steps.translate import TranslateStep
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


def test_runner_records_step_failures_in_job_and_log(tmp_path: Path) -> None:
    @dataclass
    class FailingStep:
        name: str = "transcribe"

        def run(self, job, work_dir: Path) -> StepResult:
            raise RuntimeError(f"boom for {job.job_id}")

    jobs_dir = tmp_path / "jobs"
    store = JobStore(jobs_dir)
    steps = {
        "download": FakeStep("download"),
        "transcribe": FailingStep(),
        "translate": FakeStep("translate"),
        "synthesize": FakeStep("synthesize"),
        "compose": FakeStep("compose"),
    }
    runner = PipelineRunner(store=store, steps=steps)

    with pytest.raises(RuntimeError, match="boom"):
        runner.run("https://youtube.com/watch?v=abc")

    job = store.list_jobs()[0]
    log_path = jobs_dir / job.job_id / "logs" / "transcribe.log"

    assert job.steps["download"].status == "completed"
    assert job.steps["transcribe"].status == "failed"
    assert job.current_step == "transcribe"
    assert log_path.exists()
    assert "boom" in log_path.read_text(encoding="utf-8")


def test_compose_step_writes_final_artifacts(tmp_path: Path, monkeypatch) -> None:
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video", encoding="utf-8")
    clip_one = tmp_path / "segment-0001.mp3"
    clip_two = tmp_path / "segment-0002.mp3"
    clip_one.write_text("one", encoding="utf-8")
    clip_two.write_text("two", encoding="utf-8")
    translation_path = tmp_path / "translation.json"
    translation_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"start_ms": 0, "end_ms": 500, "text": "bonjour"},
                    {"start_ms": 600, "end_ms": 1000, "text": "monde"},
                ]
            }
        ),
        encoding="utf-8",
    )
    synthesize_path = tmp_path / "dubbed-audio.json"
    synthesize_path.write_text(
        json.dumps(
            {
                "clips": [
                    {"audio_path": str(clip_one), "text": "bonjour"},
                    {"audio_path": str(clip_two), "text": "monde"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ffmpeg_calls: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]):
        ffmpeg_calls.append(args)
        if str(tmp_path / "merged-dub.mp3") in args:
            (tmp_path / "merged-dub.mp3").write_text("merged", encoding="utf-8")
        if str(tmp_path / "final-video.mp4") in args:
            (tmp_path / "final-video.mp4").write_text("final", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.compose.run_ffmpeg", fake_run_ffmpeg)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {
            "download": str(source_video),
            "translate": str(translation_path),
            "synthesize": str(synthesize_path),
        }
    )
    step = ComposeStep()

    result = step.run(job, tmp_path)

    assert result.artifacts["compose"].endswith(".mp4")
    assert result.artifacts["compose_srt"].endswith(".srt")
    assert Path(result.artifacts["compose"]).exists()
    assert Path(result.artifacts["compose_srt"]).exists()
    assert "bonjour" in Path(result.artifacts["compose_srt"]).read_text(encoding="utf-8")
    assert "monde" in Path(result.artifacts["compose_srt"]).read_text(encoding="utf-8")
    assert len(ffmpeg_calls) == 2


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


def test_transcribe_step_writes_segments_from_selected_provider(tmp_path: Path, monkeypatch) -> None:
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video", encoding="utf-8")

    def fake_run_ffmpeg(_args: list[str]):
        (tmp_path / "source.wav").write_text("audio", encoding="utf-8")
        return None

    class FakeTranscriber:
        def transcribe(self, audio_path: Path, transport=None) -> list[Segment]:
            assert audio_path.name == "source.wav"
            return [Segment(start_ms=0, end_ms=1000, text="hello world")]

    monkeypatch.setattr("ytdub.pipeline.steps.transcribe.run_ffmpeg", fake_run_ffmpeg)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {"download": str(source_video)}
    )
    step = TranscribeStep(transcriber=FakeTranscriber())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["transcribe"]).read_text(encoding="utf-8"))

    assert payload["segments"] == [{"start_ms": 0, "end_ms": 1000, "text": "hello world"}]


def test_translate_step_records_provider_and_target_language(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text('{"segments": []}', encoding="utf-8")
    job = JobRecord.create(
        job_id="job-123",
        url="https://youtube.com/watch?v=abc",
        settings=JobSettings(
            transcriber="deepgram",
            translator="deepl",
            tts="openai",
            target_language="fr",
        ),
    ).with_artifacts({"transcribe": str(transcript_path)})
    step = TranslateStep()

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["translate"]).read_text(encoding="utf-8"))

    assert payload["provider"] == "deepl"
    assert payload["target_language"] == "fr"


def test_translate_step_uses_translator_for_segments(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"start_ms": 0, "end_ms": 500, "text": "hello"},
                    {"start_ms": 600, "end_ms": 1000, "text": "world"},
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTranslator:
        def translate_segments(self, segments: list[Segment], target_language: str, transport=None) -> list[Segment]:
            assert [segment.text for segment in segments] == ["hello", "world"]
            assert target_language == "fr"
            return [
                Segment(start_ms=0, end_ms=500, text="bonjour"),
                Segment(start_ms=600, end_ms=1000, text="monde"),
            ]

    job = JobRecord.create(
        job_id="job-123",
        url="https://youtube.com/watch?v=abc",
        settings=JobSettings(
            transcriber="deepgram",
            translator="deepl",
            tts="openai",
            target_language="fr",
        ),
    ).with_artifacts({"transcribe": str(transcript_path)})
    step = TranslateStep(translator=FakeTranslator())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["translate"]).read_text(encoding="utf-8"))

    assert [segment["text"] for segment in payload["segments"]] == ["bonjour", "monde"]


def test_synthesize_step_records_selected_tts_provider(tmp_path: Path) -> None:
    translation_path = tmp_path / "translation.json"
    translation_path.write_text('{"segments": []}', encoding="utf-8")
    job = JobRecord.create(
        job_id="job-123",
        url="https://youtube.com/watch?v=abc",
        settings=JobSettings(
            transcriber="deepgram",
            translator="deepl",
            tts="elevenlabs",
            target_language="fr",
        ),
    ).with_artifacts({"translate": str(translation_path)})
    step = SynthesizeStep()

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["synthesize"]).read_text(encoding="utf-8"))

    assert payload["provider"] == "elevenlabs"
    assert payload["target_language"] == "fr"


def test_synthesize_step_uses_tts_provider_for_each_segment(tmp_path: Path) -> None:
    translation_path = tmp_path / "translation.json"
    translation_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"start_ms": 0, "end_ms": 500, "text": "bonjour"},
                    {"start_ms": 600, "end_ms": 1000, "text": "monde"},
                ]
            }
        ),
        encoding="utf-8",
    )

    written_paths: list[Path] = []

    class FakeSynthesizer:
        def synthesize_segment(self, segment: Segment, output_path: Path, transport=None) -> Path:
            output_path.write_text(segment.text, encoding="utf-8")
            written_paths.append(output_path)
            return output_path

    job = JobRecord.create(
        job_id="job-123",
        url="https://youtube.com/watch?v=abc",
        settings=JobSettings(
            transcriber="deepgram",
            translator="deepl",
            tts="elevenlabs",
            target_language="fr",
        ),
    ).with_artifacts({"translate": str(translation_path)})
    step = SynthesizeStep(synthesizer=FakeSynthesizer())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["synthesize"]).read_text(encoding="utf-8"))

    assert len(written_paths) == 2
    assert payload["clips"][0]["text"] == "bonjour"
    assert payload["clips"][1]["text"] == "monde"
