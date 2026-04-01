from __future__ import annotations

import os
from dataclasses import dataclass, field

from ytdub.config import AppConfig
from ytdub.models.job import JobSettings
from ytdub.providers.transcribers.deepgram import DeepgramTranscriber
from ytdub.providers.transcribers.openai import OpenAITranscriber
from ytdub.providers.translators.deepseek import DeepSeekTranslator
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
    registry.register_transcriber(OpenAITranscriber(api_key=""))
    registry.register_translator(DeepLTranslator(api_key=""))
    registry.register_translator(DeepSeekTranslator(api_key=""))
    registry.register_tts(OpenAITTS(api_key="", voice="alloy"))
    registry.register_tts(ElevenLabsTTS(api_key="", voice_id="default"))
    return registry


def create_runtime_registry(
    config: AppConfig,
    settings: JobSettings | None = None,
) -> ProviderRegistry:
    registry = ProviderRegistry()

    required = settings or JobSettings(
        transcriber=config.providers.transcriber,
        translator=config.providers.translator,
        tts=config.providers.tts,
        target_language=config.defaults.target_language,
    )

    _register_transcriber(
        registry,
        "deepgram",
        config,
        required=required.transcriber == "deepgram",
    )
    _register_transcriber(
        registry,
        "openai",
        config,
        required=required.transcriber == "openai",
    )
    _register_translator(
        registry,
        "deepl",
        config,
        required=required.translator == "deepl",
    )
    _register_translator(
        registry,
        "deepseek",
        config,
        required=required.translator == "deepseek",
    )
    _register_tts(
        registry,
        "openai",
        config,
        required=required.tts == "openai",
    )
    _register_tts(
        registry,
        "elevenlabs",
        config,
        required=required.tts == "elevenlabs",
    )

    return registry


def _require_secret(config: AppConfig, provider_name: str) -> str:
    env_var_name = config.credentials[provider_name]
    secret = os.environ.get(env_var_name)
    if not secret:
        raise ValueError(f"Missing credential for {provider_name}: expected env var {env_var_name}")
    return secret


def _optional_secret(config: AppConfig, provider_name: str) -> str | None:
    env_var_name = config.credentials.get(provider_name)
    if not env_var_name:
        return None
    return os.environ.get(env_var_name)


def _register_transcriber(
    registry: ProviderRegistry,
    provider_name: str,
    config: AppConfig,
    *,
    required: bool,
) -> None:
    api_key = _require_secret(config, provider_name) if required else _optional_secret(config, provider_name)
    if not api_key:
        return

    if provider_name == "deepgram":
        registry.register_transcriber(DeepgramTranscriber(api_key=api_key))
        return

    if provider_name == "openai":
        registry.register_transcriber(
            OpenAITranscriber(
                api_key=api_key,
                model=os.environ.get("YTDUB_OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
                base_url=os.environ.get("YTDUB_OPENAI_TRANSCRIBE_BASE_URL", "https://api.302.ai/v1"),
                timeout=float(os.environ.get("YTDUB_OPENAI_TRANSCRIBE_TIMEOUT", "180")),
            )
        )


def _register_translator(
    registry: ProviderRegistry,
    provider_name: str,
    config: AppConfig,
    *,
    required: bool,
) -> None:
    api_key = _require_secret(config, provider_name) if required else _optional_secret(config, provider_name)
    if not api_key:
        return

    if provider_name == "deepl":
        registry.register_translator(DeepLTranslator(api_key=api_key))
        return

    if provider_name == "deepseek":
        registry.register_translator(
            DeepSeekTranslator(
                api_key=api_key,
                model=os.environ.get("YTDUB_DEEPSEEK_MODEL", "deepseek-chat"),
                base_url=os.environ.get("YTDUB_DEEPSEEK_BASE_URL", "https://api.302.ai/v1"),
            )
        )


def _register_tts(
    registry: ProviderRegistry,
    provider_name: str,
    config: AppConfig,
    *,
    required: bool,
) -> None:
    api_key = _require_secret(config, provider_name) if required else _optional_secret(config, provider_name)
    if not api_key:
        return

    if provider_name == "openai":
        registry.register_tts(
            OpenAITTS(
                api_key=api_key,
                voice=os.environ.get("YTDUB_OPENAI_VOICE", "alloy"),
                model=os.environ.get("YTDUB_OPENAI_MODEL", "gpt-4o-mini-tts"),
                base_url=os.environ.get("YTDUB_OPENAI_BASE_URL", "https://api.302.ai/v1"),
            )
        )
        return

    if provider_name == "elevenlabs":
        registry.register_tts(
            ElevenLabsTTS(
                api_key=api_key,
                voice_id=os.environ.get("YTDUB_ELEVENLABS_VOICE_ID", "default"),
            )
        )
