from __future__ import annotations

from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.tts.elevenlabs import ElevenLabsTTS
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_elevenlabs_builds_speech_request() -> None:
    provider = ElevenLabsTTS(api_key="secret", voice_id="voice-123")
    request = provider.build_request(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
    )

    assert request["url"].endswith("/text-to-speech/voice-123")
    assert request["headers"]["xi-api-key"] == "secret"
    assert request["json"]["text"] == "hello world"


def test_elevenlabs_writes_audio_with_injected_transport(tmp_path: Path) -> None:
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

    provider = ElevenLabsTTS(api_key="secret", voice_id="voice-123")
    provider.synthesize_segment(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
        output_path,
        transport=FakeTransport(),
    )

    assert "output_format=mp3_44100_128" in captured["request"].url
    assert output_path.read_bytes() == b"mp3-bytes"
