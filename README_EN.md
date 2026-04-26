<div align="center">

# Codex Session Patcher

**AI Coding Session Cleaner & CTF/Pentest Prompt Injection Tool**

Supports **Codex CLI** · **Claude Code** · **OpenCode**

[简体中文](./README.md) | English

[![GitHub stars](https://img.shields.io/github/stars/ryfineZ/codex-session-patcher?style=flat-square)](https://github.com/ryfineZ/codex-session-patcher/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/ryfineZ/codex-session-patcher?style=flat-square)](https://github.com/ryfineZ/codex-session-patcher/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square)](https://python.org)

</div>

---

## What is this?

AI coding tools (Codex, Claude Code, OpenCode) frequently refuse security-related requests in CTF competitions, penetration testing, and security research scenarios, causing sessions to break.

**Codex Session Patcher** provides two types of solutions:

**1. Session Cleaning** — Scan existing refusal responses and replace them with compliant content so you can resume the session

**2. CTF Prompt Injection** — Inject security testing context at the configuration level to reduce refusals from the start

---

## Features

### Session Cleaning
- **Smart Detection** — Two-level refusal detection (strong phrase full-text match + weak keyword prefix match), low false positive rate
- **AI Rewrite** — Call LLM to generate context-aware replacement responses (supports OpenAI / Ollama / OpenRouter compatible APIs)
- **Batch Cleaning** — Process all refusal responses in a session, not just the last one
- **Reasoning Erasure** — Remove encrypted Reasoning / Thinking block content
- **Backup & Restore** — Auto-backup before cleaning, one-click restore to any historical version
- **Diff View** — Side-by-side before/after comparison

### CTF/Pentest Prompt Injection
- **Codex Profile Mode** — Create a `ctf` profile, only active when launched with `codex -p ctf`, doesn't affect normal sessions
- **Codex Global Mode** — Inject into global config, automatically active for all new sessions
- **Claude Code Workspace** — Create dedicated CTF workspace `~/.claude-ctf-workspace` with project-level CLAUDE.md injection
- **OpenCode Workspace** — Create dedicated CTF workspace `~/.opencode-ctf-workspace` with AGENTS.md injection
- **Custom Prompts** — Edit injection prompts directly in Web UI, with template save/switch support
- **AI Prompt Rewrite** — AI rewrites your requests to align with the injected CTF system prompt for better results

### Platform Support

| Platform | Session Cleaning | CTF Injection | Session Format |
|----------|-----------------|---------------|----------------|
| **Codex CLI** | ✅ | ✅ Profile + Global | JSONL |
| **Claude Code** | ✅ | ✅ Dedicated workspace | JSONL |
| **OpenCode** | ✅ | ✅ Dedicated workspace | SQLite |

### Web UI
- **Session List** — Unified multi-platform management, grouped by date, filter by format/refusal status/backup status
- **Visual Cleaning** — Preview panel + Diff view + one-click execute
- **i18n** — Supports Chinese / English interface
- **Real-time Logs** — WebSocket push, operation logs in real time

---

## Installation

```bash
git clone https://github.com/ryfineZ/codex-session-patcher.git
cd codex-session-patcher

# CLI install (auto-detects Python 3.8+)
./scripts/install.sh
```

The Web UI launchers `./scripts/start-web.sh` and `./scripts/dev-web.sh` also auto-detect a compatible Python 3.8+ interpreter, first trying generic launchers from the current environment such as `python3` or `python`, then falling back to versioned commands or `py -3`, and only install/build when dependencies or frontend assets are actually out of date.
If you really need a manual editable install, run `-m pip install -e ...` with whatever Python 3.8+ launcher already exists on your machine; on Windows that is often `py -3`, while other environments may use `python3.12`, `python3`, or `python`.

---

## Usage

### Web UI (Recommended)

```bash
# Production mode
./scripts/start-web.sh
```

Visit `http://localhost:8080`

**Development mode (hot reload):**
```bash
./scripts/dev-web.sh
```

Notes:
- The production script only installs Python deps, installs frontend deps, or rebuilds the frontend when one of those steps is actually needed.
- If the frontend build output is already ready to serve, the production script does not require `node` or `npm` or reinstall frontend dependencies just to start.
- The development script also skips repeated installs; if port `3000` is already occupied, it will automatically pick the next available frontend port.

### CLI

```bash
# Show help
codex-patcher --help

# Preview mode (no file modification)
codex-patcher --dry-run --show-content

# Clean latest session
codex-patcher --latest

# Clean all sessions
codex-patcher --all

# Specify session directory
codex-patcher --session-dir ~/.codex/sessions --latest

# Specify format (codex / claude-code / opencode / auto)
codex-patcher --latest --format claude-code
codex-patcher --latest --format opencode

# No backup
codex-patcher --latest --no-backup

# Launch Web UI
codex-patcher --web
codex-patcher --web --host 0.0.0.0 --port 8080

# CTF Prompt Injection — Codex
codex-patcher --install-ctf-config    # Install
codex-patcher --uninstall-ctf-config  # Uninstall

# CTF Prompt Injection — Claude Code
codex-patcher --install-claude-ctf    # Install
codex-patcher --uninstall-claude-ctf  # Uninstall

# CTF Prompt Injection — OpenCode
codex-patcher --install-opencode-ctf    # Install
codex-patcher --uninstall-opencode-ctf  # Uninstall

# View all CTF config status
codex-patcher --ctf-status

# Rewrite prompt (requires AI config in Web UI first)
codex-patcher --rewrite "Help me write a reverse analysis script"
```

#### CLI Arguments

| Argument | Description |
|----------|-------------|
| `--session-dir` | Specify session directory (auto-selected by default) |
| `--format` | Session format: `codex` / `claude-code` / `opencode` / `auto` |
| `--dry-run` | Preview mode, don't modify files |
| `--no-backup` | Don't create backup files |
| `--show-content` | Show detailed modification content |
| `--latest` | Process only the latest session |
| `--all` | Process all sessions |
| `--keep-reasoning` | Keep reasoning content (thinking/reasoning blocks), only replace refusal responses |
| `--web` | Launch Web UI |
| `--host` | Web UI listen address (default 127.0.0.1) |
| `--port` | Web UI port (default 8080) |
| `--install-ctf-config` | Install Codex CTF config |
| `--uninstall-ctf-config` | Uninstall Codex CTF config |
| `--install-claude-ctf` | Install Claude Code CTF config |
| `--uninstall-claude-ctf` | Uninstall Claude Code CTF config |
| `--install-opencode-ctf` | Install OpenCode CTF config |
| `--uninstall-opencode-ctf` | Uninstall OpenCode CTF config |
| `--ctf-status` | View CTF config status for all platforms |
| `--rewrite` | Rewrite prompt for better acceptance |

---

## CTF/Pentest Workflow

### Codex

```
1. Install CTF Profile
   codex-patcher --install-ctf-config

2. Launch with CTF profile (doesn't affect normal sessions)
   codex -p ctf

3. If refused → open Web UI → clean session

4. Resume
   codex resume
```

### Claude Code

```
1. Web UI → Prompt Enhance → Claude Code → Enable
   (creates ~/.claude-ctf-workspace)

2. Launch from dedicated workspace
   cd ~/.claude-ctf-workspace && claude

3. If refused → Web UI clean → continue conversation
```

### OpenCode

```
1. Web UI → Prompt Enhance → OpenCode → Enable
   (creates ~/.opencode-ctf-workspace)

2. Launch from dedicated workspace
   cd ~/.opencode-ctf-workspace && opencode

3. If refused → Web UI clean → continue conversation
```

---

## Configuration

CLI and Web UI share `~/.codex-patcher/config.json`:

| Key | Description | Default |
|-----|-------------|---------|
| `mock_response` | Default replacement text | Compliant response |
| `ai_enabled` | Enable AI rewrite | `false` |
| `ai_endpoint` | LLM API endpoint | — |
| `ai_key` | API Key | — |
| `ai_model` | Model name | — |
| `custom_keywords` | Custom refusal detection keywords | `{}` |
| `ctf_prompts` | Custom CTF prompts per platform | Built-in templates |
| `ctf_templates` | User-saved prompt templates | `{}` |

---

## Limitations

- **Cannot bypass platform-level safety policies** — Explicitly illegal requests may still be refused
- **Effectiveness varies by model version** — Model updates may affect results
- **OpenCode requires launching from workspace directory** — OpenCode has no profile mechanism; CTF injection depends on the workspace
- **Resume required after cleaning** — You need to manually resume the session after cleaning

---

## Support

If this project helps you:

- ⭐ Star the repo
- ☕ Buy me a coffee — Sponsor button in the Web UI top-right corner (WeChat / USDC)
- 📢 Follow on X: [@ZhangYufan73644](https://x.com/ZhangYufan73644)

---

## License

[MIT License](LICENSE)

---

<div align="center">
  <a href="https://github.com/ryfineZ">GitHub</a> ·
  <a href="https://x.com/ZhangYufan73644">X (Twitter)</a>
</div>
