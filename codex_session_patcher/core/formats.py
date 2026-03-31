# -*- coding: utf-8 -*-
"""
会话格式策略 — 支持 Codex CLI 和 Claude Code 两种 JSONL 格式
"""
from __future__ import annotations

import copy
import json
import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class SessionFormat(Enum):
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"


# ─── 策略基类 ─────────────────────────────────────────────────────────────────

class FormatStrategy(ABC):
    """格式特定操作的抽象基类"""

    @abstractmethod
    def get_assistant_messages(self, lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        """返回 [(行索引, 消息数据), ...]"""

    @abstractmethod
    def get_thinking_items(self, lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        """返回需要整行删除的 thinking/reasoning 条目"""

    @abstractmethod
    def extract_text_content(self, msg: Dict[str, Any]) -> str:
        """从一条助手消息中提取纯文本"""

    @abstractmethod
    def update_text_content(self, msg: Dict[str, Any], new_text: str) -> Dict[str, Any]:
        """替换消息中的文本内容，返回深拷贝"""

    def remove_thinking_from_message(self, msg: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """移除消息 content 数组中嵌入的 thinking 块。
        返回 (更新后的消息, 被移除的数量)。
        默认实现：不做任何事（Codex 的 thinking 是独立行）。
        """
        return msg, 0


# ─── Codex 策略 ───────────────────────────────────────────────────────────────

class CodexFormatStrategy(FormatStrategy):
    """Codex CLI 格式：response_item + payload 包装"""

    def get_assistant_messages(self, lines):
        messages = []
        for idx, line in enumerate(lines):
            line_type = line.get('type')
            payload = line.get('payload', {})

            # response_item: role=assistant（主消息结构）
            if line_type == 'response_item':
                if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                    messages.append((idx, line))

            # event_msg: agent_message（assistant 回复的冗余副本，resume 时展示用）
            elif line_type == 'event_msg':
                pt = payload.get('type')
                if pt == 'agent_message' and payload.get('message'):
                    messages.append((idx, line))
                elif pt == 'task_complete' and payload.get('last_agent_message'):
                    messages.append((idx, line))

        return messages

    def get_thinking_items(self, lines):
        items = []
        for idx, line in enumerate(lines):
            if line.get('type') == 'response_item':
                payload = line.get('payload', {})
                if payload.get('type') == 'reasoning':
                    items.append((idx, line))
        return items

    def extract_text_content(self, msg):
        line_type = msg.get('type')
        payload = msg.get('payload', {})

        # event_msg/agent_message
        if line_type == 'event_msg':
            pt = payload.get('type')
            if pt == 'agent_message':
                return payload.get('message', '')
            if pt == 'task_complete':
                return payload.get('last_agent_message', '')
            return ''

        # response_item/assistant
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

    def update_text_content(self, msg, new_text):
        updated = copy.deepcopy(msg)
        line_type = updated.get('type')
        payload = updated.get('payload', {})

        # event_msg/agent_message 和 event_msg/task_complete
        if line_type == 'event_msg':
            pt = payload.get('type')
            if pt == 'agent_message':
                payload['message'] = new_text
            elif pt == 'task_complete':
                payload['last_agent_message'] = new_text
            return updated

        # response_item/assistant
        content = payload.get('content', [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'output_text':
                    item['text'] = new_text
        else:
            payload['content'] = [{'type': 'output_text', 'text': new_text}]
        return updated


# ─── Claude Code 策略 ─────────────────────────────────────────────────────────

class ClaudeCodeFormatStrategy(FormatStrategy):
    """Claude Code 格式：顶层 type=assistant，message.content 包含 thinking/text 等"""

    def get_assistant_messages(self, lines):
        messages = []
        for idx, line in enumerate(lines):
            if line.get('type') == 'assistant':
                msg = line.get('message', {})
                if msg.get('role') == 'assistant':
                    messages.append((idx, line))
        return messages

    def get_thinking_items(self, lines):
        # Claude Code 的 thinking 嵌入在 message.content[] 中，不是独立行
        return []

    def extract_text_content(self, msg):
        message = msg.get('message', {})
        content = message.get('content', [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    texts.append(item.get('text', ''))
            return '\n'.join(texts)
        return ''

    def update_text_content(self, msg, new_text):
        updated = copy.deepcopy(msg)
        message = updated.get('message', {})
        content = message.get('content', [])
        if isinstance(content, list):
            replaced = False
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    item['text'] = new_text
                    replaced = True
                    break
            if not replaced:
                content.append({'type': 'text', 'text': new_text})
        else:
            message['content'] = [{'type': 'text', 'text': new_text}]
        return updated

    def remove_thinking_from_message(self, msg):
        updated = copy.deepcopy(msg)
        message = updated.get('message', {})
        content = message.get('content', [])
        if not isinstance(content, list):
            return updated, 0
        original_len = len(content)
        message['content'] = [
            item for item in content
            if not (isinstance(item, dict) and item.get('type') == 'thinking')
        ]
        removed = original_len - len(message['content'])
        return updated, removed


# ─── OpenCode 策略 ───────────────────────────────────────────────────────────

class OpenCodeFormatStrategy(FormatStrategy):
    """OpenCode 格式：从 SQLite 转换后的 dict，结构与 Claude Code 类似。

    消息格式（由 sqlite_adapter 转换）:
    {
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "text", "text": "..."},
            {"type": "thinking", "text": "..."},  # reasoning 映射为 thinking
        ]},
        "_oc_msg_id": "msg_xxx",
        "_oc_parts": [...]
    }
    """

    def get_assistant_messages(self, lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        messages = []
        for idx, line in enumerate(lines):
            if line.get('type') == 'assistant':
                msg = line.get('message', {})
                if msg.get('role') == 'assistant':
                    messages.append((idx, line))
        return messages

    def get_thinking_items(self, lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
        # OpenCode 的 thinking 嵌入在 message.content[] 中（与 Claude Code 相同）
        return []

    def extract_text_content(self, msg: Dict[str, Any]) -> str:
        message = msg.get('message', {})
        content = message.get('content', [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    texts.append(item.get('text', ''))
            return '\n'.join(texts)
        return ''

    def update_text_content(self, msg: Dict[str, Any], new_text: str) -> Dict[str, Any]:
        updated = copy.deepcopy(msg)
        message = updated.get('message', {})
        content = message.get('content', [])
        if isinstance(content, list):
            replaced = False
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    item['text'] = new_text
                    replaced = True
                    break
            if not replaced:
                content.append({'type': 'text', 'text': new_text})
        else:
            message['content'] = [{'type': 'text', 'text': new_text}]
        return updated

    def remove_thinking_from_message(self, msg: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        updated = copy.deepcopy(msg)
        message = updated.get('message', {})
        content = message.get('content', [])
        if not isinstance(content, list):
            return updated, 0
        original_len = len(content)
        message['content'] = [
            item for item in content
            if not (isinstance(item, dict) and item.get('type') == 'thinking')
        ]
        removed = original_len - len(message['content'])
        return updated, removed


# ─── 工厂 & 工具函数 ──────────────────────────────────────────────────────────

def get_format_strategy(fmt: SessionFormat) -> FormatStrategy:
    if fmt == SessionFormat.CODEX:
        return CodexFormatStrategy()
    elif fmt == SessionFormat.CLAUDE_CODE:
        return ClaudeCodeFormatStrategy()
    elif fmt == SessionFormat.OPENCODE:
        return OpenCodeFormatStrategy()
    raise ValueError(f"未知的会话格式: {fmt}")


def detect_session_format(file_path: str) -> SessionFormat:
    """通过读取 JSONL 文件的前 20 行来判断格式"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, raw_line in enumerate(f):
                if i >= 20:
                    break
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                line_type = data.get('type', '')
                if line_type == 'response_item':
                    return SessionFormat.CODEX
                if line_type in ('assistant', 'user', 'system', 'file-history-snapshot', 'last-prompt'):
                    return SessionFormat.CLAUDE_CODE
    except Exception:
        logger.warning("检测会话格式失败: %s", file_path, exc_info=True)
    # 回退：根据目录路径推测
    return _detect_format_from_path(file_path)


def _detect_format_from_path(file_path: str) -> SessionFormat:
    """根据文件所在目录推测格式"""
    expanded = os.path.expanduser(file_path)
    codex_dir = os.path.expanduser("~/.codex/")
    claude_dir = os.path.expanduser("~/.claude/")
    opencode_dir = os.path.expanduser("~/.local/share/opencode/")
    if expanded.startswith(codex_dir):
        return SessionFormat.CODEX
    if expanded.startswith(claude_dir):
        return SessionFormat.CLAUDE_CODE
    if expanded.startswith(opencode_dir) or expanded.endswith('.db'):
        return SessionFormat.OPENCODE
    return SessionFormat.CODEX  # 默认回退


def decode_claude_project_path(encoded: str) -> str:
    """将 Claude Code 的编码目录名转回文件系统路径。
    例："-Users-foo-bar" → "/Users/foo/bar"
    """
    if not encoded or not encoded.startswith('-'):
        return encoded
    # 去掉首个 '-'，然后将 '-' 替换为 '/'
    return '/' + encoded[1:].replace('-', '/')


def encode_claude_project_path(path: str) -> str:
    """将文件系统路径编码为 Claude Code 的项目目录名。
    例："/Users/foo/bar" → "-Users-foo-bar"
    """
    if not path:
        return ""

    normalized = os.path.realpath(os.path.expanduser(path)).rstrip("/\\")
    if not normalized:
        return ""

    return normalized.replace("\\", "-").replace("/", "-")
