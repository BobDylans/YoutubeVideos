from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from dataclasses import dataclass

from ytdub.config import load_config, resolve_job_settings, resolve_runtime_paths
from ytdub.models.job import JobRecord, JobSettings
from ytdub.pipeline.runner import PipelineRunner, StepResult
from ytdub.pipeline.steps import build_default_steps
from ytdub.providers.registry import create_runtime_registry
from ytdub.storage.jobs import JobStore
from ytdub.models.job import PIPELINE_STEPS

COMMAND_NAMES = (
    "run",
    "batch-run",
    "resume",
    "rerun",
    "list-jobs",
    "show-job",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ytdub")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("youtube_url")

    batch_parser = subparsers.add_parser("batch-run")
    batch_parser.add_argument("file")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("job_id")

    rerun_parser = subparsers.add_parser("rerun")
    rerun_parser.add_argument("job_id")
    rerun_parser.add_argument("--from", dest="from_step", required=True, choices=PIPELINE_STEPS)

    subparsers.add_parser("list-jobs")

    show_parser = subparsers.add_parser("show-job")
    show_parser.add_argument("job_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runner, store, job_settings = _build_runtime()

    if args.command == "run":
        result = runner.run(args.youtube_url, settings=job_settings)
        _print_json({"job_id": result.job.job_id, "executed_steps": result.executed_steps})
        return 0

    if args.command == "batch-run":
        results = []
        for line in Path(args.file).read_text(encoding="utf-8").splitlines():
            youtube_url = line.strip()
            if not youtube_url:
                continue
            result = runner.run(youtube_url, settings=job_settings)
            results.append({"job_id": result.job.job_id, "url": youtube_url})
        _print_json(results)
        return 0

    if args.command == "resume":
        result = runner.resume(args.job_id)
        _print_json({"job_id": result.job.job_id, "executed_steps": result.executed_steps})
        return 0

    if args.command == "rerun":
        result = runner.rerun(args.job_id, from_step=args.from_step)
        _print_json({"job_id": result.job.job_id, "executed_steps": result.executed_steps})
        return 0

    if args.command == "list-jobs":
        _print_json([job.to_dict() for job in store.list_jobs()])
        return 0

    if args.command == "show-job":
        _print_json(store.load(args.job_id).to_dict())
        return 0

    return 0


def _build_runtime() -> tuple[PipelineRunner, JobStore, JobSettings]:
    config = load_config(Path("configs/default.toml"))
    runtime_paths = resolve_runtime_paths(config)
    store = JobStore(runtime_paths.jobs_dir)
    steps = (
        build_stub_steps()
        if os.environ.get("YTDUB_USE_STUB_STEPS") == "1"
        else build_default_steps(create_runtime_registry(config))
    )
    runner = PipelineRunner(store=store, steps=steps)
    job_settings = resolve_job_settings(config)
    return runner, store, job_settings


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))


@dataclass
class _StubStep:
    name: str

    def run(self, job: JobRecord, work_dir: Path) -> StepResult:
        suffix = "mp4" if self.name == "compose" else "json"
        artifact = work_dir / f"{self.name}.{suffix}"
        artifact.write_text(f"{job.job_id}:{self.name}", encoding="utf-8")
        return StepResult(artifacts={self.name: str(artifact)})


def build_stub_steps() -> dict[str, _StubStep]:
    return {name: _StubStep(name) for name in PIPELINE_STEPS}


if __name__ == "__main__":
    raise SystemExit(main())
