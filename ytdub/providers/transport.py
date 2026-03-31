from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    json_body: dict[str, object] | None = None
    content: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> dict[str, object]:
        return json.loads(self.content.decode("utf-8"))


class HttpTransport(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse: ...


@dataclass(frozen=True)
class ProviderHTTPError(RuntimeError):
    provider: str
    status_code: int
    message: str

    def __str__(self) -> str:
        return f"{self.provider} request failed with status {self.status_code}: {self.message}"


class UrllibTransport:
    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def send(self, request: HttpRequest) -> HttpResponse:
        url = request.url
        if request.params:
            url = f"{url}?{urlencode(request.params)}"

        body = request.content
        headers = dict(request.headers)
        if request.json_body is not None:
            body = json.dumps(request.json_body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        raw_request = Request(url=url, data=body, headers=headers, method=request.method)

        try:
            with urlopen(raw_request, timeout=self.timeout) as response:
                return HttpResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    content=response.read(),
                )
        except HTTPError as exc:
            raise ProviderHTTPError(
                provider=url,
                status_code=exc.code,
                message=exc.read().decode("utf-8", errors="replace"),
            ) from exc
        except URLError as exc:
            raise ProviderHTTPError(
                provider=url,
                status_code=0,
                message=str(exc.reason),
            ) from exc
