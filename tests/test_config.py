from __future__ import annotations

from pathlib import Path

import pytest

from ytdub.config import load_config


def test_loads_default_provider_names() -> None:
    config = load_config(Path("configs/default.toml"))

    assert config.providers.transcriber == "deepgram"
    assert config.providers.translator == "deepl"
    assert config.providers.tts == "openai"


def test_requires_selected_provider_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
        [paths]
        jobs_dir = "jobs"
        outputs_dir = "outputs"

        [providers]
        transcriber = "deepgram"
        translator = "deepl"
        tts = "openai"

        [defaults]
        target_language = "zh"

        [credentials.deepgram]
        api_key_env = "DEEPGRAM_API_KEY"

        [credentials.deepl]
        api_key_env = "DEEPL_API_KEY"
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="openai"):
        load_config(config_path)
