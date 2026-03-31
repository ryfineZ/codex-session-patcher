# -*- coding: utf-8 -*-
"""
Claude Code 项目目录扫描测试
"""
from __future__ import annotations

import json
from pathlib import Path

from codex_session_patcher.core.formats import SessionFormat, encode_claude_project_path
from codex_session_patcher.core.parser import (
    resolve_claude_session_dirs,
    list_sessions_from_directories,
)


def _write_claude_session(session_dir: Path, filename: str = "12345678-1234-1234-1234-123456789abc.jsonl") -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / filename
    with open(session_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "正常回复"}
                ],
            },
        }, ensure_ascii=False) + "\n")
    return session_path


class TestClaudeProjectScan:
    def test_resolve_project_root_to_global_claude_store(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        project_root.mkdir(parents=True, exist_ok=True)

        mapped_dir = claude_store / encode_claude_project_path(str(project_root))
        _write_claude_session(mapped_dir)

        scan_dirs = resolve_claude_session_dirs(
            [str(project_root)],
            default_dir=str(claude_store),
        )

        assert str(claude_store.resolve()) in scan_dirs
        assert str(mapped_dir.resolve()) in scan_dirs

    def test_resolve_local_project_claude_directory(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        local_projects_dir = project_root / ".claude" / "projects"
        _write_claude_session(local_projects_dir)

        scan_dirs = resolve_claude_session_dirs(
            [str(project_root)],
            default_dir=str(claude_store),
        )

        assert str(local_projects_dir.resolve()) in scan_dirs

    def test_resolve_local_project_prefixed_claude_directory(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        local_projects_dir = project_root / ".claude_config_glm" / "projects"
        _write_claude_session(local_projects_dir)

        scan_dirs = resolve_claude_session_dirs(
            [str(project_root)],
            default_dir=str(claude_store),
        )

        assert str(local_projects_dir.resolve()) in scan_dirs

    def test_resolve_prefixed_claude_root_directory(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        claude_root = project_root / ".claude_config_glm"
        local_projects_dir = claude_root / "projects"
        _write_claude_session(local_projects_dir)

        scan_dirs = resolve_claude_session_dirs(
            [str(claude_root)],
            default_dir=str(claude_store),
        )

        assert str(local_projects_dir.resolve()) in scan_dirs
        assert str(claude_root.resolve()) not in scan_dirs

    def test_does_not_resolve_prefixed_claude_subdirectory(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        claude_root = project_root / ".claude_config_glm"
        local_projects_dir = claude_root / "projects"
        sessions_dir = claude_root / "sessions"
        _write_claude_session(local_projects_dir)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        scan_dirs = resolve_claude_session_dirs(
            [str(sessions_dir)],
            default_dir=str(claude_store),
        )

        assert str(local_projects_dir.resolve()) not in scan_dirs

    def test_list_sessions_dedupes_overlapping_directories(self, tmp_path):
        claude_store = tmp_path / "claude-projects"
        project_root = tmp_path / "workspace" / "demo_project"
        mapped_dir = claude_store / encode_claude_project_path(str(project_root))
        session_path = _write_claude_session(mapped_dir)

        sessions = list_sessions_from_directories(
            [str(claude_store), str(mapped_dir)],
            session_format=SessionFormat.CLAUDE_CODE,
        )

        assert len(sessions) == 1
        assert sessions[0].path == str(session_path)
