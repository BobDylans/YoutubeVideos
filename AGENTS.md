# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `ytdub/`. Keep modules focused by responsibility: CLI entrypoints in `ytdub/cli.py`, config loading in `ytdub/config.py`, storage in `ytdub/storage/`, media helpers in `ytdub/media/`, provider adapters in `ytdub/providers/`, and shared models in `ytdub/models/`. Tests live in `tests/`, with provider-specific cases under `tests/providers/`. Default runtime settings belong in `configs/default.toml`. Design and implementation references are stored in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Build, Test, and Development Commands
Run the CLI help locally with `python -m ytdub.cli --help`. Execute the full test suite with `pytest -v`. Run a focused loop with commands like `pytest tests/test_config.py -v` or `pytest tests/providers -v`. When adding commands or pipeline behavior, verify the relevant smoke tests before moving on.

## Coding Style & Naming Conventions
Use Python 3.11+ style with 4-space indentation, explicit type hints, and small, single-purpose modules. Prefer `pathlib.Path`, `dataclass`, and standard-library tools where practical. Name modules and files in `snake_case`; classes use `PascalCase`; functions, variables, and pytest tests use `snake_case`. Avoid hardcoded provider secrets or filesystem paths outside the project structure.

## Testing Guidelines
This repository follows TDD: write the test first, confirm it fails for the expected reason, then add the minimal implementation. Use `pytest` for unit, integration, and CLI smoke tests. Keep tests isolated and deterministic; mock network calls and external commands instead of hitting real APIs or `yt-dlp`/`ffmpeg` in default runs. Maintain at least 80% coverage for new work.

## Commit & Pull Request Guidelines
There is no meaningful Git history yet, so use Conventional Commits from the start, for example `feat: add config loader` or `test: cover provider registry`. PRs should include a short summary, linked issue or plan reference, test evidence (`pytest -v` output), and screenshots only if a future UI is introduced.

## Security & Configuration Tips
Keep API keys in environment variables referenced by `configs/default.toml`; never commit secrets. Validate required config before provider calls, and preserve job artifacts and logs under `jobs/<job_id>/` for debugging and reruns.
