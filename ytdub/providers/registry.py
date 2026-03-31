from __future__ import annotations

import os
from dataclasses import dataclass, field

from ytdub.config import AppConfig
from ytdub.providers.transcribers.deepgram import DeepgramTranscriber
from ytdub.providers.translators.deepl import DeepLTranslator
from ytdub.providers.tts.elevenlabs import ElevenLabsTTS
from ytdub.providers.tts.openai import OpenAITTS


@dataclass
class ProviderRegistry:
    transcribers: dict[str, object] = field(default_factory=dict)
    translators: dict[str, object] = field(default_factory=dict)
    tts_providers: dict[str, object] = field(default_factory=dict)

    def register_transcriber(self, provider: object) -> None:
        self.transcribers[getattr(provider, "name")] = provider

    def register_translator(self, provider: object) -> None:
        self.translators[getattr(provider, "name")] = provider

    def register_tts(self, provider: object) -> None:
        self.tts_providers[getattr(provider, "name")] = provider

    def get_transcriber(self, name: str) -> object:
        return self._lookup(self.transcribers, name)

    def get_translator(self, name: str) -> object:
        return self._lookup(self.translators, name)

    def get_tts(self, name: str) -> object:
        return self._lookup(self.tts_providers, name)

    @staticmethod
    def _lookup(providers: dict[str, object], name: str) -> object:
        try:
            return providers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown provider: {name}") from exc


def create_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register_transcriber(DeepgramTranscriber(api_key=""))
    registry.register_translator(DeepLTranslator(api_key=""))
    registry.register_tts(OpenAITTS(api_key="", voice="alloy"))
    registry.register_tts(ElevenLabsTTS(api_key="", voice_id="default"))
    return registry


def create_runtime_registry(config: AppConfig) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register_transcriber(
        DeepgramTranscriber(api_key=_require_secret(config, "deepgram"))
    )
    registry.register_translator(
        DeepLTranslator(api_key=_require_secret(config, "deepl"))
    )
    registry.register_tts(
        OpenAITTS(
            api_key=_require_secret(config, "openai"),
            voice=os.environ.get("YTDUB_OPENAI_VOICE", "alloy"),
        )
    )
    registry.register_tts(
        ElevenLabsTTS(
            api_key=_require_secret(config, "elevenlabs"),
            voice_id=os.environ.get("YTDUB_ELEVENLABS_VOICE_ID", "default"),
        )
    )
    return registry


def _require_secret(config: AppConfig, provider_name: str) -> str:
    env_var_name = config.credentials[provider_name]
    secret = os.environ.get(env_var_name)
    if not secret:
        raise ValueError(f"Missing credential for {provider_name}: expected env var {env_var_name}")
    return secret
