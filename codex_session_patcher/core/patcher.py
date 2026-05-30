# -*- coding: utf-8 -*-
"""
会话清理逻辑 — 支持 Codex CLI 和 Claude Code 两种格式
"""

import json
import copy
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

from .constants import MOCK_RESPONSE
from .detector import RefusalDetector
from .formats import SessionFormat, get_format_strategy


@dataclass
class ChangeDetail:
    """修改详情"""
    line_num: int
    change_type: str  # 'replace', 'delete', 'remove_thinking'
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    line_nums: Optional[List[int]] = None  # 所有关联行号（含冗余副本）


def clean_session_jsonl(
    lines: List[Dict[str, Any]],
    detector: RefusalDetector,
    show_content: bool = False,
    mock_response: Optional[str] = None,
    session_format: SessionFormat = SessionFormat.CODEX,
    selected_lines: Optional[List[int]] = None,
    clean_reasoning: bool = True,
) -> Tuple[List[Dict[str, Any]], bool, List[ChangeDetail]]:
    """
    清洗 JSONL 会话数据

    Args:
        lines: JSONL 行列表
        detector: 拒绝检测器
        show_content: 是否返回详细内容
        mock_response: 替换文本
        session_format: 会话格式
        selected_lines: 只清理选中的行号列表（None 表示全部清理）
        clean_reasoning: 是否清理推理内容（thinking/reasoning blocks）

    Returns:
        (清洗后的行列表, 是否进行了修改, 修改详情列表)
    """
    modified = False
    changes = []

    if mock_response is None:
        mock_response = MOCK_RESPONSE

    # selected_lines 转为集合方便快速查找
    selected_set = set(selected_lines) if selected_lines else None

    strategy = get_format_strategy(session_format)

    # 1. 替换拒绝的助手消息
    assistant_msgs = strategy.get_assistant_messages(lines)
    # 先分组：primary（response_item）-> companion idxs（event_msg 冗余副本）
    refusal_groups: List[Tuple[int, List[int]]] = []  # [(primary_idx, [companion_idxs])]
    companion_set: set = set()
    primary_map: dict = {}
    for msg_idx, msg in assistant_msgs:
        content = strategy.extract_text_content(msg)
        if not content or not detector.detect(content):
            continue
        if msg.get('type') == 'event_msg':
            if refusal_groups:
                refusal_groups[-1][1].append(msg_idx)
            else:
                # 历史 Codex 会话可能只有 event_msg/agent_message，
                # 没有对应 response_item；不要让这类拦截只能被检测、不能被清理。
                refusal_groups.append((msg_idx, []))
            companion_set.add(msg_idx)
        else:
            refusal_groups.append((msg_idx, []))

    for primary_idx, companion_idxs in refusal_groups:
        # 如果指定了选中行，检查是否在选中列表中
        primary_line_num = primary_idx + 1
        if selected_set is not None and primary_line_num not in selected_set:
            continue  # 跳过未选中的记录

        primary_msg = lines[primary_idx]
        content = strategy.extract_text_content(primary_msg)
        all_line_nums = sorted([primary_idx + 1] + [i + 1 for i in companion_idxs])

        change = ChangeDetail(
            line_num=primary_idx + 1,
            change_type='replace',
            line_nums=all_line_nums,
        )
        if show_content:
            change.original_content = content[:500] + ('...' if len(content) > 500 else '')
            change.new_content = mock_response
        changes.append(change)

        # 替换 primary 行
        lines[primary_idx] = strategy.update_text_content(primary_msg, mock_response)
        # 替换所有 companion 行
        for cidx in companion_idxs:
            lines[cidx] = strategy.update_text_content(lines[cidx], mock_response)
        modified = True

    # 2. 删除独立的 thinking/reasoning 行（Codex 格式）- 可选
    if clean_reasoning:
        thinking_items = strategy.get_thinking_items(lines)
        if thinking_items:
            for idx, item in thinking_items:
                change = ChangeDetail(
                    line_num=idx + 1,
                    change_type='delete'
                )
                if show_content:
                    payload = lines[idx].get('payload', {})
                    summary = payload.get('summary', [])
                    if isinstance(summary, list):
                        texts = [s.get('text', '') for s in summary if isinstance(s, dict)]
                        content_preview = ' '.join(texts)[:100]
                    else:
                        content_preview = str(summary)[:100]
                    if not content_preview:
                        content_preview = '推理内容'
                    change.original_content = content_preview + ('...' if len(content_preview) >= 100 else '')
                changes.append(change)
                lines[idx] = None
                modified = True

    # 3. 移除嵌入在消息 content[] 中的 thinking 块（Claude Code 格式）- 可选
    if clean_reasoning:
        for idx, line in enumerate(lines):
            if line is None:
                continue
            updated, removed_count = strategy.remove_thinking_from_message(line)
            if removed_count > 0:
                change = ChangeDetail(
                    line_num=idx + 1,
                    change_type='remove_thinking'
                )
                if show_content:
                    change.original_content = f'移除 {removed_count} 个 thinking block'
                changes.append(change)
                lines[idx] = updated
                modified = True

    # 4. 过滤掉标记为 None 的行
    lines = [line for line in lines if line is not None]

    return lines, modified, changes


def save_session_jsonl(lines: List[Dict[str, Any]], file_path: str) -> None:
    """保存 JSONL 会话数据"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                line_copy = {k: v for k, v in line.items() if not k.startswith('_')}
                f.write(json.dumps(line_copy, ensure_ascii=False) + '\n')
    except PermissionError as e:
        raise ValueError(f"写入文件失败，权限不足: {file_path}\n{e}")
    except Exception as e:
        raise ValueError(f"写入文件失败: {file_path}\n{e}")
