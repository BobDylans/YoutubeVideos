from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib

from ytdub.models.job import JobSettings


@dataclass(frozen=True)
class ProviderConfig:
    transcriber: str
    translator: str
    tts: str


@dataclass(frozen=True)
class PathConfig:
    jobs_dir: Path
    outputs_dir: Path


@dataclass(frozen=True)
class DefaultsConfig:
    target_language: str


@dataclass(frozen=True)
class AppConfig:
    paths: PathConfig
    providers: ProviderConfig
    defaults: DefaultsConfig
    credentials: dict[str, str]


def resolve_runtime_paths(config: AppConfig) -> PathConfig:
    jobs_dir = Path(os.environ.get("YTDUB_JOBS_DIR", config.paths.jobs_dir))
    outputs_dir = Path(os.environ.get("YTDUB_OUTPUTS_DIR", config.paths.outputs_dir))
    return PathConfig(jobs_dir=jobs_dir, outputs_dir=outputs_dir)


def resolve_job_settings(config: AppConfig) -> JobSettings:
    return JobSettings(
        transcriber=os.environ.get("YTDUB_TRANSCRIBER", config.providers.transcriber),
        translator=os.environ.get("YTDUB_TRANSLATOR", config.providers.translator),
        tts=os.environ.get("YTDUB_TTS", config.providers.tts),
        target_language=os.environ.get("YTDUB_TARGET_LANGUAGE", config.defaults.target_language),
    )


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    providers_data = data["providers"]
    credentials_data = data["credentials"]
    selected_providers = {
        "transcriber": providers_data["transcriber"],
        "translator": providers_data["translator"],
        "tts": providers_data["tts"],
    }

    missing_credentials = [
        provider_name
        for provider_name in selected_providers.values()
        if not credentials_data.get(provider_name, {}).get("api_key_env")
    ]
    if missing_credentials:
        raise ValueError(
            "Missing api_key_env for selected providers: "
            + ", ".join(sorted(missing_credentials))
        )

    return AppConfig(
        paths=PathConfig(
            jobs_dir=Path(data["paths"]["jobs_dir"]),
            outputs_dir=Path(data["paths"]["outputs_dir"]),
        ),
        providers=ProviderConfig(
            transcriber=selected_providers["transcriber"],
            translator=selected_providers["translator"],
            tts=selected_providers["tts"],
        ),
        defaults=DefaultsConfig(target_language=data["defaults"]["target_language"]),
        credentials={
            provider_name: provider_data["api_key_env"]
            for provider_name, provider_data in credentials_data.items()
            if provider_data.get("api_key_env")
        },
    )
