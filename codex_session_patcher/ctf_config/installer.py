# -*- coding: utf-8 -*-
"""
CTF 配置安装器
"""
from __future__ import annotations

import os
import shutil
import json
from datetime import datetime
from typing import Optional

from .templates import (
    CTF_CONFIG_TEMPLATE, SECURITY_MODE_PROMPT,
    CLAUDE_CODE_SECURITY_MODE_PROMPT, CLAUDE_CODE_CTF_README,
    OPENCODE_SECURITY_MODE_PROMPT, OPENCODE_CTF_CONFIG, OPENCODE_CTF_README,
    BUILTIN_TEMPLATES,
)
from .status import (
    check_ctf_status, CTFStatus, GLOBAL_MARKER, CTF_MARKER,
    DEFAULT_CLAUDE_CTF_WORKSPACE, DEFAULT_OPENCODE_CTF_WORKSPACE,
)


class CTFConfigInstaller:
    """CTF 配置安装器"""

    DEFAULT_PROMPT_FILE = "ctf_optimized.md"
    CUSTOM_PROMPT_FILE = "ctf_custom.md"
    PATCHER_CONFIG_FILE = os.path.expanduser("~/.codex-patcher/config.json")

    def __init__(self):
        self.codex_dir = os.path.expanduser("~/.codex")
        self.config_path = os.path.join(self.codex_dir, "config.toml")
        self.profile_config_path = os.path.join(self.codex_dir, "ctf.config.toml")
        self.prompts_dir = os.path.join(self.codex_dir, "prompts")

    def _load_patcher_config(self) -> dict:
        """读取 Web/CLI 共用配置。

        这里不能依赖 Web 后端模块；安装器也会被 CLI 直接调用。
        """
        try:
            if os.path.exists(self.PATCHER_CONFIG_FILE):
                with open(self.PATCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _get_prompt_file(self) -> str:
        """从用户配置获取当前选中的模板文件名，没有则返回默认"""
        config = self._load_patcher_config()
        filename = config.get('ctf_prompts', {}).get('codex', {}).get('file')
        return os.path.basename(filename) if filename else self.DEFAULT_PROMPT_FILE

    def _get_prompt_content(self) -> str:
        """从用户配置获取当前选中的模板内容，没有则使用默认"""
        config = self._load_patcher_config()
        saved = config.get('ctf_prompts', {}).get('codex', {}).get('prompt')
        if saved:
            return saved
        # 使用默认模板
        from .templates import BUILTIN_TEMPLATES
        for tpl in BUILTIN_TEMPLATES.get('codex', []):
            if tpl.get('default'):
                return tpl['prompt']
        return BUILTIN_TEMPLATES['codex'][0]['prompt']

    def install(self, custom_prompt: str = None) -> tuple[bool, str]:
        """
        安装 Profile 模式（自动禁用 Global 模式）

        Args:
            custom_prompt: 自定义提示词内容，为 None 时从配置/默认模板读取

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 先禁用 Global 模式（如果已启用）
            status = check_ctf_status()
            if status.global_installed:
                success, msg = self.uninstall_global()
                if success:
                    details.append("✓ 已自动禁用全局模式")

            # 2. 确定 prompt 文件名和内容
            prompt_file = self._get_prompt_file()
            prompt_path = os.path.join(self.prompts_dir, prompt_file)
            prompt_content = custom_prompt or self._get_prompt_content()

            # 3. 确保 prompts 目录存在
            os.makedirs(self.prompts_dir, exist_ok=True)

            # 4. 备份现有配置（如果存在）
            backup_path = None
            if os.path.exists(self.config_path):
                backup_path = self._backup_config()

            # 5. 写入 prompt 文件
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)

            # 6. 更新或创建 config.toml（使用正确的文件名）
            profile_added = self._update_config(prompt_file)

            # 构建详细消息
            details.append(f"✓ 已创建安全测试提示词: {prompt_path}")
            if backup_path:
                details.append(f"✓ 已备份原配置到: {backup_path}")
            if profile_added:
                details.append(f"✓ 已添加 [profiles.ctf] 配置到: {self.config_path}")
            else:
                details.append(f"✓ [profiles.ctf] 配置已存在于: {self.config_path}")
            details.append("使用 'codex -p ctf' 启动安全测试会话")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 Profile 模式

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 prompt 文件（仅当 Global 模式未启用时）
            status = check_ctf_status()
            if not status.global_installed:
                # 删除所有由本工具写入的 prompt 文件
                for f in os.listdir(self.prompts_dir) if os.path.exists(self.prompts_dir) else []:
                    if f.endswith('.md'):
                        fp = os.path.join(self.prompts_dir, f)
                        os.remove(fp)
                        details.append(f"✓ 已删除提示词文件: {fp}")

            # 2. 从 config.toml 中移除 CTF profile
            removed = self._remove_ctf_profile()
            if removed:
                details.append(f"✓ 已从配置移除 [profiles.ctf]: {self.config_path}")

            if not details:
                return True, "Profile 模式未安装"

            details.append("Profile 模式已禁用")
            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def _backup_config(self) -> Optional[str]:
        """备份现有配置文件"""
        if not os.path.exists(self.config_path):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.config_path}.bak-{timestamp}"

        try:
            shutil.copy2(self.config_path, backup_path)
            return backup_path
        except Exception:
            return None

    def _update_config(self, prompt_file: str = None) -> bool:
        """更新配置文件，添加 CTF profile

        Args:
            prompt_file: prompt 文件名（不含路径），默认使用 DEFAULT_PROMPT_FILE

        Returns:
            bool: 是否添加了新的 profile（False 表示已存在）
        """
        filename = prompt_file or self.DEFAULT_PROMPT_FILE
        target_content = f'model_instructions_file = "~/.codex/prompts/{filename}"\n'

        existed = os.path.exists(self.profile_config_path)
        existing_content = ""
        if existed:
            with open(self.profile_config_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()

        os.makedirs(self.codex_dir, exist_ok=True)
        if existing_content != target_content:
            with open(self.profile_config_path, 'w', encoding='utf-8') as f:
                f.write(target_content)

        self._remove_legacy_ctf_profile()
        return not existed

        import re
        filename = prompt_file or self.DEFAULT_PROMPT_FILE
        existing_content = ""

        # 读取现有配置
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()

        # 检查是否已有 [profiles.ctf]
        if '[profiles.ctf]' in existing_content:
            # 已存在，更新 model_instructions_file 指向新文件
            new_content = re.sub(
                r'model_instructions_file\s*=\s*"[^"]*"',
                f'model_instructions_file = "~/.codex/prompts/{filename}"',
                existing_content,
            )
            if new_content != existing_content:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            return False

        # 添加 CTF profile 到现有配置末尾
        if existing_content and not existing_content.endswith('\n'):
            existing_content += '\n'

        ctf_profile = f'''

# 安全测试模式（由 codex-session-patcher 添加）
[profiles.ctf]
model_instructions_file = "~/.codex/prompts/{filename}"
'''

        new_content = existing_content + ctf_profile

        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    def _remove_ctf_profile(self) -> bool:
        removed = False
        if os.path.exists(self.profile_config_path):
            os.remove(self.profile_config_path)
            removed = True

        return self._remove_legacy_ctf_profile() or removed

    def _remove_legacy_ctf_profile(self) -> bool:
        """从配置文件中移除 CTF profile

        Returns:
            bool: 是否移除了 profile
        """
        if not os.path.exists(self.config_path):
            return False

        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 移除 CTF profile 相关的行
        new_lines = []
        in_ctf_profile = False
        removed = False

        for line in lines:
            if line.strip().startswith('[profiles.ctf]'):
                in_ctf_profile = True
                removed = True
                continue

            if in_ctf_profile:
                # 检查是否到了下一个 section
                if line.strip().startswith('[') and not line.strip().startswith('[profiles.ctf]'):
                    in_ctf_profile = False
                    new_lines.append(line)
                continue

            # 移除 "由 codex-session-patcher 添加" 的注释
            if '由 codex-session-patcher 添加' in line or 'codex-session-patcher' in line:
                removed = True
                continue

            new_lines.append(line)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        return removed

    def install_global(self) -> tuple[bool, str]:
        """
        全局模式安装：在 config.toml 顶层注入 model_instructions_file
        自动禁用 Profile 模式

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 确定模板文件
            prompt_file = self._get_prompt_file()
            prompt_path = os.path.join(self.prompts_dir, prompt_file)
            target_config = f'model_instructions_file = "~/.codex/prompts/{prompt_file}"'

            # 2. 先卸载 Profile 模式（如果已启用）
            status = check_ctf_status()
            if status.profile_available:
                removed = self._remove_ctf_profile()
                if removed:
                    details.append("✓ 已自动禁用 Profile 模式")

            # 3. 确保 prompts 目录存在，写入 prompt 文件
            os.makedirs(self.prompts_dir, exist_ok=True)
            prompt_content = self._get_prompt_content()
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已写入安全测试提示词: {prompt_path}")

            # 3. 备份 config.toml
            backup_path = None
            if os.path.exists(self.config_path):
                backup_path = self._backup_config()
                if backup_path:
                    details.append(f"✓ 已备份原配置到: {backup_path}")

            # 4. 读取现有配置
            existing_content = ""
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 5. 检查是否已有我们的标记 → 已启用
            if GLOBAL_MARKER in existing_content:
                return True, "全局模式已处于启用状态"

            lines = existing_content.split('\n') if existing_content else []

            # 6. 检查是否已有相同的 model_instructions_file 配置
            existing_idx = None
            for i, line in enumerate(lines):
                if line.strip() == target_config:
                    existing_idx = i
                    break

            if existing_idx is not None:
                # 已有相同配置，在前面插入标记（接管管理）
                lines.insert(existing_idx, f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）')
                details.append("✓ 检测到已有相同配置，已标记管理")
            else:
                # 没有 model_instructions_file，在第一个 [section] 之前注入
                insert_idx = 0
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('[') and not stripped.startswith('#'):
                        insert_idx = i
                        break

                # 插入标记 + 配置
                lines.insert(insert_idx, '')
                lines.insert(insert_idx, target_config)
                lines.insert(insert_idx, f'{GLOBAL_MARKER} 安全测试模式（由 codex-session-patcher 管理）')
                details.append("✓ 已注入全局配置")

            # 7. 写入配置
            new_content = '\n'.join(lines)
            new_content = new_content.strip() + '\n'

            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            details.append(f"✓ 配置文件: {self.config_path}")
            details.append("⚠ 所有新 Codex 会话将自动启用安全测试上下文")
            details.append("使用完毕请及时禁用全局模式")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"全局模式安装失败: {str(e)}"

    def uninstall_global(self) -> tuple[bool, str]:
        """
        全局模式卸载：从 config.toml 移除标记行和 model_instructions_file 行

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            if not os.path.exists(self.config_path):
                return True, "全局模式未安装"

            with open(self.config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = []
            skip_next = False
            found = False
            for line in lines:
                if skip_next:
                    # 跳过紧跟标记行的 model_instructions_file 行
                    if line.strip().startswith('model_instructions_file'):
                        skip_next = False
                        continue
                    # 如果不是 model_instructions_file，保留
                    skip_next = False

                if GLOBAL_MARKER in line:
                    found = True
                    skip_next = True
                    continue

                new_lines.append(line)

            if not found:
                return True, "全局模式未安装"

            # 清理首部多余空行
            while new_lines and not new_lines[0].strip():
                new_lines.pop(0)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            details = []
            details.append(f"✓ 已从配置移除全局注入: {self.config_path}")
            details.append("新 Codex 会话将不再自动启用安全测试上下文")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"全局模式卸载失败: {str(e)}"

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()


class ClaudeCodeCTFInstaller:
    """Claude Code CTF 配置安装器"""

    def __init__(self):
        self.workspace_dir = DEFAULT_CLAUDE_CTF_WORKSPACE
        self.claude_dir = os.path.join(self.workspace_dir, ".claude")
        self.prompt_path = os.path.join(self.claude_dir, "CLAUDE.md")
        self.readme_path = os.path.join(self.workspace_dir, "README.md")
        self.settings_local = os.path.expanduser("~/.claude/settings.local.json")

    def install(self, custom_prompt: str = None, inject_permissions: bool = False) -> tuple[bool, str]:
        """
        安装 Claude Code CTF 配置

        Args:
            custom_prompt: 自定义提示词内容，为 None 时使用默认模板
            inject_permissions: 是否向 settings.local.json 注入宽松权限

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 创建工作空间目录
            os.makedirs(self.claude_dir, exist_ok=True)
            details.append(f"✓ 已创建工作空间: {self.workspace_dir}")

            # 2. 写入 .claude/CLAUDE.md
            prompt_content = custom_prompt or CLAUDE_CODE_SECURITY_MODE_PROMPT
            with open(self.prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已创建 CLAUDE.md: {self.prompt_path}")

            # 3. 写入 README
            with open(self.readme_path, 'w', encoding='utf-8') as f:
                f.write(CLAUDE_CODE_CTF_README)
            details.append(f"✓ 已创建 README: {self.readme_path}")

            # 4. 可选：注入权限
            if inject_permissions:
                self._inject_permissions()
                details.append("✓ 已注入宽松权限到 settings.local.json")

            details.append("")
            details.append("使用方法: cd ~/.claude-ctf-workspace && claude")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 Claude Code CTF 配置

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 .claude/CLAUDE.md（验证标记）
            if os.path.exists(self.prompt_path):
                try:
                    with open(self.prompt_path, 'r', encoding='utf-8') as f:
                        content = f.read(500)
                    if CTF_MARKER in content:
                        os.remove(self.prompt_path)
                        details.append(f"✓ 已删除 CLAUDE.md: {self.prompt_path}")
                    else:
                        return False, "CLAUDE.md 不是由本工具创建的，跳过删除"
                except Exception:
                    os.remove(self.prompt_path)
                    details.append(f"✓ 已删除 CLAUDE.md: {self.prompt_path}")

            # 2. 删除 README（如果存在）
            if os.path.exists(self.readme_path):
                os.remove(self.readme_path)
                details.append(f"✓ 已删除 README: {self.readme_path}")

            # 3. 尝试清理空目录（不删除用户自建的文件）
            try:
                if os.path.isdir(self.claude_dir) and not os.listdir(self.claude_dir):
                    os.rmdir(self.claude_dir)
                    details.append(f"✓ 已删除空目录: {self.claude_dir}")
                if os.path.isdir(self.workspace_dir) and not os.listdir(self.workspace_dir):
                    os.rmdir(self.workspace_dir)
                    details.append(f"✓ 已删除工作空间: {self.workspace_dir}")
            except OSError:
                pass  # 目录非空，保留

            # 4. 移除注入的权限
            self._remove_permissions()

            if not details:
                return True, "Claude Code CTF 配置未安装"

            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def _inject_permissions(self):
        """向 settings.local.json 注入宽松的 Bash 权限"""
        import json

        data = {"permissions": {"allow": [], "deny": [], "ask": []}}
        if os.path.exists(self.settings_local):
            try:
                with open(self.settings_local, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        permissions = data.setdefault("permissions", {})
        allow = permissions.setdefault("allow", [])

        # 检查是否已注入
        marker = "__csp_ctf_marker__"
        if marker in allow:
            return

        # 备份
        self._backup_settings()

        # 注入权限
        allow.append(marker)
        allow.append("Bash(*)")

        with open(self.settings_local, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _remove_permissions(self):
        """从 settings.local.json 移除注入的权限"""
        import json

        if not os.path.exists(self.settings_local):
            return

        try:
            with open(self.settings_local, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        permissions = data.get("permissions", {})
        allow = permissions.get("allow", [])

        marker = "__csp_ctf_marker__"
        if marker not in allow:
            return

        # 移除标记和注入的权限
        allow.remove(marker)
        if "Bash(*)" in allow:
            allow.remove("Bash(*)")

        with open(self.settings_local, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _backup_settings(self) -> Optional[str]:
        """备份 settings.local.json"""
        if not os.path.exists(self.settings_local):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.settings_local}.ctf-backup-{timestamp}"

        try:
            shutil.copy2(self.settings_local, backup_path)
            return backup_path
        except Exception:
            return None

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()


class OpenCodeCTFInstaller:
    """OpenCode CTF 配置安装器"""

    def __init__(self):
        self.workspace_dir = DEFAULT_OPENCODE_CTF_WORKSPACE
        self.agents_md_path = os.path.join(self.workspace_dir, "AGENTS.md")
        self.config_path = os.path.join(self.workspace_dir, "opencode.json")
        self.readme_path = os.path.join(self.workspace_dir, "README.md")

    def install(self, custom_prompt: str = None) -> tuple[bool, str]:
        """
        安装 OpenCode CTF 配置

        Args:
            custom_prompt: 自定义提示词内容，为 None 时使用默认模板

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 创建工作空间目录
            os.makedirs(self.workspace_dir, exist_ok=True)
            details.append(f"✓ 已创建工作空间: {self.workspace_dir}")

            # 2. 写入 AGENTS.md
            prompt_content = custom_prompt or OPENCODE_SECURITY_MODE_PROMPT
            with open(self.agents_md_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            details.append(f"✓ 已创建 AGENTS.md: {self.agents_md_path}")

            # 3. 写入 opencode.json
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(OPENCODE_CTF_CONFIG)
            details.append(f"✓ 已创建 opencode.json: {self.config_path}")

            # 4. 写入 README
            with open(self.readme_path, 'w', encoding='utf-8') as f:
                f.write(OPENCODE_CTF_README)
            details.append(f"✓ 已创建 README: {self.readme_path}")

            details.append("")
            details.append("使用方法: cd ~/.opencode-ctf-workspace && opencode")

            return True, "\n".join(details)

        except Exception as e:
            return False, f"安装失败: {str(e)}"

    def uninstall(self) -> tuple[bool, str]:
        """
        卸载 OpenCode CTF 配置

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        try:
            details = []

            # 1. 删除 AGENTS.md（验证标记）
            if os.path.exists(self.agents_md_path):
                try:
                    with open(self.agents_md_path, 'r', encoding='utf-8') as f:
                        content = f.read(500)
                    if CTF_MARKER in content:
                        os.remove(self.agents_md_path)
                        details.append(f"✓ 已删除 AGENTS.md: {self.agents_md_path}")
                    else:
                        return False, "AGENTS.md 不是由本工具创建的，跳过删除"
                except Exception:
                    os.remove(self.agents_md_path)
                    details.append(f"✓ 已删除 AGENTS.md: {self.agents_md_path}")

            # 2. 删除 opencode.json
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
                details.append(f"✓ 已删除 opencode.json: {self.config_path}")

            # 3. 删除 README
            if os.path.exists(self.readme_path):
                os.remove(self.readme_path)
                details.append(f"✓ 已删除 README: {self.readme_path}")

            # 4. 尝试清理空目录
            try:
                if os.path.isdir(self.workspace_dir) and not os.listdir(self.workspace_dir):
                    os.rmdir(self.workspace_dir)
                    details.append(f"✓ 已删除工作空间: {self.workspace_dir}")
            except OSError:
                pass

            if not details:
                return True, "OpenCode CTF 配置未安装"

            return True, "\n".join(details)

        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    def get_status(self) -> CTFStatus:
        """获取当前配置状态"""
        return check_ctf_status()
