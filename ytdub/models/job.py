from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime


PIPELINE_STEPS = ("download", "transcribe", "translate", "synthesize", "compose")


@dataclass(frozen=True)
class StepStatus:
    status: str
    updated_at: str


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    url: str
    current_step: str
    steps: dict[str, StepStatus]
    artifacts: dict[str, str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "current_step": self.current_step,
            "steps": {name: asdict(step) for name, step in self.steps.items()},
            "artifacts": self.artifacts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def create(cls, job_id: str, url: str) -> "JobRecord":
        now = _timestamp()
        return cls(
            job_id=job_id,
            url=url,
            current_step=PIPELINE_STEPS[0],
            steps={step_name: StepStatus(status="pending", updated_at=now) for step_name in PIPELINE_STEPS},
            artifacts={},
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "JobRecord":
        raw_steps = data["steps"]
        assert isinstance(raw_steps, dict)
        return cls(
            job_id=str(data["job_id"]),
            url=str(data["url"]),
            current_step=str(data["current_step"]),
            steps={
                step_name: StepStatus(
                    status=str(step_data["status"]),
                    updated_at=str(step_data["updated_at"]),
                )
                for step_name, step_data in raw_steps.items()
            },
            artifacts={key: str(value) for key, value in dict(data.get("artifacts", {})).items()},
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )

    def with_step_status(self, step_name: str, status: str, *, current_step: str | None = None) -> "JobRecord":
        now = _timestamp()
        return JobRecord(
            job_id=self.job_id,
            url=self.url,
            current_step=current_step or step_name,
            steps={
                **self.steps,
                step_name: StepStatus(status=status, updated_at=now),
            },
            artifacts=self.artifacts,
            created_at=self.created_at,
            updated_at=now,
        )

    def with_artifacts(self, artifacts: dict[str, str]) -> "JobRecord":
        now = _timestamp()
        return JobRecord(
            job_id=self.job_id,
            url=self.url,
            current_step=self.current_step,
            steps=self.steps,
            artifacts={**self.artifacts, **artifacts},
            created_at=self.created_at,
            updated_at=now,
        )

    def reset_from(self, step_name: str) -> "JobRecord":
        now = _timestamp()
        start_index = PIPELINE_STEPS.index(step_name)
        reset_steps = {
            name: (
                StepStatus(status="pending", updated_at=now)
                if index >= start_index
                else step
            )
            for index, (name, step) in enumerate(self.steps.items())
        }
        remaining_artifacts = {
            name: path
            for name, path in self.artifacts.items()
            if PIPELINE_STEPS.index(name) < start_index
        }
        return JobRecord(
            job_id=self.job_id,
            url=self.url,
            current_step=step_name,
            steps=reset_steps,
            artifacts=remaining_artifacts,
            created_at=self.created_at,
            updated_at=now,
        )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()
