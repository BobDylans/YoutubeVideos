from __future__ import annotations

import json

from ytdub.models.segments import Segment
from ytdub.providers.translators.deepseek import DeepSeekTranslator
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_deepseek_builds_chat_completion_request() -> None:
    provider = DeepSeekTranslator(api_key="secret")
    payload = provider.build_payload(
        [
            Segment(start_ms=0, end_ms=500, text="hello"),
            Segment(start_ms=600, end_ms=1000, text="world"),
        ],
        target_language="zh",
    )

    assert payload["model"] == "deepseek-chat"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0]["role"] == "system"
    assert "target language" in payload["messages"][0]["content"].lower()
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["target_language"] == "zh"
    assert user_payload["segments"][0]["text"] == "hello"


def test_deepseek_translates_segments_with_injected_transport() -> None:
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "translations": [
                                                {"text": "bonjour"},
                                                {"text": "monde"},
                                            ]
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8"),
            )

    provider = DeepSeekTranslator(api_key="secret")
    translated = provider.translate_segments(
        [
            Segment(start_ms=0, end_ms=500, text="hello"),
            Segment(start_ms=600, end_ms=1000, text="world"),
        ],
        target_language="fr",
        transport=FakeTransport(),
    )

    assert captured["request"].url == "https://api.302.ai/v1/chat/completions"
    assert captured["request"].headers["Authorization"] == "Bearer secret"
    assert [segment.text for segment in translated] == ["bonjour", "monde"]
