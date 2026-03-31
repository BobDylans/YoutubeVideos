from __future__ import annotations

from pathlib import Path

import pytest

from ytdub.config import load_config
from ytdub.providers.registry import create_default_registry, create_runtime_registry


def test_registry_resolves_initial_providers() -> None:
    registry = create_default_registry()

    assert registry.get_transcriber("deepgram").name == "deepgram"
    assert registry.get_translator("deepl").name == "deepl"
    assert registry.get_tts("openai").name == "openai"
    assert registry.get_tts("elevenlabs").name == "elevenlabs"


def test_registry_rejects_unknown_provider() -> None:
    registry = create_default_registry()

    with pytest.raises(KeyError, match="missing"):
        registry.get_transcriber("missing")


def test_runtime_registry_reads_provider_credentials_from_environment(monkeypatch) -> None:
    config = load_config(Path("configs/default.toml"))
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-secret")
    monkeypatch.setenv("DEEPL_API_KEY", "dl-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-secret")
    monkeypatch.setenv("YTDUB_OPENAI_VOICE", "echo")
    monkeypatch.setenv("YTDUB_ELEVENLABS_VOICE_ID", "voice-123")

    registry = create_runtime_registry(config)

    assert registry.get_transcriber("deepgram").api_key == "dg-secret"
    assert registry.get_translator("deepl").api_key == "dl-secret"
    assert registry.get_tts("openai").voice == "echo"
    assert registry.get_tts("elevenlabs").voice_id == "voice-123"
