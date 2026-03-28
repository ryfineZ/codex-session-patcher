"""
API 路由 — 支持 Codex CLI 和 Claude Code 双格式
"""

import os
import json
import re
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .schemas import (
    Session, SessionListResponse, SessionFormatEnum, PreviewResponse,
    PatchResponse, Settings, ChangeDetail, ChangeType, WSMessage,
    AIRewriteResponse, PatchRequest, BackupInfo, RestoreResponse, DiffItem,
    CTFStatusResponse, CTFInstallResponse, PromptRewriteRequest, PromptRewriteResponse
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


# ─── 格式解析工具 ────────────────────────────────────────────────────────────

def _resolve_format(format_str: str) -> Optional[SessionFormat]:
    """将 API 参数字符串转为 SessionFormat，'auto' 返回 None"""
    if format_str == 'codex':
        return SessionFormat.CODEX
    elif format_str == 'claude_code':
        return SessionFormat.CLAUDE_CODE
    return None  # auto


def _to_schema_format(fmt: SessionFormat) -> SessionFormatEnum:
    """将核心 SessionFormat 转为 API schema enum"""
    if fmt == SessionFormat.CLAUDE_CODE:
        return SessionFormatEnum.CLAUDE_CODE
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
        pass
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
        pass
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
    if session_format is None:
        # auto 模式：扫描两个目录
        if os.path.exists(DEFAULT_SESSION_DIR):
            scan_targets.append((DEFAULT_SESSION_DIR, SessionFormat.CODEX))
        if os.path.exists(DEFAULT_CLAUDE_SESSION_DIR):
            scan_targets.append((DEFAULT_CLAUDE_SESSION_DIR, SessionFormat.CLAUDE_CODE))
    elif session_format == SessionFormat.CODEX:
        scan_targets.append((DEFAULT_SESSION_DIR, SessionFormat.CODEX))
    elif session_format == SessionFormat.CLAUDE_CODE:
        scan_targets.append((DEFAULT_CLAUDE_SESSION_DIR, SessionFormat.CLAUDE_CODE))

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
                continue

    sessions.sort(key=lambda x: x.mtime, reverse=True)
    return sessions


def _session_core_format(session: Session) -> SessionFormat:
    """从 API Session schema 转为核心 SessionFormat"""
    if session.format == SessionFormatEnum.CLAUDE_CODE:
        return SessionFormat.CLAUDE_CODE
    return SessionFormat.CODEX


# ─── 预览 & 清理 ─────────────────────────────────────────────────────────────

def preview_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                   custom_keywords: dict = None,
                   session_format: SessionFormat = SessionFormat.CODEX) -> PreviewResponse:
    """预览会话修改"""
    changes = []
    detector = RefusalDetector(custom_keywords)
    strategy = get_format_strategy(session_format)

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

    # 检测拒绝
    assistant_msgs = strategy.get_assistant_messages(parsed_lines)
    for idx, msg in assistant_msgs:
        content = strategy.extract_text_content(msg)
        if content and detector.detect(content):
            changes.append(ChangeDetail(
                line_num=idx + 1,
                type=ChangeType.REPLACE,
                original=content[:500] + ('...' if len(content) > 500 else ''),
                replacement=mock_response
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
    )


def patch_session(file_path: str, mock_response: str = MOCK_RESPONSE,
                 custom_keywords: dict = None, create_backup: bool = True,
                 replacements: dict = None,
                 session_format: SessionFormat = SessionFormat.CODEX) -> PatchResponse:
    """执行会话清理"""
    if replacements is None:
        replacements = {}

    detector = RefusalDetector(custom_keywords)

    try:
        backup_path = None
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{file_path}.{timestamp}.bak"
            shutil.copy2(file_path, backup_path)

        parser = SessionParser(session_format=session_format)
        lines = parser.parse_session_jsonl(file_path)

        # 使用统一的清理逻辑
        cleaned_lines, modified, core_changes = clean_session_jsonl(
            lines, detector, show_content=True,
            mock_response=mock_response,
            session_format=session_format,
        )

        # 应用自定义替换（AI 改写的按行替换）
        if replacements:
            strategy = get_format_strategy(session_format)
            for idx, line in enumerate(cleaned_lines):
                line_num = line.get('_line_num', idx + 1)
                if line_num in replacements:
                    cleaned_lines[idx] = strategy.update_text_content(line, replacements[line_num])

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

        # 保存
        save_session_jsonl(cleaned_lines, file_path)

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
            pass
    return Settings()


def save_settings(settings: Settings) -> bool:
    """保存设置"""
    try:
        os.makedirs(os.path.dirname(DEFAULT_CONFIG_FILE), exist_ok=True)
        with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)
        return True
    except Exception:
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
        pass
    return diff_items


# ─── API 路由 ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(skip_check: bool = False, limit: int = 0, format: str = "auto"):
    """获取会话列表"""
    session_format = _resolve_format(format)
    sessions = list_sessions(session_format=session_format, skip_refusal_check=skip_check)
    limited_sessions = sessions[:limit] if limit > 0 else sessions
    return SessionListResponse(
        sessions=limited_sessions,
        total=len(sessions),
        format=format,
    )


def _find_session(session_id: str, session_format: Optional[SessionFormat] = None) -> Optional[Session]:
    """查找会话"""
    sessions = list_sessions(session_format=session_format, skip_refusal_check=True)
    for session in sessions:
        if session.id == session_id:
            return session
    return None


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, check_refusal: bool = True, format: str = "auto"):
    """获取单个会话详情"""
    session_format = _resolve_format(format)
    sessions = list_sessions(session_format=session_format, skip_refusal_check=not check_refusal)
    for session in sessions:
        if session.id == session_id:
            return session
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/preview", response_model=PreviewResponse)
async def preview_session_api(session_id: str):
    """预览会话修改"""
    settings = load_settings()
    fmt = _resolve_format(settings.active_format)
    sessions = list_sessions(session_format=fmt)
    for session in sessions:
        if session.id == session_id:
            core_fmt = _session_core_format(session)
            result = preview_session(
                session.path,
                settings.mock_response,
                settings.custom_keywords,
                session_format=core_fmt,
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
    raise HTTPException(status_code=404, detail="会话不存在")


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

    fmt = _resolve_format(settings.active_format)
    sessions = list_sessions(session_format=fmt)
    for session in sessions:
        if session.id == session_id:
            try:
                from .ai_service import generate_ai_rewrite
                core_fmt = _session_core_format(session)
                result = await generate_ai_rewrite(
                    session.path, settings, settings.custom_keywords,
                    session_format=core_fmt,
                )
                return result
            except Exception as e:
                return AIRewriteResponse(success=False, error=str(e))
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/patch", response_model=PatchResponse)
async def patch_session_api(session_id: str, body: PatchRequest = None):
    """执行会话清理"""
    settings = load_settings()
    fmt = _resolve_format(settings.active_format)
    sessions = list_sessions(session_format=fmt)
    for session in sessions:
        if session.id == session_id:
            mock_response = settings.mock_response

            replacements_map = {}
            if body and body.replacements:
                for item in body.replacements:
                    replacements_map[item.line_num] = item.replacement_text
            elif body and body.replacement_text:
                mock_response = body.replacement_text

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
            )

            if result.success:
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
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/sessions/{session_id}/backups")
async def list_backups(session_id: str):
    """列出会话的所有备份"""
    sessions = list_sessions(skip_refusal_check=True)
    for session in sessions:
        if session.id == session_id:
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
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/{session_id}/restore", response_model=RestoreResponse)
async def restore_session(session_id: str, backup_filename: str):
    """从备份还原会话"""
    sessions = list_sessions(skip_refusal_check=True)
    for session in sessions:
        if session.id == session_id:
            session_dir = os.path.dirname(session.path)
            backup_path = os.path.join(session_dir, backup_filename)

            if not os.path.exists(backup_path):
                return RestoreResponse(success=False, message="备份文件不存在")

            if os.path.dirname(os.path.realpath(backup_path)) != os.path.realpath(session_dir):
                return RestoreResponse(success=False, message="非法的备份路径")

            try:
                shutil.copy2(backup_path, session.path)
                await manager.broadcast(WSMessage(
                    type="log",
                    data={"level": "success", "message": f"会话 {session_id} 已从备份还原"}
                ))
                return RestoreResponse(success=True, message="还原成功")
            except Exception as e:
                return RestoreResponse(success=False, message=f"还原失败: {str(e)}")
    raise HTTPException(status_code=404, detail="会话不存在")


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

@router.get("/ctf/status", response_model=CTFStatusResponse)
async def get_ctf_status():
    """获取 CTF 配置状态（Codex + Claude Code）"""
    from codex_session_patcher.ctf_config import check_ctf_status
    status = check_ctf_status()
    return CTFStatusResponse(
        installed=status.installed,
        config_exists=status.config_exists,
        prompt_exists=status.prompt_exists,
        profile_available=status.profile_available,
        config_path=status.config_path,
        prompt_path=status.prompt_path,
        claude_installed=status.claude_installed,
        claude_workspace_exists=status.claude_workspace_exists,
        claude_prompt_exists=status.claude_prompt_exists,
        claude_workspace_path=status.claude_workspace_path,
        claude_prompt_path=status.claude_prompt_path,
    )


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
        profile_command="codex -p ctf"
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
        profile_command=""
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
    )


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
        from .prompt_rewriter import rewrite_prompt
        rewritten, strategy = await rewrite_prompt(
            request.original_request,
            settings.ai_endpoint,
            settings.ai_key,
            settings.ai_model,
            target=request.target,
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
