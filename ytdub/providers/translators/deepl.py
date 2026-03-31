from __future__ import annotations

from dataclasses import dataclass

from ytdub.models.segments import Segment


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
