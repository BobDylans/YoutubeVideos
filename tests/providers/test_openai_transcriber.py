from __future__ import annotations

from pathlib import Path

from ytdub.models.segments import Segment
from ytdub.providers.transcribers.openai import OpenAITranscriber
from ytdub.providers.transport import HttpRequest, HttpResponse


def test_openai_transcriber_builds_multipart_request(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    provider = OpenAITranscriber(api_key="secret")
    request = provider.build_request(audio_path)

    assert request["url"] == "https://api.302.ai/v1/audio/transcriptions"
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert "multipart/form-data" in request["headers"]["Content-Type"]
    assert b'name="model"' in request["body"]
    assert b'whisper-1' in request["body"]
    assert b'name="response_format"' in request["body"]
    assert b'verbose_json' in request["body"]
    assert b'name="timestamp_granularities[]"' in request["body"]


def test_openai_transcriber_reads_segment_timestamps_from_verbose_json(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    captured: dict[str, HttpRequest] = {}

    class FakeTransport:
        def send(self, request: HttpRequest) -> HttpResponse:
            captured["request"] = request
            return HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=(
                    b'{"text":"hello world","segments":[{"start":0.0,"end":1.2,"text":"hello world"}]}'
                ),
            )

    provider = OpenAITranscriber(api_key="secret")
    segments = provider.transcribe(audio_path, transport=FakeTransport())

    assert captured["request"].method == "POST"
    assert captured["request"].headers["Authorization"] == "Bearer secret"
    assert segments == [Segment(start_ms=0, end_ms=1200, text="hello world")]


def test_openai_transcriber_falls_back_to_single_segment_when_no_segments_present(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    class FakeTransport:
        def send(self, _request: HttpRequest) -> HttpResponse:
            return HttpResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                content=b'{"text":"hello world","duration":2.5}',
            )

    provider = OpenAITranscriber(api_key="secret")
    segments = provider.transcribe(audio_path, transport=FakeTransport())

    assert segments == [Segment(start_ms=0, end_ms=2500, text="hello world")]
