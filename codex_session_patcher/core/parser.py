# -*- coding: utf-8 -*-
"""
会话解析器 — 支持 Codex CLI 和 Claude Code 两种 JSONL 格式
"""
from __future__ import annotations

import logging
import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field

from .formats import (
    SessionFormat,
    detect_session_format,
    decode_claude_project_path,
    encode_claude_project_path,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """会话信息"""
    path: str
    filename: str
    mtime: float
    mtime_str: str
    date: str
    session_id: str
    size: int
    format: SessionFormat = SessionFormat.CODEX
    project_path: Optional[str] = None  # Claude Code 专用：解码后的项目路径


class SessionParser:
    """会话文件解析器 - 支持 JSONL 格式"""

    DEFAULT_DIRS = {
        SessionFormat.CODEX: "~/.codex/sessions/",
        SessionFormat.CLAUDE_CODE: "~/.claude/projects/",
        SessionFormat.OPENCODE: "~/.local/share/opencode/",
    }

    def __init__(self, session_dir: str = None, session_format: SessionFormat = None):
        """
        Args:
            session_dir: 会话目录，为 None 时根据 session_format 使用默认值
            session_format: 会话格式，为 None 时自动检测
        """
        if session_format is not None and session_dir is None:
            session_dir = self.DEFAULT_DIRS.get(session_format, "~/.codex/sessions/")
        elif session_dir is None:
            session_dir = "~/.codex/sessions/"

        self.session_dir = os.path.realpath(os.path.expanduser(session_dir))
        self.session_format = session_format

    def list_sessions(self) -> List[SessionInfo]:
        """列出所有会话文件，按修改时间降序排序"""
        if not os.path.exists(self.session_dir):
            return []

        sessions = []
        for root, dirs, files in os.walk(self.session_dir):
            for f in files:
                if not f.endswith(".jsonl"):
                    continue
                # 跳过备份文件
                if f.endswith(".bak"):
                    continue
                full_path = os.path.join(root, f)
                try:
                    info = self._parse_session_file(full_path, f, root)
                    if info:
                        sessions.append(info)
                except Exception:
                    logger.debug("解析会话文件失败: %s", full_path, exc_info=True)
                    continue

        sessions.sort(key=lambda x: x.mtime, reverse=True)
        return sessions

    def _parse_session_file(self, full_path: str, filename: str, root: str) -> Optional[SessionInfo]:
        """解析单个会话文件的元信息"""
        stat = os.stat(full_path)
        mtime = stat.st_mtime
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

        # 根据格式决定解析方式
        fmt = self.session_format
        if fmt is None:
            fmt = self._detect_format(full_path, root)

        if fmt == SessionFormat.CODEX:
            date, session_id = self._parse_codex_filename(filename, mtime_str)
            project_path = None
        else:
            date, session_id = self._parse_claude_filename(filename, mtime_str)
            project_path = self._extract_project_path(root)

        return SessionInfo(
            path=full_path,
            filename=filename,
            mtime=mtime,
            mtime_str=mtime_str,
            date=date,
            session_id=session_id,
            size=stat.st_size,
            format=fmt,
            project_path=project_path,
        )

    def _detect_format(self, full_path: str, root: str) -> SessionFormat:
        """自动检测文件格式"""
        codex_dir = os.path.expanduser("~/.codex/")
        claude_dir = os.path.expanduser("~/.claude/")
        if root.startswith(codex_dir):
            return SessionFormat.CODEX
        if root.startswith(claude_dir):
            return SessionFormat.CLAUDE_CODE
        # 回退到内容检测
        return detect_session_format(full_path)

    @staticmethod
    def _parse_codex_filename(filename: str, mtime_str: str) -> Tuple[str, str]:
        """从 Codex 文件名提取日期和 ID"""
        match = re.match(r'rollout-(\d{4}-\d{2}-\d{2})T[\d-]+-([a-f0-9-]+)\.jsonl', filename)
        if match:
            return match.group(1), match.group(2)[:8]
        return mtime_str[:10], filename[:8]

    @staticmethod
    def _parse_claude_filename(filename: str, mtime_str: str) -> Tuple[str, str]:
        """从 Claude Code 文件名提取日期和 ID"""
        # Claude Code 文件名格式：{uuid}.jsonl
        uuid_match = re.match(r'([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})\.jsonl', filename)
        if uuid_match:
            return mtime_str[:10], uuid_match.group(1)[:8]
        return mtime_str[:10], filename[:8]

    def _extract_project_path(self, root: str) -> Optional[str]:
        """从 Claude Code 目录路径中提取项目路径"""
        candidate_roots = []
        seen = set()

        def add_root(path: str):
            expanded = os.path.realpath(os.path.expanduser(path))
            if expanded not in seen:
                seen.add(expanded)
                candidate_roots.append(expanded)

        session_root = os.path.realpath(self.session_dir)
        add_root("~/.claude/projects/")
        add_root(session_root)

        parent_dir = os.path.dirname(session_root.rstrip(os.sep))
        if os.path.basename(parent_dir) == "projects":
            add_root(parent_dir)

        for base_dir in candidate_roots:
            try:
                relative = os.path.relpath(root, base_dir)
            except ValueError:
                continue

            if relative == ".":
                base_name = os.path.basename(base_dir)
                if base_name.startswith("-"):
                    return decode_claude_project_path(base_name)
                continue

            if relative.startswith(".."):
                continue

            encoded = relative.split(os.sep, 1)[0]
            if encoded.startswith("-"):
                return decode_claude_project_path(encoded)

        return None

    def parse_session_jsonl(self, file_path: str) -> List[Dict[str, Any]]:
        """解析 JSONL 格式的会话文件"""
        lines = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        data['_line_num'] = line_num
                        lines.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            raise ValueError(f"读取文件失败: {file_path}\n{e}")
        return lines


def _find_first_jsonl_file(dir_path: str) -> Optional[str]:
    """递归查找目录下的第一个 JSONL 会话文件。"""
    if not os.path.isdir(dir_path):
        return None

    for root, dirs, files in os.walk(dir_path):
        dirs.sort()
        for filename in sorted(files):
            if filename.endswith(".jsonl") and not filename.endswith(".bak"):
                return os.path.join(root, filename)
    return None


def _looks_like_claude_session_dir(dir_path: str) -> bool:
    """判断目录是否像 Claude Code 会话目录。"""
    sample = _find_first_jsonl_file(dir_path)
    if not sample:
        return False
    return detect_session_format(sample) == SessionFormat.CLAUDE_CODE


def _is_claude_prefixed_dir(path: str) -> bool:
    return os.path.basename(path).startswith(".claude")


def _discover_claude_prefixed_dirs(path: str) -> List[str]:
    """从输入路径推导可能的 `.claude*` 根目录。

    支持两种情况：
    1. 直接传入 `.claude*`
    2. 传入项目根目录，自动查找其一级子目录中的 `.claude*`
    """
    resolved: List[str] = []
    seen = set()

    def add_dir(candidate: str):
        expanded = os.path.realpath(os.path.expanduser(candidate))
        if not os.path.isdir(expanded) or expanded in seen:
            return
        seen.add(expanded)
        resolved.append(expanded)

    root_path = os.path.realpath(os.path.expanduser(path))
    if _is_claude_prefixed_dir(root_path):
        add_dir(root_path)
    elif os.path.isdir(root_path):
        try:
            for entry in sorted(os.scandir(root_path), key=lambda item: item.name):
                if entry.is_dir() and entry.name.startswith(".claude"):
                    add_dir(entry.path)
        except OSError:
            logger.debug("扫描 `.claude*` 子目录失败: %s", root_path, exc_info=True)

    return resolved


def resolve_claude_session_dirs(
    project_dirs: Optional[List[str]] = None,
    default_dir: Optional[str] = None,
) -> List[str]:
    """解析 Claude Code 的扫描目录。

    支持三类输入：
    1. Claude 全局会话目录（默认始终加入）
    2. 直接导入的会话目录
    3. 普通项目目录，会尝试匹配：
       - <project>/.claude*/projects
       - ~/.claude/projects/<encoded-project-path>
    """
    default_root = os.path.realpath(os.path.expanduser(
        default_dir or SessionParser.DEFAULT_DIRS[SessionFormat.CLAUDE_CODE]
    ))

    resolved_dirs: List[str] = []
    seen_dirs = set()

    def add_dir(path: Optional[str]):
        if not path:
            return
        expanded = os.path.realpath(os.path.expanduser(path.strip()))
        if not os.path.isdir(expanded) or expanded in seen_dirs:
            return
        seen_dirs.add(expanded)
        resolved_dirs.append(expanded)

    add_dir(default_root)

    for raw_path in project_dirs or []:
        if not raw_path or not str(raw_path).strip():
            continue

        normalized = os.path.realpath(os.path.expanduser(str(raw_path).strip()))

        if normalized == default_root or normalized.startswith(default_root + os.sep):
            add_dir(normalized)
            continue

        added_nested_dir = False
        for claude_root in _discover_claude_prefixed_dirs(normalized):
            projects_dir = os.path.join(claude_root, "projects")
            if _looks_like_claude_session_dir(projects_dir):
                add_dir(projects_dir)
                added_nested_dir = True

        mapped_global_dir = os.path.join(default_root, encode_claude_project_path(normalized))
        add_dir(mapped_global_dir)

    return resolved_dirs


def list_sessions_from_directories(
    session_dirs: List[str],
    session_format: Optional[SessionFormat] = None,
) -> List[SessionInfo]:
    """从多个目录聚合会话，并按文件路径去重。"""
    sessions: List[SessionInfo] = []
    seen_paths = set()

    for session_dir in session_dirs:
        parser = SessionParser(session_dir, session_format=session_format)
        for info in parser.list_sessions():
            real_path = os.path.realpath(info.path)
            if real_path in seen_paths:
                continue
            seen_paths.add(real_path)
            sessions.append(info)

    sessions.sort(key=lambda x: x.mtime, reverse=True)
    return sessions


# ─── 向后兼容的模块级函数（Codex 格式专用） ─────────────────────────────────────

def get_assistant_messages(lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    """从 Codex JSONL 行中提取助手消息"""
    messages = []
    for idx, line in enumerate(lines):
        if line.get('type') == 'response_item':
            payload = line.get('payload', {})
            if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                messages.append((idx, line))
    return messages


def get_reasoning_items(lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    """从 Codex JSONL 行中提取推理内容"""
    items = []
    for idx, line in enumerate(lines):
        if line.get('type') == 'response_item':
            payload = line.get('payload', {})
            if payload.get('type') == 'reasoning':
                items.append((idx, line))
    return items


def extract_text_content(message_line: Dict[str, Any]) -> str:
    """从 Codex 消息行中提取文本内容"""
    payload = message_line.get('payload', {})
    content = payload.get('content', [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'output_text':
                texts.append(item.get('text', ''))
        return '\n'.join(texts)
    return ''


def update_text_content(message_line: Dict[str, Any], new_text: str) -> Dict[str, Any]:
    """更新 Codex 消息行的文本内容"""
    import copy
    updated = copy.deepcopy(message_line)
    payload = updated.get('payload', {})
    content = payload.get('content', [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'output_text':
                item['text'] = new_text
    else:
        payload['content'] = [{'type': 'output_text', 'text': new_text}]
    return updated
