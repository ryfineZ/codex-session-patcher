# -*- coding: utf-8 -*-
"""
提示词改写服务

使用 AI 将可能被拒绝的请求改写为更易接受的形式。
"""

from __future__ import annotations

from typing import Optional

from .llm_client import request_openai_chat_completion
from codex_session_patcher.ctf_config.templates import (
    PROMPT_REWRITER_SYSTEM,
    PROMPT_REWRITER_SYSTEM_WITH_CTF,
)


async def rewrite_prompt(
    original_request: str,
    ai_endpoint: str,
    ai_key: str,
    ai_model: str,
    target: str = "codex",
    ctf_prompt: Optional[str] = None,
) -> tuple[str, str]:
    """
    改写提示词

    Args:
        original_request: 原始请求
        ai_endpoint: AI API endpoint
        ai_key: API key
        ai_model: 模型名称
        ctf_prompt: 当前注入的 CTF 系统提示词（有则配合使用）

    Returns:
        tuple[str, str]: (改写后的提示词, 使用的策略)
    """
    if ctf_prompt and ctf_prompt.strip():
        system_prompt = PROMPT_REWRITER_SYSTEM_WITH_CTF.format(
            ctf_prompt=ctf_prompt.strip()
        )
    else:
        system_prompt = PROMPT_REWRITER_SYSTEM
    user_message = f"请改写以下请求：\n\n{original_request}"

    body = {
        "model": ai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    data = await request_openai_chat_completion(ai_endpoint, ai_key, body)
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("AI 返回了空结果")

    rewritten = choices[0]["message"]["content"].strip()

    # 简单判断使用的策略（基于改写结果）
    strategy = _detect_strategy(rewritten)

    return rewritten, strategy


def _detect_strategy(rewritten: str) -> str:
    """根据改写结果判断使用的策略"""
    rewritten_lower = rewritten.lower()

    if (
        "ctf" in rewritten_lower
        or "比赛" in rewritten_lower
        or "夺旗" in rewritten_lower
    ):
        return "ctf"
    elif (
        "渗透" in rewritten_lower
        or "授权" in rewritten_lower
        or "评估" in rewritten_lower
    ):
        return "pentest"
    elif (
        "学习" in rewritten_lower
        or "研究" in rewritten_lower
        or "论文" in rewritten_lower
    ):
        return "learning"
    elif (
        "披露" in rewritten_lower
        or "厂商" in rewritten_lower
        or "cve" in rewritten_lower
    ):
        return "vulnerability"
    else:
        return "ctf"  # 默认使用 CTF 策略
