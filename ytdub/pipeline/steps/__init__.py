from __future__ import annotations

from ytdub.pipeline.steps.compose import ComposeStep
from ytdub.pipeline.steps.download import DownloadStep
from ytdub.pipeline.steps.transcribe import TranscribeStep
from ytdub.pipeline.steps.translate import TranslateStep
from ytdub.providers.registry import ProviderRegistry

# 这个方法返回的类型如下,之后将这个字典传给PipelineRunner
"""
{
    "download": DownloadStep(...),
    "transcribe": TranscribeStep(...),
    "translate": TranslateStep(...),
    "compose": ComposeStep(...),
}
"""
def build_default_steps(registry: ProviderRegistry) -> dict[str, object]:
    return {
        "download": DownloadStep(),
        "transcribe": TranscribeStep(registry=registry),
        "translate": TranslateStep(registry=registry),
        "compose": ComposeStep(),
    }
