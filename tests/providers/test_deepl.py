from __future__ import annotations

from ytdub.models.segments import Segment
from ytdub.providers.translators.deepl import DeepLTranslator


def test_deepl_builds_translate_request() -> None:
    provider = DeepLTranslator(api_key="secret")
    payload = provider.build_payload(
        [Segment(start_ms=0, end_ms=500, text="hello")],
        target_language="ZH",
    )

    assert payload["target_lang"] == "ZH"
    assert payload["text"] == ["hello"]
