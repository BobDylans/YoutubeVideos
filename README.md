# YouTube Dubbing CLI

Local CLI for downloading YouTube videos, transcribing speech, translating text,
synthesizing dubbed audio, and composing final video artifacts.

## Current Status

The project currently includes a tested local scaffold for:

- CLI entrypoints for `run`, `batch-run`, `resume`, `rerun`, `list-jobs`, and `show-job`
- on-disk job state under `jobs/<job_id>/job.json`
- pipeline orchestration with resumable step execution
- placeholder step implementations that create deterministic local artifacts
- provider registry and request-shaping helpers for Deepgram, DeepL, OpenAI TTS, and ElevenLabs

The media and provider integrations are still stubs. They do not call real APIs yet.

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

Runtime path overrides are available through environment variables:

- `YTDUB_JOBS_DIR`
- `YTDUB_OUTPUTS_DIR`

## Usage

Show help:

```bash
python -m ytdub.cli --help
```

Run one URL through the local placeholder pipeline:

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

- The current environment does not have `httpx` installed, so provider modules only build request payloads for now.
- Final media composition currently writes placeholder `.mp4` and `.srt` artifacts so the orchestration path can be tested end-to-end.
