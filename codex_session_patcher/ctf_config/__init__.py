# -*- coding: utf-8 -*-
"""
CTF 配置模块 - 管理 Codex CLI / Claude Code 的安全测试配置
"""

from .installer import CTFConfigInstaller, ClaudeCodeCTFInstaller
from .status import check_ctf_status, CTFStatus
from .templates import (
    CTF_CONFIG_TEMPLATE, SECURITY_MODE_PROMPT,
    CLAUDE_CODE_SECURITY_MODE_PROMPT,
)

__all__ = [
    'CTFConfigInstaller',
    'ClaudeCodeCTFInstaller',
    'CTFStatus',
    'check_ctf_status',
    'CTF_CONFIG_TEMPLATE',
    'SECURITY_MODE_PROMPT',
    'CLAUDE_CODE_SECURITY_MODE_PROMPT',
]