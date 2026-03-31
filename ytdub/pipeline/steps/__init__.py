from __future__ import annotations

from ytdub.pipeline.steps.compose import ComposeStep
from ytdub.pipeline.steps.download import DownloadStep
from ytdub.pipeline.steps.synthesize import SynthesizeStep
from ytdub.pipeline.steps.transcribe import TranscribeStep
from ytdub.pipeline.steps.translate import TranslateStep


def build_default_steps() -> dict[str, object]:
    return {
        "download": DownloadStep(),
        "transcribe": TranscribeStep(),
        "translate": TranslateStep(),
        "synthesize": SynthesizeStep(),
        "compose": ComposeStep(),
    }
