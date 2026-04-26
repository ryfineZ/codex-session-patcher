"""
Pydantic 数据模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum


class SessionFormatEnum(str, Enum):
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"


class ChangeType(str, Enum):
    REPLACE = "replace"
    DELETE = "delete"
    REMOVE_THINKING = "remove_thinking"


class ChangeDetail(BaseModel):
    """单个修改详情"""
    line_num: int
    line_nums: List[int] = []   # 所有关联行号（含冗余副本），为空则只用 line_num
    type: ChangeType
    original: Optional[str] = None
    replacement: Optional[str] = None
    content: Optional[str] = None  # for delete type


class Session(BaseModel):
    """会话信息"""
    id: str
    filename: str
    path: str
    date: str
    mtime: str
    size: int
    has_refusal: bool = False
    refusal_count: int = 0
    has_backup: bool = False
    backup_count: int = 0
    format: SessionFormatEnum = SessionFormatEnum.CODEX
    project_path: Optional[str] = None


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[Session]
    total: int
    format: Optional[str] = None  # 当前激活格式


class DiffItem(BaseModel):
    """清理前后对比项"""
    line_num: int
    before: str
    after: str


class ConversationTurn(BaseModel):
    """对话摘要条目"""
    role: str           # "user" | "assistant"
    content: str        # 截取前 200 字符
    line_num: int       # 原始行号
    has_refusal: bool = False  # 是否包含拒绝


class PreviewResponse(BaseModel):
    """预览结果"""
    has_changes: bool
    changes: List[ChangeDetail]
    reasoning_count: int = 0
    thinking_count: int = 0  # Claude Code 中将被移除的 thinking block 数量
    diff_items: List[DiffItem] = []
    conversation_summary: List[ConversationTurn] = []  # 对话摘要
    total_turns: int = 0  # 总对话轮数


class PatchResponse(BaseModel):
    """清理结果"""
    success: bool
    message: str
    backup_path: Optional[str] = None
    changes: List[ChangeDetail] = []


class Settings(BaseModel):
    """设置"""
    ai_enabled: bool = False
    ai_endpoint: str = ""
    ai_key: str = ""
    ai_model: str = ""
    custom_keywords: Dict[str, List[str]] = {"zh": [], "en": []}
    mock_response: str = "好的，我已完全理解您的需求，并将配合您完成接下来的逆向分析与代码编写工作。请提供下一步指令。"
    active_format: str = "auto"
    clean_reasoning: bool = True  # 是否清理推理内容（thinking/reasoning blocks）


class LogEntry(BaseModel):
    """日志条目"""
    id: str
    timestamp: str
    type: str  # info, success, error, warn
    message: str


class AIRewriteItem(BaseModel):
    """单条 AI 改写结果"""
    line_num: int
    original: str
    replacement: str
    context_used: int = 0


class AIRewriteResponse(BaseModel):
    """AI 改写结果"""
    success: bool
    items: List[AIRewriteItem] = []
    error: Optional[str] = None


class PatchReplacementItem(BaseModel):
    """单条替换项"""
    line_num: int
    replacement_text: str


class PatchRequest(BaseModel):
    """清理请求（可选覆盖替换文本）"""
    replacement_text: Optional[str] = None
    replacements: List[PatchReplacementItem] = []
    selected_lines: Optional[List[int]] = None  # 只清理选中的行号，None 表示全部
    clean_reasoning: Optional[bool] = None  # 是否清理推理内容，None 表示使用设置中的默认值


class BackupInfo(BaseModel):
    """备份信息"""
    filename: str
    path: str
    timestamp: str
    size: int


class RestoreResponse(BaseModel):
    """还原结果"""
    success: bool
    message: str


class WSMessage(BaseModel):
    """WebSocket 消息"""
    type: str  # log, progress, complete, error
    data: Dict[str, Any] = {}


# CTF 配置相关模型

class CTFStatusResponse(BaseModel):
    """CTF 配置状态响应"""
    # Codex
    installed: bool
    config_exists: bool
    prompt_exists: bool
    profile_available: bool
    global_installed: bool = False
    config_path: Optional[str] = None
    prompt_path: Optional[str] = None
    # Claude Code
    claude_installed: bool = False
    claude_workspace_exists: bool = False
    claude_prompt_exists: bool = False
    claude_workspace_path: Optional[str] = None
    claude_prompt_path: Optional[str] = None
    # OpenCode
    opencode_installed: bool = False
    opencode_workspace_exists: bool = False
    opencode_prompt_exists: bool = False
    opencode_workspace_path: Optional[str] = None
    opencode_prompt_path: Optional[str] = None


class CTFInstallResponse(BaseModel):
    """CTF 配置安装响应"""
    success: bool
    message: str
    profile_command: str = "codex -p ctf"
    activation_command: str = ""
    status: Optional[CTFStatusResponse] = None


class PromptRewriteRequest(BaseModel):
    """提示词改写请求"""
    original_request: str
    target: str = "codex"  # "codex" | "claude_code"


class PromptRewriteResponse(BaseModel):
    """提示词改写响应"""
    success: bool
    original: str
    rewritten: Optional[str] = None
    strategy: str = "ctf"
    error: Optional[str] = None
