# -*- coding: utf-8 -*-
"""
CTF 配置状态检查
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

CTF_MARKER = 'managed-by: codex-session-patcher:ctf'
DEFAULT_CLAUDE_CTF_WORKSPACE = os.path.expanduser("~/.claude-ctf-workspace")
DEFAULT_OPENCODE_CTF_WORKSPACE = os.path.expanduser("~/.opencode-ctf-workspace")


GLOBAL_MARKER = '# __csp_ctf_global__'


@dataclass
class CTFStatus:
    """CTF 配置状态"""
    # Codex
    installed: bool = False
    config_exists: bool = False
    prompt_exists: bool = False
    profile_available: bool = False
    global_installed: bool = False
    config_path: Optional[str] = None
    prompt_path: Optional[str] = None
    # Claude Code
    claude_installed: bool = False
    claude_workspace_exists: bool = False
    claude_prompt_exists: bool = False
    claude_workspace_path: Optional[str] = None
    claude_prompt_path: Optional[str] = None
    # OpenCode
    opencode_installed: bool = False
    opencode_workspace_exists: bool = False
    opencode_prompt_exists: bool = False
    opencode_workspace_path: Optional[str] = None
    opencode_prompt_path: Optional[str] = None


def check_ctf_status() -> CTFStatus:
    """
    检查 CTF 配置的安装状态（Codex + Claude Code）

    Returns:
        CTFStatus: 配置状态信息
    """
    # ── Codex 检查 ──
    codex_dir = os.path.expanduser("~/.codex")
    config_path = os.path.join(codex_dir, "config.toml")

    status = CTFStatus(
        config_path=config_path,
        prompt_path=None,
    )

    if os.path.exists(config_path):
        status.config_exists = True
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '[profiles.ctf]' in content:
                    status.profile_available = True
                    # 从 [profiles.ctf] 提取实际指向的 prompt 文件路径
                    match = re.search(r'model_instructions_file\s*=\s*"([^"]+)"', content)
                    if match:
                        status.prompt_path = os.path.expanduser(match.group(1))
                if GLOBAL_MARKER in content:
                    status.global_installed = True
        except Exception:
            pass

    if status.prompt_path and os.path.exists(status.prompt_path):
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

    # ── OpenCode 检查 ──
    opencode_workspace = DEFAULT_OPENCODE_CTF_WORKSPACE
    opencode_agents_path = os.path.join(opencode_workspace, "AGENTS.md")

    status.opencode_workspace_path = opencode_workspace
    status.opencode_prompt_path = opencode_agents_path
    status.opencode_workspace_exists = os.path.isdir(opencode_workspace)

    if os.path.exists(opencode_agents_path):
        try:
            with open(opencode_agents_path, 'r', encoding='utf-8') as f:
                content = f.read(500)
                if CTF_MARKER in content:
                    status.opencode_prompt_exists = True
        except Exception:
            pass

    status.opencode_installed = status.opencode_workspace_exists and status.opencode_prompt_exists

    return status