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
    global_prompt_path: Optional[str] = None
    global_prompt_exists: bool = False
    codex_profile_ready: bool = False
    codex_global_active: bool = False
    codex_mode: str = "off"  # off | profile | profile_broken | global | global_broken
    codex_activation_command: str = "codex-patcher --install-ctf-config"
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


_SECTION_RE = re.compile(r'^\s*\[([^\]]+)\]\s*(?:#.*)?$')
_MODEL_INSTRUCTIONS_RE = re.compile(
    r'''^\s*model_instructions_file\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s#]+))'''
)


def _extract_model_instructions_path(line: str) -> Optional[str]:
    """从一行 TOML 中提取 model_instructions_file 的路径。"""
    match = _MODEL_INSTRUCTIONS_RE.search(line)
    if not match:
        return None
    raw = next((group for group in match.groups() if group), None)
    if not raw:
        return None
    return os.path.expandvars(os.path.expanduser(raw))


def _parse_codex_config(content: str) -> tuple[bool, Optional[str], bool, Optional[str]]:
    """解析 Codex config.toml 中的 CTF profile 与全局注入路径。

    返回:
        (profile_available, profile_prompt_path, global_installed, global_prompt_path)

    旧实现用全文正则提取第一个 model_instructions_file，容易把全局配置误判成
    [profiles.ctf] 的 prompt。这里按 section 解析，避免 UI 展示和状态判断混淆。
    """
    profile_available = False
    profile_prompt_path: Optional[str] = None
    global_installed = GLOBAL_MARKER in content
    global_prompt_path: Optional[str] = None

    lines = content.splitlines()
    current_section: Optional[str] = None
    top_level_prompt_path: Optional[str] = None

    for line in lines:
        section_match = _SECTION_RE.match(line.strip())
        if section_match:
            current_section = section_match.group(1).strip()
            if current_section == "profiles.ctf":
                profile_available = True
            continue

        prompt_path = _extract_model_instructions_path(line)
        if not prompt_path:
            continue

        if current_section == "profiles.ctf":
            profile_prompt_path = prompt_path
        elif current_section is None:
            top_level_prompt_path = prompt_path

    if global_installed:
        # 优先读取紧跟 marker 后的 model_instructions_file；兼容 marker 与配置中间有空行。
        for idx, line in enumerate(lines):
            if GLOBAL_MARKER not in line:
                continue
            for next_line in lines[idx + 1:]:
                stripped = next_line.strip()
                if not stripped:
                    continue
                if _SECTION_RE.match(stripped):
                    break
                prompt_path = _extract_model_instructions_path(next_line)
                if prompt_path:
                    global_prompt_path = prompt_path
                    break
            if global_prompt_path:
                break

        # 兜底：旧版本 marker 管理的是顶层 model_instructions_file。
        if not global_prompt_path:
            global_prompt_path = top_level_prompt_path

    return profile_available, profile_prompt_path, global_installed, global_prompt_path


def check_ctf_status() -> CTFStatus:
    """
    检查 CTF 配置的安装状态（Codex + Claude Code）

    Returns:
        CTFStatus: 配置状态信息
    """
    # ── Codex 检查 ──
    codex_dir = os.path.expanduser("~/.codex")
    config_path = os.path.join(codex_dir, "config.toml")
    profile_config_path = os.path.join(codex_dir, "ctf.config.toml")

    status = CTFStatus(
        config_path=config_path,
        prompt_path=None,
    )

    if os.path.exists(config_path):
        status.config_exists = True
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            (
                status.profile_available,
                status.prompt_path,
                status.global_installed,
                status.global_prompt_path,
            ) = _parse_codex_config(content)
        except Exception:
            pass

    if os.path.exists(profile_config_path):
        status.config_exists = True
        try:
            with open(profile_config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    prompt_path = _extract_model_instructions_path(line)
                    if prompt_path:
                        status.profile_available = True
                        status.prompt_path = prompt_path
                        break
        except Exception:
            pass

    if status.prompt_path and os.path.exists(status.prompt_path):
        status.prompt_exists = True

    status.installed = status.config_exists and status.prompt_exists and status.profile_available
    status.codex_profile_ready = status.installed

    if status.global_prompt_path and os.path.exists(status.global_prompt_path):
        status.global_prompt_exists = True

    status.codex_global_active = status.global_installed and status.global_prompt_exists

    if status.codex_global_active:
        status.codex_mode = "global"
        status.codex_activation_command = "codex"
    elif status.global_installed:
        status.codex_mode = "global_broken"
        status.codex_activation_command = "codex-patcher --install-ctf-config"
    elif status.codex_profile_ready:
        status.codex_mode = "profile"
        status.codex_activation_command = "codex -p ctf"
    elif status.profile_available:
        status.codex_mode = "profile_broken"
        status.codex_activation_command = "codex-patcher --install-ctf-config"
    else:
        status.codex_mode = "off"
        status.codex_activation_command = "codex-patcher --install-ctf-config"

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
