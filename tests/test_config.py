from __future__ import annotations

from pathlib import Path

import pytest

from ytdub.config import load_config, resolve_job_settings, resolve_runtime_paths


def test_loads_default_provider_names() -> None:
    config = load_config(Path("configs/default.toml"))

    assert config.providers.transcriber == "openai"
    assert config.providers.translator == "deepseek"
    assert config.providers.tts == "none"


def test_requires_selected_provider_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
        [paths]
        jobs_dir = "jobs"
        outputs_dir = "outputs"

        [providers]
        transcriber = "openai"
        translator = "deepl"
        tts = "openai"

        [defaults]
        target_language = "zh"

        [credentials.deepl]
        api_key_env = "DEEPL_API_KEY"
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="openai"):
        load_config(config_path)


def test_resolves_job_settings_with_environment_overrides(monkeypatch) -> None:
    config = load_config(Path("configs/default.toml"))
    monkeypatch.setenv("YTDUB_TRANSLATOR", "custom-translator")
    monkeypatch.setenv("YTDUB_TARGET_LANGUAGE", "en")

    settings = resolve_job_settings(config)

    assert settings.transcriber == "openai"
    assert settings.translator == "custom-translator"
    assert settings.tts == "none"
    assert settings.target_language == "en"


def test_load_config_reads_repo_env_file(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "default.toml"
    config_path.write_text(
        """
        [paths]
        jobs_dir = "jobs"
        outputs_dir = "outputs"

        [providers]
        transcriber = "openai"
        translator = "deepseek"
        tts = "openai"

        [defaults]
        target_language = "zh"

        [credentials.deepseek]
        api_key_env = "OPENAI_API_KEY"

        [credentials.openai]
        api_key_env = "OPENAI_API_KEY"
        """,
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        """
        OPENAI_API_KEY=from-dotenv
        YTDUB_TARGET_LANGUAGE=ja
        YTDUB_JOBS_DIR=custom-jobs
        """,
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("YTDUB_TARGET_LANGUAGE", raising=False)
    monkeypatch.delenv("YTDUB_JOBS_DIR", raising=False)

    config = load_config(config_path)
    settings = resolve_job_settings(config)
    paths = resolve_runtime_paths(config)

    assert settings.target_language == "ja"
    assert paths.jobs_dir == Path("custom-jobs")
