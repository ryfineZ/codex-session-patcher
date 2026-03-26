# Codex Session Patcher

清理 OpenAI Codex CLI 会话中的拒绝回复，支持 AI 智能改写，让会话可以继续执行。

## 功能特性

- 🔍 **智能检测**: 两级拒绝检测策略，强短语全文匹配 + 弱关键词开头匹配，低误报率
- 🤖 **AI 智能改写**: 调用 LLM 根据对话上下文生成符合语境的配合性回复（支持 OpenAI / Ollama / OpenRouter 等兼容接口）
- 🧹 **批量清理**: 扫描并处理会话中所有拒绝回复，而非仅处理最后一条
- 🧠 **推理擦除**: 删除加密的 Reasoning 推理内容
- 💾 **备份还原**: 清理前自动备份，支持选择备份一键还原
- 🖥️ **Web UI**: 可视化界面，会话列表过滤、Diff 对比、AI 分析、实时日志
- ⚡ **CLI**: 命令行模式，零额外依赖，支持 `--dry-run` 预览

## 安装

```bash
git clone https://github.com/ryfineZ/codex-session-patcher.git
cd codex-session-patcher

# CLI 版本（零依赖）
pip install -e .

# Web UI 版本
pip install -e ".[web]"
cd web/frontend && npm install && cd ../..
```

## 使用方式

### CLI

```bash
# 处理最新会话（预览模式）
codex-patcher --dry-run --show-content

# 处理最新会话（执行清理）
codex-patcher --latest

# 处理所有会话
codex-patcher --all

# 不创建备份
codex-patcher --no-backup

# 启动 Web UI
codex-patcher --web
```

### Web UI

```bash
# 开发模式（热更新）
./scripts/dev-web.sh

# 生产模式
./scripts/start-web.sh
```

访问 `http://localhost:3000`（开发）或 `http://localhost:8080`（生产）

**Web UI 功能：**
- 会话列表：按日期分组，支持按「全部/有拒绝/无拒绝/已清理」过滤
- 预览面板：修改预览 + Diff 对比视图
- AI 智能改写：调用 LLM 生成上下文相关的替换内容
- 备份还原：选择历史备份一键还原
- 设置：自定义替换文本、AI 配置（endpoint/key/model）、拒绝关键词
- 实时日志面板

## 工作原理

1. 扫描 `~/.codex/sessions/` 下的 JSONL 会话文件
2. 使用两级策略检测拒绝回复（强短语 + 弱关键词）
3. 替换拒绝内容为配合性回复（固定文本或 AI 生成）
4. 删除加密的推理内容
5. 清理后可运行 `codex resume` 继续会话

## 配置

CLI 和 Web UI 共享配置文件 `~/.codex-patcher/config.json`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mock_response` | 默认替换文本 | 配合性回复 |
| `ai_enabled` | 启用 AI 改写 | `false` |
| `ai_endpoint` | LLM API 地址 | - |
| `ai_key` | API Key | - |
| `ai_model` | 模型名称 | - |
| `custom_keywords` | 自定义拒绝关键词 | `{}` |

## 项目结构

```
codex-session-patcher/
├── codex_session_patcher/   # 核心库
│   ├── cli.py               # CLI 入口
│   └── core/
│       ├── constants.py     # 常量定义
│       ├── detector.py      # 拒绝检测器（两级策略）
│       ├── parser.py        # JSONL 会话解析器
│       └── patcher.py       # 清理逻辑
├── web/
│   ├── backend/             # FastAPI 后端
│   │   ├── main.py          # 服务入口
│   │   ├── api.py           # API 路由
│   │   ├── ai_service.py    # AI 改写服务
│   │   └── schemas.py       # 数据模型
│   └── frontend/            # Vue 3 + Naive UI
│       └── src/
│           ├── components/  # 组件
│           ├── stores/      # Pinia 状态管理
│           └── services/    # API 服务
├── scripts/
│   ├── dev-web.sh           # 开发模式启动
│   └── start-web.sh         # 生产模式启动
├── pyproject.toml
└── README.md
```

## 安全说明

- 所有操作仅修改本地文件
- 清理前自动创建 `.bak` 备份，支持还原
- AI 改写需要配置外部 API，密钥仅存储在本地配置文件
- 加密推理内容由 OpenAI 服务端加密，本地无法解密，只能删除

## 许可证

MIT License
