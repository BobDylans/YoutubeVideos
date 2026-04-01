from __future__ import annotations

import json
from dataclasses import dataclass

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


@dataclass(frozen=True)
class DeepSeekTranslator:
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.302.ai/v1"
    name: str = "deepseek"

    def build_payload(
        self,
        segments: list[Segment],
        target_language: str,
    ) -> dict[str, object]:
        return {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You translate subtitle segments into the target language. "
                        "Preserve ordering. Return JSON only with the shape "
                        '{"translations":[{"text":"..."}]}. Do not add explanations.'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "target_language": target_language,
                            "segments": [
                                {
                                    "start_ms": segment.start_ms,
                                    "end_ms": segment.end_ms,
                                    "text": segment.text,
                                }
                                for segment in segments
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

    def build_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def translate_segments(
        self,
        segments: list[Segment],
        target_language: str,
        transport: HttpTransport | None = None,
    ) -> list[Segment]:
        response = (transport or UrllibTransport()).send(
            HttpRequest(
                method="POST",
                url=f"{self.base_url.rstrip('/')}/chat/completions",
                headers=self.build_headers(),
                json_body=self.build_payload(segments, target_language),
            )
        )
        payload = response.json()
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        translated_payload = _parse_json_content(str(content))
        translations = translated_payload.get("translations", [])
        if len(translations) != len(segments):
            raise ValueError(
                f"DeepSeek returned {len(translations)} translations for {len(segments)} segments"
            )
        return [
            Segment(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=str(translations[index]["text"]),
            )
            for index, segment in enumerate(segments)
        ]


def _parse_json_content(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)
