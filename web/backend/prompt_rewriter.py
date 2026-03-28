# -*- coding: utf-8 -*-
"""
提示词改写服务

使用 AI 将可能被拒绝的请求改写为更易接受的形式。
"""

from typing import Optional

import httpx

from codex_session_patcher.ctf_config.templates import (
    PROMPT_REWRITER_SYSTEM,
    PROMPT_REWRITER_SYSTEM_CLAUDE,
)


async def rewrite_prompt(
    original_request: str,
    ai_endpoint: str,
    ai_key: str,
    ai_model: str,
    target: str = "codex",
) -> tuple[str, str]:
    """
    改写提示词

    Args:
        original_request: 原始请求
        ai_endpoint: AI API endpoint
        ai_key: API key
        ai_model: 模型名称

    Returns:
        tuple[str, str]: (改写后的提示词, 使用的策略)
    """
    # 构建请求
    endpoint = ai_endpoint.rstrip('/')
    if not endpoint.endswith('/chat/completions'):
        endpoint = f"{endpoint}/chat/completions"

    headers = {
        'Content-Type': 'application/json',
    }
    if ai_key:
        headers['Authorization'] = f'Bearer {ai_key}'

    system_prompt = PROMPT_REWRITER_SYSTEM_CLAUDE if target == "claude_code" else PROMPT_REWRITER_SYSTEM
    user_message = f"请改写以下请求：\n\n{original_request}"

    body = {
        'model': ai_model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
        'max_tokens': 1024,
        'temperature': 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(endpoint, json=body, headers=headers)

        if resp.status_code == 401 or resp.status_code == 403:
            raise RuntimeError('API 认证失败，请检查 API Key')
        if resp.status_code == 429:
            raise RuntimeError('API 请求频率受限，请稍后重试')
        if resp.status_code >= 400:
            raise RuntimeError(f'API 请求失败 (HTTP {resp.status_code})')

        data = resp.json()
        choices = data.get('choices', [])
        if not choices:
            raise RuntimeError('AI 返回了空结果')

        rewritten = choices[0]['message']['content'].strip()

        # 简单判断使用的策略（基于改写结果）
        strategy = _detect_strategy(rewritten)

        return rewritten, strategy


def _detect_strategy(rewritten: str) -> str:
    """根据改写结果判断使用的策略"""
    rewritten_lower = rewritten.lower()

    if 'ctf' in rewritten_lower or '比赛' in rewritten_lower or '夺旗' in rewritten_lower:
        return 'ctf'
    elif '渗透' in rewritten_lower or '授权' in rewritten_lower or '评估' in rewritten_lower:
        return 'pentest'
    elif '学习' in rewritten_lower or '研究' in rewritten_lower or '论文' in rewritten_lower:
        return 'learning'
    elif '披露' in rewritten_lower or '厂商' in rewritten_lower or 'cve' in rewritten_lower:
        return 'vulnerability'
    else:
        return 'ctf'  # 默认使用 CTF 策略