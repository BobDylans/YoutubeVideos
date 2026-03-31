from __future__ import annotations

from ytdub.models.segments import Segment
from ytdub.providers.translators.deepl import DeepLTranslator
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_deepl_builds_translate_request() -> None:
    provider = DeepLTranslator(api_key="secret")
    payload = provider.build_payload(
        [Segment(start_ms=0, end_ms=500, text="hello")],
        target_language="ZH",
    )

    assert payload["target_lang"] == "ZH"
    assert payload["text"] == ["hello"]


def test_deepl_translates_segments_with_injected_transport() -> None:
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=b'{"translations":[{"text":"bonjour"}]}',
            )

    provider = DeepLTranslator(api_key="secret")
    translated = provider.translate_segments(
        [Segment(start_ms=0, end_ms=500, text="hello")],
        target_language="FR",
        transport=FakeTransport(),
    )

    assert captured["request"].headers["Authorization"] == "DeepL-Auth-Key secret"
    assert translated == [Segment(start_ms=0, end_ms=500, text="bonjour")]
