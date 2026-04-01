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

# 规定好里面具体有哪些参数
# 命令名常量的集合
COMMAND_NAMES = (
    "run",
    "batch-run",
    "resume",
    "rerun",
    "list-jobs",
    "show-job",
)

# 创建一个命令行参数解析器,定义好了每一个子命令的参数规则
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ytdub")
    subparsers = parser.add_subparsers(dest="command")
    # 说明这个指令是必须的
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
    # 先创建一个命令行解释器
    parser = build_parser()
    # 再将参数格式化成可以直接调用的类型
    args = parser.parse_args(argv)
    runner, store, job_settings = _build_runtime()
    # 解析用户输入的指令的具体内容
    if args.command == "run":
        # 具体的实现交给runner来完成,cli部分只负责最基本的词义解析和结果的返回
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

# 返回值是具体用于执行的runner,记录job执行情况和结果的store,执行过程中需要知道的配置信息
def _build_runtime() -> tuple[PipelineRunner, JobStore, JobSettings]:
    # 从配置文件取出相关的信息
    config = load_config(Path("configs/default.toml"))
    runtime_paths = resolve_runtime_paths(config)
    # 在这里确认Job(也就是每一个任务)的存储地址,方便存储中间结果和最终效果
    store = JobStore(runtime_paths.jobs_dir)
    job_settings = resolve_job_settings(config)
    # 实际上返回可用的steps是通过build_stub_steps()实现的
    # 下面的参数实际上等效于检查环境变量中是否允许真的进行调用(而非测试)
    # 如果是测试就调用第一个方法build_stub_steps(),否则就使用第二个方法build_default_steps()
    steps = (
        build_stub_steps()
        if os.environ.get("YTDUB_USE_STUB_STEPS") == "1"
        else build_default_steps(create_runtime_registry(config, job_settings))
    )
    # 将相关的参数传入runner中,并返回一个可以直接使用的runner
    runner = PipelineRunner(store=store, steps=steps)
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
