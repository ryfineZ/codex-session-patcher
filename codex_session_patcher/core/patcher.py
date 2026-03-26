# -*- coding: utf-8 -*-
"""
会话清理逻辑
"""

import json
import copy
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

from .constants import MOCK_RESPONSE
from .detector import RefusalDetector
from .parser import get_assistant_messages, get_reasoning_items, extract_text_content, update_text_content


@dataclass
class ChangeDetail:
    """修改详情"""
    line_num: int
    change_type: str  # 'replace' 或 'delete'
    original_content: Optional[str] = None
    new_content: Optional[str] = None


def clean_session_jsonl(
    lines: List[Dict[str, Any]],
    detector: RefusalDetector,
    show_content: bool = False,
    mock_response: str = None,
) -> Tuple[List[Dict[str, Any]], bool, List[ChangeDetail]]:
    """
    清洗 JSONL 会话数据

    Args:
        lines: JSONL 行列表
        detector: 拒绝检测器
        show_content: 是否返回详细内容

    Returns:
        (清洗后的行列表, 是否进行了修改, 修改详情列表)
    """
    modified = False
    changes = []

    # 获取所有助手消息
    assistant_msgs = get_assistant_messages(lines)

    if not assistant_msgs:
        return lines, False, []

    if mock_response is None:
        mock_response = MOCK_RESPONSE

    # 处理所有拒绝的助手消息
    for msg_idx, msg in assistant_msgs:
        content = extract_text_content(msg)
        if detector.detect(content):
            change = ChangeDetail(
                line_num=msg_idx + 1,
                change_type='replace'
            )
            if show_content:
                change.original_content = content[:500] + ('...' if len(content) > 500 else '')
                change.new_content = mock_response
            changes.append(change)

            updated_msg = update_text_content(msg, mock_response)
            lines[msg_idx] = updated_msg
            modified = True

    # 删除推理内容
    reasoning_items = get_reasoning_items(lines)
    if reasoning_items:
        for idx, _ in reasoning_items:
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
            lines[idx] = None  # 标记删除
            modified = True

    # 过滤掉 None 的行
    lines = [line for line in lines if line is not None]

    return lines, modified, changes


def save_session_jsonl(lines: List[Dict[str, Any]], file_path: str) -> None:
    """
    保存 JSONL 会话数据

    Args:
        lines: JSONL 行列表
        file_path: 目标文件路径
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                line_copy = {k: v for k, v in line.items() if not k.startswith('_')}
                f.write(json.dumps(line_copy, ensure_ascii=False) + '\n')
    except PermissionError as e:
        raise ValueError(f"写入文件失败，权限不足: {file_path}\n{e}")
    except Exception as e:
        raise ValueError(f"写入文件失败: {file_path}\n{e}")
