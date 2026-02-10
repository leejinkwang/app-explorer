# Controller Specification

The Controller is the **brain**. Runs as daemon on Linux. Two HTTP servers, session management, Claude agent loop, credential vault, file storage, webhooks.

## Components

```
controller/
├── SPEC.md              ← You are here
├── controller.py        ← Entry point (starts both servers)
├── api_server.py        ← REST API for Console (:5900)
├── agent.py             ← Claude agent loop (mode + task aware)
├── command_queue.py     ← Worker polling server (:5901) + command queue
├── session.py           ← Session manager + credential vault + file storage
├── config.yaml
└── requirements.txt
```

---

## controller.py

```bash
python controller.py                          # defaults
python controller.py --api-port 5900 --worker-port 5901 --host 0.0.0.0
```

1. Load config.yaml
2. Init SessionManager
3. Start Worker server on :5901 (daemon thread)
4. Start API server on :5900 (main thread)
5. Ctrl+C → graceful shutdown

---

## session.py

### SessionManager

```python
class SessionManager:
    def create_session(params) -> str
    def get_session(session_id) -> dict
    def list_sessions() -> list
    def stop_session(session_id)
    def get_log(session_id, after?) -> list
    def get_report(session_id) -> str
    def get_notes(session_id) -> list
    def list_files(session_id) -> list
    def get_file_path(session_id, filename) -> str
    def store_file(session_id, filename, data)
    def set_confirmation(session_id, confirmation)
    def get_confirmation(session_id) -> dict | None
    def resolve_confirmation(session_id, approved: bool)
```

### Session Object

```python
{
    "session_id": "sess_20250210_143022",
    "status": "running",            # waiting | running | confirming | finished | error | stopped
    "mode": "task",                 # "explore" or "task"
    "target": "https://...",
    "instruction": "Download all...",
    "goal": None,
    "options": {"max_turns": 200, "auto_confirm": false},
    "notifications": {...},
    "output_dir": "./output/sess_.../",
    "agent_thread": <Thread>,
    "log_buffer": [...],
    "turn": 12,
    "files": [],                    # [{filename, size_kb, type: "download"|"generated"|"screenshot"}]
    "confirmation_pending": None,
    "confirmation_event": Event(),
    "confirmation_result": None,
}
```

### CredentialVault

Memory-only. `store()`, `get()`, `clear()`. Cleared on session end.

### File Storage Layout

```
output/sess_YYYYMMDD_HHMMSS/
├── report.md
├── notes.json
├── conversation_log.json
├── screenshots/
└── files/                          ← downloads + generated
    ├── Vol1_Ch01.pdf
    ├── pricing.csv
    └── ...
```

---

## api_server.py

Flask on :5900. Full endpoints in [docs/architecture.md](../docs/architecture.md).

Key endpoints:

| Endpoint | Description |
|----------|-------------|
| `POST /sessions` | Create explore/task session |
| `GET /sessions/:id/files` | List all output files |
| `GET /sessions/:id/files/:name` | Download file |
| `GET /sessions/:id/files/zip` | Download all as zip |
| `GET /sessions/:id/confirmation` | Check pending confirmation |
| `POST /sessions/:id/confirmation` | Approve/deny |

### `POST /upload` (on Worker port :5901)

Receives file from Worker → `session_manager.store_file()`.

---

## command_queue.py

Worker polling server on :5901. Same sync mechanism (Queue + Event) with added `/upload` endpoint.

---

## agent.py — Tool Sets

### Mode × Type Matrix

| | Explore | Task |
|---|---|---|
| **App** | 13 tools | 16+ tools |
| **Browser** | 18 tools | 30+ tools |

### Explore — App (13)

`screenshot`, `get_ui_tree`, `list_elements`, `click`, `right_click`, `double_click`, `type_text`, `press_key`, `scroll`, `switch_window`, `get_window_info`, `save_note`, `finish_exploration`

### Explore — Browser (18)

15 core browser + `perform_login`(if creds) + `save_note` + `finish_exploration`

### Task — App (16+)

All explore-app tools PLUS:

| Tool | Input | Handled |
|------|-------|---------|
| `request_confirmation` | `{action, description, details?, risk_level?}` | Local |
| `save_file` | `{filename, content, encoding?}` | Local |
| `send_notification` | `{message, include_files?}` | Local |
| `finish_task` | `{summary, report_markdown?}` | Local |

### Task — Browser (30+)

All explore-browser tools PLUS task-app tools PLUS:

| Tool | Input | Handled |
|------|-------|---------|
| `browser_download` | `{url, filename?}` | Worker |
| `browser_download_batch` | `{urls: [{url, filename?}]}` | Worker |
| `browser_scrape_links` | `{selector?, pattern?, attribute?}` | Worker |
| `browser_scrape_table` | `{selector, format?}` | Worker |
| `browser_scrape_text` | `{selectors: [{name, selector}]}` | Worker |
| `browser_fill_form` | `{fields: [{selector, value, type?}]}` | Worker |
| `browser_submit_form` | `{selector?, submit_selector?}` | Worker |

### Tool Routing

```
Claude returns tool_use
  ├─ LOCAL TOOLS (handled in Agent):
  │   save_note, finish_exploration, finish_task,
  │   request_confirmation, save_file, send_notification, perform_login
  │
  └─ WORKER TOOLS (forwarded via put_command):
      ├─ *screenshot → image block to Claude
      ├─ *download*  → Worker downloads + uploads → metadata to Claude
      └─ Others      → JSON text to Claude
```

---

## agent.py — Local Tool Implementations

### `request_confirmation`

```python
def _handle_request_confirmation(self, params):
    if self.session["options"].get("auto_confirm"):
        return {"approved": True, "auto": True}
    
    conf = {
        "confirmation_id": f"conf_{self.conf_counter:03d}",
        "action": params["action"],
        "description": params["description"],
        "details": params.get("details", []),
        "risk_level": params.get("risk_level", "medium"),
    }
    self.session_manager.set_confirmation(self.session_id, conf)
    self.session["status"] = "confirming"
    self._log("system", f"⏳ Awaiting confirmation: {conf['description']}")
    
    approved = self.session["confirmation_event"].wait(timeout=300)
    self.session["status"] = "running"
    
    if not approved or not self.session.get("confirmation_result"):
        return {"approved": False}
    return {"approved": True}
```

### `save_file`

Write text/CSV to `output/sess_xxx/files/`. Sanitize filename (no path traversal).

### `send_notification`

Controller sends HTTP from itself (not Worker):
- **Telegram**: `POST https://api.telegram.org/bot{token}/sendMessage`
- **Webhook**: POST/PUT to user-specified URL with `{message, session_id, files}`

### `perform_login`

Read vault → navigate → type fields → click submit → wait → screenshot. Same as before.

---

## agent.py — System Prompts

### Explore Prompts (same as before)

App: systematic analysis, observe-only, save_note, finish_exploration.
Browser: navigate pages, read DOM, observe-only, save_note, finish_exploration.

### Task Prompt — App

```
You are an automation agent controlling a Windows PC application.
Execute the user's task through the available tools.

## Principles
1. Understand first — screenshot and read UI before acting
2. For risky actions: call request_confirmation
3. Report progress via save_note
4. Use save_file for output files (CSV, text)
5. Call finish_task when done
6. If error, stop and report
```

### Task Prompt — Browser

```
You are an automation agent controlling a Chromium browser.
Execute the user's task through the available tools.

## Principles
1. Understand first — screenshot + get_dom before acting
2. If credentials provided: call perform_login FIRST
3. For risky actions (batch downloads, form submissions): call request_confirmation
4. Download workflow: browser_scrape_links → request_confirmation → browser_download_batch
5. Scraping workflow: browser_get_dom → browser_scrape_table/text → save_file
6. Form workflow: browser_fill_form → request_confirmation → browser_submit_form
7. Report progress via save_note
8. Call finish_task when done
9. Use send_notification for long tasks

## CSS Selectors: #id, .class, tag, [attr], text=..., :has-text(...)
```

---

## agent.py — Agent Class

```python
class Agent:
    def __init__(self, config, output_dir, mode, session_type, session_manager, session_id)
    # mode: "app" | "browser"
    # session_type: "explore" | "task"
    
    def start(self, target, instruction, goal) -> dict
    def _run_loop(self)
    def _handle_tool(self, name, params, tool_id) -> dict
    def _log(self, type, text, **kwargs)
    def _save_results(self) -> dict
```

---

## config.yaml

```yaml
api:
  api_key: ""
  model: "claude-sonnet-4-20250514"
  max_tokens: 4096

server:
  host: "0.0.0.0"
  api_port: 5900
  worker_port: 5901

exploration:
  max_turns: 50
  click_delay: 1.0
  screenshot_delay: 0.5

task:
  max_turns: 200
  confirmation_timeout: 300

browser:
  headless: false
  viewport_width: 1280
  viewport_height: 720

files:
  max_file_size_mb: 500
  max_session_storage_mb: 5000
  max_files_per_session: 1000

output:
  dir: "./output"
```

---

## Dependencies

```
anthropic>=0.39.0
flask>=3.0.0
waitress>=3.0.0
rich>=13.0.0
pyyaml>=6.0
requests>=2.31.0
```
