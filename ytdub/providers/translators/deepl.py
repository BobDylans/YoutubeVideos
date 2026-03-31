from __future__ import annotations

from dataclasses import dataclass

from ytdub.models.segments import Segment
from ytdub.providers.transport import HttpRequest, HttpTransport, UrllibTransport


@dataclass(frozen=True)
class DeepLTranslator:
    api_key: str
    name: str = "deepl"

    def build_payload(
        self,
        segments: list[Segment],
        target_language: str,
    ) -> dict[str, object]:
        return {
            "text": [segment.text for segment in segments],
            "target_lang": target_language,
        }

    def build_headers(self) -> dict[str, str]:
        return {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

    def translate_segments(
        self,
        segments: list[Segment],
        target_language: str,
        transport: HttpTransport | None = None,
    ) -> list[Segment]:
        response = (transport or UrllibTransport()).send(
            HttpRequest(
                method="POST",
                url="https://api.deepl.com/v2/translate",
                headers=self.build_headers(),
                json_body=self.build_payload(segments, target_language),
            )
        )
        payload = response.json()
        translations = payload.get("translations", [])
        return [
            Segment(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=str(translations[index]["text"]),
            )
            for index, segment in enumerate(segments)
        ]
