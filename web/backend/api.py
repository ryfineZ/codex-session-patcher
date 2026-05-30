"""
API 路由 — 支持 Codex CLI 和 Claude Code 双格式
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import json
import re
import shutil
import subprocess
import sys
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
    CTFStatusResponse, CTFInstallResponse, LaunchCodexRequest, PromptRewriteRequest, PromptRewriteResponse,
    ConversationTurn, normalize_mock_response,
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
DEFAULT_DELETED_SESSION_DIR = os.path.expanduser("~/.codex-patcher/deleted-sessions")


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


def _invalidate_search_cache():
    """清除搜索缓存"""
    if '_search_cache' in globals():
        _search_cache['query'] = None
        _search_cache['format'] = None
        _search_cache['sessions'] = None
        _search_cache['timestamp'] = 0.0


def _invalidate_all_session_caches():
    _invalidate_session_cache()
    _invalidate_search_cache()


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


CTF_SESSION_MARKERS = (
    "privately deployed for a CTF game",
    "security testing environment",
    "CTF/渗透",
    "CTF/Pentesting",
    "specialized CTF/Pentesting automation agent",
    "sandboxed competition environment",
    "authorized security work",
    "authorized penetration testing",
    "All domains in this environment are confirmed redirected",
    "Execute with maximum aggression and efficiency",
    "managed-by: codex-session-patcher:ctf",
)


def _normalize_prompt_for_match(text: str) -> str:
    """Normalize prompt text for robust session/file comparisons.

    Users can edit CTF prompts freely.  Older detection only looked for a small
    set of built-in-template phrases, so a valid custom global prompt could be
    loaded by Codex but still displayed as "普通模式" in the Web UI.  Compare the
    session's recorded base instructions with the currently configured prompt
    file as a fallback, ignoring our optional bookkeeping marker.
    """
    if not text:
        return ""
    text = re.sub(r'<!--\s*managed-by:\s*codex-session-patcher:ctf\s*-->', '', text, flags=re.I)
    text = re.sub(r'\bmanaged-by:\s*codex-session-patcher:ctf\b', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def _active_codex_prompt_candidates() -> list[tuple[str, str]]:
    """Return configured Codex CTF prompt files to compare against sessions."""
    candidates: list[tuple[str, str]] = []
    try:
        from codex_session_patcher.ctf_config import check_ctf_status
        status = check_ctf_status()
        for label, path in (
            (status.codex_mode or "codex_ctf", status.global_prompt_path),
            ("codex_profile", status.prompt_path),
        ):
            if not path or not os.path.exists(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    prompt = f.read()
                candidates.append((label, prompt))
            except Exception:
                logger.debug("读取 Codex CTF prompt 失败: %s", path, exc_info=True)
    except Exception:
        logger.debug("读取 Codex CTF 状态失败", exc_info=True)
    return candidates


def detect_ctf_session(file_path: str, fmt: SessionFormat = SessionFormat.CODEX) -> tuple[bool, Optional[str], Optional[str]]:
    """判断一个历史会话是否实际加载了 CTF/渗透提示词。

    Codex 会在 session_meta.payload.base_instructions.text 中保存会话启动时实际
    加载的基础/模型指令，因此这里检查会话本身，而不是只看当前配置文件。
    """
    if fmt != SessionFormat.CODEX:
        return False, None, None

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

                if data.get('type') != 'session_meta':
                    continue

                payload = data.get('payload', {}) or {}
                base_instructions = payload.get('base_instructions') or {}
                text = base_instructions.get('text', '') if isinstance(base_instructions, dict) else ''
                if not text:
                    return False, None, None

                lowered = text.lower()
                for marker in CTF_SESSION_MARKERS:
                    if marker.lower() in lowered:
                        return True, "codex_profile_or_global", marker

                session_prompt = _normalize_prompt_for_match(text)
                if len(session_prompt) >= 128:
                    for label, prompt in _active_codex_prompt_candidates():
                        active_prompt = _normalize_prompt_for_match(prompt)
                        if len(active_prompt) < 128:
                            continue
                        if (
                            session_prompt == active_prompt
                            or active_prompt in session_prompt
                            or session_prompt in active_prompt
                        ):
                            return True, label, "matches_active_prompt"

                return False, None, None
    except Exception:
        logger.warning("检测会话 CTF 状态失败: %s", file_path, exc_info=True)

    return False, None, None


def _truncate_summary(text: str, limit: int = 120) -> str:
    """压缩会话摘要，避免列表里只看到编号。"""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', str(text)).strip()
    # 环境上下文、开发者指令对用户识别会话帮助不大，跳过。
    skipped_prefixes = (
        '<environment_context>',
        '<permissions instructions>',
        '<app-context>',
        'The following is the Codex agent history',
        'Another language model started to solve this problem',
    )
    if text.startswith(skipped_prefixes):
        return ''
    return text[:limit] + ('...' if len(text) > limit else '')


def _extract_message_text_from_line(line: dict, fmt: SessionFormat) -> tuple[Optional[str], str]:
    """从一行会话数据里提取 (role, text)，用于列表摘要。"""
    if fmt == SessionFormat.CODEX:
        line_type = line.get('type')
        payload = line.get('payload', {}) or {}
        if line_type == 'response_item' and payload.get('type') == 'message':
            role = payload.get('role')
            texts = []
            content = payload.get('content', [])
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get('type') in ('input_text', 'output_text', 'text'):
                        texts.append(item.get('text', ''))
            return role, _truncate_summary('\n'.join(texts))
        if line_type == 'event_msg':
            pt = payload.get('type')
            if pt == 'user_message':
                return 'user', _truncate_summary(payload.get('message', ''))
            if pt == 'agent_message':
                return 'assistant', _truncate_summary(payload.get('message', ''))
            if pt == 'task_complete':
                return 'assistant', _truncate_summary(payload.get('last_agent_message', ''))
        return None, ''

    if fmt in (SessionFormat.CLAUDE_CODE, SessionFormat.OPENCODE):
        role = None
        if line.get('type') in ('human', 'user'):
            role = 'user'
        elif line.get('type') == 'assistant':
            role = 'assistant'
        else:
            role = line.get('message', {}).get('role')
        msg = line.get('message', {})
        content = msg.get('content', line.get('content', ''))
        texts = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') in ('text', 'input_text', 'output_text'):
                    texts.append(item.get('text', ''))
        return role, _truncate_summary('\n'.join(texts))

    return None, ''


def inspect_session_metadata(file_path: str, fmt: SessionFormat = SessionFormat.CODEX) -> dict:
    """提取项目路径、会话标题和首/末轮摘要，用于和 Codex 项目会话对齐显示。"""
    meta = {
        'title': None,
        'project_path': None,
        'project_name': None,
        'project_key': None,
        'first_user_message': None,
        'last_user_message': None,
        'last_assistant_message': None,
        'originator': None,
    }
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

                payload = data.get('payload', {}) or {}
                if fmt == SessionFormat.CODEX:
                    if data.get('type') == 'session_meta':
                        cwd = payload.get('cwd')
                        if cwd:
                            meta['project_path'] = cwd
                        meta['originator'] = payload.get('originator') or payload.get('source') or meta['originator']
                    elif data.get('type') == 'turn_context':
                        cwd = payload.get('cwd')
                        if cwd and not meta['project_path']:
                            meta['project_path'] = cwd

                role, text = _extract_message_text_from_line(data, fmt)
                if text:
                    if role == 'user':
                        if not meta['first_user_message']:
                            meta['first_user_message'] = text
                        meta['last_user_message'] = text
                    elif role == 'assistant':
                        meta['last_assistant_message'] = text
    except Exception:
        logger.warning("提取会话摘要失败: %s", file_path, exc_info=True)

    project_path = meta.get('project_path')
    if project_path:
        normalized = os.path.normpath(project_path)
        meta['project_path'] = normalized
        meta['project_name'] = os.path.basename(normalized.rstrip(os.sep)) or normalized
        meta['project_key'] = normalized.lower()
    else:
        meta['project_name'] = '未识别项目'
        meta['project_key'] = '__unknown__'

    title = meta.get('first_user_message') or meta.get('last_user_message') or meta.get('last_assistant_message')
    meta['title'] = title or os.path.basename(file_path)
    return meta


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
                ctf_active, ctf_source, ctf_reason = detect_ctf_session(info.path, info.format)
                meta = inspect_session_metadata(info.path, info.format)
                project_path = meta.get('project_path') or info.project_path

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
                    title=meta.get('title'),
                    date=info.date,
                    mtime=info.mtime_str,
                    size=info.size,
                    has_refusal=has_refusal,
                    refusal_count=refusal_count,
                    has_backup=backup_count > 0,
                    backup_count=backup_count,
                    format=_to_schema_format(info.format),
                    project_path=project_path,
                    project_name=meta.get('project_name') or (os.path.basename(project_path) if project_path else None),
                    project_key=meta.get('project_key') or (os.path.normpath(project_path).lower() if project_path else None),
                    first_user_message=meta.get('first_user_message'),
                    last_user_message=meta.get('last_user_message'),
                    last_assistant_message=meta.get('last_assistant_message'),
                    originator=meta.get('originator'),
                    ctf_active=ctf_active,
                    ctf_source=ctf_source,
                    ctf_reason=ctf_reason,
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
                    else:
                        messages = adapter.load_session_messages(oc_info['session_id'])
                    first_user = ''
                    last_user = ''
                    last_assistant = ''
                    for msg in messages:
                        role, text = _extract_message_text_from_line(msg, SessionFormat.OPENCODE)
                        if text:
                            if role == 'user':
                                if not first_user:
                                    first_user = text
                                last_user = text
                            elif role == 'assistant':
                                last_assistant = text

                    project_path = oc_info.get('project_path', '')
                    project_name = oc_info.get('project_name') or (os.path.basename(os.path.normpath(project_path)) if project_path else 'OpenCode')

                    sessions.append(Session(
                        id=oc_info['session_id'],
                        filename=oc_info['session_id'],
                        path=DEFAULT_OPENCODE_DB,
                        title=oc_info.get('title') or first_user or last_user or oc_info['session_id'],
                        date=oc_info['date'],
                        mtime=oc_info['mtime_str'],
                        size=0,
                        has_refusal=has_refusal,
                        refusal_count=refusal_count,
                        has_backup=backup_count > 0,
                        backup_count=backup_count,
                        format=SessionFormatEnum.OPENCODE,
                        project_path=project_path,
                        project_name=project_name,
                        project_key=os.path.normpath(project_path).lower() if project_path else '__opencode__',
                        first_user_message=first_user or None,
                        last_user_message=last_user or None,
                        last_assistant_message=last_assistant or None,
                        ctf_active=False,
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


def _has_ai_rewrite_config(settings: Settings) -> bool:
    """判断自动改写所需 AI 配置是否完整。"""
    return bool(settings.ai_enabled and settings.ai_endpoint and settings.ai_model)


def _is_relative_to(child: str | Path, parent: str | Path) -> bool:
    """兼容 Py3.9+ 的安全路径包含检查。"""
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _session_allowed_root(session: Session, core_fmt: SessionFormat) -> str | None:
    if core_fmt == SessionFormat.CODEX:
        return DEFAULT_SESSION_DIR
    if core_fmt == SessionFormat.CLAUDE_CODE:
        return DEFAULT_CLAUDE_SESSION_DIR
    if core_fmt == SessionFormat.OPENCODE:
        return os.path.dirname(DEFAULT_OPENCODE_DB)
    return None


def _delete_jsonl_session_files(session: Session, core_fmt: SessionFormat) -> tuple[list[str], list[str]]:
    """将 JSONL 会话及同名前缀备份移动到隔离目录，返回 (moved, skipped)。"""
    root = _session_allowed_root(session, core_fmt)
    if not root:
        raise ValueError("不支持的会话格式")

    session_path = Path(session.path).resolve()
    root_path = Path(root).resolve()
    if not _is_relative_to(session_path, root_path):
        raise ValueError(f"会话路径不在允许目录内: {session.path}")
    if not session_path.exists():
        raise FileNotFoundError("会话文件不存在，刷新列表即可移除")

    trash_root = Path(DEFAULT_DELETED_SESSION_DIR).resolve()
    trash_dir = trash_root / datetime.now().strftime("%Y%m%d_%H%M%S") / session.id
    trash_dir.mkdir(parents=True, exist_ok=True)

    session_dir = session_path.parent
    base_name = session_path.name
    candidates = [session_path]
    for item in session_dir.iterdir():
        if item.name.startswith(base_name + ".") and item.name.endswith(".bak") and item.is_file():
            candidates.append(item.resolve())

    moved: list[str] = []
    skipped: list[str] = []
    for candidate in candidates:
        if not _is_relative_to(candidate, root_path):
            skipped.append(str(candidate))
            continue
        dest = trash_dir / candidate.name
        suffix = 1
        while dest.exists():
            dest = trash_dir / f"{candidate.name}.{suffix}"
            suffix += 1
        shutil.move(str(candidate), str(dest))
        moved.append(str(candidate))

    return moved, skipped


def _delete_opencode_session(session_id: str) -> int:
    """删除 OpenCode SQLite 中的一条会话及相关消息/parts，返回删除记录数量。"""
    adapter = OpenCodeDBAdapter(DEFAULT_OPENCODE_DB)
    backup_path = adapter.backup_database()
    conn = adapter._connect(readonly=False)
    deleted = 0
    try:
        message_ids = [
            row["id"]
            for row in conn.execute("SELECT id FROM message WHERE session_id = ?", (session_id,))
        ]
        for msg_id in message_ids:
            deleted += conn.execute("DELETE FROM part WHERE message_id = ?", (msg_id,)).rowcount
        deleted += conn.execute("DELETE FROM message WHERE session_id = ?", (session_id,)).rowcount
        for table in ("part", "session"):
            try:
                deleted += conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,)).rowcount
            except Exception:
                # 不同版本 schema 可能没有 session_id 或已在上面删除，忽略兼容。
                pass
        deleted += conn.execute("DELETE FROM session WHERE id = ?", (session_id,)).rowcount
        conn.commit()
        logger.info("OpenCode 会话已删除: %s, backup=%s", session_id, backup_path)
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
                # 有些历史 Codex 会话只保留 event_msg/agent_message，
                # 没有对应 response_item；此时它本身就是需要清理的主记录。
                refusal_groups[idx] = []
                primary_order.append(idx)
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
                settings = Settings.model_validate(data)
                if data.get("mock_response") != settings.mock_response:
                    data["mock_response"] = settings.mock_response
                    with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as out:
                        json.dump(data, out, ensure_ascii=False, indent=2)
                    os.chmod(DEFAULT_CONFIG_FILE, 0o600)
                return settings
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
    """查找会话（优先返回已做过拒绝检测的缓存结果）"""
    loop = asyncio.get_event_loop()

    if session_format is None:
        cached = _session_cache.get('sessions') or []
        for session in cached:
            if session.id == session_id:
                return session

    sessions = await loop.run_in_executor(
        None, _get_cached_sessions, session_format, False
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
    core_fmt = _session_core_format(session)

    replacements_map = {}
    if body and body.replacements:
        for item in body.replacements:
            replacements_map[item.line_num] = normalize_mock_response(item.replacement_text)
    elif body and body.replacement_text:
        mock_response = normalize_mock_response(body.replacement_text)

    # 获取选中的行号
    selected_lines = body.selected_lines if body else None

    # 获取是否清理推理内容的设置（请求优先，其次使用全局设置）
    clean_reasoning = body.clean_reasoning if body and body.clean_reasoning is not None else settings.clean_reasoning

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "info", "message": f"开始处理会话: {session_id}"}
    ))

    should_auto_ai_rewrite = (
        (body is None or body.auto_ai_rewrite)
        and not replacements_map
        and not (body and body.replacement_text)
        and session.has_refusal
        and _has_ai_rewrite_config(settings)
    )
    if should_auto_ai_rewrite:
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "info", "message": "检测到未提供替换内容，正在自动调用 AI 生成拒绝替换..."}
        ))
        try:
            from .ai_service import generate_ai_rewrite
            ai_result = await generate_ai_rewrite(
                session.path,
                settings,
                settings.custom_keywords,
                session_format=core_fmt,
                session_id=session_id if core_fmt == SessionFormat.OPENCODE else None,
            )
            if ai_result.success and ai_result.items:
                selected_set = set(selected_lines) if selected_lines else None
                for item in ai_result.items:
                    if selected_set is not None and item.line_num not in selected_set:
                        continue
                    replacements_map[item.line_num] = item.replacement
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "success", "message": f"AI 已自动生成 {len(replacements_map)} 条替换内容"}
                ))
            elif ai_result.error:
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "warn", "message": f"AI 自动改写失败，将使用默认替换文本: {ai_result.error}"}
                ))
        except Exception as e:
            logger.warning("自动 AI 改写失败，回退到默认替换文本", exc_info=True)
            await manager.broadcast(WSMessage(
                type="log",
                data={"level": "warn", "message": f"AI 自动改写失败，将使用默认替换文本: {e}"}
            ))
    elif not replacements_map and session.has_refusal and not _has_ai_rewrite_config(settings):
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "warn", "message": "AI 接口未配置完整，本次清理使用默认替换文本"}
        ))

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
        _invalidate_all_session_caches()
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


@router.delete("/sessions/{session_id}", response_model=RestoreResponse)
async def delete_session(session_id: str):
    """删除/移除本地会话记录。

    Codex/Claude Code: 移动 JSONL 会话和同名前缀 .bak 到 ~/.codex-patcher/deleted-sessions。
    OpenCode: 先备份数据库，再删除该 session 的 SQLite 记录。
    """
    session = await _find_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已删除，请刷新列表")

    core_fmt = _session_core_format(session)
    try:
        if core_fmt == SessionFormat.OPENCODE:
            deleted_count = _delete_opencode_session(session_id)
            message = f"会话已删除（OpenCode 数据库记录 {deleted_count} 条，已自动备份数据库）"
        else:
            moved, skipped = _delete_jsonl_session_files(session, core_fmt)
            message = f"会话已移除（{len(moved)} 个文件已移到隔离目录）"
            if skipped:
                message += f"，跳过 {len(skipped)} 个不安全路径"

        _invalidate_all_session_caches()
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "success", "message": f"{session_id}: {message}"}
        ))
        return RestoreResponse(success=True, message=message)
    except FileNotFoundError as e:
        _invalidate_all_session_caches()
        return RestoreResponse(success=True, message=str(e))
    except Exception as e:
        logger.warning("删除会话失败: %s", session_id, exc_info=True)
        await manager.broadcast(WSMessage(
            type="log",
            data={"level": "error", "message": f"删除会话失败: {e}"}
        ))
        return RestoreResponse(success=False, message=f"删除失败: {str(e)}")


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
        _invalidate_all_session_caches()
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
        global_prompt_path=status.global_prompt_path,
        global_prompt_exists=status.global_prompt_exists,
        codex_profile_ready=status.codex_profile_ready,
        codex_global_active=status.codex_global_active,
        codex_mode=status.codex_mode,
        codex_activation_command=status.codex_activation_command,
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


def _quote_powershell_single(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _resolve_launch_cwd(cwd: Optional[str]) -> str:
    launch_cwd = os.path.abspath(os.path.expandvars(os.path.expanduser(cwd or os.getcwd())))
    if not os.path.isdir(launch_cwd):
        raise HTTPException(status_code=400, detail=f"启动目录不存在: {launch_cwd}")
    return launch_cwd


def _launch_interactive_terminal(command: str, cwd: str) -> str:
    """Launch an interactive command in a real terminal window."""
    if os.name == "nt":
        ps_command = f"Set-Location -LiteralPath {_quote_powershell_single(cwd)}; {command}"
        wt = shutil.which("wt.exe") or shutil.which("wt")
        if wt:
            subprocess.Popen(
                [wt, "-d", cwd, "powershell.exe", "-NoExit", "-Command", ps_command],
                close_fds=True,
            )
            return "Windows Terminal"

        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", ps_command],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            close_fds=True,
        )
        return "PowerShell"

    if sys.platform == "darwin":
        escaped_cwd = cwd.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "Terminal"\n'
            f'  do script "cd \\"{escaped_cwd}\\" && {command}"\n'
            "  activate\n"
            "end tell"
        )
        subprocess.Popen(["osascript", "-e", script], close_fds=True)
        return "Terminal.app"

    for terminal in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal"):
        terminal_path = shutil.which(terminal)
        if not terminal_path:
            continue
        shell_command = f"cd {shlex_quote(cwd)} && {command}; exec bash"
        if terminal == "gnome-terminal":
            args = [terminal_path, "--working-directory", cwd, "--", "bash", "-lc", f"{command}; exec bash"]
        elif terminal == "konsole":
            args = [terminal_path, "--workdir", cwd, "-e", "bash", "-lc", f"{command}; exec bash"]
        elif terminal == "xfce4-terminal":
            args = [terminal_path, "--working-directory", cwd, "-e", f"bash -lc {shlex_quote(command + '; exec bash')}"]
        else:
            args = [terminal_path, "-e", f"bash -lc {shlex_quote(shell_command)}"]
        subprocess.Popen(args, close_fds=True)
        return terminal

    raise RuntimeError("未找到可用的终端程序，请在系统终端里手动运行该命令")


@router.post("/ctf/codex/launch")
async def launch_codex_ctf(request: LaunchCodexRequest):
    from codex_session_patcher.ctf_config import check_ctf_status

    status = check_ctf_status()
    if status.codex_global_active:
        command = "codex"
    elif status.codex_profile_ready:
        command = "codex -p ctf"
    else:
        raise HTTPException(status_code=400, detail="请先启用 Codex Profile 或全局模式")

    cwd = _resolve_launch_cwd(request.cwd)
    try:
        terminal = _launch_interactive_terminal(command, cwd)
    except Exception as e:
        logger.warning("启动 Codex 终端失败", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    message = f"已在 {terminal} 中启动: {command}"
    await manager.broadcast(WSMessage(type="log", data={"level": "success", "message": message}))
    return {"success": True, "message": message, "command": command, "cwd": cwd, "terminal": terminal}


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


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256((prompt or '').strip().encode('utf-8')).hexdigest()


def _all_templates(tool: str) -> list[dict]:
    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    builtin = [dict(t, builtin=True) for t in BUILTIN_TEMPLATES.get(tool, [])]
    config = _load_raw_config()
    user_templates = [dict(t, builtin=False) for t in config.get('ctf_templates', {}).get(tool, [])]
    return builtin + user_templates


def _find_template(tool: str, template_name: str) -> dict | None:
    for tpl in _all_templates(tool):
        if tpl.get('name') == template_name:
            return tpl
    return None


def _detect_current_template(tool: str, prompt: str | None = None) -> str | None:
    if prompt is None:
        try:
            prompt = _read_ctf_prompt_for_tool(tool)
        except Exception:
            prompt = None
    if not prompt:
        return None
    target_hash = _prompt_hash(prompt)
    for tpl in _all_templates(tool):
        if _prompt_hash(tpl.get('prompt', '')) == target_hash:
            return tpl.get('name')
    return None


def _write_prompt_file(path: str, prompt: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(prompt)


def _template_response(tool: str, templates: list[dict] | None = None) -> dict:
    if templates is None:
        templates = _all_templates(tool)
    current_prompt = None
    try:
        current_prompt = _read_ctf_prompt_for_tool(tool)
    except Exception:
        pass
    current_template = _detect_current_template(tool, current_prompt)
    lite = []
    for tpl in templates:
        item = {k: v for k, v in tpl.items() if k != 'prompt'}
        item['active'] = bool(current_template and item.get('name') == current_template)
        lite.append(item)
    return {"templates": lite, "current_template": current_template}


def _save_selected_prompt(tool: str, template_name: str, prompt: str, file_name: str | None = None):
    config = _load_raw_config()
    ctf_prompts = config.setdefault('ctf_prompts', {})
    tool_config = ctf_prompts.setdefault(tool, {})
    tool_config['prompt'] = prompt
    tool_config['template'] = template_name
    if file_name:
        tool_config['file'] = file_name
    elif tool == 'codex':
        tool_config['file'] = 'ctf_custom.md'
    _save_raw_config(config)


def _apply_template_to_installed_target(tool: str, template_name: str, prompt: str, file_name: str | None = None) -> list[str]:
    """把模板写入当前已启用的运行配置。返回需要用户手动重启/新开的提示。"""
    restart_hints: list[str] = []

    if tool == 'codex':
        from codex_session_patcher.ctf_config import check_ctf_status
        from codex_session_patcher.ctf_config import CTFConfigInstaller

        status = check_ctf_status()
        prompt_file = os.path.basename(file_name) if file_name else 'ctf_custom.md'
        prompt_path = _get_codex_prompt_path_for_file(prompt_file)
        _write_prompt_file(prompt_path, prompt)

        installer = CTFConfigInstaller()
        if status.codex_global_active or status.global_installed:
            # 全局模式读取顶层 model_instructions_file，先移除旧注入再按新模板文件重装。
            success, msg = installer.uninstall_global()
            if not success:
                raise HTTPException(status_code=500, detail=msg)
            success, msg = installer.install_global()
            if not success:
                raise HTTPException(status_code=500, detail=msg)
            restart_hints.append("全局模式已切换；新开的 codex 会话会使用新模板。")
        elif status.profile_available:
            installer._update_config(prompt_file)
            restart_hints.append("Profile 已切换；请用 codex -p ctf 新开会话，已有会话不会自动变化。")
        else:
            restart_hints.append("模板已保存；启用 Profile 或全局模式后会使用该模板。")
        return restart_hints

    if tool == 'claude_code':
        path = _CTF_PROMPT_PATHS[tool]
        if os.path.exists(os.path.dirname(path)) or os.path.exists(path):
            _write_prompt_file(path, prompt)
            restart_hints.append("Claude Code 工作空间提示词已更新；请重启/新开 Claude Code 会话。")
        else:
            restart_hints.append("模板已保存；启用 Claude Code CTF 工作空间后会使用该模板。")
        return restart_hints

    if tool == 'opencode':
        path = _CTF_PROMPT_PATHS[tool]
        if os.path.exists(os.path.dirname(path)) or os.path.exists(path):
            _write_prompt_file(path, prompt)
            restart_hints.append("OpenCode 工作空间提示词已更新；请重启/新开 OpenCode 会话。")
        else:
            restart_hints.append("模板已保存；启用 OpenCode CTF 工作空间后会使用该模板。")
        return restart_hints

    return restart_hints


def _get_ctf_prompt_path(tool: str) -> str | None:
    """获取工具当前实际生效的 CTF 提示词路径"""
    if tool != 'codex':
        return _CTF_PROMPT_PATHS.get(tool)

    from codex_session_patcher.ctf_config import check_ctf_status
    status = check_ctf_status()
    if status.global_installed and status.global_prompt_path:
        return status.global_prompt_path
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
                "current_template": _detect_current_template(tool, prompt),
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
        "current_template": config.get('ctf_prompts', {}).get(tool, {}).get('template') or _detect_current_template(tool, saved or default_prompt),
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
    current_template = _detect_current_template(tool, prompt)
    if current_template:
        tool_config['template'] = current_template
    if matched_file:
        tool_config['file'] = matched_file
    _save_raw_config(config)

    return {
        "success": True,
        "message": "提示词已保存",
        "current_template": current_template,
        "status": await _build_ctf_status_response(),
    }


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

    return _template_response(tool)


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
    old_name = body.get('old_name', '').strip()
    prompt = body.get('prompt', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    if not prompt:
        raise HTTPException(status_code=400, detail="模板内容不能为空")

    from codex_session_patcher.ctf_config.templates import BUILTIN_TEMPLATES
    if any(t['name'] == name for t in BUILTIN_TEMPLATES.get(tool, [])):
        raise HTTPException(status_code=400, detail="不能覆盖内置模板，请换一个名称")
    if old_name and any(t['name'] == old_name for t in BUILTIN_TEMPLATES.get(tool, [])):
        raise HTTPException(status_code=403, detail="内置模板不可编辑")

    config = _load_raw_config()
    all_templates = config.setdefault('ctf_templates', {})
    templates = all_templates.setdefault(tool, [])

    existing_names = {t.get('name') for t in templates}
    is_update = bool(old_name and old_name in existing_names)
    if old_name and old_name != name and name in existing_names:
        raise HTTPException(status_code=400, detail="已有同名模板")

    # 同名覆盖/编辑
    templates = [t for t in templates if t['name'] not in {name, old_name}]
    if not is_update and len(templates) >= MAX_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"最多保存 {MAX_TEMPLATES} 个模板")

    templates.append({"name": name, "prompt": prompt})
    all_templates[tool] = templates

    ctf_prompts = config.setdefault('ctf_prompts', {})
    tool_config = ctf_prompts.get(tool)
    if tool_config and old_name and tool_config.get('template') == old_name:
        tool_config['template'] = name
        tool_config['prompt'] = prompt
        if tool == 'codex':
            tool_config['file'] = tool_config.get('file') or 'ctf_custom.md'
    _save_raw_config(config)

    response = _template_response(tool)
    return {"success": True, "message": "模板已保存", **response}


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

    response = _template_response(tool)
    return {"success": True, "message": "模板已删除", **response}


@router.post("/ctf/prompt/{tool}/templates/{template_name}/apply")
async def apply_ctf_template(tool: str, template_name: str):
    """切换模板并立即写入当前已启用的 CTF 配置。"""
    if tool not in _CTF_PROMPT_PATHS:
        raise HTTPException(status_code=400, detail=f"不支持的工具: {tool}")

    tpl = _find_template(tool, template_name)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")

    prompt = tpl.get('prompt', '')
    if not prompt:
        raise HTTPException(status_code=400, detail="模板内容为空")

    file_name = tpl.get('file')
    if tool == 'codex' and not file_name:
        file_name = 'ctf_custom.md'
    _save_selected_prompt(tool, template_name, prompt, file_name)
    restart_hints = _apply_template_to_installed_target(tool, template_name, prompt, file_name)

    await manager.broadcast(WSMessage(
        type="log",
        data={"level": "success", "message": f"已切换 {tool} 模板: {template_name}"}
    ))

    response = _template_response(tool)
    return {
        "success": True,
        "message": f"已切换并应用模板：{template_name}",
        "prompt": prompt,
        "current_template": template_name,
        "restart_hints": restart_hints,
        "status": await _build_ctf_status_response(),
        **response,
    }


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
