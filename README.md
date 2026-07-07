# 🐑 Wool

**Ultra-lightweight CLI AI Agent** — pure REPL, zero TUI, runs everywhere.

> Your terminal is the IDE. Wool is the brain.

[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Termux-green.svg)](#installation)

---

## ⚡ One-Line Install

```bash
curl -fsSL https://universeking4.github.io/Wool/install.sh | bash
```

The installer automatically detects your OS, installs all dependencies (Python 3.11+, Git, pip), and sets up the `wool` command globally. Works on **all Linux distros** and **Android Termux**.

---

## 🚀 Quick Start

```bash
# Launch the agent
wool

# Update Wool to the latest version
wool -u

# Resume the last session instead of starting fresh
wool -c

# Add your AI provider
wool › /provider add openrouter https://openrouter.ai/api/v1 sk-or-xxxx
# OR open the interactive menu
wool › /providers

# Pick a model
wool › /model gemini-2.5-pro
# OR open the interactive menu
wool › /models

# Start chatting — Wool handles everything
wool › read this codebase and explain the architecture
```

---

## ✨ Features

### 🔌 Multi-Provider Support
Works with **any OpenAI-compatible API** — OpenAI, Anthropic, Google, Groq, Mistral, OpenRouter, local models (Ollama, LM Studio), and more. Switch providers and models on the fly.

### 🛠️ Built-in Tools & Interactive Management
Wool comes with 8 powerful built-in tools. But more importantly, **all tools can be dynamically enabled/disabled** without restarting the application via the interactive `/tools` TUI menu.

| Tool | Description |
|------|-------------|
| `execute_bash` | Run shell commands with timeout, safety guards & process isolation |
| `fs_read` | Read files with line ranges, directory listings, grep search |
| `fs_write` | Create, replace, insert, or append file content surgically |
| `code_intelligence` | Symbol search, codebase maps, pattern search across projects |
| `web_fetch` | Fetch & extract readable content from any URL |
| `web_search` | Search the live web via DuckDuckGo |
| `use_subagent` | Delegate tasks to parallel sub-agents for concurrent execution |
| `multi_tool_use` | Execute multiple tools concurrently in a single step to bypass limitations |

**Interactive `/tools` Menu:** Run `/tools` to open a dual-tabbed TUI menu (navigate tabs with `←`/`→`, scroll with `↑`/`↓`, toggle with `Enter`). You can disable specific built-in tools or MCP tools on the fly, and the AI will dynamically adapt to the graceful tool degradation. If you run `/tools <args>`, it prints an error as it's purely interactive.

### 🔗 MCP Protocol Support
Connect to **any MCP server** — stdio, HTTP/SSE, or Streamable HTTP transports. Full support for authentication headers. Wool launches all connections **in parallel** via `asyncio.gather` for blazing fast boot times.

```bash
# Local stdio server
wool › /mcp connect fs npx -y @modelcontextprotocol/server-filesystem /tmp

# Remote HTTP server with API key
wool › /mcp connect exa http https://mcp.exa.ai/mcp -H "Authorization: Bearer your-key"

# Open the interactive toggle menu for MCP servers
wool › /mcps
```

**Dual-Mode Commands:** The `/mcp` and `/mcps` commands are hyper-ergonomic. Run `/mcps` with no arguments to get the interactive TUI menu with live-toggling (syncs states dynamically without a restart), or pass arguments (`/mcps disconnect apify`) to bypass the menu and execute the underlying `/mcp` command directly. Both commands seamlessly overlap depending on whether you provide arguments!

### 🎛️ Interactive TUI Menus
Wool is fully driven by a rich, zero-lag CLI interface without needing a bloated frontend. All these commands open keyboard-navigable interactive menus:
- `/tools` — Toggle Built-in and MCP tools on/off across tabs.
- `/mcps` — Toggle MCP servers on/off.
- `/providers` — Select an AI provider dynamically.
- `/models` — Select a model from the active provider.
- `/sessions` — Browse and switch between chat sessions.
- `/rewind` — Select a previous message in the chat history to rewind the conversation to.
- `/settings` — Toggle core settings like the Secure Workspace Restriction.

### 💬 Session Management
- **Multiple named sessions** — work on different tasks independently (`/new`, `/rename`)
- **Interactive session menu** — TUI-style browser (`/sessions`)
- **Fork conversations** — branch a conversation into a new session (`/fork`)
- **Rewind history** — step back to any previous message interactively (`/rewind`)
- **Compact history** — AI-powered summarization to reduce context size (`/compact`)
- **Auto-cleanup** — ghost sessions with no messages are perfectly scrubbed to keep workspaces clean

### 🧠 Advanced Agent Capabilities
- **Real-time streaming** — tokens stream live with markdown rendering
- **Thinking/Reasoning display** — see the model's chain-of-thought in real-time
- **Goal mode** — set a goal (`/goal <task>`) and let Wool work autonomously until complete
- **Parallel subagents** — delegate multiple tasks to run concurrently in the background
- **Smart context tracking** — detailed token usage and context breakdown (`/context`, `/usage`)
- **Zero-lag event loop** — blazing fast, non-blocking I/O ensures the UI never hangs
- **Atomic persistence** — process-safe, corruption-proof session and configuration saving
- **Graceful cancellation & teardown** — hit Escape (or Ctrl+C) to safely abort LLM generation or tool execution. Unhandled interrupts or shutdowns perfectly terminate all background child processes without leaking orphans.
- **Graceful Tool Degradation** — If you disable a tool via the interactive menus, Wool elegantly notifies the LLM in-context so it can dynamically adapt without crashing.

### 🛡️ Secure Workspace Restrictions
Strict path validations and regex heuristics confine the agent perfectly to your current working directory to prevent arbitrary file modifications. Fully toggleable via the interactive `/settings` menu.

### 📱 Cross-Platform
Natively supports **all Linux distributions** and **Android Termux**. No hardcoded paths — dynamically adapts to your environment. Native Termux clipboard integration.

---

## 📋 All Commands

| Command | Description |
|---------|-------------|
| `wool -u`, `--update`, `--upgrade` | Update Wool to the latest version |
| `wool -e`, `--export` | Export config and sessions to `./wool-export` |
| `wool -i`, `--import` | Import config and sessions from `./wool-export` |
| `wool --uninstall` | Completely remove Wool, including sessions & config |
| `wool -c`, `-r`, `--continue`, `--resume` | Resume the last session instead of starting fresh |
| `/help` | Show this help message |
| `/provider [list|add|remove|switch]` | View or manage AI providers |
| `/providers [args...]` | Open interactive provider menu (or pass args) |
| `/model [list|switch <id>]` | View or change the active model |
| `/models [args...]` | Open interactive model menu (or pass args) |
| `/session [list|new]` | Manage sessions |
| `/sessions [args...]` | Open interactive session menu (or pass args) |
| `/new [name]` | Create and switch to a new session |
| `/rename <new_name>` | Rename the current session |
| `/fork [name]` | Fork current conversation to a new session |
| `/resume`, `/continue` | Resume the last previous session |
| `/rewind` | Interactively rewind history to a specific message |
| `/tools` | Open interactive menu to manage and toggle tools |
| `/mcp [list|connect|disconnect]` | Manage MCP servers |
| `/mcps [args...]` | Open interactive MCP menu (or pass args) |
| `/goal` | Set a goal and work autonomously until complete |
| `/usage` | View token usage for the current session |
| `/context` | View detailed token breakdown of current context |
| `/clear` | Clear conversation history |
| `/compact` | Compact history (keep system + last 4 turns) |
| `/status` | Show current session status |
| `/copy` | Copy the last AI response to clipboard |
| `/settings` | Open interactive settings menu |
| `/exit`, `/quit` | Exit Wool |

---

## 🏗️ Architecture

```
wool/
├── __init__.py          # Package + version
├── __main__.py          # Entry point
├── cli.py               # REPL loop, streaming, spinner, keyboard handling
├── agent.py             # Core agentic loop (brain)
├── config.py            # JSON persistence (~/.config/wool/)
├── commands/
│   └── slash.py         # All slash commands
├── providers/
│   ├── base.py          # Provider ABC, ChatMessage, ToolCall, StreamEvent
│   ├── registry.py      # Provider registry
│   └── openai_compat.py # OpenAI-compatible streaming provider
├── tools/
│   ├── base.py          # Tool ABC + ToolResult
│   ├── registry.py      # Tool registry
│   ├── bash.py          # Secure shell execution
│   ├── fs_read.py       # File system read operations
│   ├── fs_write.py      # File system write operations
│   ├── code_intel.py    # Code intelligence (symbols, maps, grep)
│   ├── web_fetch.py     # URL content fetching
│   ├── web_search.py    # DuckDuckGo web search
│   └── subagent.py      # Parallel subagent delegation
├── mcp/
│   ├── client.py        # MCP JSON-RPC 2.0 client (stdio + SSE + HTTP)
│   └── manager.py       # Multi-server connection manager
└── utils/
    ├── ansi.py          # ANSI color helpers
    ├── markdown.py      # Terminal markdown renderer
    ├── menu.py          # Interactive TUI menu
    └── streaming.py     # Real-time stream printer
```

---

## ⚙️ Requirements

- **Python** ≥ 3.11 (Fully typed & statically verified via `mypy` and `ruff`)
- **Linux** or **Android Termux**
- Dependencies: `httpx`, `aiofiles`, `pyperclip` (auto-installed)

---

## 📦 Manual Installation

If you prefer to install manually instead of using the one-line installer:

```bash
git clone https://github.com/UniverseKing4/Wool.git
cd Wool
pip install .
wool
```

---

## 🔧 Configuration

All configuration is stored in `~/.config/wool/`:

```
~/.config/wool/
├── config.json          # Providers, active model, MCP servers
└── sessions/
    ├── default.json     # Default session history
    └── my-project.json  # Named session histories
```

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<p align="center">
  <strong>🐑 Wool</strong> — Ultra-lightweight CLI AI Agent<br>
  <a href="https://github.com/UniverseKing4/Wool">GitHub</a> · <a href="https://universeking4.github.io/Wool">Website</a>
</p>
