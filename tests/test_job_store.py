from __future__ import annotations

from ytdub.models.job import JobSettings
from ytdub.models.job import JobRecord
from ytdub.storage.jobs import JobStore


def test_create_job_writes_job_json(tmp_path) -> None:
    store = JobStore(tmp_path)

    job = store.create(url="https://youtube.com/watch?v=abc123")

    assert job.job_id
    assert (tmp_path / job.job_id / "job.json").exists()
    assert job.current_step == "download"
    assert job.steps["download"].status == "pending"


def test_update_and_list_jobs(tmp_path) -> None:
    store = JobStore(tmp_path)
    first = store.create(url="https://youtube.com/watch?v=first")
    second = store.create(url="https://youtube.com/watch?v=second")

    updated = store.update_step(second.job_id, "download", "completed")
    loaded = store.load(second.job_id)
    jobs = store.list_jobs()

    assert updated.steps["download"].status == "completed"
    assert loaded.steps["download"].status == "completed"
    assert sorted(job.url for job in jobs) == [
        "https://youtube.com/watch?v=first",
        "https://youtube.com/watch?v=second",
    ]


def test_create_job_persists_job_settings(tmp_path) -> None:
    store = JobStore(tmp_path)

    job = store.create(
        url="https://youtube.com/watch?v=abc123",
        settings=JobSettings(
            transcriber="deepgram",
            translator="deepl",
            tts="elevenlabs",
            target_language="ja",
        ),
    )
    loaded = store.load(job.job_id)

    assert loaded.settings.translator == "deepl"
    assert loaded.settings.tts == "elevenlabs"
    assert loaded.settings.target_language == "ja"


def test_job_record_from_dict_drops_deprecated_synthesize_step() -> None:
    job = JobRecord.from_dict(
        {
            "job_id": "job-123",
            "url": "https://youtube.com/watch?v=abc123",
            "settings": {
                "transcriber": "openai",
                "translator": "deepseek",
                "tts": "openai",
                "target_language": "zh",
            },
            "current_step": "synthesize",
            "steps": {
                "download": {"status": "completed", "updated_at": "2026-01-01T00:00:00+00:00"},
                "transcribe": {"status": "completed", "updated_at": "2026-01-01T00:00:01+00:00"},
                "translate": {"status": "completed", "updated_at": "2026-01-01T00:00:02+00:00"},
                "synthesize": {"status": "failed", "updated_at": "2026-01-01T00:00:03+00:00"},
                "compose": {"status": "pending", "updated_at": "2026-01-01T00:00:04+00:00"},
            },
            "artifacts": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:04+00:00",
        }
    )

    assert list(job.steps) == ["download", "transcribe", "translate", "compose"]
    assert job.current_step == "compose"
