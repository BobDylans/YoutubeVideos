from __future__ import annotations

from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.transcribers.deepgram import DeepgramTranscriber
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_deepgram_builds_transcribe_request(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    provider = DeepgramTranscriber(api_key="secret")
    request = provider.build_request(audio_path)

    assert request["url"].endswith("/v1/listen")
    assert request["headers"]["Authorization"] == "Token secret"
    assert request["body"] == b"audio"


def test_deepgram_transcribes_with_injected_transport(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=b'{"results":{"channels":[{"alternatives":[{"paragraphs":{"paragraphs":[{"start":0.0,"end":1.2,"sentences":[{"text":"hello world"}]}]}}]}]}}',
            )

    provider = DeepgramTranscriber(api_key="secret")
    segments = provider.transcribe(audio_path, transport=FakeTransport())

    assert captured["request"].method == "POST"
    assert captured["request"].headers["Authorization"] == "Token secret"
    assert segments == [Segment(start_ms=0, end_ms=1200, text="hello world")]
