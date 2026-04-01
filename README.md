# YouTube Dubbing CLI

Local CLI for downloading YouTube videos, transcribing speech, translating text,
synthesizing dubbed audio, and composing final video artifacts.

## Current Status

The project currently includes a tested local implementation for:

- CLI entrypoints for `run`, `batch-run`, `resume`, `rerun`, `list-jobs`, and `show-job`
- on-disk job state under `jobs/<job_id>/job.json`
- pipeline orchestration with resumable step execution
- step implementations for download, transcribe, translate, synthesize, and compose
- provider registry and runtime credential resolution for Deepgram, DeepL, OpenAI TTS, and ElevenLabs
- HTTP-backed provider clients and external tool wrappers for `yt-dlp`, `ffmpeg`, and `ffprobe`
- automated test coverage for CLI behavior, config loading, job storage, pipeline execution, subtitle rendering, and provider adapters

The code now calls real external tools and provider APIs. The automated test suite uses mocks and stub steps where appropriate, so manual end-to-end validation with real credentials and local media tooling is still recommended.

## Project Layout

```text
configs/
  default.toml
docs/
tests/
ytdub/
  cli.py
  config.py
  media/
  models/
  pipeline/
  providers/
  storage/
```

## Configuration

Default config lives at `configs/default.toml`.
If a repository-root `.env` file exists, the CLI will load it automatically before resolving runtime settings.

Runtime path overrides are available through environment variables:

- `YTDUB_JOBS_DIR`
- `YTDUB_OUTPUTS_DIR`

## Usage

Show help:

```bash
python -m ytdub.cli --help
```

Run one URL through the pipeline:

```bash
python -m ytdub.cli run "https://youtube.com/watch?v=example"
```

Run a batch from a text file:

```bash
python -m ytdub.cli batch-run urls.txt
```

Inspect jobs:

```bash
python -m ytdub.cli list-jobs
python -m ytdub.cli show-job <job_id>
python -m ytdub.cli resume <job_id>
python -m ytdub.cli rerun <job_id> --from translate
```

## Testing

Run the full suite:

```bash
pytest -v
```

## Notes

- Provider calls use the standard library `urllib` transport. You need valid API keys in the environment variables referenced by `configs/default.toml`.
- You can store local secrets in a repository-root `.env` file. Use `.env.example` as the starting point and keep the real `.env` uncommitted.
- Local media steps require `yt-dlp`, `ffmpeg`, and `ffprobe` to be installed and available on `PATH`.
- Job artifacts are written under `jobs/<job_id>/...`, including intermediate outputs, logs, the final MP4, and the final SRT.
- `outputs_dir` is configured but not yet used as a separate export location; the current implementation keeps artifacts inside each job directory.
