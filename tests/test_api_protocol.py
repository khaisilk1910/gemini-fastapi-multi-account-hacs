"""Offline contract tests for native SSE transport (no HA installation required)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import httpx
import pytest


def _module(monkeypatch):
    """Load only the native HTTP transport with minimal HA import shims."""
    root = "gemini_fastapi_transport_test"
    package = types.ModuleType(root)
    package.__path__ = []
    monkeypatch.setitem(sys.modules, root, package)
    const = types.ModuleType(f"{root}.const")
    const.REQUEST_TIMEOUT = 145.0
    const.LocalAiConfigKey = types.SimpleNamespace(BASE_URL="base_url")
    monkeypatch.setitem(sys.modules, f"{root}.const", const)

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.CONF_API_KEY = "api_key"
    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = object
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_httpx = types.ModuleType("homeassistant.helpers.httpx_client")
    ha_httpx.get_async_client = lambda hass: hass
    for name, value in (
        ("homeassistant", ha),
        ("homeassistant.const", ha_const),
        ("homeassistant.core", ha_core),
        ("homeassistant.helpers", ha_helpers),
        ("homeassistant.helpers.httpx_client", ha_httpx),
    ):
        monkeypatch.setitem(sys.modules, name, value)

    path = Path(__file__).resolve().parents[1] / "custom_components/gemini_fastapi_multi_account/api.py"
    spec = importlib.util.spec_from_file_location(f"{root}.api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _exercise(module, body: str, status: int = 200):
    received_headers = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.append(request.headers)
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(status, text=body, headers={"content-type": "text/event-stream"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = module.GeminiFastApiClient(http_client, "http://testserver/v1", "secret")
            return [part async for part in client.chat_completions_stream({"model": "test"})]

    return asyncio.run(run()), received_headers


def test_successful_stream_yields_complete_chunks(monkeypatch):
    module = _module(monkeypatch)
    result, headers = _exercise(
        module,
        'data: {"choices":[{"delta":{"content":"Xin chao"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        'data: [DONE]\n\n',
    )
    assert len(result) == 2
    assert result[0]["choices"][0]["delta"]["content"] == "Xin chao"
    assert headers[0]["accept"] == "text/event-stream"
    assert headers[0]["authorization"] == "Bearer secret"


def test_sse_error_is_not_ignored_after_http_200(monkeypatch):
    module = _module(monkeypatch)
    body = 'data: ' + json.dumps({"error": {"type": "server_error", "message": "upstream failed"}}) + '\n\ndata: [DONE]\n\n'
    with pytest.raises(module.ApiClientError, match="upstream failed"):
        _exercise(module, body)


def test_incomplete_stream_is_not_success(monkeypatch):
    module = _module(monkeypatch)
    with pytest.raises(module.ApiClientError, match="without \\[DONE\\]"):
        _exercise(module, 'data: {"choices": [{"delta": {"content": "incomplete"}}]}\n\n')


def test_invalid_sse_object_is_rejected(monkeypatch):
    module = _module(monkeypatch)
    with pytest.raises(module.ApiClientError, match="expected a JSON object"):
        _exercise(module, 'data: [1, 2]\n\ndata: [DONE]\n\n')


def test_http_503_is_distinct_from_sse_errors(monkeypatch):
    module = _module(monkeypatch)
    with pytest.raises(module.ApiClientError) as info:
        _exercise(module, '{"detail": "all accounts cooling down"}', status=503)
    assert info.value.status_code == 503


def test_url_normalization_is_backward_compatible(monkeypatch):
    module = _module(monkeypatch)
    assert module.normalize_base_url('http://host:8000') == 'http://host:8000/v1'
    assert module.normalize_base_url('http://host:8000/v1/chat/completions') == 'http://host:8000/v1'
