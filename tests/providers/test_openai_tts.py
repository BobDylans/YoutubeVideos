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

    assert captured["request"].url.endswith("/v1/audio/speech")
    assert output_path.read_bytes() == b"mp3-bytes"
