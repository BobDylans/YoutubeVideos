from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import traceback
from typing import Protocol

from ytdub.models.job import JobRecord, JobSettings, PIPELINE_STEPS
from ytdub.storage.jobs import JobStore

# 每一个step执行完毕都会返回一个结果对象
@dataclass(frozen=True)
class StepResult:
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
# 这个是整个pipeLine跑完之后返回的结果,job是job的最终状态
class PipelineRunResult:
    job: JobRecord
    executed_steps: list[str]

# 这里说明只要某个对象的特征符合 1.拥有name 2.有run(job,work_dir)
# 就可以被视为一个Pipeline
class PipelineStep(Protocol):
    name: str

    def run(self, job: JobRecord, work_dir: Path) -> StepResult: ...


class PipelineRunner:
    def __init__(self, store: JobStore, steps: dict[str, PipelineStep]) -> None:
        self.store = store
        self.steps = steps
    # 创建一个新的job,执行它还没有执行完的部分
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
    # 这个方法是核心,在这里进行整体的调用
    # 注意这里的参数,说明step_names可以是一个字符串列表,也可以是一个字符串元组
    def _execute(self, job: JobRecord, step_names: tuple[str, ...] | list[str]) -> PipelineRunResult:
        executed_steps: list[str] = []
        # 遍历要执行的step名称
        # 找到对应的step对象
        for step_name in step_names:
            step = self.steps[step_name]
            work_dir = self.store.root / job.job_id / step_name
            # 创建该step对应的文件目录
            work_dir.mkdir(parents=True, exist_ok=True)
            # 修改job的状态
            job = self.store.save(job.with_step_status(step_name, "running"))
            try:
                # 执行step
                result = step.run(job, work_dir)
            # 如果执行失败就记录日志
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
