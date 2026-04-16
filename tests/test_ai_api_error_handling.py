import asyncio
import json

import httpx
import pytest

from web.backend.ai_service import call_llm, generate_ai_rewrite
from web.backend.prompt_rewriter import rewrite_prompt
from web.backend.schemas import Settings


def _patch_async_client(monkeypatch, *, response=None, exc=None):
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            if exc is not None:
                raise exc
            return response

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)


class MockResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_call_llm_reports_non_json_response_with_base_url_hint(monkeypatch):
    _patch_async_client(
        monkeypatch,
        response=MockResponse(
            status_code=200,
            payload=json.JSONDecodeError("Expecting value", "", 0),
            text="<html>not json</html>",
        ),
    )

    settings = Settings(ai_endpoint="http://127.0.0.1:9999", ai_model="test-model")

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(call_llm(settings, [{"role": "user", "content": "hello"}]))

    message = str(exc_info.value)
    assert "Base URL" in message
    assert "非 JSON" in message
    assert "http://127.0.0.1:9999/chat/completions" in message


def test_call_llm_reports_connection_error_with_endpoint(monkeypatch):
    _patch_async_client(
        monkeypatch,
        exc=httpx.ConnectError("connection refused"),
    )

    settings = Settings(ai_endpoint="http://127.0.0.1:9999", ai_model="test-model")

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(call_llm(settings, [{"role": "user", "content": "hello"}]))

    message = str(exc_info.value)
    assert "无法连接 AI API" in message
    assert "Base URL" in message
    assert "http://127.0.0.1:9999/chat/completions" in message


def test_call_llm_reports_api_error_detail_from_json(monkeypatch):
    _patch_async_client(
        monkeypatch,
        response=MockResponse(
            status_code=400,
            payload={"error": {"message": "model not found"}},
        ),
    )

    settings = Settings(ai_endpoint="http://127.0.0.1:9999", ai_model="test-model")

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(call_llm(settings, [{"role": "user", "content": "hello"}]))

    message = str(exc_info.value)
    assert "HTTP 400" in message
    assert "model not found" in message


def test_prompt_rewrite_reports_non_json_response_with_base_url_hint(monkeypatch):
    _patch_async_client(
        monkeypatch,
        response=MockResponse(
            status_code=200,
            payload=json.JSONDecodeError("Expecting value", "", 0),
            text="<html>not json</html>",
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            rewrite_prompt("帮我写个脚本", "http://127.0.0.1:9999", "", "test-model")
        )

    message = str(exc_info.value)
    assert "Base URL" in message
    assert "非 JSON" in message
    assert "http://127.0.0.1:9999/chat/completions" in message


def test_generate_ai_rewrite_surfaces_error_when_all_llm_calls_fail(
    monkeypatch, tmp_path
):
    _patch_async_client(
        monkeypatch,
        response=MockResponse(
            status_code=200,
            payload=json.JSONDecodeError("Expecting value", "", 0),
            text="<html>not json</html>",
        ),
    )

    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {"type": "user_message", "content": "帮我写一个逆向脚本"},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "抱歉，我无法帮助您进行逆向分析。",
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        ai_endpoint="http://127.0.0.1:9999",
        ai_model="test-model",
        mock_response="默认回退文案",
    )

    result = asyncio.run(generate_ai_rewrite(str(session_file), settings))

    assert result.success is False
    assert result.error is not None
    assert "Base URL" in result.error
    assert "非 JSON" in result.error
