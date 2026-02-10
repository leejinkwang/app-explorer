# MCP Server Specification

MCP (Model Context Protocol) server that wraps the Controller REST API as native Claude tools. Enables Claude Code and Claude Desktop to directly control App Explorer without a human operating the Console.

## Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Claude Code / Desktop              Controller          Worker       │
│  ┌────────────────────┐            ┌───────────┐      ┌───────────┐│
│  │ Claude LLM         │            │ REST API  │      │ pywinauto ││
│  │   ↕ MCP protocol   │            │ :5900     │      │ Playwright││
│  │ MCP Server         │──REST──►   │           │◄poll─│           ││
│  │ (stdio transport)  │            │ Agent     │      │           ││
│  │                    │            │ Sessions  │      │           ││
│  └────────────────────┘            └───────────┘      └───────────┘│
│                                                                      │
│  Human (optional)                                                    │
│  ┌────────────────────┐                                              │
│  │ Console CLI        │──REST──►   (same Controller)                 │
│  └────────────────────┘                                              │
└──────────────────────────────────────────────────────────────────────┘
```

MCP Server is a **thin adapter** — it translates MCP tool calls into Controller REST API calls. No business logic lives here.

## Components

```
mcp/
├── SPEC.md              ← You are here
├── server.py            ← MCP server (stdio transport)
├── config.json          ← Claude Code/Desktop MCP config
└── requirements.txt     ← mcp, requests
```

---

## MCP Tools

The MCP server exposes these tools to Claude:

### Session Management

#### `app_explorer_explore`

Start an exploration session (observe-only).

```json
{
  "name": "app_explorer_explore",
  "description": "Start an exploration session to analyze an app or website. Returns session ID.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "description": "Target URL (browser mode)"},
      "title": {"type": "string", "description": "Window title (app mode)"},
      "goal": {"type": "string", "description": "What to focus on"},
      "login": {"type": "string", "description": "Login username/email"},
      "password": {"type": "string", "description": "Login password"}
    }
  }
}
```

#### `app_explorer_task`

Start a task session (execute actions).

```json
{
  "name": "app_explorer_task",
  "description": "Start a task session to automate actions on an app or website.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "description": "Target URL (browser mode)"},
      "title": {"type": "string", "description": "Window title (app mode)"},
      "instruction": {"type": "string", "description": "What to do (e.g., 'Download all PDFs')"},
      "login": {"type": "string", "description": "Login username/email"},
      "password": {"type": "string", "description": "Login password"},
      "auto_confirm": {"type": "boolean", "description": "Skip confirmations", "default": false},
      "telegram_token": {"type": "string", "description": "Telegram bot token for notifications"},
      "telegram_chat": {"type": "string", "description": "Telegram chat ID"},
      "webhook_url": {"type": "string", "description": "Webhook URL for notifications"}
    },
    "required": ["instruction"]
  }
}
```

### Monitoring

#### `app_explorer_status`

```json
{
  "name": "app_explorer_status",
  "description": "Get current session status including turn count, file count, and progress.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string", "description": "Session ID (omit for latest)"}
    }
  }
}
```

#### `app_explorer_log`

```json
{
  "name": "app_explorer_log",
  "description": "Get recent log entries from the current session.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"},
      "last": {"type": "integer", "description": "Number of recent entries", "default": 20}
    }
  }
}
```

#### `app_explorer_wait_for_completion`

```json
{
  "name": "app_explorer_wait_for_completion",
  "description": "Poll session until finished/error. Returns final status. Use for fire-and-wait pattern.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"},
      "poll_interval": {"type": "number", "default": 5},
      "timeout": {"type": "number", "description": "Max wait seconds", "default": 600}
    }
  }
}
```

### Confirmations

#### `app_explorer_check_confirmation`

```json
{
  "name": "app_explorer_check_confirmation",
  "description": "Check if the session is waiting for user confirmation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"}
    }
  }
}
```

#### `app_explorer_confirm`

```json
{
  "name": "app_explorer_confirm",
  "description": "Approve or deny a pending confirmation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"},
      "confirmation_id": {"type": "string"},
      "approved": {"type": "boolean"}
    },
    "required": ["confirmation_id", "approved"]
  }
}
```

### Results

#### `app_explorer_report`

```json
{
  "name": "app_explorer_report",
  "description": "Get the final exploration/task report as Markdown.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"}
    }
  }
}
```

#### `app_explorer_notes`

```json
{
  "name": "app_explorer_notes",
  "description": "Get all saved notes from the session.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"}
    }
  }
}
```

#### `app_explorer_files`

```json
{
  "name": "app_explorer_files",
  "description": "List all output files (screenshots, downloads, generated files).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"}
    }
  }
}
```

#### `app_explorer_download_file`

```json
{
  "name": "app_explorer_download_file",
  "description": "Download a specific file from the session output.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"},
      "filename": {"type": "string"},
      "save_to": {"type": "string", "description": "Local path to save the file"}
    },
    "required": ["filename", "save_to"]
  }
}
```

### System

#### `app_explorer_workers`

```json
{
  "name": "app_explorer_workers",
  "description": "List connected Workers.",
  "inputSchema": {"type": "object", "properties": {}}
}
```

#### `app_explorer_stop`

```json
{
  "name": "app_explorer_stop",
  "description": "Stop the current or specified session.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string"}
    }
  }
}
```

---

## server.py Implementation

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
import requests

CONTROLLER_URL = os.environ.get("APP_EXPLORER_URL", "http://localhost:5900")
current_session_id = None   # track latest session

app = Server("app-explorer")

@app.tool()
async def app_explorer_task(url=None, title=None, instruction="", ...):
    """Start a task session."""
    global current_session_id
    body = {"mode": "task", "instruction": instruction, ...}
    resp = requests.post(f"{CONTROLLER_URL}/sessions", json=body)
    current_session_id = resp.json()["session_id"]
    return resp.json()

@app.tool()
async def app_explorer_status(session_id=None):
    sid = session_id or current_session_id
    return requests.get(f"{CONTROLLER_URL}/sessions/{sid}").json()

@app.tool()
async def app_explorer_wait_for_completion(session_id=None, poll_interval=5, timeout=600):
    """Poll until session finishes."""
    sid = session_id or current_session_id
    start = time.time()
    while time.time() - start < timeout:
        status = requests.get(f"{CONTROLLER_URL}/sessions/{sid}").json()
        if status["status"] in ("finished", "error", "stopped"):
            return status
        if status["status"] == "confirming":
            return {"status": "confirming", "needs_confirmation": True, **status}
        await asyncio.sleep(poll_interval)
    return {"status": "timeout"}

# ... similar thin wrappers for all other tools

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write)
```

Each tool is a thin REST wrapper — no business logic.

---

## Claude Code Configuration

### `claude_code_config.json` (add to `~/.claude/`)

```json
{
  "mcpServers": {
    "app-explorer": {
      "command": "python",
      "args": ["/path/to/mcp/server.py"],
      "env": {
        "APP_EXPLORER_URL": "http://localhost:5900"
      }
    }
  }
}
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "app-explorer": {
      "command": "python",
      "args": ["/path/to/mcp/server.py"],
      "env": {
        "APP_EXPLORER_URL": "http://localhost:5900"
      }
    }
  }
}
```

---

## Typical Interaction Flow

### Example: "Download all Feynman lecture PDFs"

```
User (in Claude Code):
  "파인만 강의 사이트에서 모든 PDF를 다운받아"

Claude:
  1. app_explorer_workers()
     → Verify Worker is connected

  2. app_explorer_task(
       url="https://feynmanlectures.caltech.edu",
       instruction="Find and download all lecture PDF files"
     )
     → session_id: "sess_20250210_150511"

  3. app_explorer_wait_for_completion(timeout=300)
     → returns: {status: "confirming", needs_confirmation: true}

  4. app_explorer_check_confirmation()
     → {pending: true, action: "batch_download",
        description: "Download 47 PDF files (230MB)"}

  5. [Claude decides to approve, or asks user]
     app_explorer_confirm(confirmation_id="conf_001", approved=true)

  6. app_explorer_wait_for_completion(timeout=600)
     → {status: "finished", files: 47}

  7. app_explorer_report()
     → Markdown summary

  8. app_explorer_files()
     → [{filename: "Vol1_Ch01.pdf", size_kb: 4500}, ...]

  9. app_explorer_download_file(filename="...", save_to="./downloads/")
     → (for each file, or bulk)

  Claude: "47개 PDF 파일을 모두 다운로드했습니다. ./downloads/ 에 저장했어요."
```

### Example: "Analyze this website"

```
User: "이 사이트 분석해줘 https://example.com"

Claude:
  1. app_explorer_explore(url="https://example.com")
  2. app_explorer_wait_for_completion()
  3. app_explorer_report() → show to user
```

---

## Smart Confirmation in MCP Context

When Claude Code receives a confirmation request, it can:

1. **Auto-approve** if the original user instruction implies consent (e.g., "download ALL")
2. **Ask the user** in the Claude Code conversation: "47개 PDF를 다운로드할까요?"
3. **Deny** if it seems risky

The MCP server exposes the raw confirmation data — Claude (the outer LLM) makes the judgment call.

---

## Dependencies

```
mcp>=1.0.0
requests>=2.31.0
```
