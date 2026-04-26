"""
API 路由 — 支持 Codex CLI 和 Claude Code 双格式
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
import re
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

import time as _time

from .schemas import (
    Session, SessionListResponse, SessionFormatEnum, PreviewResponse,
    PatchResponse, Settings, ChangeDetail, ChangeType, WSMessage,
    AIRewriteResponse, PatchRequest, BackupInfo, RestoreResponse, DiffItem,
    CTFStatusResponse, CTFInstallResponse, PromptRewriteRequest, PromptRewriteResponse,
    ConversationTurn,
)

from codex_session_patcher.core import (
    RefusalDetector,
    SessionParser,
    SessionFormat,
    get_format_strategy,
    detect_session_format,
    extract_text_content,
    get_assistant_messages,
    get_reasoning_items,
    MOCK_RESPONSE,
)
from codex_session_patcher.core.patcher import clean_session_jsonl, save_session_jsonl
from codex_session_patcher.core.sqlite_adapter import OpenCodeDBAdapter, DEFAULT_OPENCODE_DB

logger = logging.getLogger(__name__)

router = APIRouter()

# 默认路径
DEFAULT_SESSION_DIR = os.path.expanduser("~/.codex/sessions/")
DEFAULT_CLAUDE_SESSION_DIR = os.path.expanduser("~/.claude/projects/")
DEFAULT_MEMORY_FILE = os.path.expanduser("~/.codex/memories/MEMORY.md")
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.codex-patcher/config.json")


# ─── WebSocket 连接管理 ──────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: WSMessage):
        for connection in self.active_connections:
            await connection.send_json(message.model_dump())


manager = ConnectionManager()


# ─── 全局检测器 ──────────────────────────────────────────────────────────────

_detector = RefusalDetector()


# ─── 会话缓存 ────────────────────────────────────────────────────────────────

_session_cache: dict = {
    'sessions': None,       # Optional[list[Session]]
    'timestamp': 0.0,       # 缓存时间
    'ttl': 30,              # 30 秒 TTL
}


def _invalidate_session_cache():
    """清除会话缓存"""
    _session_cache['sessions'] = None
    _session_cache['timestamp'] = 0.0


def _get_cached_sessions(
    session_format: Optional[SessionFormat] = None,
    skip_refusal_check: bool = False,
) -> list:
    """带缓存的会话列表获取"""
    now = _time.time()
    cached = _session_cache['sessions']
    # 缓存命中：非跳过检测请求 + 缓存存在 + 未过期
    if cached is not None and not skip_refusal_check and (now - _session_cache['timestamp']) < _session_cache['ttl']:
        if session_format is None:
            return cached
        fmt_str = _to_schema_format(session_format)
        return [s for s in cached if s.format == fmt_str]

    # 缓存未命中，执行扫描
    sessions = list_sessions(session_format=session_format, skip_refusal_check=skip_refusal_check)

    # 只缓存全量扫描（含拒绝检测）的结果
    if session_format is None and not skip_refusal_check:
        _session_cache['sessions'] = sessions
        _session_cache['timestamp'] = now

    return sessions


# ─── 格式解析工具 ────────────────────────────────────────────────────────────

def _resolve_format(format_str: str) -> Optional[SessionFormat]:
    """将 API 参数字符串转为 SessionFormat，'auto' 返回 None"""
    if format_str == 'codex':
        return SessionFormat.CODEX
    elif format_str == 'claude_code':
        return SessionFormat.CLAUDE_CODE
    elif format_str == 'opencode':
        return SessionFormat.OPENCODE
    return None  # auto


def _to_schema_format(fmt: SessionFormat) -> SessionFormatEnum:
    """将核心 SessionFormat 转为 API schema enum"""
    if fmt == SessionFormat.CLAUDE_CODE:
        return SessionFormatEnum.CLAUDE_CODE
    elif fmt == SessionFormat.OPENCODE:
        return SessionFormatEnum.OPENCODE
    return SessionFormatEnum.CODEX


# ─── 会话扫描 ────────────────────────────────────────────────────────────────

def check_session_refusal(file_path: str, fmt: SessionFormat = SessionFormat.CODEX) -> tuple[bool, int]:
    """检查会话是否包含拒绝内容"""
    count = 0
    strategy = get_format_strategy(fmt)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = []
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    lines.append(json.loads(raw_line))
                except json.JSONDecodeError:
                    continue

        for _, msg in strategy.get_assistant_messages(lines):
            content = strategy.extract_text_content(msg)
            if content and _detector.detect(content):
                count += 1
    except Exception:
        logger.warning("检查会话拒绝状态失败", exc_info=True)
    return count > 0, count


def count_thinking_blocks(file_path: str, fmt: SessionFormat) -> int:
    """统计 Claude Code 会话中 thinking block 的数量"""
    if fmt != SessionFormat.CLAUDE_CODE:
        return 0
    count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if data.get('type') != 'assistant':
                    continue
                content = data.get('message', {}).get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'thinking':
                            count += 1
    except Exception:
        logger.warning("统计 thinking 块失败", exc_info=True)
    return count


def list_sessions(
    session_format: Optional[SessionFormat] = None,
    skip_refusal_check: bool = False,
) -> list[Session]:
    """列出所有会话

    Args:
        session_format: 指定格式，None 表示 auto（扫描两个目录）
        skip_refusal_check: 是否跳过拒绝检测
    """
    sessions = []

    # 确定需要扫描的目录
    scan_targets = []
    scan_opencode = False

    if session_format is None:
        # auto 模式：扫描所有目录
        if os.path.exists(DEFAULT_SESSION_DIR):
            scan_targets.append((DEFAULT_SESSION_DIR, SessionFormat.CODEX))
        if os.path.exists(DEFAULT_CLAUDE_SESSION_DIR):
            scan_targets.append((DEFAULT_CLAUDE_SESSION_DIR, SessionFormat.CLAUDE_CODE))
        if os.path.exists(DEFAULT_OPENCODE_DB):
            scan_opencode = True
    elif session_format == SessionFormat.CODEX:
        scan_targets.append((DEFAULT_SESSION_DIR, SessionFormat.CODEX))
    elif session_format == SessionFormat.CLAUDE_CODE:
        scan_targets.append((DEFAULT_CLAUDE_SESSION_DIR, SessionFormat.CLAUDE_CODE))
    elif session_format == SessionFormat.OPENCODE:
        scan_opencode = True

    # 扫描 JSONL 格式会话（Codex / Claude Code）
    for session_dir, fmt in scan_targets:
        parser = SessionParser(session_dir, session_format=fmt)
        for info in parser.list_sessions():
            try:
                if skip_refusal_check:
                    has_refusal = False
                    refusal_count = 0
                else:
                    has_refusal, refusal_count = check_session_refusal(info.path, info.format)

                # 检查备份文件
                backup_count = 0
                dir_path = os.path.dirname(info.path)
                for bak_file in os.listdir(dir_path):
                    if bak_file.startswith(info.filename + ".") and bak_file.endswith(".bak"):
                        backup_count += 1

                sessions.append(Session(
                    id=info.session_id,
                    filename=info.filename,
                    path=info.path,
                    date=info.date,
                    mtime=info.mtime_str,
                    size=info.size,
                    has_refusal=has_refusal,
                    refusal_count=refusal_count,
                    has_backup=backup_count > 0,
                    backup_count=backup_count,
                    format=_to_schema_format(info.format),
                    project_path=info.project_path,
                ))
            except Exception:
                logger.warning("处理会话 %s 失败", info.path, exc_info=True)
                continue

    # 扫描 OpenCode SQLite 会话
    if scan_opencode:
        try:
            adapter = OpenCodeDBAdapter()
            oc_sessions = adapter.list_sessions()
            strategy = get_format_strategy(SessionFormat.OPENCODE)
            detector = RefusalDetector()
            backup_count = len(adapter.list_backups())

            for oc_info in oc_sessions:
                try:
                    has_refusal = False
                    refusal_count = 0
                    if not skip_refusal_check:
                        messages = adapter.load_session_messages(oc_info['session_id'])
                        for _, msg in strategy.get_assistant_messages(messages):
                            content = strategy.extract_text_content(msg)
                            if content and detector.detect(content):
                                refusal_count += 1
                        has_refusal = refusal_count > 0

                    sessions.append(Session(
                        id=oc_info['session_id'],
                        filename=oc_info['session_id'],
                        path=DEFAULT_OPENCODE_DB,
                        date=oc_info['date'],
                        mtime=oc_info['mtime_str'],
                        size=0,
                        has_refusal=has_refusal,
                        refusal_count=refusal_count,
                        has_backup=backup_count > 0,
                        backup_count=backup_count,
                        format=SessionFormatEnum.OPENCODE,
                        project_path=oc_info.get('project_path', ''),
                    ))
                except Exception:
                    logger.warning("处理 OpenCode 会话 %s 失败", oc_info.get('session_id', ''), exc_info=True)
                    continue
        except Exception:
            logger.warning("扫描 OpenCode 数据库失败", exc_info=True)

    sessions.sort(key=lambda x: x.mtime, reverse=True)
    return sessions


def _session_core_format(session: Session) -> SessionFormat:
    """从 API Session schema 转为核心 SessionFormat"""
    if session.format == SessionFormatEnum.CLAUDE_CODE:
        return SessionFormat.CLAUDE_CODE
    elif session.format == SessionFormatEnum.OPENCODE:
        return SessionFormat.OPENCODE
    return SessionFormat.CODEX


# ─── 预览 & 清理 ─────────────────────────────────────────────────────────────

def preview_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                   custom_keywords: dict = None,
                   session_format: SessionFormat = SessionFormat.CODEX,
                   session_id: str = None) -> PreviewResponse:
    """预览会话修改"""
    changes = []
    detector = RefusalDetector(custom_keywords)
    strategy = get_format_strategy(session_format)

    # OpenCode: 从 SQLite 加载
    if session_format == SessionFormat.OPENCODE and session_id:
        try:
            adapter = OpenCodeDBAdapter(file_path)
            parsed_lines = adapter.load_session_messages(session_id)
        except Exception:
            logger.warning("加载 OpenCode 会话失败: %s", session_id, exc_info=True)
            return PreviewResponse(has_changes=False, changes=[])
    else:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return PreviewResponse(has_changes=False, changes=[])

        parsed_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                parsed_lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # 检测拒绝 & 收集对话摘要
    assistant_msgs = strategy.get_assistant_messages(parsed_lines)
    refusal_lines = set()
    # 先收集所有拒绝行（含 event_msg 冗余副本），按内容分组
    refusal_groups: dict[int, list[int]] = {}  # primary_idx -> [companion_idxs]
    primary_order: list[int] = []
    for idx, msg in assistant_msgs:
        content = strategy.extract_text_content(msg)
        if not content or not detector.detect(content):
            continue
        refusal_lines.add(idx)
        if msg.get('type') == 'event_msg':
            # 冗余副本：挂到最近的 primary 下
            if primary_order:
                refusal_groups[primary_order[-1]].append(idx)
        else:
            refusal_groups[idx] = []
            primary_order.append(idx)

    for primary_idx in primary_order:
        companion_idxs = refusal_groups[primary_idx]
        all_line_nums = sorted([primary_idx + 1] + [i + 1 for i in companion_idxs])
        msg = parsed_lines[primary_idx]
        content = strategy.extract_text_content(msg)
        changes.append(ChangeDetail(
            line_num=primary_idx + 1,
            line_nums=all_line_nums,
            type=ChangeType.REPLACE,
            original=content[:500] + ('...' if len(content) > 500 else ''),
            replacement=mock_response
        ))

    # 收集对话摘要（user + assistant 消息）
    conversation_summary = []
    for idx, line in enumerate(parsed_lines):
        role = None
        content = ''
        line_type = line.get('type', '')

        # Claude Code / OpenCode 格式
        if line_type == 'human':
            role = 'user'
            msg = line.get('message', {})
            msg_content = msg.get('content', '')
            if isinstance(msg_content, str):
                content = msg_content
            elif isinstance(msg_content, list):
                texts = [item.get('text', '') for item in msg_content if isinstance(item, dict) and item.get('type') == 'text']
                content = '\n'.join(texts)
        elif line_type == 'user':
            # OpenCode user 消息
            role = 'user'
            msg = line.get('message', {})
            msg_content = msg.get('content', [])
            if isinstance(msg_content, str):
                content = msg_content
            elif isinstance(msg_content, list):
                texts = [item.get('text', '') for item in msg_content if isinstance(item, dict) and item.get('type') == 'text']
                content = '\n'.join(texts)
        elif line_type == 'assistant':
            role = 'assistant'
            content = strategy.extract_text_content(line)

        # Codex 格式
        elif line_type == 'response_item':
            payload = line.get('payload', {})
            msg_role = payload.get('role', '')
            if msg_role == 'assistant':
                role = 'assistant'
                content = strategy.extract_text_content(line)
        elif line_type == 'user_message':
            role = 'user'
            content = line.get('content', '')
            if isinstance(content, list):
                texts = [item.get('text', '') for item in content if isinstance(item, dict)]
                content = '\n'.join(texts)

        if role and content:
            truncated = content[:200] + ('...' if len(content) > 200 else '')
            conversation_summary.append(ConversationTurn(
                role=role,
                content=truncated,
                line_num=idx + 1,
                has_refusal=idx in refusal_lines,
            ))

    # 统计推理内容（Codex 格式独立行）
    thinking_items = strategy.get_thinking_items(parsed_lines)
    reasoning_count = len(thinking_items)

    # 统计 thinking blocks（Claude Code 格式嵌入在 content 中）
    thinking_count = 0
    for msg_line in parsed_lines:
        _, removed = strategy.remove_thinking_from_message(msg_line)
        thinking_count += removed

    has_changes = len(changes) > 0 or reasoning_count > 0 or thinking_count > 0

    return PreviewResponse(
        has_changes=has_changes,
        changes=changes,
        reasoning_count=reasoning_count,
        thinking_count=thinking_count,
        conversation_summary=conversation_summary,
        total_turns=len(conversation_summary),
    )


def patch_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                 custom_keywords: dict = None, create_backup: bool = True,
                 replacements: dict = None,
                 session_format: SessionFormat = SessionFormat.CODEX,
                 session_id: str = None,
                 selected_lines: list = None,
                 clean_reasoning: bool = True) -> PatchResponse:
    """执行会话清理

    Args:
        selected_lines: 只清理选中的行号列表，None 表示全部清理
        clean_reasoning: 是否清理推理内容（thinking/reasoning blocks）
    """
    if replacements is None:
        replacements = {}

    detector = RefusalDetector(custom_keywords)

    try:
        backup_path = None

        # OpenCode: SQLite 处理
        if session_format == SessionFormat.OPENCODE and session_id:
            adapter = OpenCodeDBAdapter(file_path)
            if create_backup:
                backup_path = adapter.backup_database()

            lines = adapter.load_session_messages(session_id)

            cleaned_lines, modified, core_changes = clean_session_jsonl(
                lines, detector, show_content=True,
                mock_response=mock_response,
                session_format=session_format,
                selected_lines=selected_lines,
                clean_reasoning=clean_reasoning,
            )

            if replacements:
                strategy = get_format_strategy(session_format)
                for idx, line in enumerate(cleaned_lines):
                    line_num = idx + 1
                    if line_num in replacements:
                        cleaned_lines[idx] = strategy.update_text_content(line, replacements[line_num])

            # 写回 SQLite
            adapter.save_session_messages(session_id, cleaned_lines)
        else:
            # JSONL 处理（Codex / Claude Code）
            if create_backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{file_path}.{timestamp}.bak"
                shutil.copy2(file_path, backup_path)

            parser = SessionParser(session_format=session_format)
            lines = parser.parse_session_jsonl(file_path)

            cleaned_lines, modified, core_changes = clean_session_jsonl(
                lines, detector, show_content=True,
                mock_response=mock_response,
                session_format=session_format,
                selected_lines=selected_lines,
                clean_reasoning=clean_reasoning,
            )

            if replacements:
                strategy = get_format_strategy(session_format)
                for idx, line in enumerate(cleaned_lines):
                    line_num = line.get('_line_num', idx + 1)
                    if line_num in replacements:
                        cleaned_lines[idx] = strategy.update_text_content(line, replacements[line_num])

            save_session_jsonl(cleaned_lines, file_path)

        # 转换为 API ChangeDetail
        api_changes = []
        for c in core_changes:
            ct = ChangeType.REPLACE
            if c.change_type == 'delete':
                ct = ChangeType.DELETE
            elif c.change_type == 'remove_thinking':
                ct = ChangeType.REMOVE_THINKING
            api_changes.append(ChangeDetail(
                line_num=c.line_num,
                type=ct,
                original=c.original_content,
                replacement=c.new_content,
            ))

        return PatchResponse(
            success=True,
            message="会话清理完成",
            backup_path=backup_path,
            changes=api_changes,
        )

    except Exception as e:
        return PatchResponse(
            success=False,
            message=f"清理失败: {str(e)}"
        )


# ─── 设置 ────────────────────────────────────────────────────────────────────

def load_settings() -> Settings:
    """加载设置"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Settings.model_validate(data)
        except Exception:
            logger.warning("加载配置文件失败: %s", DEFAULT_CONFIG_FILE, exc_info=True)
    return Settings()


def save_settings(settings: Settings) -> bool:
    """保存设置（保留非 Settings 字段如 ctf_prompts）"""
    try:
        config_dir = os.path.dirname(DEFAULT_CONFIG_FILE)
        os.makedirs(config_dir, exist_ok=True)
        os.chmod(config_dir, 0o700)
        # 读取现有配置以保留额外字段
        existing = _load_raw_config()
        existing.update(settings.model_dump())
        with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        os.chmod(DEFAULT_CONFIG_FILE, 0o600)
        return True
    except Exception:
        logger.warning("保存配置文件失败", exc_info=True)
        return False


# ─── Diff 计算 ───────────────────────────────────────────────────────────────

def compute_backup_diff(current_path: str, backup_path: str,
                       session_format: SessionFormat = SessionFormat.CODEX) -> list[DiffItem]:
    """对比当前文件和备份文件，找出助手消息的差异"""
    diff_items = []
    strategy = get_format_strategy(session_format)
    try:
        def parse_file(path):
            parsed = []
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            parsed.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return parsed

        current_parsed = parse_file(current_path)
        backup_parsed = parse_file(backup_path)

        backup_assistant = strategy.get_assistant_messages(backup_parsed)
        current_assistant = strategy.get_assistant_messages(current_parsed)

        for i in range(min(len(backup_assistant), len(current_assistant))):
            _, bak_msg = backup_assistant[i]
            cur_idx, cur_msg = current_assistant[i]
            backup_text = strategy.extract_text_content(bak_msg)
            current_text = strategy.extract_text_content(cur_msg)
            if backup_text != current_text:
                diff_items.append(DiffItem(
                    line_num=cur_idx + 1,
                    before=backup_text[:1000] + ('...' if len(backup_text) > 1000 else ''),
                    after=current_text[:1000] + ('...' if len(current_text) > 1000 else ''),
                ))

        # 检查被删除的推理/thinking 内容
        backup_thinking = strategy.get_thinking_items(backup_parsed)
        current_thinking = strategy.get_thinking_items(current_parsed)
        removed_count = len(backup_thinking) - len(current_thinking)
        if removed_count > 0:
            diff_items.append(DiffItem(
                line_num=0,
                before=f'包含 {len(backup_thinking)} 条推理内容',
                after=f'已删除 {removed_count} 条推理内容',
            ))

    except Exception:
        logger.warning("计算备份差异失败", exc_info=True)
    return diff_items


# ─── API 路由 ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(skip_check: bool = False, limit: int = 0, format: str = "auto"):
    """获取会话列表"""
    session_format = _resolve_format(format)
    loop = asyncio.get_event_loop()
    sessions = await loop.run_in_executor(
        None, _get_cached_sessions, session_format, skip_check
    )
    limited_sessions = sessions[:limit] if limit > 0 else sessions
    return SessionListResponse(
        sessions=limited_sessions,
        total=len(sessions),
        format=format,
    )


# ─── 搜索缓存 ────────────────────────────────────────────────────────────────

_search_cache: dict = {
    'query': None,
    'format': None,
    'sessions': None,
    'timestamp': 0.0,
    'ttl': 10,  # 10 秒 TTL（搜索结果缓存较短）
}


@router.get("/sessions/search", response_model=SessionListResponse)
async def search_sessions(query: str, format: str = "auto"):
    """根据关键词搜索会话内容"""
    if not query or not query.strip():
        return SessionListResponse(sessions=[], total=0, format=format)

    query = query.strip().lower()
    session_format = _resolve_format(format)

    # 检查搜索缓存
    now = _time.time()
    if (_search_cache['query'] == query and
        _search_cache['format'] == format and
        _search_cache['sessions'] is not None and
        (now - _search_cache['timestamp']) < _search_cache['ttl']):
        # 缓存命中
        cached_sessions = _search_cache['sessions']
        if session_format is None:
            return SessionListResponse(sessions=cached_sessions, total=len(cached_sessions), format=format)
        fmt_str = _to_schema_format(session_format)
        filtered = [s for s in cached_sessions if s.format == fmt_str]
        return SessionListResponse(sessions=filtered, total=len(filtered), format=format)

    # 使用缓存获取会话列表（避免重新扫描）
    loop = asyncio.get_event_loop()
    all_sessions = await loop.run_in_executor(
        None, _get_cached_sessions, session_format, True
    )
    matched_sessions = []

    for session in all_sessions:
        try:
            core_fmt = _session_core_format(session)
            if core_fmt == SessionFormat.OPENCODE:
                # OpenCode: 从 SQLite 加载
                adapter = OpenCodeDBAdapter(session.path)
                messages = adapter.load_session_messages(session.id)
                content_lines = []
                strategy = get_format_strategy(core_fmt)
                for msg in messages:
                    text = strategy.extract_text_content(msg)
                    if text:
                        content_lines.append(text)
                content = '\n'.join(content_lines)
            else:
                # JSONL 格式
                with open(session.path, 'r', encoding='utf-8') as f:
                    content = f.read()

            if query in content.lower():
                # 需要重新检测拒绝状态
                if not session.has_refusal:
                    has_refusal, refusal_count = check_session_refusal(session.path, core_fmt)
                    session = session.model_copy(update={
                        'has_refusal': has_refusal,
                        'refusal_count': refusal_count
                    })
                matched_sessions.append(session)
        except Exception:
            logger.warning("搜索会话 %s 失败", session.id, exc_info=True)
            continue

    # 更新搜索缓存
    _search_cache['query'] = query
    _search_cache['format'] = format
    _search_cache['sessions'] = matched_sessions
    _search_cache['timestamp'] = now

    return SessionListResponse(
        sessions=matched_sessions,
        total=len(matched_sessions),
        format=format,
    )


async def _find_session(session_id: str, session_format: Optional[SessionFormat] = None) -> Optional[Session]:
    """查找会话（优先从缓存获取）"""
    loop = asyncio.get_event_loop()
    sessions = await loop.run_in_executor(
        None, _get_cached_sessions, session_format, True
    )
    for session in sessions:
        if session.id == session_id:
            return session
    return None


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, check_refusal: bool = True, format: str = "auto"):
    """获取单个会话详情"""
    # 优先从缓存查找，避免全量扫描
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 如果需要拒绝检测且缓存中未检测过，单独检测这一个文件
    if check_refusal and not session.has_refusal:
        core_fmt = _session_core_format(session)
        has_refusal, refusal_count = check_session_refusal(session.path, core_fmt)
        session = session.model_copy(update={'has_refusal': has_refusal, 'refusal_count': refusal_count})

    return session


@router.post("/sessions/{session_id}/preview", response_model=PreviewResponse)
async def preview_session_api(session_id: str):
    """预览会话修改"""
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    settings = load_settings()
    core_fmt = _session_core_format(session)
    result = preview_session(
        session.path,
        settings.mock_response,
        settings.custom_keywords,
        session_format=core_fmt,
        session_id=session_id if core_fmt == SessionFormat.OPENCODE else None,
    )

    # 如果有备份，计算 diff
    if session.has_backup:
        session_dir = os.path.dirname(session.path)
        base_name = os.path.basename(session.path)
        bak_files = []
        for f in os.listdir(session_dir):
            if f.startswith(base_name + ".") and f.endswith(".bak"):
                bak_files.append(os.path.join(session_dir, f))
        if bak_files:
            bak_files.sort(reverse=True)
            result.diff_items = compute_backup_diff(
                session.path, bak_files[0], session_format=core_fmt
            )

    return result


@router.post("/sessions/{session_id}/ai-rewrite", response_model=AIRewriteResponse)
async def ai_rewrite_session_api(session_id: str):
    """AI 智能改写拒绝内容"""
    settings = load_settings()

    if not settings.ai_enabled:
        return AIRewriteResponse(success=False, error="AI 分析未启用，请在设置中开启")
    if not settings.ai_endpoint:
        return AIRewriteResponse(success=False, error="AI 配置不完整：缺少 API Endpoint")
    if not settings.ai_model:
        return AIRewriteResponse(success=False, error="AI 配置不完整：缺少模型名称")

    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        from .ai_service import generate_ai_rewrite
        core_fmt = _session_core_format(session)
        result = await generate_ai_rewrite(
            session.path, settings, settings.custom_keywords,
            session_format=core_fmt,
            session_id=session_id if core_fmt == SessionFormat.OPENCODE else None,
        )
        return result
    except Exception as e:
        return AIRewriteResponse(success=False, error=str(e))


@router.post("/sessions/{session_id}/patch", response_model=PatchResponse)
async def patch_session_api(session_id: str, body: PatchRequest = None):
    """执行会话清理"""
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    settings = load_settings()
    mock_response = settings.mock_response

    replacements_map = {}
    if body and body.replacements:
        for item in body.replacements:
            replacements_map[item.line_num] = item.replacement_text
    elif body and body.replacement_text:
        mock_response = body.replacement_text

    # 获取选中的行号
    selected_lines = body.selected_lines if body else None

    # 获取是否清理推理内容的设置（请求优先，其次使用全局设置）
    clean_reasoning = body.clean_reasoning if body and body.clean_reasoning is not None else settings.clean_reasoning

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "info", "message": f"开始处理会话: {session_id}"}
    ))

    core_fmt = _session_core_format(session)
    result = patch_session(
        session.path,
        mock_response,
        settings.custom_keywords,
        replacements=replacements_map,
        session_format=core_fmt,
        session_id=session_id if core_fmt == SessionFormat.OPENCODE else None,
        selected_lines=selected_lines,
        clean_reasoning=clean_reasoning,
    )

    if result.success:
        _invalidate_session_cache()
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "success", "message": result.message}
        ))
    else:
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "error", "message": result.message}
        ))

    return result


@router.get("/sessions/{session_id}/backups")
async def list_backups(session_id: str):
    """列出会话的所有备份"""
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    session_dir = os.path.dirname(session.path)
    base_name = os.path.basename(session.path)
    backups = []
    for f in os.listdir(session_dir):
        if f.startswith(base_name + ".") and f.endswith(".bak"):
            bak_path = os.path.join(session_dir, f)
            stat = os.stat(bak_path)
            ts_part = f[len(base_name) + 1:-4]
            try:
                ts = datetime.strptime(ts_part, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            backups.append(BackupInfo(
                filename=f,
                path=bak_path,
                timestamp=ts,
                size=stat.st_size
            ))
    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return backups


@router.post("/sessions/{session_id}/restore", response_model=RestoreResponse)
async def restore_session(session_id: str, backup_filename: str):
    """从备份还原会话"""
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    session_dir = os.path.dirname(session.path)
    backup_path = os.path.join(session_dir, backup_filename)

    if not os.path.exists(backup_path):
        return RestoreResponse(success=False, message="备份文件不存在")

    if os.path.dirname(os.path.realpath(backup_path)) != os.path.realpath(session_dir):
        return RestoreResponse(success=False, message="非法的备份路径")

    try:
        shutil.copy2(backup_path, session.path)
        _invalidate_session_cache()
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "success", "message": f"会话 {session_id} 已从备份还原"}
        ))
        return RestoreResponse(success=True, message="还原成功")
    except Exception as e:
        return RestoreResponse(success=False, message=f"还原失败: {str(e)}")


# ─── 设置 API ────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=Settings)
async def get_settings():
    """获取设置"""
    return load_settings()


@router.put("/settings")
async def update_settings(settings: Settings):
    """更新设置"""
    if save_settings(settings):
        return {"success": True, "message": "设置已保存"}
    raise HTTPException(status_code=500, detail="保存设置失败")


# ─── WebSocket ───────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─── CTF 配置 API ────────────────────────────────────────────────────────────

async def _build_ctf_status_response() -> CTFStatusResponse:
    """从磁盘状态构建 CTFStatusResponse"""
    from codex_session_patcher.ctf_config import check_ctf_status
    loop = asyncio.get_event_loop()
    status = await loop.run_in_executor(None, check_ctf_status)
    return CTFStatusResponse(
        installed=status.installed,
        config_exists=status.config_exists,
        prompt_exists=status.prompt_exists,
        profile_available=status.profile_available,
        global_installed=status.global_installed,
        config_path=status.config_path,
        prompt_path=status.prompt_path,
        claude_installed=status.claude_installed,
        claude_workspace_exists=status.claude_workspace_exists,
        claude_prompt_exists=status.claude_prompt_exists,
        claude_workspace_path=status.claude_workspace_path,
        claude_prompt_path=status.claude_prompt_path,
        opencode_installed=status.opencode_installed,
        opencode_workspace_exists=status.opencode_workspace_exists,
        opencode_prompt_exists=status.opencode_prompt_exists,
        opencode_workspace_path=status.opencode_workspace_path,
        opencode_prompt_path=status.opencode_prompt_path,
    )


@router.get("/ctf/status", response_model=CTFStatusResponse)
async def get_ctf_status():
    """获取 CTF 配置状态（Codex + Claude Code）"""
    return await _build_ctf_status_response()


@router.post("/ctf/install", response_model=CTFInstallResponse)
async def install_ctf_config():
    """安装 CTF 配置"""
    from codex_session_patcher.ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()
    success, message = installer.install()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="codex -p ctf",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/uninstall", response_model=CTFInstallResponse)
async def uninstall_ctf_config():
    """卸载 CTF 配置"""
    from codex_session_patcher.ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()
    success, message = installer.uninstall()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/global/install", response_model=CTFInstallResponse)
async def install_ctf_global():
    """启用 CTF 全局模式"""
    from codex_session_patcher.ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()
    success, message = installer.install_global()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/global/uninstall", response_model=CTFInstallResponse)
async def uninstall_ctf_global():
    """禁用 CTF 全局模式"""
    from codex_session_patcher.ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()
    success, message = installer.uninstall_global()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/claude/install", response_model=CTFInstallResponse)
async def install_claude_ctf_config():
    """安装 Claude Code CTF 配置"""
    from codex_session_patcher.ctf_config import ClaudeCodeCTFInstaller
    installer = ClaudeCodeCTFInstaller()
    success, message = installer.install()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        activation_command="cd ~/.claude-ctf-workspace && claude",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/claude/uninstall", response_model=CTFInstallResponse)
async def uninstall_claude_ctf_config():
    """卸载 Claude Code CTF 配置"""
    from codex_session_patcher.ctf_config import ClaudeCodeCTFInstaller
    installer = ClaudeCodeCTFInstaller()
    success, message = installer.uninstall()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        activation_command="",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/opencode/install", response_model=CTFInstallResponse)
async def install_opencode_ctf_config():
    """安装 OpenCode CTF 配置"""
    from codex_session_patcher.ctf_config import OpenCodeCTFInstaller
    installer = OpenCodeCTFInstaller()

    # 检查是否有自定义提示词
    settings_data = _load_raw_config()
    custom_prompt = settings_data.get('ctf_prompts', {}).get('opencode', {}).get('prompt')
    success, message = installer.install(custom_prompt=custom_prompt)

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        activation_command="cd ~/.opencode-ctf-workspace && opencode",
        status=await _build_ctf_status_response(),
    )


@router.post("/ctf/opencode/uninstall", response_model=CTFInstallResponse)
async def uninstall_opencode_ctf_config():
    """卸载 OpenCode CTF 配置"""
    from codex_session_patcher.ctf_config import OpenCodeCTFInstaller
    installer = OpenCodeCTFInstaller()
    success, message = installer.uninstall()

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success" if success else "error", "message": message}
    ))

    return CTFInstallResponse(
        success=success,
        message=message,
        profile_command="",
        activation_command="",
        status=await _build_ctf_status_response(),
    )


# ─── CTF 提示词 CRUD ────────────────────────────────────────────────────────

def _load_raw_config() -> dict:
    """加载原始配置文件"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logger.warning("加载配置文件失败", exc_info=True)
    return {}


def _save_raw_config(data: dict):
    """保存原始配置文件"""
    config_dir = os.path.dirname(DEFAULT_CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)
    os.chmod(config_dir, 0o700)
    with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.chmod(DEFAULT_CONFIG_FILE, 0o600)


_CTF_PROMPT_PATHS = {
    'codex': os.path.expanduser("~/.codex/prompts/ctf_optimized.md"),
    'claude_code': os.path.expanduser("~/.claude-ctf-workspace/.claude/CLAUDE.md"),
    'opencode': os.path.expanduser("~/.opencode-ctf-workspace/AGENTS.md"),
}


def _get_ctf_prompt_path(tool: str) -> str | None:
    """获取工具当前实际生效的 CTF 提示词路径"""
    if tool != 'codex':
        return _CTF_PROMPT_PATHS.get(tool)

    from codex_session_patcher.ctf_config import check_ctf_status
    status = check_ctf_status()
    return status.prompt_path or _CTF_PROMPT_PATHS['codex']


def _get_codex_prompt_path_for_file(filename: str) -> str:
    """根据内置模板文件名得到 Codex prompt 绝对路径"""
    return os.path.join(os.path.expanduser("~/.codex/prompts"), os.path.basename(filename))


def _sync_codex_profile_prompt_file(filename: str):
    """同步 [profiles.ctf].model_instructions_file 到指定内置模板文件"""
    from codex_session_patcher.ctf_config import CTFConfigInstaller
    CTFConfigInstaller()._update_config(os.path.basename(filename))


def _codex_profile_available() -> bool:
    from codex_session_patcher.ctf_config import check_ctf_status
    return check_ctf_status().profile_available


def _read_ctf_prompt_for_tool(tool: str) -> str | None:
    """读取工具当前实际安装的 CTF 提示词，未安装时从配置中读取自定义内容，都没有则返回 None"""
    # 优先读已安装的实际文件
    path = _get_ctf_prompt_path(tool)
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    # 其次读用户保存到配置的自定义提示词
    config = _load_raw_config()
    saved = config.get('ctf_prompts', {}).get(tool, {}).get('prompt')
    return saved or None


def _get_default_prompt(tool: str) -> str:
    """获取工具的默认提示词模板（从 BUILTIN_TEMPLATES 中取 default:True 的条目）"""
    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    templates = BUILTIN_TEMPLATES.get(tool, [])
    for t in templates:
        if t.get('default'):
            return t['prompt']
    # 兜底：返回第一个
    return templates[0]['prompt'] if templates else ''


@router.get("/ctf/prompt/{tool}")
async def get_ctf_prompt(tool: str):
    """获取 CTF 提示词内容"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    prompt_path = _get_ctf_prompt_path(tool)
    default_prompt = _get_default_prompt(tool)
    is_installed = bool(prompt_path and os.path.exists(prompt_path))

    # 已安装：读取实际文件
    if is_installed:
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            return {
                "prompt": prompt,
                "is_installed": True,
                "is_default": prompt.strip() == default_prompt.strip(),
            }
        except Exception:
            logger.warning("读取提示词文件失败: %s", prompt_path, exc_info=True)

    # 未安装：从配置或默认模板
    config = _load_raw_config()
    saved = config.get('ctf_prompts', {}).get(tool, {}).get('prompt')

    return {
        "prompt": saved or default_prompt,
        "is_installed": False,
        "is_default": saved is None,
    }


@router.post("/ctf/prompt/{tool}")
async def save_ctf_prompt(tool: str, body: dict):
    """保存 CTF 提示词"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    prompt = body.get('prompt', '')
    if not prompt:
        raise HTTPException(status_code=400, detail="提示词内容不能为空")

    prompt_path = _get_ctf_prompt_path(tool)

    # 查找匹配的内置模板，获取其目标文件名
    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    matched_file = None
    for tpl in BUILTIN_TEMPLATES.get(tool, []):
        if tpl.get('file') and tpl['prompt'].strip() == prompt.strip():
            matched_file = tpl['file']
            break

    should_write_installed = bool(prompt_path and os.path.exists(prompt_path))
    if tool == 'codex' and _codex_profile_available():
        if matched_file:
            prompt_path = _get_codex_prompt_path_for_file(matched_file)
            _sync_codex_profile_prompt_file(matched_file)
        should_write_installed = bool(prompt_path)

    # 已安装：写入对应文件
    if should_write_installed:
        try:
            os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")

    # 保存到配置（供安装时使用）
    config = _load_raw_config()
    ctf_prompts = config.setdefault('ctf_prompts', {})
    tool_config = ctf_prompts.setdefault(tool, {})
    tool_config['prompt'] = prompt
    if matched_file:
        tool_config['file'] = matched_file
    _save_raw_config(config)

    return {"success": True, "message": "提示词已保存"}


@router.post("/ctf/prompt/{tool}/reset")
async def reset_ctf_prompt(tool: str):
    """恢复 CTF 提示词为默认值"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    default_prompt = _get_default_prompt(tool)
    prompt_path = _get_ctf_prompt_path(tool)
    should_write_installed = bool(prompt_path and os.path.exists(prompt_path))

    if tool == 'codex' and _codex_profile_available():
        from codex_session_patcher.ctf_config.installer import CTFConfigInstaller
        prompt_path = _get_codex_prompt_path_for_file(CTFConfigInstaller.DEFAULT_PROMPT_FILE)
        _sync_codex_profile_prompt_file(CTFConfigInstaller.DEFAULT_PROMPT_FILE)
        should_write_installed = True

    # 已安装：更新文件为默认
    if should_write_installed:
        try:
            os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(default_prompt)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")

    # 从配置中移除自定义提示词
    config = _load_raw_config()
    ctf_prompts = config.get('ctf_prompts', {})
    if tool in ctf_prompts:
        del ctf_prompts[tool]
        _save_raw_config(config)

    return {"success": True, "message": "已恢复默认提示词", "prompt": default_prompt}


MAX_TEMPLATES = 5


@router.get("/ctf/prompt/{tool}/templates")
async def list_ctf_templates(tool: str):
    """获取工具的所有提示词模板（内置模板 + 用户模板），不返回 prompt 内容"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    builtin = [{k: v for k, v in t.items() if k != 'prompt'} | {'builtin': True} for t in BUILTIN_TEMPLATES.get(tool, [])]

    config = _load_raw_config()
    user_templates = config.get('ctf_templates', {}).get(tool, [])
    # 用户模板也不返回 prompt 内容
    user_templates_lite = [{k: v for k, v in t.items() if k != 'prompt'} for t in user_templates]
    return {"templates": builtin + user_templates_lite}


@router.get("/ctf/prompt/{tool}/templates/{template_name}")
async def get_ctf_template_prompt(tool: str, template_name: str):
    """获取单个模板的 prompt 内容"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    for tpl in BUILTIN_TEMPLATES.get(tool, []):
        if tpl.get('name') == template_name:
            return {"name": tpl['name'], "prompt": tpl.get('prompt', '')}

    config = _load_raw_config()
    for tpl in config.get('ctf_templates', {}).get(tool, []):
        if tpl.get('name') == template_name:
            return {"name": tpl['name'], "prompt": tpl.get('prompt', '')}

    raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")


@router.post("/ctf/prompt/{tool}/templates")
async def save_ctf_template(tool: str, body: dict):
    """保存提示词为模板（最多 5 个）"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    name = body.get('name', '').strip()
    prompt = body.get('prompt', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    if not prompt:
        raise HTTPException(status_code=400, detail="模板内容不能为空")

    config = _load_raw_config()
    all_templates = config.setdefault('ctf_templates', {})
    templates = all_templates.setdefault(tool, [])

    # 同名覆盖
    templates = [t for t in templates if t['name'] != name]
    if len(templates) >= MAX_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"最多保存 {MAX_TEMPLATES} 个模板")

    templates.append({"name": name, "prompt": prompt})
    all_templates[tool] = templates
    _save_raw_config(config)

    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    builtin = [dict(t, builtin=True) for t in BUILTIN_TEMPLATES.get(tool, [])]
    return {"success": True, "message": "模板已保存", "templates": builtin + templates}


@router.delete("/ctf/prompt/{tool}/templates/{template_name}")
async def delete_ctf_template(tool: str, template_name: str):
    """删除指定用户模板（内置模板不可删除）"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    if any(t['name'] == template_name for t in BUILTIN_TEMPLATES.get(tool, [])):
        raise HTTPException(status_code=403, detail="内置模板不可删除")

    config = _load_raw_config()
    all_templates = config.get('ctf_templates', {})
    templates = all_templates.get(tool, [])

    new_templates = [t for t in templates if t['name'] != template_name]
    if len(new_templates) == len(templates):
        raise HTTPException(status_code=404, detail="模板不存在")

    all_templates[tool] = new_templates
    _save_raw_config(config)

    builtin = [dict(t, builtin=True) for t in BUILTIN_TEMPLATES.get(tool, [])]
    return {"success": True, "message": "模板已删除", "templates": builtin + new_templates}


# ─── 提示词改写 API ─────────────────────────────────────────────────────────

@router.post("/prompt-rewrite", response_model=PromptRewriteResponse)
async def rewrite_prompt(request: PromptRewriteRequest):
    """改写提示词"""
    settings = load_settings()

    if not settings.ai_endpoint:
        return PromptRewriteResponse(
            success=False,
            original=request.original_request,
            error="AI 未配置：请在设置中填写 API Endpoint"
        )
    if not settings.ai_model:
        return PromptRewriteResponse(
            success=False,
            original=request.original_request,
            error="AI 未配置：请在设置中填写模型名称"
        )

    try:
        from .prompt_rewriter import rewrite_prompt as _do_rewrite

        # 读取对应工具当前的 CTF 注入提示词（有则配合改写）
        tool = request.target or 'codex'
        ctf_prompt: str | None = None
        try:
            ctf_prompt = _read_ctf_prompt_for_tool(tool)
        except Exception:
            pass

        rewritten, strategy = await _do_rewrite(
            request.original_request,
            settings.ai_endpoint,
            settings.ai_key,
            settings.ai_model,
            target=tool,
            ctf_prompt=ctf_prompt,
        )
        return PromptRewriteResponse(
            success=True,
            original=request.original_request,
            rewritten=rewritten,
            strategy=strategy,
        )
    except Exception as e:
        return PromptRewriteResponse(
            success=False,
            original=request.original_request,
            error=str(e),
        )
