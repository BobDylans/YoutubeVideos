from __future__ import annotations

from ytdub.models.segments import Segment
from ytdub.providers.tts.elevenlabs import ElevenLabsTTS


def test_elevenlabs_builds_speech_request() -> None:
    provider = ElevenLabsTTS(api_key="secret", voice_id="voice-123")
    request = provider.build_request(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
    )

    assert request["url"].endswith("/text-to-speech/voice-123")
    assert request["headers"]["xi-api-key"] == "secret"
    assert request["json"]["text"] == "hello world"
