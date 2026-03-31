from __future__ import annotations

from pathlib import Path

from ytdub.providers.transcribers.deepgram import DeepgramTranscriber


def test_deepgram_builds_transcribe_request(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    provider = DeepgramTranscriber(api_key="secret")
    request = provider.build_request(audio_path)

    assert request["url"].endswith("/v1/listen")
    assert request["headers"]["Authorization"] == "Token secret"
    assert request["body"] == b"audio"
