from __future__ import annotations

import json
from typing import Any

import httpx


def build_chat_completions_endpoint(ai_endpoint: str) -> str:
    """规范化 OpenAI 兼容接口地址。"""
    endpoint = ai_endpoint.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"
    return endpoint


def _truncate_text(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, list):
        parts = [_extract_error_message(item) for item in payload]
        return "; ".join(part for part in parts if part)

    if isinstance(payload, dict):
        candidates = [
            payload.get("error"),
            payload.get("detail"),
            payload.get("message"),
            payload.get("msg"),
            payload.get("error_message"),
            payload.get("description"),
        ]
        for candidate in candidates:
            message = _extract_error_message(candidate)
            if message:
                return message

    return ""


def _extract_response_detail(response: Any) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        text = _truncate_text(getattr(response, "text", ""))
        return text or "响应为空"

    message = _extract_error_message(payload)
    if message:
        return message

    if isinstance(payload, (dict, list)):
        serialized = _truncate_text(json.dumps(payload, ensure_ascii=False))
        if serialized:
            return serialized

    return "未返回详细错误信息"


def _build_endpoint_hint(endpoint: str) -> str:
    return f"Base URL/Endpoint: {endpoint}"


def _raise_for_error_response(endpoint: str, response: Any) -> None:
    status_code = getattr(response, "status_code", None)
    if status_code is None or status_code < 400:
        return

    detail = _extract_response_detail(response)
    endpoint_hint = _build_endpoint_hint(endpoint)

    if status_code in (401, 403):
        raise RuntimeError(
            f"API 认证失败 (HTTP {status_code})：{detail}。{endpoint_hint}"
        )
    if status_code == 429:
        raise RuntimeError(f"API 请求频率受限 (HTTP 429)：{detail}。{endpoint_hint}")

    raise RuntimeError(
        f"AI API 请求失败 (HTTP {status_code})：{detail}。{endpoint_hint}"
    )


def parse_json_response(endpoint: str, response: Any) -> dict:
    """解析 JSON 响应，并在失败时给出可诊断的错误信息。"""
    _raise_for_error_response(endpoint, response)

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        snippet = _truncate_text(getattr(response, "text", "")) or "响应为空"
        endpoint_hint = _build_endpoint_hint(endpoint)
        raise RuntimeError(
            f"AI API 返回非 JSON 响应，请检查 Base URL 是否正确。{endpoint_hint}。响应片段: {snippet}"
        ) from exc

    if not isinstance(data, dict):
        endpoint_hint = _build_endpoint_hint(endpoint)
        raise RuntimeError(f"AI API 返回了异常响应结构。{endpoint_hint}")

    return data


async def request_openai_chat_completion(
    ai_endpoint: str,
    ai_key: str,
    body: dict,
    timeout: float = 30.0,
) -> dict:
    """发送 OpenAI 兼容 chat/completions 请求并统一处理错误。"""
    endpoint = build_chat_completions_endpoint(ai_endpoint)

    headers = {
        "Content-Type": "application/json",
    }
    if ai_key:
        headers["Authorization"] = f"Bearer {ai_key}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(endpoint, json=body, headers=headers)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接 AI API，请检查 Base URL 是否正确。{_build_endpoint_hint(endpoint)}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"AI API 请求失败：{exc}。{_build_endpoint_hint(endpoint)}"
            ) from exc

    return parse_json_response(endpoint, response)
