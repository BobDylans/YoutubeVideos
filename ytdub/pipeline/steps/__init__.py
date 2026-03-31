from __future__ import annotations

from ytdub.pipeline.steps.compose import ComposeStep
from ytdub.pipeline.steps.download import DownloadStep
from ytdub.pipeline.steps.synthesize import SynthesizeStep
from ytdub.pipeline.steps.transcribe import TranscribeStep
from ytdub.pipeline.steps.translate import TranslateStep
from ytdub.providers.registry import ProviderRegistry


def build_default_steps(registry: ProviderRegistry) -> dict[str, object]:
    return {
        "download": DownloadStep(),
        "transcribe": TranscribeStep(registry=registry),
        "translate": TranslateStep(registry=registry),
        "synthesize": SynthesizeStep(registry=registry),
        "compose": ComposeStep(),
    }
