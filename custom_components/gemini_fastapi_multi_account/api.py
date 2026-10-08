"""Native HTTP client for Gemini FastAPI Multi-Account.

This module intentionally does not depend on the OpenAI Python SDK.  The backend
implements an OpenAI-compatible HTTP surface, so talking to it directly keeps the
Home Assistant integration insulated from SDK version pins in Home Assistant Core.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import REQUEST_TIMEOUT, LocalAiConfigKey


class ApiClientError(Exception):
    """Base error raised by the native Gemini FastAPI client."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class ImageGenerationResult:
    """Image-generation payload stored in Home Assistant ChatLog native content."""

    result: str | None
    output_format: str | None = None
    size: str | None = None
    revised_prompt: str | None = None
    type: str = "image_generation_call"


def extract_response_output_text(response: Mapping[str, Any]) -> str | None:
    """Extract the Responses API convenience output_text value from raw JSON.

    The OpenAI SDK exposes ``response.output_text`` as a computed convenience
    property.  Raw HTTP responses do not contain that property, so the custom
    integration reconstructs it from assistant message content.
    """
    texts: list[str] = []
    output = response.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                texts.append(text)
    combined = "".join(texts).strip()
    return combined or None


def normalize_base_url(raw_url: object) -> str:
    """Normalize a server URL to the OpenAI-compatible /v1 base path."""
    value = str(raw_url or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Server URL must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("Server URL must not contain query parameters or fragments")
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    for endpoint in ("/models", "/chat/completions", "/responses"):
        if lower_path.endswith(f"/v1{endpoint}"):
            path = path[: -len(endpoint)]
            lower_path = path.lower()
            break
    if not lower_path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class GeminiFastApiClient:
    """Small OpenAI-compatible client backed by Home Assistant's shared HTTPX client."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
    ) -> None:
        self._http_client = http_client
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, extra_headers: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @staticmethod
    async def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        await response.aread()
        detail = response.text.strip()
        if len(detail) > 1000:
            detail = f"{detail[:1000]}..."
        raise ApiClientError(
            f"HTTP {response.status_code} from Gemini FastAPI: {detail or response.reason_phrase}",
            status_code=response.status_code,
        )

    async def list_models(self, *, timeout: float) -> list[str]:
        """Return model IDs from GET /v1/models."""
        try:
            response = await self._http_client.get(
                self._url("models"),
                headers=self._headers(),
                timeout=timeout,
            )
            await self._raise_for_status(response)
            payload = response.json()
        except ApiClientError:
            raise
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as err:
            raise ApiClientError(f"Unable to retrieve models: {err}") from err

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ApiClientError("Invalid /models response: expected a data array")

        models: list[str] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                model_id = item["id"].strip()
                if model_id:
                    models.append(model_id)
        return models

    async def chat_completions_stream(
        self,
        payload: dict[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded SSE chunks from POST /v1/chat/completions."""
        try:
            async with self._http_client.stream(
                "POST",
                self._url("chat/completions"),
                headers=self._headers(extra_headers),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                await self._raise_for_status(response)
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError as err:
                        raise ApiClientError(
                            f"Invalid SSE JSON from Gemini FastAPI: {err}"
                        ) from err
                    if isinstance(event, dict):
                        yield event
        except ApiClientError:
            raise
        except httpx.HTTPError as err:
            raise ApiClientError(f"Gemini FastAPI streaming request failed: {err}") from err

    async def create_response(
        self,
        payload: dict[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Call POST /v1/responses and return the decoded JSON response."""
        try:
            response = await self._http_client.post(
                self._url("responses"),
                headers=self._headers(extra_headers),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            await self._raise_for_status(response)
            result = response.json()
        except ApiClientError:
            raise
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as err:
            raise ApiClientError(f"Gemini FastAPI response request failed: {err}") from err
        if not isinstance(result, dict):
            raise ApiClientError("Invalid /responses response: expected a JSON object")
        return result


def create_client(hass: HomeAssistant, data: dict[str, object]) -> GeminiFastApiClient:
    """Create a native client using Home Assistant's shared HTTPX session."""
    api_key = str(data.get(CONF_API_KEY) or "").strip()
    return GeminiFastApiClient(
        get_async_client(hass),
        normalize_base_url(data[LocalAiConfigKey.BASE_URL]),
        api_key,
    )
