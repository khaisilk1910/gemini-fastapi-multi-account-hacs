"""OpenAI-compatible client helpers for Gemini FastAPI Multi-Account."""
from __future__ import annotations
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from openai import AsyncOpenAI
from .const import REQUEST_TIMEOUT, LocalAiConfigKey

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

def create_client(hass: HomeAssistant, data: dict[str, object]) -> AsyncOpenAI:
    """Create a client using Home Assistant's shared HTTPX session."""
    api_key = str(data.get(CONF_API_KEY) or "").strip() or "not-needed"
    return AsyncOpenAI(
        base_url=normalize_base_url(data[LocalAiConfigKey.BASE_URL]),
        api_key=api_key,
        http_client=cast(Any, get_async_client(hass)),
        timeout=REQUEST_TIMEOUT,
        max_retries=0,
    )
