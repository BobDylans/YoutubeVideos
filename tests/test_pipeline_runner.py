from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ytdub.media.ffmpeg import ExternalCommandError
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
    steps = {name: FakeStep(name) for name in ("download", "transcribe", "translate", "compose")}
    return PipelineRunner(store=store, steps=steps), store


def test_runner_skips_completed_steps(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)
    job = store.create(url="https://youtube.com/watch?v=abc")
    store.update_step(job.job_id, "download", "completed")

    result = runner.resume(job.job_id)
    loaded = store.load(job.job_id)

    assert "download" not in result.executed_steps
    assert result.executed_steps == ["transcribe", "translate", "compose"]
    assert loaded.steps["compose"].status == "completed"


def test_rerun_invalidates_selected_step_and_downstream(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)
    result = runner.run("https://youtube.com/watch?v=abc")

    rerun_result = runner.rerun(result.job.job_id, from_step="translate")
    loaded = store.load(result.job.job_id)

    assert rerun_result.executed_steps == ["translate", "compose"]
    assert loaded.steps["download"].status == "completed"
    assert loaded.steps["translate"].status == "completed"
    assert loaded.current_step == "compose"


def test_rerun_handles_auxiliary_artifacts_linked_to_pipeline_steps(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)
    result = runner.run("https://youtube.com/watch?v=abc")
    job = store.load(result.job.job_id).with_artifacts(
        {
            "transcribe_audio": str(tmp_path / "jobs" / result.job.job_id / "transcribe" / "source.wav"),
            "compose_srt": str(tmp_path / "jobs" / result.job.job_id / "compose" / "final-subtitles.srt"),
        }
    )
    store.save(job)

    rerun_result = runner.rerun(result.job.job_id, from_step="translate")
    loaded = store.load(result.job.job_id)

    assert rerun_result.executed_steps == ["translate", "compose"]
    assert "download" in loaded.artifacts
    assert "transcribe_audio" in loaded.artifacts
    assert "compose_srt" not in loaded.artifacts


def test_runner_registers_artifacts_and_step_directories(tmp_path: Path) -> None:
    runner, store = build_runner(tmp_path)

    result = runner.run("https://youtube.com/watch?v=abc")
    loaded = store.load(result.job.job_id)
    job_root = tmp_path / "jobs" / result.job.job_id

    assert (job_root / "download").is_dir()
    assert (job_root / "compose").is_dir()
    compose_artifact = Path(loaded.artifacts["compose"])
    assert compose_artifact.parent.name == "compose"
    assert compose_artifact.name == "compose.txt"


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
    ffmpeg_calls: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]):
        ffmpeg_calls.append(args)
        if str(tmp_path / "final-video.mp4") in args:
            (tmp_path / "final-video.mp4").write_text("final", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.compose.run_ffmpeg", fake_run_ffmpeg)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {
            "download": str(source_video),
            "translate": str(translation_path),
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
    assert len(ffmpeg_calls) == 1
    assert ffmpeg_calls[0][:2] == ["-i", str(source_video)]
    assert "0:a?" in ffmpeg_calls[0]
    assert "-vf" in ffmpeg_calls[0]
    assert "subtitles='" in ffmpeg_calls[0][ffmpeg_calls[0].index("-vf") + 1]
    assert "libx264" in ffmpeg_calls[0]
    assert "aac" in ffmpeg_calls[0]
    assert str(tmp_path / "final-video.mp4") == ffmpeg_calls[0][-1]


def test_download_step_uses_ytdlp_and_returns_downloaded_file(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run_ytdlp(args: list[str]):
        captured["args"] = args
        (tmp_path / "source.mp4").write_text("video", encoding="utf-8")
        (tmp_path / "source.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.download.run_ytdlp", fake_run_ytdlp)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc")
    step = DownloadStep()

    result = step.run(job, tmp_path)

    assert "--output" in captured["args"]
    assert "--write-subs" in captured["args"]
    assert "--write-auto-subs" in captured["args"]
    assert "--sub-langs" in captured["args"]
    assert "en.*" in captured["args"]
    assert "--convert-subs" in captured["args"]
    assert "srt" in captured["args"]
    assert "https://youtube.com/watch?v=abc" in captured["args"]
    assert result.artifacts["download"].endswith("source.mp4")
    assert result.artifacts["download_subtitles"].endswith("source.en.srt")


def test_download_step_retries_without_subtitles_when_ytdlp_subtitle_fetch_fails(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []

    def fake_run_ytdlp(args: list[str]):
        calls.append(args)
        if len(calls) == 1:
            raise ExternalCommandError(
                command="yt-dlp",
                exit_code=1,
                stderr="ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests",
            )
        (tmp_path / "source.webm").write_text("video", encoding="utf-8")
        return None

    monkeypatch.setattr("ytdub.pipeline.steps.download.run_ytdlp", fake_run_ytdlp)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc")
    step = DownloadStep()

    result = step.run(job, tmp_path)

    assert len(calls) == 2
    assert "--write-subs" in calls[0]
    assert "--write-subs" not in calls[1]
    assert "--write-auto-subs" not in calls[1]
    assert result.artifacts["download"].endswith("source.webm")
    assert "download_subtitles" not in result.artifacts


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
    assert "-ac" in captured["args"]
    assert captured["args"][captured["args"].index("-ac") + 1] == "1"
    assert "-ar" in captured["args"]
    assert captured["args"][captured["args"].index("-ar") + 1] == "16000"
    assert result.artifacts["transcribe"].endswith("transcript.json")


def test_transcribe_step_uses_downloaded_subtitles_before_asr(tmp_path: Path, monkeypatch) -> None:
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video", encoding="utf-8")
    subtitle_path = tmp_path / "source.en.srt"
    stale_audio_path = tmp_path / "source.wav"
    stale_audio_path.write_text("stale", encoding="utf-8")
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,200\nHello world\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\nSecond line\n",
        encoding="utf-8",
    )

    def fail_run_ffmpeg(_args: list[str]):
        raise AssertionError("ffmpeg should not run when downloaded subtitles are available")

    class FakeTranscriber:
        def transcribe(self, _audio_path: Path, transport=None) -> list[Segment]:
            raise AssertionError("ASR provider should not run when downloaded subtitles are available")

    monkeypatch.setattr("ytdub.pipeline.steps.transcribe.run_ffmpeg", fail_run_ffmpeg)
    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {
            "download": str(source_video),
            "download_subtitles": str(subtitle_path),
        }
    )
    step = TranscribeStep(transcriber=FakeTranscriber())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["transcribe"]).read_text(encoding="utf-8"))

    assert payload["provider"] == "youtube_subtitles"
    assert payload["extracted_audio"] is None
    assert "transcribe_audio" not in result.artifacts
    assert not stale_audio_path.exists()
    assert payload["segments"] == [
        {"start_ms": 0, "end_ms": 1200, "text": "Hello world"},
        {"start_ms": 1500, "end_ms": 3000, "text": "Second line"},
    ]


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


def test_translate_step_reshapes_long_translated_segments_for_subtitles(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_ms": 0,
                        "end_ms": 6000,
                        "text": "First we check the shelves then we check the back room and finally we call the manager",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTranslator:
        def translate_segments(self, segments: list[Segment], target_language: str, transport=None) -> list[Segment]:
            assert len(segments) == 1
            assert target_language == "zh"
            return [
                Segment(
                    start_ms=0,
                    end_ms=6000,
                    text="First we check the shelves, then we check the back room, and finally we call the manager.",
                )
            ]

    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {"transcribe": str(transcript_path)}
    )
    step = TranslateStep(translator=FakeTranslator())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["translate"]).read_text(encoding="utf-8"))

    assert [segment["text"] for segment in payload["segments"]] == [
        "First we check the shelves,",
        "then we check the back room,",
        "and finally we call the manager.",
    ]
    assert payload["segments"][0]["start_ms"] == 0
    assert payload["segments"][-1]["end_ms"] == 6000


def test_translate_step_normalizes_chinese_punctuation_and_semantic_breaks(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_ms": 0,
                        "end_ms": 6000,
                        "text": "we first check the shelves and then the back room and finally call the manager",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTranslator:
        def translate_segments(self, segments: list[Segment], target_language: str, transport=None) -> list[Segment]:
            assert len(segments) == 1
            assert target_language == "zh"
            return [
                Segment(
                    start_ms=0,
                    end_ms=6000,
                    text="我们先检查货架然后检查后仓最后给经理打电话",
                )
            ]

    job = JobRecord.create(job_id="job-123", url="https://youtube.com/watch?v=abc").with_artifacts(
        {"transcribe": str(transcript_path)}
    )
    step = TranslateStep(translator=FakeTranslator())

    result = step.run(job, tmp_path)
    payload = json.loads(Path(result.artifacts["translate"]).read_text(encoding="utf-8"))

    assert [segment["text"] for segment in payload["segments"]] == [
        "我们先检查货架，",
        "然后检查后仓，",
        "最后给经理打电话。",
    ]


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
