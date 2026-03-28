# -*- coding: utf-8 -*-
"""
CTF 配置状态检查
"""

import os
from dataclasses import dataclass
from typing import Optional

CTF_MARKER = 'managed-by: codex-session-patcher:ctf'
DEFAULT_CLAUDE_CTF_WORKSPACE = os.path.expanduser("~/.claude-ctf-workspace")


@dataclass
class CTFStatus:
    """CTF 配置状态"""
    # Codex
    installed: bool = False
    config_exists: bool = False
    prompt_exists: bool = False
    profile_available: bool = False
    config_path: Optional[str] = None
    prompt_path: Optional[str] = None
    # Claude Code
    claude_installed: bool = False
    claude_workspace_exists: bool = False
    claude_prompt_exists: bool = False
    claude_workspace_path: Optional[str] = None
    claude_prompt_path: Optional[str] = None


def check_ctf_status() -> CTFStatus:
    """
    检查 CTF 配置的安装状态（Codex + Claude Code）

    Returns:
        CTFStatus: 配置状态信息
    """
    # ── Codex 检查 ──
    codex_dir = os.path.expanduser("~/.codex")
    config_path = os.path.join(codex_dir, "config.toml")
    prompts_dir = os.path.join(codex_dir, "prompts")
    prompt_path = os.path.join(prompts_dir, "security_mode.md")

    status = CTFStatus(
        config_path=config_path,
        prompt_path=prompt_path,
    )

    if os.path.exists(config_path):
        status.config_exists = True
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '[profiles.ctf]' in content:
                    status.profile_available = True
        except Exception:
            pass

    if os.path.exists(prompt_path):
        status.prompt_exists = True

    status.installed = status.config_exists and status.prompt_exists and status.profile_available

    # ── Claude Code 检查 ──
    workspace_path = DEFAULT_CLAUDE_CTF_WORKSPACE
    claude_prompt_path = os.path.join(workspace_path, ".claude", "CLAUDE.md")

    status.claude_workspace_path = workspace_path
    status.claude_prompt_path = claude_prompt_path
    status.claude_workspace_exists = os.path.isdir(workspace_path)

    if os.path.exists(claude_prompt_path):
        try:
            with open(claude_prompt_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # 只需读开头
                if CTF_MARKER in content:
                    status.claude_prompt_exists = True
        except Exception:
            pass

    status.claude_installed = status.claude_workspace_exists and status.claude_prompt_exists

    return status