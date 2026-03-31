from __future__ import annotations

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
    assert [job.url for job in jobs] == [
        "https://youtube.com/watch?v=first",
        "https://youtube.com/watch?v=second",
    ]
