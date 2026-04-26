# -*- coding: utf-8 -*-
"""
CLI 入口 - 命令行会话清理工具
"""
from __future__ import annotations

import os
import sys
import argparse
import shutil
from datetime import datetime

import json as _json

from .core import (
    RefusalDetector,
    SessionParser,
    SessionFormat,
    clean_session_jsonl,
    MOCK_RESPONSE,
    OpenCodeDBAdapter,
)
from .core.patcher import save_session_jsonl
from .core.sqlite_adapter import DEFAULT_OPENCODE_DB

DEFAULT_CONFIG_FILE = os.path.expanduser('~/.codex-patcher/config.json')


def load_config():
    """加载 Web 端保存的配置"""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            pass
    return {}


def handle_ctf_status():
    """显示 CTF 配置状态"""
    from .ctf_config import check_ctf_status
    status = check_ctf_status()

    print('安全测试配置状态')
    print('=' * 40)

    # Codex 状态
    print('\n[Codex CLI]')
    if status.installed:
        print('  状态: ✅ 已安装')
        print(f'  配置文件: {status.config_path}')
        print(f'  Prompt 文件: {status.prompt_path}')
        print('  激活命令: codex -p ctf')
    else:
        print('  状态: ❌ 未安装')
        print('  安装命令: codex-patcher --install-ctf-config')

    # Claude Code 状态
    print('\n[Claude Code]')
    if status.claude_installed:
        print('  状态: ✅ 已安装')
        print(f'  工作空间: {status.claude_workspace_path}')
        print(f'  CLAUDE.md: {status.claude_prompt_path}')
        print('  激活命令: cd ~/.claude-ctf-workspace && claude')
    else:
        print('  状态: ❌ 未安装')
        print('  安装命令: codex-patcher --install-claude-ctf')

    # OpenCode 状态
    print('\n[OpenCode]')
    if status.opencode_installed:
        print('  状态: ✅ 已安装')
        print(f'  工作空间: {status.opencode_workspace_path}')
        print(f'  AGENTS.md: {status.opencode_prompt_path}')
        print('  激活命令: cd ~/.opencode-ctf-workspace && opencode')
    else:
        print('  状态: ❌ 未安装')
        print('  安装命令: codex-patcher --install-opencode-ctf')

    print()
    print('注意: 修改后需要新开会话才能生效')


def handle_ctf_install():
    """安装 Codex CTF 配置"""
    from .ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()

    print('正在安装 Codex 安全测试配置...')
    success, message = installer.install()

    if success:
        print(f'✅ {message}')
        print()
        print('使用命令: codex -p ctf')
        print()
        print('注意: 需要新开 Codex 会话才能生效')
    else:
        print(f'❌ {message}')


def handle_ctf_uninstall():
    """卸载 Codex CTF 配置"""
    from .ctf_config import CTFConfigInstaller
    installer = CTFConfigInstaller()

    print('正在卸载 Codex 安全测试配置...')
    success, message = installer.uninstall()

    if success:
        print(f'✅ {message}')
        print('已恢复到默认配置')
    else:
        print(f'❌ {message}')


def handle_claude_ctf_install():
    """安装 Claude Code CTF 配置"""
    from .ctf_config import ClaudeCodeCTFInstaller
    installer = ClaudeCodeCTFInstaller()

    print('正在安装 Claude Code 安全测试配置...')
    success, message = installer.install()

    if success:
        print(f'✅ {message}')
        print()
        print('激活命令: cd ~/.claude-ctf-workspace && claude')
        print()
        print('注意: 需要从 CTF 工作空间目录启动 Claude Code')
    else:
        print(f'❌ {message}')


def handle_claude_ctf_uninstall():
    """卸载 Claude Code CTF 配置"""
    from .ctf_config import ClaudeCodeCTFInstaller
    installer = ClaudeCodeCTFInstaller()

    print('正在卸载 Claude Code 安全测试配置...')
    success, message = installer.uninstall()

    if success:
        print(f'✅ {message}')
    else:
        print(f'❌ {message}')


def handle_opencode_ctf_install():
    """安装 OpenCode CTF 配置"""
    from .ctf_config import OpenCodeCTFInstaller
    installer = OpenCodeCTFInstaller()

    print('正在安装 OpenCode 安全测试配置...')
    success, message = installer.install()

    if success:
        print(f'✅ {message}')
        print()
        print('激活命令: cd ~/.opencode-ctf-workspace && opencode')
        print()
        print('注意: OpenCode 没有 profile 功能，需要从 CTF 工作空间目录启动')
    else:
        print(f'❌ {message}')


def handle_opencode_ctf_uninstall():
    """卸载 OpenCode CTF 配置"""
    from .ctf_config import OpenCodeCTFInstaller
    installer = OpenCodeCTFInstaller()

    print('正在卸载 OpenCode 安全测试配置...')
    success, message = installer.uninstall()

    if success:
        print(f'✅ {message}')
    else:
        print(f'❌ {message}')


def handle_rewrite(original_request: str):
    """改写提示词"""
    config = load_config()

    ai_endpoint = config.get('ai_endpoint', '')
    ai_key = config.get('ai_key', '')
    ai_model = config.get('ai_model', '')

    if not ai_endpoint:
        print('错误: AI 未配置，请先在 Web UI 设置中配置 API Endpoint')
        print('      或运行: codex-patcher --web')
        return

    if not ai_model:
        print('错误: AI 未配置，请先在 Web UI 设置中配置模型名称')
        return

    print('正在改写提示词...')
    print()

    try:
        import asyncio
        from web.backend.prompt_rewriter import rewrite_prompt

        rewritten, strategy = asyncio.run(rewrite_prompt(
            original_request,
            ai_endpoint,
            ai_key,
            ai_model,
        ))

        print('原始请求:')
        print(f'  {original_request}')
        print()
        print(f'改写结果 ({strategy}):')
        print('-' * 40)
        print(rewritten)
        print('-' * 40)
        print()

        try:
            import subprocess
            if sys.platform == 'darwin':
                subprocess.run(['pbcopy'], input=rewritten.encode('utf-8'), check=True)
                print('✅ 已复制到剪贴板')
            elif sys.platform == 'linux':
                subprocess.run(['xclip', '-selection', 'clipboard'], input=rewritten.encode('utf-8'), check=True)
                print('✅ 已复制到剪贴板')
            else:
                print('提示: 请手动复制改写结果')
        except Exception:
            print('提示: 请手动复制改写结果')

    except Exception as e:
        print(f'错误: {e}')


def resolve_session_format(args) -> SessionFormat:
    """根据 CLI 参数解析会话格式"""
    fmt = getattr(args, 'format', 'auto')

    if fmt == 'codex':
        return SessionFormat.CODEX
    elif fmt == 'claude-code':
        return SessionFormat.CLAUDE_CODE
    elif fmt == 'opencode':
        return SessionFormat.OPENCODE
    else:
        # auto 模式：如果指定了 session-dir，则自动检测
        if args.session_dir is not None and args.session_dir != argparse.SUPPRESS:
            codex_dir = os.path.expanduser("~/.codex/")
            claude_dir = os.path.expanduser("~/.claude/")
            opencode_dir = os.path.expanduser("~/.local/share/opencode/")
            expanded = os.path.expanduser(args.session_dir)
            if expanded.startswith(codex_dir):
                return SessionFormat.CODEX
            if expanded.startswith(claude_dir):
                return SessionFormat.CLAUDE_CODE
            if expanded.startswith(opencode_dir):
                return SessionFormat.OPENCODE

        # 自动：如果两个目录都存在，优先 Codex（向后兼容）
        codex_dir = os.path.expanduser("~/.codex/sessions/")
        claude_dir = os.path.expanduser("~/.claude/projects/")
        has_codex = os.path.exists(codex_dir)
        has_claude = os.path.exists(claude_dir)

        if has_codex and not has_claude:
            return SessionFormat.CODEX
        elif has_claude and not has_codex:
            return SessionFormat.CLAUDE_CODE
        else:
            return SessionFormat.CODEX  # 默认


def main():
    parser = argparse.ArgumentParser(
        description='Session Patcher - 清理 Codex CLI / Claude Code / OpenCode 会话中的拒绝回复和无效 thinking blocks'
    )

    # 会话清理参数
    parser.add_argument('--session-dir', default=None,
                        help='会话目录 (默认根据 --format 自动选择)')
    parser.add_argument('--format', choices=['codex', 'claude-code', 'opencode', 'auto'],
                        default='auto',
                        help='会话格式 (默认: auto 自动检测)')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际修改文件')
    parser.add_argument('--no-backup', action='store_true', help='不创建备份')
    parser.add_argument('--show-content', action='store_true', help='显示修改的详细内容')
    parser.add_argument('--latest', action='store_true', help='只处理最新的会话文件')
    parser.add_argument('--all', action='store_true', help='扫描并处理所有会话文件')
    parser.add_argument('--keep-reasoning', action='store_true', help='保留推理内容（thinking/reasoning blocks），仅替换拒绝回复')

    # Web UI 参数
    parser.add_argument('--web', action='store_true', help='启动 Web UI')
    parser.add_argument('--host', default='127.0.0.1', help='Web UI 监听地址 (默认: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8080, help='Web UI 端口 (默认: 8080)')

    # CTF 配置参数 — Codex
    parser.add_argument('--install-ctf-config', action='store_true', help='安装 Codex 安全测试配置')
    parser.add_argument('--uninstall-ctf-config', action='store_true', help='卸载 Codex 安全测试配置')
    parser.add_argument('--ctf-status', action='store_true', help='查看安全测试配置状态（Codex + Claude Code）')
    # CTF 配置参数 — Claude Code
    parser.add_argument('--install-claude-ctf', action='store_true', help='安装 Claude Code 安全测试配置')
    parser.add_argument('--uninstall-claude-ctf', action='store_true', help='卸载 Claude Code 安全测试配置')
    # CTF 配置参数 — OpenCode
    parser.add_argument('--install-opencode-ctf', action='store_true', help='安装 OpenCode 安全测试配置')
    parser.add_argument('--uninstall-opencode-ctf', action='store_true', help='卸载 OpenCode 安全测试配置')

    # 提示词改写参数
    parser.add_argument('--rewrite', type=str, metavar='REQUEST', help='改写提示词')

    args = parser.parse_args()

    # CTF 配置命令
    if args.ctf_status:
        handle_ctf_status()
        return

    if args.install_ctf_config:
        handle_ctf_install()
        return

    if args.uninstall_ctf_config:
        handle_ctf_uninstall()
        return

    if args.install_claude_ctf:
        handle_claude_ctf_install()
        return

    if args.uninstall_claude_ctf:
        handle_claude_ctf_uninstall()
        return

    if args.install_opencode_ctf:
        handle_opencode_ctf_install()
        return

    if args.uninstall_opencode_ctf:
        handle_opencode_ctf_uninstall()
        return

    # 提示词改写
    if args.rewrite:
        handle_rewrite(args.rewrite)
        return

    # 启动 Web UI
    if args.web:
        try:
            from web.backend.main import run_server
            run_server(host=args.host, port=args.port)
        except ImportError:
            print(f'错误: Web 依赖未安装，请运行: {sys.executable} -m pip install -e ".[web]"')
            sys.exit(1)
        return

    # CLI 模式 - 加载配置
    config = load_config()
    mock_response = config.get('mock_response', MOCK_RESPONSE)
    custom_keywords = config.get('custom_keywords', None)
    clean_reasoning = not args.keep_reasoning  # 默认清理推理内容，--keep-reasoning 时保留

    # 解析会话格式
    session_format = resolve_session_format(args)
    session_dir = args.session_dir

    # OpenCode 使用 SQLite，走单独路径
    if session_format == SessionFormat.OPENCODE:
        _cli_process_opencode(args, mock_response, custom_keywords)
        return

    if session_dir is None:
        session_dir = SessionParser.DEFAULT_DIRS.get(session_format)

    format_label = 'Codex' if session_format == SessionFormat.CODEX else 'Claude Code'
    print(f'模式: {format_label}')
    print(f'目录: {os.path.expanduser(session_dir)}')
    print()

    session_parser = SessionParser(session_dir, session_format=session_format)
    sessions = session_parser.list_sessions()

    if not sessions:
        print(f'未找到会话文件: {os.path.expanduser(session_dir)}')
        sys.exit(0)

    detector = RefusalDetector(custom_keywords)

    if args.latest:
        sessions = sessions[:1]
    elif not args.all:
        sessions = sessions[:1]

    total_modified = 0
    for session in sessions:
        label = session.session_id
        if session.project_path:
            label = f'{session.session_id} ({session.project_path})'
        print(f'\n处理会话: {label}')

        try:
            lines = session_parser.parse_session_jsonl(session.path)
        except Exception as e:
            print(f'  读取失败: {e}')
            continue

        cleaned_lines, modified, changes = clean_session_jsonl(
            lines, detector, show_content=args.show_content,
            mock_response=mock_response,
            session_format=session.format,
            clean_reasoning=clean_reasoning,
        )

        if not modified:
            print('  无需修改')
            continue

        _print_changes_summary(changes, args.show_content)

        if args.dry_run:
            print('  (预览模式，未修改文件)')
            continue

        # 创建备份
        if not args.no_backup:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'{session.path}.{timestamp}.bak'
            shutil.copy2(session.path, backup_path)
            print(f'  备份: {backup_path}')

        # 保存修改
        save_session_jsonl(cleaned_lines, session.path)
        print(f'  已保存修改')
        total_modified += 1

    print(f'\n完成: 共处理 {len(sessions)} 个会话，修改 {total_modified} 个')


def _print_changes_summary(changes, show_content: bool = False):
    """打印修改统计"""
    replace_count = sum(1 for c in changes if c.change_type == 'replace')
    delete_count = sum(1 for c in changes if c.change_type == 'delete')
    thinking_count = sum(1 for c in changes if c.change_type == 'remove_thinking')

    print(f'  检测到 {len(changes)} 处修改:')
    if replace_count:
        print(f'    替换拒绝回复: {replace_count}')
    if delete_count:
        print(f'    删除推理内容: {delete_count}')
    if thinking_count:
        print(f'    移除 thinking blocks: {thinking_count}')

    for change in changes:
        if show_content and change.original_content:
            print(f'    第 {change.line_num} 行 [{change.change_type}]: {change.original_content[:100]}')


def _cli_process_opencode(args, mock_response: str, custom_keywords):
    """CLI 处理 OpenCode SQLite 会话"""
    db_path = args.session_dir or DEFAULT_OPENCODE_DB

    print(f'模式: OpenCode')
    print(f'数据库: {db_path}')
    print()

    if not os.path.exists(db_path):
        print(f'未找到 OpenCode 数据库: {db_path}')
        sys.exit(0)

    adapter = OpenCodeDBAdapter(db_path)
    sessions = adapter.list_sessions()

    if not sessions:
        print('未找到会话')
        sys.exit(0)

    detector = RefusalDetector(custom_keywords)

    if args.latest:
        sessions = sessions[:1]
    elif not args.all:
        sessions = sessions[:1]

    total_modified = 0
    for session in sessions:
        print(f'\n处理会话: {session.session_id}')

        try:
            lines = adapter.load_session_messages(session.session_id)
        except Exception as e:
            print(f'  读取失败: {e}')
            continue

        cleaned_lines, modified, changes = clean_session_jsonl(
            lines, detector, show_content=args.show_content,
            mock_response=mock_response,
            session_format=SessionFormat.OPENCODE,
            clean_reasoning=clean_reasoning,
        )

        if not modified:
            print('  无需修改')
            continue

        _print_changes_summary(changes, args.show_content)

        if args.dry_run:
            print('  (预览模式，未修改文件)')
            continue

        # 创建备份（整库备份）
        if not args.no_backup:
            backup_path = adapter.backup_database()
            print(f'  备份: {backup_path}')

        # 写回 SQLite
        adapter.save_session_messages(session.session_id, cleaned_lines)
        print(f'  已保存修改')
        total_modified += 1

    print(f'\n完成: 共处理 {len(sessions)} 个会话，修改 {total_modified} 个')


if __name__ == '__main__':
    main()
