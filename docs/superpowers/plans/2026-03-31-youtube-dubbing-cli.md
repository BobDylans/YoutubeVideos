# YouTube Dubbing CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that downloads YouTube videos, transcribes them, translates subtitles, synthesizes dubbed speech via switchable providers, and composes a final MP4 while preserving intermediate artifacts and resumable job state.

**Architecture:** Use a local pipeline orchestrator in Python, fixed local integrations for `yt-dlp` and `ffmpeg`, and provider adapters for transcription, translation, and TTS. Persist every job to disk so runs can resume or rerun from a chosen step without redoing unaffected work.

**Tech Stack:** Python 3.11+, `argparse`, `dataclasses`, `pathlib`, `json`, `tomllib`, `subprocess`, `httpx`, `pytest`, `yt-dlp`, `ffmpeg`, `ffprobe`

---

## File Map

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `configs/default.toml`
- Create: `app/ytdub/__init__.py`
- Create: `app/ytdub/cli.py`
- Create: `app/ytdub/config.py`
- Create: `app/ytdub/models/__init__.py`
- Create: `app/ytdub/models/job.py`
- Create: `app/ytdub/models/segments.py`
- Create: `app/ytdub/storage/__init__.py`
- Create: `app/ytdub/storage/jobs.py`
- Create: `app/ytdub/pipeline/__init__.py`
- Create: `app/ytdub/pipeline/runner.py`
- Create: `app/ytdub/pipeline/steps/__init__.py`
- Create: `app/ytdub/pipeline/steps/download.py`
- Create: `app/ytdub/pipeline/steps/transcribe.py`
- Create: `app/ytdub/pipeline/steps/translate.py`
- Create: `app/ytdub/pipeline/steps/synthesize.py`
- Create: `app/ytdub/pipeline/steps/compose.py`
- Create: `app/ytdub/providers/__init__.py`
- Create: `app/ytdub/providers/base.py`
- Create: `app/ytdub/providers/registry.py`
- Create: `app/ytdub/providers/transcribers/__init__.py`
- Create: `app/ytdub/providers/transcribers/deepgram.py`
- Create: `app/ytdub/providers/translators/__init__.py`
- Create: `app/ytdub/providers/translators/deepl.py`
- Create: `app/ytdub/providers/tts/__init__.py`
- Create: `app/ytdub/providers/tts/openai.py`
- Create: `app/ytdub/providers/tts/elevenlabs.py`
- Create: `app/ytdub/media/__init__.py`
- Create: `app/ytdub/media/ffmpeg.py`
- Create: `app/ytdub/media/ytdlp.py`
- Create: `app/ytdub/media/subtitles.py`
- Create: `app/ytdub/utils/__init__.py`
- Create: `app/ytdub/utils/logging.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_config.py`
- Create: `tests/test_job_store.py`
- Create: `tests/test_provider_registry.py`
- Create: `tests/test_pipeline_runner.py`
- Create: `tests/test_subtitles.py`
- Create: `tests/providers/test_deepgram.py`
- Create: `tests/providers/test_deepl.py`
- Create: `tests/providers/test_openai_tts.py`
- Create: `tests/providers/test_elevenlabs_tts.py`

## Implementation Notes

- Use `src`-style packaging only if it simplifies local execution. Otherwise keep `app/ytdub` and set `pyproject.toml` accordingly.
- Prefer standard library config parsing with `tomllib`.
- Use fake providers and mocked subprocess calls in tests.
- Do not hardcode API keys. Read them from environment variables named in config.
- The project is not yet a Git repository. Commit steps below are conditional and should be skipped until Git is initialized.

## Chunk 1: Project Skeleton And Config

### Task 1: Bootstrap the Python project layout

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `app/ytdub/__init__.py`
- Create: `app/ytdub/cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
from subprocess import run

def test_cli_shows_help():
    result = run(["python", "-m", "ytdub.cli", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "run" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_shows_help -v`
Expected: FAIL because package and entrypoint do not exist yet

- [ ] **Step 3: Create `pyproject.toml` and minimal package entrypoint**

```python
def main() -> int:
    return 0
```

- [ ] **Step 4: Wire basic argparse help output**

```python
parser.add_argument("--help", action="help")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_shows_help -v`
Expected: PASS

- [ ] **Step 6: Commit if Git is initialized**

```bash
git add pyproject.toml README.md app/ytdub/__init__.py app/ytdub/cli.py tests/test_cli.py
git commit -m "feat: bootstrap youtube dubbing cli"
```

### Task 2: Add configuration loading and validation

**Files:**
- Create: `configs/default.toml`
- Create: `app/ytdub/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing config parsing tests**

```python
def test_loads_default_provider_names():
    config = load_config("configs/default.toml")
    assert config.providers.transcriber == "deepgram"
    assert config.providers.translator == "deepl"
    assert config.providers.tts == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL because config loader does not exist

- [ ] **Step 3: Create TOML config schema and loader**

```python
@dataclass(frozen=True)
class ProviderConfig:
    transcriber: str
    translator: str
    tts: str
```

- [ ] **Step 4: Validate required settings and environment variable names**

Run: `pytest tests/test_config.py -v`
Expected: PASS for valid config and FAIL for missing keys when extra validation tests are added

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add configs/default.toml app/ytdub/config.py tests/test_config.py
git commit -m "feat: add config loading and validation"
```

## Chunk 2: Job State, Storage, And Local Media Wrappers

### Task 3: Implement the on-disk job store

**Files:**
- Create: `app/ytdub/models/__init__.py`
- Create: `app/ytdub/models/job.py`
- Create: `app/ytdub/storage/__init__.py`
- Create: `app/ytdub/storage/jobs.py`
- Create: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing job lifecycle tests**

```python
def test_create_job_writes_job_json(tmp_path):
    store = JobStore(tmp_path)
    job = store.create(url="https://youtube.com/watch?v=abc")
    assert (tmp_path / job.job_id / "job.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_store.py -v`
Expected: FAIL because job model and store do not exist

- [ ] **Step 3: Create dataclasses for step status and job metadata**

```python
@dataclass
class JobRecord:
    job_id: str
    url: str
    current_step: str
    steps: dict[str, dict]
```

- [ ] **Step 4: Implement create, load, update, and list operations**

Run: `pytest tests/test_job_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add app/ytdub/models app/ytdub/storage tests/test_job_store.py
git commit -m "feat: add on-disk job storage"
```

### Task 4: Wrap `yt-dlp`, `ffmpeg`, and subtitle helpers

**Files:**
- Create: `app/ytdub/media/__init__.py`
- Create: `app/ytdub/media/ytdlp.py`
- Create: `app/ytdub/media/ffmpeg.py`
- Create: `app/ytdub/media/subtitles.py`
- Create: `app/ytdub/models/segments.py`
- Create: `tests/test_subtitles.py`

- [ ] **Step 1: Write failing tests for subtitle timing serialization**

```python
def test_srt_render_preserves_segment_order():
    srt = render_srt([
        Segment(start_ms=0, end_ms=1200, text="hello"),
        Segment(start_ms=1500, end_ms=2400, text="world"),
    ])
    assert "1" in srt
    assert "2" in srt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_subtitles.py -v`
Expected: FAIL because segment model and renderer do not exist

- [ ] **Step 3: Add subprocess wrappers for external media tools**

```python
def run_ffmpeg(args: list[str]) -> CompletedProcess[str]:
    ...
```

- [ ] **Step 4: Add segment model and SRT helpers**

Run: `pytest tests/test_subtitles.py -v`
Expected: PASS

- [ ] **Step 5: Add explicit error wrapping for command failures**

Run: `pytest tests/test_subtitles.py tests/test_job_store.py -v`
Expected: PASS

- [ ] **Step 6: Commit if Git is initialized**

```bash
git add app/ytdub/media app/ytdub/models/segments.py tests/test_subtitles.py
git commit -m "feat: add media wrappers and subtitle helpers"
```

## Chunk 3: Provider Interfaces And Registry

### Task 5: Define provider contracts and registry

**Files:**
- Create: `app/ytdub/providers/__init__.py`
- Create: `app/ytdub/providers/base.py`
- Create: `app/ytdub/providers/registry.py`
- Create: `tests/test_provider_registry.py`

- [ ] **Step 1: Write the failing registry tests**

```python
def test_registry_resolves_tts_provider():
    registry = ProviderRegistry()
    provider = registry.resolve_tts("openai")
    assert provider.slug == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_provider_registry.py -v`
Expected: FAIL because provider contracts and registry do not exist

- [ ] **Step 3: Define abstract base classes**

```python
class SpeechSynthesizer(Protocol):
    slug: str
    def synthesize(self, segments, output_dir): ...
```

- [ ] **Step 4: Implement provider registry with explicit registration**

Run: `pytest tests/test_provider_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add app/ytdub/providers tests/test_provider_registry.py
git commit -m "feat: add provider interfaces and registry"
```

### Task 6: Add initial provider clients

**Files:**
- Create: `app/ytdub/providers/transcribers/__init__.py`
- Create: `app/ytdub/providers/transcribers/deepgram.py`
- Create: `app/ytdub/providers/translators/__init__.py`
- Create: `app/ytdub/providers/translators/deepl.py`
- Create: `app/ytdub/providers/tts/__init__.py`
- Create: `app/ytdub/providers/tts/openai.py`
- Create: `app/ytdub/providers/tts/elevenlabs.py`
- Create: `tests/providers/test_deepgram.py`
- Create: `tests/providers/test_deepl.py`
- Create: `tests/providers/test_openai_tts.py`
- Create: `tests/providers/test_elevenlabs_tts.py`

- [ ] **Step 1: Write failing tests for provider request shaping**

```python
def test_deepl_builds_translate_request():
    payload = build_translate_payload(["hello"], target_lang="ZH")
    assert payload["target_lang"] == "ZH"
```

- [ ] **Step 2: Run provider tests to verify they fail**

Run: `pytest tests/providers -v`
Expected: FAIL because provider modules do not exist

- [ ] **Step 3: Implement Deepgram transcription client with mocked HTTP transport support**

Run: `pytest tests/providers/test_deepgram.py -v`
Expected: PASS

- [ ] **Step 4: Implement DeepL translation client with mocked HTTP transport support**

Run: `pytest tests/providers/test_deepl.py -v`
Expected: PASS

- [ ] **Step 5: Implement OpenAI TTS client with streamed audio handling abstraction**

Run: `pytest tests/providers/test_openai_tts.py -v`
Expected: PASS

- [ ] **Step 6: Implement ElevenLabs TTS client with file output contract matching OpenAI TTS**

Run: `pytest tests/providers/test_elevenlabs_tts.py -v`
Expected: PASS

- [ ] **Step 7: Register all initial providers**

Run: `pytest tests/test_provider_registry.py tests/providers -v`
Expected: PASS

- [ ] **Step 8: Commit if Git is initialized**

```bash
git add app/ytdub/providers tests/providers tests/test_provider_registry.py
git commit -m "feat: add initial provider implementations"
```

## Chunk 4: Pipeline Execution And Resume Behavior

### Task 7: Implement the pipeline runner

**Files:**
- Create: `app/ytdub/pipeline/__init__.py`
- Create: `app/ytdub/pipeline/runner.py`
- Create: `app/ytdub/pipeline/steps/__init__.py`
- Create: `app/ytdub/pipeline/steps/download.py`
- Create: `app/ytdub/pipeline/steps/transcribe.py`
- Create: `app/ytdub/pipeline/steps/translate.py`
- Create: `app/ytdub/pipeline/steps/synthesize.py`
- Create: `app/ytdub/pipeline/steps/compose.py`
- Create: `tests/test_pipeline_runner.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
def test_runner_skips_completed_steps(tmp_path):
    runner = PipelineRunner(...)
    result = runner.resume(job_id="job-123")
    assert "download" not in result.executed_steps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_runner.py -v`
Expected: FAIL because pipeline runner does not exist

- [ ] **Step 3: Implement step contracts and ordered execution**

```python
STEPS = ["download", "transcribe", "translate", "synthesize", "compose"]
```

- [ ] **Step 4: Implement `resume` behavior from first incomplete step**

Run: `pytest tests/test_pipeline_runner.py::test_runner_skips_completed_steps -v`
Expected: PASS

- [ ] **Step 5: Implement `rerun --from <step>` invalidation rules**

Run: `pytest tests/test_pipeline_runner.py -v`
Expected: PASS

- [ ] **Step 6: Implement per-step output directories and artifact registration**

Run: `pytest tests/test_pipeline_runner.py tests/test_job_store.py -v`
Expected: PASS

- [ ] **Step 7: Commit if Git is initialized**

```bash
git add app/ytdub/pipeline tests/test_pipeline_runner.py
git commit -m "feat: add resumable pipeline runner"
```

### Task 8: Implement composition rules for final outputs

**Files:**
- Modify: `app/ytdub/media/ffmpeg.py`
- Modify: `app/ytdub/media/subtitles.py`
- Modify: `app/ytdub/pipeline/steps/synthesize.py`
- Modify: `app/ytdub/pipeline/steps/compose.py`
- Modify: `tests/test_pipeline_runner.py`
- Modify: `tests/test_subtitles.py`

- [ ] **Step 1: Write a failing test for final artifact registration**

```python
def test_compose_step_writes_final_artifacts(tmp_path):
    result = compose_step.run(...)
    assert result.final_video_path.name.endswith(".mp4")
    assert result.final_srt_path.name.endswith(".srt")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_runner.py tests/test_subtitles.py -v`
Expected: FAIL because compose step is incomplete

- [ ] **Step 3: Implement segment-level audio merge and final track assembly**

Run: `pytest tests/test_pipeline_runner.py::test_compose_step_writes_final_artifacts -v`
Expected: PASS

- [ ] **Step 4: Add configurable background audio mix behavior**

Run: `pytest tests/test_pipeline_runner.py tests/test_subtitles.py -v`
Expected: PASS

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add app/ytdub/media app/ytdub/pipeline/steps tests/test_pipeline_runner.py tests/test_subtitles.py
git commit -m "feat: compose final dubbed video outputs"
```

## Chunk 5: CLI Commands, Batch Mode, And Documentation

### Task 9: Expose CLI commands over the pipeline

**Files:**
- Modify: `app/ytdub/cli.py`
- Modify: `app/ytdub/config.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `run`, `resume`, and `show-job`**

```python
def test_run_command_accepts_url():
    result = invoke_cli(["run", "https://youtube.com/watch?v=abc"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because subcommands are incomplete

- [ ] **Step 3: Implement `run`, `resume`, `rerun`, `list-jobs`, and `show-job`**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 4: Add argument overrides for provider and target language selection**

Run: `pytest tests/test_cli.py tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add app/ytdub/cli.py app/ytdub/config.py tests/test_cli.py tests/test_config.py
git commit -m "feat: add cli workflow commands"
```

### Task 10: Add batch execution and operator docs

**Files:**
- Modify: `app/ytdub/cli.py`
- Modify: `app/ytdub/pipeline/runner.py`
- Modify: `README.md`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing batch-run tests**

```python
def test_batch_run_reads_url_file(tmp_path):
    file = tmp_path / "urls.txt"
    file.write_text("https://youtube.com/watch?v=1\n")
    result = invoke_cli(["batch-run", str(file)])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_batch_run_reads_url_file -v`
Expected: FAIL because `batch-run` is not implemented

- [ ] **Step 3: Implement sequential batch orchestration with per-URL job creation**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 4: Document setup, config, environment variables, and expected output structure**

Run: `pytest tests/test_cli.py tests/test_pipeline_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit if Git is initialized**

```bash
git add app/ytdub/cli.py app/ytdub/pipeline/runner.py README.md tests/test_cli.py
git commit -m "feat: add batch execution and usage docs"
```

## Final Verification Checklist

- [ ] Run the full unit and integration suite

Run: `pytest -v`
Expected: PASS with all local tests green

- [ ] Run a no-network CLI smoke test

Run: `python -m ytdub.cli --help`
Expected: exit code 0 with command list in output

- [ ] Run a dry local pipeline test using fake providers

Run: `pytest tests/test_pipeline_runner.py -v`
Expected: PASS

- [ ] Run a manual end-to-end test with one real provider set after credentials are configured

Run: `python -m ytdub.cli run "<youtube_url>"`
Expected: one new `jobs/<job_id>/` directory with populated step outputs and a final artifact path recorded in `job.json`

- [ ] Initialize Git before using commit steps if version history is desired

Run: `git init`
Expected: repository created at `/home/ivan/Projects/YoutubeVideos`

## Notes For Execution

- Start with the smallest red-green loop in each task.
- Keep each provider client testable with mocked HTTP transport.
- Do not call real APIs in CI-style tests.
- Treat `job.json` compatibility as a user-facing contract once manual runs exist.
- Do not widen scope into lip-sync or GUI work during the first implementation pass.

Plan complete and saved to `docs/superpowers/plans/2026-03-31-youtube-dubbing-cli.md`. Ready to execute?
