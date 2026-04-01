from __future__ import annotations

from pathlib import Path

import pytest

from ytdub.config import load_config, resolve_job_settings
from ytdub.providers.registry import create_default_registry, create_runtime_registry


def test_registry_resolves_initial_providers() -> None:
    registry = create_default_registry()

    assert registry.get_transcriber("deepgram").name == "deepgram"
    assert registry.get_transcriber("openai").name == "openai"
    assert registry.get_translator("deepl").name == "deepl"
    assert registry.get_translator("deepseek").name == "deepseek"
    assert registry.get_tts("openai").name == "openai"
    assert registry.get_tts("elevenlabs").name == "elevenlabs"


def test_registry_rejects_unknown_provider() -> None:
    registry = create_default_registry()

    with pytest.raises(KeyError, match="missing"):
        registry.get_transcriber("missing")


def test_runtime_registry_reads_provider_credentials_from_environment(monkeypatch) -> None:
    config = load_config(Path("configs/default.toml"))
    monkeypatch.setenv("DEEPL_API_KEY", "dl-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-secret")
    monkeypatch.setenv("YTDUB_OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    monkeypatch.setenv("YTDUB_OPENAI_TRANSCRIBE_BASE_URL", "https://api.302.ai/v1")
    monkeypatch.setenv("YTDUB_OPENAI_TRANSCRIBE_TIMEOUT", "180")
    monkeypatch.setenv("YTDUB_OPENAI_VOICE", "echo")
    monkeypatch.setenv("YTDUB_OPENAI_MODEL", "tts-1")
    monkeypatch.setenv("YTDUB_OPENAI_BASE_URL", "https://api.302.ai/v1")
    monkeypatch.setenv("YTDUB_DEEPSEEK_MODEL", "deepseek-v3.2")
    monkeypatch.setenv("YTDUB_DEEPSEEK_BASE_URL", "https://api.302.ai/v1")
    monkeypatch.setenv("YTDUB_ELEVENLABS_VOICE_ID", "voice-123")

    registry = create_runtime_registry(config)

    assert registry.get_transcriber("openai").api_key == "oa-secret"
    assert registry.get_transcriber("openai").model == "gpt-4o-mini-transcribe"
    assert registry.get_transcriber("openai").base_url == "https://api.302.ai/v1"
    assert registry.get_transcriber("openai").timeout == 180.0
    assert registry.get_translator("deepl").api_key == "dl-secret"
    assert registry.get_translator("deepseek").api_key == "oa-secret"
    assert registry.get_translator("deepseek").model == "deepseek-v3.2"
    assert registry.get_translator("deepseek").base_url == "https://api.302.ai/v1"
    assert registry.get_tts("openai").voice == "echo"
    assert registry.get_tts("openai").model == "tts-1"
    assert registry.get_tts("openai").base_url == "https://api.302.ai/v1"
    assert registry.get_tts("elevenlabs").voice_id == "voice-123"


def test_runtime_registry_does_not_require_unselected_provider_credentials(monkeypatch) -> None:
    config = load_config(Path("configs/default.toml"))
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("DEEPL_API_KEY", "dl-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-secret")
    monkeypatch.setenv("YTDUB_TRANSLATOR", "deepl")
    monkeypatch.setenv("YTDUB_TTS", "elevenlabs")

    settings = resolve_job_settings(config)
    registry = create_runtime_registry(config, settings)

    assert registry.get_transcriber("openai").api_key == "oa-secret"
    assert registry.get_translator("deepl").api_key == "dl-secret"
    assert registry.get_tts("elevenlabs").voice_id == "default"
    with pytest.raises(KeyError, match="deepgram"):
        registry.get_transcriber("deepgram")
