# YouTube Dubbing CLI Design

## Overview

This document records the approved design for a local, self-use CLI tool that:

- downloads a YouTube video
- transcribes the spoken audio
- translates the transcript into a target language
- synthesizes dubbed speech with switchable TTS providers
- composes a final MP4 while preserving intermediate artifacts

The project root is `/home/ivan/Projects/YoutubeVideos`.

## Goals

- Build a local CLI-first workflow, not a web app.
- Support a single YouTube URL first, while leaving space for batch execution.
- Preserve intermediate artifacts so failed or changed jobs can resume or rerun from a chosen step.
- Keep provider integrations swappable for transcription, translation, and TTS.
- Use local media tooling for download, extraction, timing, and composition.

## Non-Goals

- GUI or browser control panel
- automatic lip sync
- speaker diarization with different voices per speaker
- distributed workers or remote queues
- cloud storage and webhook-based orchestration
- advanced terminology memory in the first release

## Architecture Summary

The tool uses a split between local orchestration and external AI services:

- local tools:
  - `yt-dlp` for video acquisition
  - `ffmpeg` and `ffprobe` for extraction, timing, mix, and final packaging
- Python application:
  - CLI parsing
  - config resolution
  - job state tracking
  - step orchestration
  - provider selection
  - subtitle and timeline handling
- external providers:
  - transcription provider
  - translation provider
  - TTS provider

This keeps bandwidth-heavy and model-heavy work in provider APIs, while retaining local control over the workflow.

## Project Layout

```text
/home/ivan/Projects/YoutubeVideos/
  app/
  configs/
  docs/
    superpowers/
      specs/
      plans/
  jobs/
    <job_id>/
      input/
      download/
      transcribe/
      translate/
      synthesize/
      compose/
      artifacts/
      logs/
      job.json
  outputs/
  README.md
  pyproject.toml
```

## Task Model

Each run creates a unique `job_id` and stores all artifacts inside `jobs/<job_id>/`.

Each job tracks:

- input URL
- resolved providers
- target language
- current step
- per-step status
- file paths for outputs
- retry count and last error
- timestamps for creation and last update

The state file is `jobs/<job_id>/job.json`. It is the source of truth for `resume`, `rerun`, `list-jobs`, and `show-job`.

## Pipeline Steps

The pipeline is fixed and ordered:

1. `download`
2. `transcribe`
3. `translate`
4. `synthesize`
5. `compose`

Each step:

- reads job state and prior artifacts
- writes outputs into its own directory
- updates `job.json`
- can be skipped if already completed and inputs are unchanged

## CLI Scope

The approved command set for the first implementation is:

- `run <youtube_url>`
- `batch-run <file>`
- `resume <job_id>`
- `rerun <job_id> --from <step>`
- `list-jobs`
- `show-job <job_id>`

The tool is local and self-use only. No multi-user authentication model is needed.

## Provider Boundaries

Only three provider abstractions are needed:

- `Transcriber`
  - input: local audio or video file
  - output: transcript segments with start and end timestamps
- `Translator`
  - input: transcript or subtitle segments
  - output: translated segments preserving timing and order
- `SpeechSynthesizer`
  - input: translated segments
  - output: synthesized audio clips plus metadata needed for composition

Download and final composition are intentionally not provider abstractions. They remain fixed local capabilities.

## Initial Provider Strategy

The architecture must support switching providers via configuration, but the first implementation does not need every provider in every category on day one.

The recommended concrete starting set is:

- transcription: Deepgram
- translation: DeepL
- TTS: OpenAI and ElevenLabs

That gives immediate provider switching in the most quality-sensitive stage, while keeping the architecture open for more transcription and translation providers later.

## Configuration Strategy

Two layers are required:

- global config
  - default providers
  - target language
  - output directory behavior
  - audio mix behavior
  - environment variable names for credentials
- per-command overrides
  - provider selection
  - resume behavior
  - rerun start step
  - target language

Config should use TOML so the application can rely on Python's standard library `tomllib`.

## Artifact Strategy

The tool must preserve both the final deliverables and the intermediate working files.

Expected preserved artifacts:

- downloaded source video
- extracted source audio
- raw transcript
- translated subtitle data
- synthesized per-segment audio
- merged dubbing track
- final MP4
- final SRT

This makes partial reruns practical.

## Resume And Rerun Rules

- If `download` succeeds, later failures do not trigger a redownload.
- If `translate` succeeds, later failures do not trigger retranscription.
- `resume` continues from the first incomplete or failed step.
- `rerun --from <step>` invalidates that step and all later steps, but leaves earlier artifacts intact.
- Changing a provider only requires rerunning the steps affected by that provider and anything downstream.

## Error Handling

Errors should be explicit and step-scoped:

- external command failures capture command, exit code, and stderr
- provider failures capture HTTP status, provider name, and request context safe for logs
- validation failures should stop before any provider call when configuration is incomplete

Each failed step writes a structured error entry into `job.json` and a detailed text log into `jobs/<job_id>/logs/`.

## Testing Strategy

The implementation should follow TDD. The minimum useful test layers are:

- unit tests for config parsing, job state transitions, provider registry, and subtitle timing logic
- integration tests for pipeline orchestration using fake providers and mocked command runners
- smoke tests for CLI command behavior on a dummy job directory

Real network calls should not run in the default automated test suite.

## Open Constraints

- The directory is not currently a Git repository, so no design or plan commit is possible yet.
- Provider pricing and quotas are external and should remain config-driven, not hardcoded.
- Lip-sync quality is intentionally out of scope for the first implementation.

## Outcome

The approved direction is a Python CLI orchestrator with resumable job state, local media tooling, and switchable provider adapters for transcription, translation, and TTS.
