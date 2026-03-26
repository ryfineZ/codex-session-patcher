# -*- coding: utf-8 -*-
"""
会话解析器
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

from .detector import RefusalDetector


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


class SessionParser:
    """会话文件解析器 - 支持 JSONL 格式"""

    def __init__(self, session_dir: str = "~/.codex/sessions/"):
        self.session_dir = os.path.expanduser(session_dir)

    def list_sessions(self) -> List[SessionInfo]:
        """
        列出所有会话文件

        Returns:
            会话信息列表，按修改时间降序排序
        """
        if not os.path.exists(self.session_dir):
            return []

        sessions = []
        # 递归搜索所有 .jsonl 文件
        for root, dirs, files in os.walk(self.session_dir):
            for f in files:
                if f.endswith(".jsonl"):
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.stat(full_path)
                        mtime = stat.st_mtime
                        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                        # 从文件名提取日期和 ID
                        # 格式: rollout-2026-03-25T16-05-56-{uuid}.jsonl
                        match = re.match(r'rollout-(\d{4}-\d{2}-\d{2})T[\d-]+-([a-f0-9-]+)\.jsonl', f)
                        if match:
                            date = match.group(1)
                            session_id = match.group(2)[:8]  # 取前8位
                        else:
                            date = mtime_str[:10]
                            session_id = f[:8]

                        sessions.append(SessionInfo(
                            path=full_path,
                            filename=f,
                            mtime=mtime,
                            mtime_str=mtime_str,
                            date=date,
                            session_id=session_id,
                            size=stat.st_size
                        ))
                    except Exception:
                        continue

        # 按修改时间降序排序
        sessions.sort(key=lambda x: x.mtime, reverse=True)
        return sessions

    def parse_session_jsonl(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析 JSONL 格式的会话文件

        Args:
            file_path: 会话文件路径

        Returns:
            解析后的行列表
        """
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

    def read_last_n_bytes(self, file_path: str, n: int = 50000) -> List[Dict[str, Any]]:
        """
        读取文件最后 N 字节并解析

        Args:
            file_path: 文件路径
            n: 字节数

        Returns:
            解析后的行列表
        """
        try:
            with open(file_path, 'rb') as f:
                f.seek(0, 2)  # 移到文件末尾
                file_size = f.tell()
                start = max(0, file_size - n)
                f.seek(start)
                content = f.read().decode('utf-8', errors='ignore')

            # 解析每一行
            lines = []
            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    data['_line_num'] = line_num
                    lines.append(data)
                except json.JSONDecodeError:
                    continue
            return lines
        except Exception as e:
            raise ValueError(f"读取文件失败: {file_path}\n{e}")


def get_assistant_messages(lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    """
    从 JSONL 行中提取助手消息

    Args:
        lines: JSONL 行列表

    Returns:
        [(行索引, 消息数据), ...]
    """
    messages = []
    for idx, line in enumerate(lines):
        if line.get('type') == 'response_item':
            payload = line.get('payload', {})
            if payload.get('type') == 'message' and payload.get('role') == 'assistant':
                messages.append((idx, line))
    return messages


def get_reasoning_items(lines: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    """
    从 JSONL 行中提取推理内容

    Args:
        lines: JSONL 行列表

    Returns:
        [(行索引, 推理数据), ...]
    """
    items = []
    for idx, line in enumerate(lines):
        if line.get('type') == 'response_item':
            payload = line.get('payload', {})
            if payload.get('type') == 'reasoning':
                items.append((idx, line))
    return items


def extract_text_content(message_line: Dict[str, Any]) -> str:
    """
    从消息行中提取文本内容

    Args:
        message_line: JSONL 消息行

    Returns:
        文本内容
    """
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
    """
    更新消息行的文本内容

    Args:
        message_line: JSONL 消息行
        new_text: 新的文本内容

    Returns:
        更新后的消息行
    """
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
