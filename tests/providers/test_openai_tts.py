from __future__ import annotations

from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.tts.openai import OpenAITTS
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_openai_tts_builds_speech_request() -> None:
    provider = OpenAITTS(api_key="secret", voice="alloy")
    payload = provider.build_payload(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
    )

    assert payload["model"] == "gpt-4o-mini-tts"
    assert payload["voice"] == "alloy"
    assert payload["input"] == "hello world"
    assert payload["response_format"] == "mp3"


def test_openai_tts_writes_audio_with_injected_transport(tmp_path: Path) -> None:
    output_path = tmp_path / "speech.mp3"
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "audio/mpeg"},
                content=b"mp3-bytes",
            )

    provider = OpenAITTS(api_key="secret", voice="alloy")
    provider.synthesize_segment(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
        output_path,
        transport=FakeTransport(),
    )

    assert captured["request"].url == "https://api.302.ai/v1/audio/speech"
    assert captured["request"].json_body["response_format"] == "mp3"
    assert output_path.read_bytes() == b"mp3-bytes"


def test_openai_tts_respects_custom_base_url_and_model(tmp_path: Path) -> None:
    output_path = tmp_path / "speech.mp3"
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "audio/mpeg"},
                content=b"mp3-bytes",
            )

    provider = OpenAITTS(
        api_key="secret",
        voice="alloy",
        model="tts-1",
        base_url="https://example.com/custom/v1",
    )
    provider.synthesize_segment(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
        output_path,
        transport=FakeTransport(),
    )

    assert captured["request"].url == "https://example.com/custom/v1/audio/speech"
    assert captured["request"].json_body["model"] == "tts-1"
