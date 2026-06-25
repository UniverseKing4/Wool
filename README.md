# 🐑 Wool

**Ultra-lightweight CLI AI Agent** — pure REPL, zero TUI, Linux-native.

## Quick Start

```bash
# Install
pip install -e .

# Launch
wool
```

## Configure a Provider

```
wool › /provider add openrouter https://openrouter.ai/api/v1 sk-or-xxxx
wool › /model switch anthropic/claude-sonnet-4
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/provider list\|add\|remove\|switch` | Manage AI providers |
| `/model [list\|switch <id>]` | View or change model |
| `/tools` | List available tools |
| `/mcp list\|connect\|disconnect` | Manage MCP servers |
| `/clear` | Clear conversation history |
| `/compact` | Compact history to last 4 turns |
| `/status` | Session status |
| `/exit` | Exit Wool |

## Built-in Tools

| Tool | Description |
|------|-------------|
| `execute_bash` | Run shell commands with timeout & safety guards |
| `fs_read` | Read files, directories, grep search, image info |
| `fs_write` | Create, replace, insert, append file content |
| `code_intelligence` | Symbol search, codebase overview, project map |
| `web_fetch` | Fetch & extract content from URLs |
| `web_search` | Web search via DuckDuckGo |
| `use_subagent` | Delegate tasks to subagents |

## MCP Support

Connect to any MCP server (stdio or SSE transport):

```
wool › /mcp connect myserver npx -y @modelcontextprotocol/server-filesystem /tmp
```

## Architecture

```
wool/
├── __init__.py          # Package + version
├── __main__.py          # Entry point
├── cli.py               # REPL loop
├── agent.py             # Agentic loop (brain)
├── config.py            # JSON persistence (~/.config/wool/)
├── commands/
│   └── slash.py         # Slash command system
├── providers/
│   ├── base.py          # Provider ABC + data types
│   ├── registry.py      # Provider registry
│   └── openai_compat.py # OpenAI-compatible provider
├── tools/
│   ├── base.py          # Tool ABC
│   ├── registry.py      # Tool registry
│   ├── bash.py          # Shell execution
│   ├── fs_read.py       # File system read
│   ├── fs_write.py      # File system write
│   ├── code_intel.py    # Code intelligence
│   ├── web_fetch.py     # URL fetching
│   ├── web_search.py    # Web search
│   └── subagent.py      # Subagent delegation
├── mcp/
│   ├── client.py        # MCP JSON-RPC client
│   └── manager.py       # Multi-server manager
└── utils/
    ├── ansi.py          # ANSI color helpers
    └── streaming.py     # Stream printer
```

## Requirements

- Python ≥ 3.11
- Linux
- `httpx`, `aiofiles` (auto-installed)

## License

MIT
