from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


@dataclass(frozen=True)
class OpenAITranscriber:
    api_key: str
    model: str = "whisper-1"
    base_url: str = "https://api.302.ai/v1"
    timeout: float = 180.0
    name: str = "openai"

    def build_request(self, audio_path: Path) -> dict[str, object]:
        boundary = f"----ytdub-{uuid.uuid4().hex}"
        body = _encode_multipart_form_data(
            boundary=boundary,
            fields=[
                ("model", self.model),
                ("response_format", "verbose_json"),
                ("timestamp_granularities[]", "segment"),
            ],
            file_field_name="file",
            file_name=audio_path.name,
            file_bytes=audio_path.read_bytes(),
            file_content_type="audio/wav",
        )
        return {
            "url": f"{self.base_url.rstrip('/')}/audio/transcriptions",
            "headers": {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            "body": body,
        }

    def transcribe(self, audio_path: Path, transport: HttpTransport | None = None) -> list[Segment]:
        request_data = self.build_request(audio_path)
        response = (transport or UrllibTransport(timeout=self.timeout)).send(
            HttpRequest(
                method="POST",
                url=str(request_data["url"]),
                headers=dict(request_data["headers"]),
                content=bytes(request_data["body"]),
            )
        )
        payload = response.json()
        segments_payload = payload.get("segments", [])
        segments = [
            Segment(
                start_ms=int(float(segment["start"]) * 1000),
                end_ms=int(float(segment["end"]) * 1000),
                text=str(segment["text"]).strip(),
            )
            for segment in segments_payload
            if str(segment.get("text", "")).strip()
        ]
        if segments:
            return segments

        text = str(payload.get("text", "")).strip()
        if not text:
            return []
        duration_ms = int(float(payload.get("duration", 0.0)) * 1000)
        return [Segment(start_ms=0, end_ms=duration_ms, text=text)]


def _encode_multipart_form_data(
    *,
    boundary: str,
    fields: list[tuple[str, str]],
    file_field_name: str,
    file_name: str,
    file_bytes: bytes,
    file_content_type: str,
) -> bytes:
    line_break = b"\r\n"
    chunks: list[bytes] = []

    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"),
                b"",
                value.encode("utf-8"),
            ]
        )

    chunks.extend(
        [
            f"--{boundary}".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field_name}"; filename="{file_name}"'
            ).encode("utf-8"),
            f"Content-Type: {file_content_type}".encode("utf-8"),
            b"",
            file_bytes,
            f"--{boundary}--".encode("utf-8"),
            b"",
        ]
    )

    return line_break.join(chunks)
