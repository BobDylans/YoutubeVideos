from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime


PIPELINE_STEPS = ("download", "transcribe", "translate", "compose")


@dataclass(frozen=True)
class StepStatus:
    status: str
    updated_at: str


@dataclass(frozen=True)
class JobSettings:
    transcriber: str = "openai"
    translator: str = "deepseek"
    tts: str = "none"
    target_language: str = "zh"


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    url: str
    settings: JobSettings
    current_step: str
    steps: dict[str, StepStatus]
    artifacts: dict[str, str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "settings": asdict(self.settings),
            "current_step": self.current_step,
            "steps": {name: asdict(step) for name, step in self.steps.items()},
            "artifacts": self.artifacts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def create(
        cls,
        job_id: str,
        url: str,
        settings: JobSettings | None = None,
    ) -> "JobRecord":
        now = _timestamp()
        return cls(
            job_id=job_id,
            url=url,
            settings=settings or JobSettings(),
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
        steps = _normalize_steps(raw_steps)
        current_step = str(data["current_step"])
        if current_step not in steps:
            current_step = next(
                (
                    step_name
                    for step_name in PIPELINE_STEPS
                    if steps[step_name].status != "completed"
                ),
                PIPELINE_STEPS[-1],
            )
        return cls(
            job_id=str(data["job_id"]),
            url=str(data["url"]),
            settings=JobSettings(**dict(data.get("settings", {}))),
            current_step=current_step,
            steps=steps,
            artifacts={key: str(value) for key, value in dict(data.get("artifacts", {})).items()},
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )

    def with_step_status(self, step_name: str, status: str, *, current_step: str | None = None) -> "JobRecord":
        now = _timestamp()
        return JobRecord(
            job_id=self.job_id,
            url=self.url,
            settings=self.settings,
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
            settings=self.settings,
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
            if (artifact_step_index := _artifact_step_index(name)) is None
            or artifact_step_index < start_index
        }
        return JobRecord(
            job_id=self.job_id,
            url=self.url,
            settings=self.settings,
            current_step=step_name,
            steps=reset_steps,
            artifacts=remaining_artifacts,
            created_at=self.created_at,
            updated_at=now,
        )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _artifact_step_index(name: str) -> int | None:
    if name in PIPELINE_STEPS:
        return PIPELINE_STEPS.index(name)

    if name == "synthesize":
        return PIPELINE_STEPS.index("compose")

    step_prefix, _, _ = name.partition("_")
    if step_prefix in PIPELINE_STEPS:
        return PIPELINE_STEPS.index(step_prefix)

    if step_prefix == "synthesize":
        return PIPELINE_STEPS.index("compose")

    return None


def _normalize_steps(raw_steps: dict[str, object]) -> dict[str, StepStatus]:
    normalized: dict[str, StepStatus] = {}
    fallback_updated_at = _timestamp()
    for step_name in PIPELINE_STEPS:
        step_data = raw_steps.get(step_name)
        if isinstance(step_data, dict):
            normalized[step_name] = StepStatus(
                status=str(step_data["status"]),
                updated_at=str(step_data["updated_at"]),
            )
            continue

        normalized[step_name] = StepStatus(status="pending", updated_at=fallback_updated_at)

    return normalized
