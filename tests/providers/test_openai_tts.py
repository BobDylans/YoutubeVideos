from __future__ import annotations

from ytdub.models.segments import Segment
from ytdub.providers.tts.openai import OpenAITTS


def test_openai_tts_builds_speech_request() -> None:
    provider = OpenAITTS(api_key="secret", voice="alloy")
    payload = provider.build_payload(
        Segment(start_ms=0, end_ms=1000, text="hello world"),
    )

    assert payload["model"] == "gpt-4o-mini-tts"
    assert payload["voice"] == "alloy"
    assert payload["input"] == "hello world"
