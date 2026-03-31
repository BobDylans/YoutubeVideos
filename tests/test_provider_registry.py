from __future__ import annotations

import pytest

from ytdub.providers.registry import create_default_registry


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
