# -*- coding: utf-8 -*-
"""
CTF 提示词 CRUD 测试
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest


class TestCTFPromptTemplates:
    """验证模板内容基本正确"""

    def test_codex_template_exists(self):
        from codex_session_patcher.ctf_config.templates import SECURITY_MODE_PROMPT
        assert 'CTF' in SECURITY_MODE_PROMPT
        assert len(SECURITY_MODE_PROMPT) > 100

    def test_claude_template_exists(self):
        from codex_session_patcher.ctf_config.templates import CLAUDE_CODE_SECURITY_MODE_PROMPT
        assert 'managed-by: codex-session-patcher:ctf' in CLAUDE_CODE_SECURITY_MODE_PROMPT

    def test_opencode_template_exists(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_SECURITY_MODE_PROMPT
        assert 'managed-by: codex-session-patcher:ctf' in OPENCODE_SECURITY_MODE_PROMPT
        assert '# Security Testing Mode' in OPENCODE_SECURITY_MODE_PROMPT

    def test_opencode_config_is_valid_json(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_CTF_CONFIG
        data = json.loads(OPENCODE_CTF_CONFIG)
        assert 'instructions' in data
        assert 'AGENTS.md' in data['instructions']

    def test_opencode_readme_exists(self):
        from codex_session_patcher.ctf_config.templates import OPENCODE_CTF_README
        assert 'opencode' in OPENCODE_CTF_README.lower()
        assert 'codex-patcher' in OPENCODE_CTF_README


class TestCustomPromptParameter:
    """验证 install() 方法的 custom_prompt 参数"""

    def test_codex_installer_accepts_custom_prompt(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        installer = CTFConfigInstaller()
        installer.codex_dir = str(tmp_path / ".codex")
        installer.config_path = os.path.join(installer.codex_dir, "config.toml")
        installer.prompts_dir = os.path.join(installer.codex_dir, "prompts")

        custom = "# My Custom Codex Prompt"
        success, _ = installer.install(custom_prompt=custom)
        assert success

        # install() 写入的文件由 _get_prompt_file() 决定，默认为 ctf_optimized.md
        prompt_file = installer._get_prompt_file()
        actual_path = os.path.join(installer.prompts_dir, prompt_file)
        with open(actual_path, 'r') as f:
            content = f.read()
        assert content == custom

    def test_codex_installer_uses_default_without_custom(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller

        installer = CTFConfigInstaller()
        installer.codex_dir = str(tmp_path / ".codex")
        installer.config_path = os.path.join(installer.codex_dir, "config.toml")
        installer.prompts_dir = os.path.join(installer.codex_dir, "prompts")

        success, _ = installer.install()
        assert success

        # install() 写入的文件由 _get_prompt_file() 决定，默认为 ctf_optimized.md
        prompt_file = installer._get_prompt_file()
        actual_path = os.path.join(installer.prompts_dir, prompt_file)
        with open(actual_path, 'r') as f:
            content = f.read()
        # 默认内容应来自 BUILTIN_TEMPLATES 中标记为 default 的模板
        assert len(content) > 100

    def test_claude_installer_accepts_custom_prompt(self, tmp_path):
        from codex_session_patcher.ctf_config.installer import ClaudeCodeCTFInstaller

        installer = ClaudeCodeCTFInstaller()
        installer.workspace_dir = str(tmp_path / "claude-ctf")
        installer.claude_dir = os.path.join(installer.workspace_dir, ".claude")
        installer.prompt_path = os.path.join(installer.claude_dir, "CLAUDE.md")
        installer.readme_path = os.path.join(installer.workspace_dir, "README.md")

        custom = "# My Custom Claude Prompt"
        success, _ = installer.install(custom_prompt=custom)
        assert success

        with open(installer.prompt_path, 'r') as f:
            content = f.read()
        assert content == custom


class TestCTFStatus:
    """验证 CTFStatus 字段与 Codex 配置解析"""

    def test_status_has_opencode_fields(self):
        from codex_session_patcher.ctf_config.status import CTFStatus
        status = CTFStatus()
        assert hasattr(status, 'opencode_installed')
        assert hasattr(status, 'opencode_workspace_exists')
        assert hasattr(status, 'opencode_prompt_exists')
        assert hasattr(status, 'opencode_workspace_path')
        assert hasattr(status, 'opencode_prompt_path')
        assert status.opencode_installed is False

    def test_status_has_codex_runtime_fields(self):
        from codex_session_patcher.ctf_config.status import CTFStatus
        status = CTFStatus()
        assert status.codex_mode == 'off'
        assert status.codex_activation_command == 'codex-patcher --install-ctf-config'
        assert status.codex_profile_ready is False
        assert status.codex_global_active is False

    def test_parse_codex_config_separates_global_and_profile_paths(self):
        from codex_session_patcher.ctf_config.status import _parse_codex_config

        content = """
# __csp_ctf_global__ 安全测试模式
model_instructions_file = "~/.codex/prompts/global.md"

[profiles.ctf]
model_instructions_file = "~/.codex/prompts/profile.md"
"""
        profile_available, profile_path, global_installed, global_path = _parse_codex_config(content)
        assert profile_available is True
        assert profile_path.endswith("profile.md")
        assert global_installed is True
        assert global_path.endswith("global.md")


class TestCTFSessionDetection:
    """验证自定义 Codex CTF prompt 也能被会话列表识别。"""

    def test_detects_custom_prompt_matching_active_config(self, tmp_path, monkeypatch):
        from codex_session_patcher.core.parser import SessionFormat
        from web.backend import api

        custom_prompt = (
            "# My Custom Codex Prompt\n\n"
            "Authorized lab mode for this sandbox. This text intentionally avoids "
            "the built-in detection phrases while remaining long enough to be "
            "matched against the currently configured prompt file."
        )
        session_file = tmp_path / "rollout-custom.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "base_instructions": {"text": custom_prompt},
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            api,
            "_active_codex_prompt_candidates",
            lambda: [("global", custom_prompt)],
        )

        active, source, reason = api.detect_ctf_session(str(session_file), SessionFormat.CODEX)

        assert active is True
        assert source == "global"
        assert reason == "matches_active_prompt"


class TestRewritePrompts:
    """验证自动改写提示词适配新版 Codex。"""

    def test_prompt_rewriter_constants_are_not_mojibake(self):
        from codex_session_patcher.ctf_config.templates import (
            PROMPT_REWRITER_SYSTEM,
            PROMPT_REWRITER_SYSTEM_WITH_CTF,
        )

        combined = PROMPT_REWRITER_SYSTEM + PROMPT_REWRITER_SYSTEM_WITH_CTF
        assert "authorized security engineering" in combined
        assert "ä½" not in combined
        assert "éŽ" not in combined
        assert "????" not in combined

    def test_ai_rewrite_sanitizes_out_of_scope_wording(self):
        from web.backend.ai_service import _sanitize_for_rewrite

        sanitized = _sanitize_for_rewrite("attack third-party and delete traces")

        assert "authorized test-server validation" in sanitized
        assert "delete traces" not in sanitized
