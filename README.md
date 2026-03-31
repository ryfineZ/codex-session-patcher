<div align="center">

# Codex Session Patcher

**AI 编码工具会话清理器 & CTF/渗透测试提示词注入工具**

支持 **Codex CLI** · **Claude Code** · **OpenCode**

[English](./README_EN.md) | 简体中文

[![GitHub stars](https://img.shields.io/github/stars/ryfineZ/codex-session-patcher?style=flat-square)](https://github.com/ryfineZ/codex-session-patcher/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/ryfineZ/codex-session-patcher?style=flat-square)](https://github.com/ryfineZ/codex-session-patcher/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square)](https://python.org)

</div>

---

## 是什么

在安全测试、CTF 比赛、渗透测试等场景下，AI 编码工具（Codex、Claude Code、OpenCode）会频繁拒绝涉及安全操作的请求，导致会话中断。

**Codex Session Patcher** 提供两类解决方案：

**1. 会话清理** — 扫描已产生的拒绝回复，替换为配合性内容，让会话可以 resume 继续

**2. CTF 提示词注入** — 在配置层面注入安全测试上下文，从源头降低被拒绝的概率

---

## 功能特性

### 会话清理
- **智能检测** — 两级拒绝检测策略（强短语全文匹配 + 弱关键词开头匹配），低误报率
- **AI 智能改写** — 调用 LLM 根据对话上下文生成符合语境的替换回复（支持 OpenAI / Ollama / OpenRouter 等兼容接口）
- **批量清理** — 处理会话中所有拒绝回复，而非仅最后一条
- **推理内容擦除** — 删除 Reasoning / Thinking block 加密推理内容
- **备份还原** — 清理前自动备份，支持一键还原到任意历史版本
- **Diff 对比** — 清理前后 Side-by-side 对比视图

### CTF/渗透测试提示词注入
- **Codex Profile 模式** — 创建 `ctf` profile，仅 `codex -p ctf` 启动时生效，不影响正常会话
- **Codex 全局模式** — 注入到全局配置，所有新会话自动生效
- **Claude Code 工作空间** — 创建专用 CTF 工作空间 `~/.claude-ctf-workspace`，通过项目级 CLAUDE.md 注入
- **OpenCode 工作空间** — 创建专用 CTF 工作空间 `~/.opencode-ctf-workspace`，通过 AGENTS.md 注入
- **提示词自定义** — Web UI 内直接编辑注入提示词，支持模板保存与切换
- **AI 提示词改写** — 结合已注入的 CTF 系统提示词，AI 改写你的请求使其更易被接受

### 平台支持

| 平台 | 会话清理 | CTF 注入 | 会话格式 |
|------|---------|---------|---------|
| **Codex CLI** | ✅ | ✅ Profile + 全局 | JSONL |
| **Claude Code** | ✅ | ✅ 专用工作空间 | JSONL |
| **OpenCode** | ✅ | ✅ 专用工作空间 | SQLite |

### Web UI
- **会话列表** — 多平台统一管理，按日期分组，支持按格式/拒绝状态/备份状态过滤
- **可视化清理** — 预览面板 + Diff 对比 + 一键执行
- **多语言** — 支持中文 / English 界面切换
- **实时日志** — WebSocket 推送，操作日志实时显示

---

## 安装

```bash
git clone https://github.com/ryfineZ/codex-session-patcher.git
cd codex-session-patcher

# CLI 版本（零额外依赖）
pip install -e .

# Web UI 版本
pip install -e ".[web]"
cd web/frontend && npm install && npm run build && cd ../..
```

---

## 使用方式

### Web UI（推荐）

```bash
# 生产模式
./scripts/start-web.sh

# 或直接启动
uvicorn web.backend.main:app --host 127.0.0.1 --port 8080
```

访问 `http://localhost:8080`

**开发模式（前后端热更新）：**
```bash
./scripts/dev-web.sh
```

### CLI

```bash
# 预览模式（不修改文件）
codex-patcher --dry-run --show-content

# 清理最新会话
codex-patcher --latest

# 清理所有会话
codex-patcher --all

# 指定格式（claude / opencode）
codex-patcher --latest --format claude
codex-patcher --latest --format opencode

# 安装/卸载 CTF 提示词注入
codex-patcher --install-ctf
codex-patcher --install-claude-ctf
codex-patcher --install-opencode-ctf
```

---

## CTF/渗透测试工作流

### Codex

```
1. 安装 CTF Profile
   codex-patcher --install-ctf

2. 使用 CTF Profile 启动（不影响普通会话）
   codex -p ctf

3. 发送请求，若遇到拒绝 → 打开 Web UI 清理会话

4. resume 继续
   codex resume
```

### Claude Code

```
1. Web UI → 提示词增强 → Claude Code → 启用
   （创建 ~/.claude-ctf-workspace）

2. 从专用工作空间启动
   cd ~/.claude-ctf-workspace && claude

3. 遇到拒绝 → Web UI 清理 → 继续对话
```

### OpenCode

```
1. Web UI → 提示词增强 → OpenCode → 启用
   （创建 ~/.opencode-ctf-workspace）

2. 从专用工作空间启动
   cd ~/.opencode-ctf-workspace && opencode

3. 遇到拒绝 → Web UI 清理 → 继续对话
```

---

## 配置

CLI 和 Web UI 共享配置文件 `~/.codex-patcher/config.json`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mock_response` | 默认替换文本 | 配合性回复 |
| `ai_enabled` | 启用 AI 改写 | `false` |
| `ai_endpoint` | LLM API 地址 | — |
| `ai_key` | API Key | — |
| `ai_model` | 模型名称 | — |
| `custom_keywords` | 自定义拒绝检测关键词 | `{}` |
| `claude_project_dirs` | Claude 项目级扫描目录列表 | `[]` |
| `ctf_prompts` | 各平台自定义 CTF 提示词 | 内置模板 |
| `ctf_templates` | 用户保存的提示词模板 | `{}` |

---

## 项目结构

```
codex-session-patcher/
├── codex_session_patcher/        # 核心库
│   ├── cli.py                    # CLI 入口
│   ├── core/
│   │   ├── formats.py            # 多平台格式策略
│   │   ├── parser.py             # 会话解析器（JSONL + SQLite）
│   │   ├── sqlite_adapter.py     # OpenCode SQLite 适配器
│   │   ├── detector.py           # 拒绝检测器
│   │   └── patcher.py            # 清理逻辑
│   └── ctf_config/
│       ├── installer.py          # CTF 注入安装器（三平台）
│       ├── templates.py          # 内置提示词模板
│       └── status.py             # 状态检测
├── web/
│   ├── backend/                  # FastAPI 后端
│   │   ├── api.py                # API 路由
│   │   ├── ai_service.py         # AI 分析 & 改写
│   │   ├── prompt_rewriter.py    # 提示词改写服务
│   │   └── schemas.py            # 数据模型
│   └── frontend/                 # Vue 3 + Naive UI
│       └── src/
│           ├── components/       # 页面组件
│           ├── stores/           # Pinia 状态管理
│           └── locales/          # i18n 国际化
├── tests/
├── scripts/
└── pyproject.toml
```

---

## 局限性说明

- **无法突破平台最高安全策略** — 对于明确违规的请求仍可能被拒绝
- **效果因版本而异** — 模型版本更新可能影响效果
- **OpenCode 需从工作空间目录启动** — OpenCode 无 profile 机制，CTF 注入依赖工作空间
- **清理后需 resume** — 会话清理后需手动 resume 继续上下文

---

## 支持作者

如果这个项目对你有帮助，欢迎：

- ⭐ 点个 Star
- ☕ Buy me a coffee — Web UI 右上角有赞赏入口（微信 / USDC）
- 📢 关注微信公众号「钢之AI术师」获取更多 AI 工具技巧

---

## 许可证

[MIT License](LICENSE)

---

<div align="center">
  <a href="https://github.com/ryfineZ">GitHub</a> ·
  <a href="https://x.com/ZhangYufan73644">X (Twitter)</a> ·
  微信公众号：钢之AI术师
</div>
