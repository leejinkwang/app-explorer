# App Explorer

A Claude-powered automation agent that **explores apps/websites** and **executes tasks** on Windows PCs.  
Three-tier architecture: **Console** (user) → **Controller** (brain) → **Worker** (hands).

## What It Can Do

### Explore Mode — Analyze and Report
```bash
> explore --url "https://example.com"                    # analyze a website
> explore --title "Notepad" --goal "Find all features"   # analyze a Windows app
```

### Task Mode — Automate and Execute
```bash
> task --url "https://feynmanlectures.caltech.edu" \
       "Download all lecture PDFs"

> task --url "https://app.example.com" \
       --login user@test.com \
       "Scrape the pricing table and save as CSV"

> task --url "https://forms.example.com" \
       "Fill out the survey with: Name=John, Email=john@test.com"

> task --title "Excel" \
       "Enter this data into cells A1-A10: 10,20,30,40,50,60,70,80,90,100"

> task --url "https://news.ycombinator.com" \
       "Scrape top 30 posts, save as CSV, then send summary to Telegram"
```

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  Claude Code/Desktop     Console        Controller       Worker        │
│  ┌──────────────┐   ┌──────────┐    ┌─────────────┐  ┌───────────┐   │
│  │ Claude LLM   │   │ CLI REPL │    │ REST :5900  │  │ pywinauto │   │
│  │   ↕ MCP      │   │ Live log │    │ Agent loop  │  │ Playwright│   │
│  │ MCP Server   │──►│          │──► │ Sessions    │◄─│ Download  │   │
│  │ (stdio)      │   │ Confirm  │    │ Cred vault  │  │ Scrape    │   │
│  └──────────────┘   └──────────┘    │ Files       │  │ Upload    │   │
│   Autonomous          Human          │ Webhooks    │  │           │   │
│                                      └─────────────┘  └───────────┘   │
│                                       Linux server     Windows PC      │
└────────────────────────────────────────────────────────────────────────┘
```

### Two Ways to Control

| Method | Who | How |
|--------|-----|-----|
| **MCP Server** | Claude Code / Claude Desktop | MCP tools → REST API (autonomous) |
| **Console CLI** | Human | REPL → REST API (interactive) |

Both talk to the same Controller REST API. Can be used simultaneously.

### Communication

```
Claude Code ──MCP/stdio──► MCP Server ──REST──► Controller :5900
Human       ──Console CLI──────────────REST──► Controller :5900
Worker      ──────────────────────────poll──► Controller :5901
```

### File Flow

```
Web/App → Worker downloads → Worker uploads to Controller → Console downloads
```

### Confirmation Flow (Smart)

```
Claude decides to download 47 PDFs
  → Controller pauses agent, asks Console for confirmation
  → Console shows: "⚠️ Download 47 files (est. 230MB)? (y/n)"
  → User approves → Agent resumes
```

## Project Structure

```
app-explorer/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── safety.md
│   └── implementation-guide.md
├── mcp/                                     ← Claude Code/Desktop integration
│   ├── SPEC.md
│   ├── server.py
│   ├── config.json
│   └── requirements.txt
├── console/
│   ├── SPEC.md
│   ├── console.py
│   ├── api_client.py
│   ├── display.py
│   └── requirements.txt
├── controller/
│   ├── SPEC.md
│   ├── controller.py
│   ├── api_server.py
│   ├── agent.py
│   ├── command_queue.py
│   ├── session.py
│   ├── config.yaml
│   └── requirements.txt
└── worker/
    ├── SPEC.md
    ├── worker.py
    ├── build.bat
    └── requirements.txt
```

## Quick Start

### 1. Controller (Linux server)
```bash
cd controller
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python controller.py
```

### 2. Worker (Windows machine)
```bash
cd worker
pip install -r requirements.txt
playwright install chromium
python worker.py <controller_ip> 5901
```

### 3. Console (anywhere — human use)
```bash
cd console
pip install -r requirements.txt
python console.py --controller http://<controller_ip>:5900
```

### 4. MCP Server (Claude Code/Desktop — autonomous)
```bash
cd mcp
pip install -r requirements.txt

# Claude Code: add to ~/.claude.json
# Claude Desktop: add to claude_desktop_config.json
```

```json
{
  "mcpServers": {
    "app-explorer": {
      "command": "python",
      "args": ["/path/to/mcp/server.py"],
      "env": {"APP_EXPLORER_URL": "http://localhost:5900"}
    }
  }
}
```

Then in Claude Code:
```
> "파인만 강의 사이트에서 모든 PDF를 다운받아"
→ Claude calls app_explorer_task → monitors → confirms → downloads
```

## Documentation

| Doc | Content |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | Protocols, file transfer, confirmation flow, webhooks |
| [docs/safety.md](docs/safety.md) | Smart confirmation rules, credential handling |
| [docs/implementation-guide.md](docs/implementation-guide.md) | Phase 1-12 build order |
| [mcp/SPEC.md](mcp/SPEC.md) | MCP tools, Claude Code config, interaction flow |
| [console/SPEC.md](console/SPEC.md) | REPL, confirmation UI, file downloads |
| [controller/SPEC.md](controller/SPEC.md) | REST API, agent loop, all tools, webhooks, config |
| [worker/SPEC.md](worker/SPEC.md) | App + browser + download + scrape commands |
