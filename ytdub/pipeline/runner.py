from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import traceback
from typing import Protocol

from ytdub.models.job import JobRecord, JobSettings, PIPELINE_STEPS
from ytdub.storage.jobs import JobStore


@dataclass(frozen=True)
class StepResult:
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineRunResult:
    job: JobRecord
    executed_steps: list[str]


class PipelineStep(Protocol):
    name: str

    def run(self, job: JobRecord, work_dir: Path) -> StepResult: ...


class PipelineRunner:
    def __init__(self, store: JobStore, steps: dict[str, PipelineStep]) -> None:
        self.store = store
        self.steps = steps

    def run(self, url: str, settings: JobSettings | None = None) -> PipelineRunResult:
        job = self.store.create(url=url, settings=settings)
        return self._execute(job, self._remaining_steps(job))

    def resume(self, job_id: str) -> PipelineRunResult:
        job = self.store.load(job_id)
        return self._execute(job, self._remaining_steps(job))

    def rerun(self, job_id: str, from_step: str) -> PipelineRunResult:
        job = self.store.load(job_id).reset_from(from_step)
        self.store.save(job)
        return self._execute(job, PIPELINE_STEPS[PIPELINE_STEPS.index(from_step) :])

    def _execute(self, job: JobRecord, step_names: tuple[str, ...] | list[str]) -> PipelineRunResult:
        executed_steps: list[str] = []

        for step_name in step_names:
            step = self.steps[step_name]
            work_dir = self.store.root / job.job_id / step_name
            work_dir.mkdir(parents=True, exist_ok=True)

            job = self.store.save(job.with_step_status(step_name, "running"))
            try:
                result = step.run(job, work_dir)
            except Exception as exc:
                self.store.write_log(
                    job.job_id,
                    step_name,
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                )
                failed_job = job.with_step_status(step_name, "failed", current_step=step_name)
                self.store.save(failed_job)
                raise
            if result.artifacts:
                job = self.store.save(job.with_artifacts(result.artifacts))
            job = self.store.save(job.with_step_status(step_name, "completed"))
            executed_steps.append(step_name)

        return PipelineRunResult(job=self.store.load(job.job_id), executed_steps=executed_steps)

    @staticmethod
    def _remaining_steps(job: JobRecord) -> tuple[str, ...]:
        first_incomplete = next(
            (
                step_name
                for step_name in PIPELINE_STEPS
                if job.steps[step_name].status != "completed"
            ),
            None,
        )
        if first_incomplete is None:
            return ()
        return PIPELINE_STEPS[PIPELINE_STEPS.index(first_incomplete) :]
