# Implementation Guide

Build in this order. Each phase is independently testable.

---

## Phase 1: Worker — App Mode (`worker/worker.py`)

Single file foundation.

1. CLI parser: `host`, `port`, `--poll-interval`
2. Global state dict (app section)
3. App utilities: `is_dangerous()`, `get_rect()`, `extract_tree()`, `capture_app_png()`
4. App handlers: `do_connect`, `do_screenshot`, `do_ui_tree`, `do_list_elements`, `do_list_windows`, `do_click`, `do_right_click`, `do_double_click`, `do_type_text`, `do_press_key`, `do_scroll`, `do_switch_window`, `do_window_info`
5. `handle_command()` dispatcher
6. Polling loop: register → poll → execute → result
7. Safety blocking

**Test**: `worker.py 127.0.0.1 5901` + curl.

---

## Phase 2: Command Queue (`controller/command_queue.py`)

Worker polling server on :5901.

1. Flask: `/register`, `/command`, `/result`, `/health`
2. Queue + Event sync
3. `put_command()`, `wait_for_worker()`, `signal_shutdown()`, `start_server()`

**Test**: Start server, curl as Worker.

---

## Phase 3: Session Manager (`controller/session.py`)

1. `CredentialVault`: memory-only store/get/clear
2. `SessionManager`:
   - `create_session()`, `get_session()`, `list_sessions()`, `stop_session()`
   - `get_log()`, `get_report()`, `get_notes()`
   - `list_files()`, `store_file()`, `get_file_path()`
   - Session status state machine
   - Agent thread spawn

**Test**: Unit test session lifecycle.

---

## Phase 4: Agent — Explore/App (`controller/agent.py`)

1. `APP_EXPLORE_TOOLS` (13) + `APP_EXPLORE_PROMPT`
2. Agent class with `mode` and `session_type` params
3. `start()` → connect → screenshot → `_run_loop()`
4. `_handle_tool()` routing (local vs Worker)
5. Screenshot → image block
6. `save_note`, `finish_exploration` local handlers
7. Log buffer writing
8. `_save_results()`

**Test**: Controller + Worker → explore Notepad.

---

## Phase 5: REST API (`controller/api_server.py`)

Flask on :5900 for Console.

1. Session CRUD: `POST /sessions`, `GET /sessions`, `GET /sessions/:id`, `DELETE /sessions/:id`
2. Log: `GET /sessions/:id/log`
3. Report/notes: `GET /sessions/:id/report`, `/notes`
4. System: `GET /workers`, `GET /health`

**Test**: curl to create session, check status.

---

## Phase 6: Controller Entry (`controller/controller.py`)

1. Load config, init SessionManager
2. Start Worker server :5901 (daemon thread)
3. Start API server :5900 (main thread)
4. CLI: `--config`, `--api-port`, `--worker-port`, `--host`

**Test**: Full explore/app flow via curl.

---

## Phase 7: Worker — Browser Mode (extend `worker/worker.py`)

1. Browser state in global dict
2. Browser utilities: `capture_browser_png()`, `extract_dom()`, `is_url_blocked()`
3. Browser core handlers: open/close/screenshot/get_dom/get_text/get_url/eval_js/navigate/back/forward/refresh/wait/click/type/select/hover/scroll/press_key
4. Extend dispatcher

**Test**: curl `browser_open` + `browser_screenshot`.

---

## Phase 8: Agent — Explore/Browser (extend `controller/agent.py`)

1. `BROWSER_EXPLORE_TOOLS` (18) + `BROWSER_EXPLORE_PROMPT`
2. `perform_login` handler (vault → Worker sequence)
3. Browser startup/shutdown flow
4. Mode selection in Agent.__init__

**Test**: Explore https://example.com.

---

## Phase 9: Console (`console/`)

### 9a: api_client.py
ApiClient class wrapping all REST endpoints.

### 9b: display.py
Formatting: log entries, status, prompt, confirmation, report.

### 9c: console.py
1. CLI: `--controller` + optional inline command
2. Startup: health check → Worker status → REPL
3. REPL loop: drain log → check confirm → input → dispatch
4. Log poller daemon thread (0.5s, deque buffer)
5. Commands: `explore`, `status`, `log`, `stop`, `report`, `notes`, `workers`, `help`, `exit`
6. `explore --login` with getpass
7. Non-interactive mode

**Test**: Full explore flow end-to-end.

---

## Phase 10: Task Mode — Worker (extend `worker/worker.py`)

1. File upload utility: `upload_file_to_controller()` via `POST /upload`
2. Add `/upload` endpoint to command_queue.py (Worker port)
3. `do_browser_download`: download → temp → upload to Controller
4. `do_browser_download_batch`: loop with progress
5. `do_browser_scrape_links`: extract links + regex filter
6. `do_browser_scrape_table`: HTML table → JSON/CSV
7. `do_browser_scrape_text`: extract named selectors
8. `do_browser_fill_form`: fill multiple fields
9. `do_browser_submit_form`: submit form

**Test**: curl download/scrape commands, verify upload to Controller.

---

## Phase 11: Task Mode — Agent + Console

### Agent additions:
1. Task tool sets: `APP_TASK_TOOLS`, `BROWSER_TASK_TOOLS` + task prompts
2. `request_confirmation` handler (pause → wait for Console → resume)
3. `save_file` handler (write to output/files/)
4. `send_notification` handler (Telegram + webhook from Controller)
5. `finish_task` handler
6. `POST /sessions` accepts `mode: "task"`, `instruction`, `notifications`
7. Confirmation endpoints: `GET/POST /sessions/:id/confirmation`
8. File endpoints: `GET /sessions/:id/files`, `/files/:name`, `/files/zip`

### Console additions:
1. `task` command (instruction as positional arg)
2. Confirmation polling + prompt UI
3. `files` command (list/download/zip)
4. `--auto-confirm`, `--telegram-*`, `--webhook` args
5. Download progress display

**Test**: Download PDFs from a website with confirmation flow.

---

## Phase 12: MCP Server (`mcp/`)

See [mcp/SPEC.md](../mcp/SPEC.md).

1. `server.py`: MCP server with stdio transport
2. REST client: thin wrapper around Controller API (reuse or mirror `console/api_client.py`)
3. Tools: `app_explorer_explore`, `app_explorer_task`, `app_explorer_status`, `app_explorer_log`, `app_explorer_wait_for_completion`, `app_explorer_check_confirmation`, `app_explorer_confirm`, `app_explorer_report`, `app_explorer_notes`, `app_explorer_files`, `app_explorer_download_file`, `app_explorer_workers`, `app_explorer_stop`
4. `wait_for_completion`: poll loop with timeout, returns on finish/error/confirming
5. Session ID tracking: `current_session_id` for omit-session convenience
6. Config: `APP_EXPLORER_URL` env var, Claude Code/Desktop JSON configs

**Test**: Claude Code → `app_explorer_task(url="https://example.com", instruction="...")` → poll → report.

---

## Test Scenarios

### Explore

| # | Scenario | Command |
|---|----------|---------|
| 1 | Notepad | `explore --title "Notepad"` |
| 2 | Website | `explore --url "https://example.com"` |
| 3 | With goal | `explore --url "..." --goal "Analyze nav"` |
| 4 | With login | `explore --url "..." --login user@test.com` |

### Task — Download

| # | Scenario | Command |
|---|----------|---------|
| 5 | Batch download | `task --url "..." "Download all PDFs"` |
| 6 | Auto-confirm | `task --url "..." --auto-confirm "Download all"` |
| 7 | Download + notify | `task --url "..." --telegram-token "..." "Download and notify"` |

### Task — Scrape

| # | Scenario | Command |
|---|----------|---------|
| 8 | Table to CSV | `task --url "..." "Scrape pricing table to CSV"` |
| 9 | Link extract | `task --url "..." "List all PDF links"` |

### Task — Form + App

| # | Scenario | Command |
|---|----------|---------|
| 10 | Fill form | `task --url "..." "Fill: Name=John"` |
| 11 | Login + task | `task --url "..." --login u@t.com "Download invoices"` |
| 12 | App data entry | `task --title "Excel" "Enter 1-10 in A1:A10"` |

### Console + Edge Cases

| # | Scenario |
|---|----------|
| 13 | Confirmation approve/deny |
| 14 | File download to local |
| 15 | Confirmation timeout (5 min) |
| 16 | Worker drops mid-task |
| 17 | URL safety block |
| 18 | File size limit exceeded |

### MCP Server

| # | Scenario |
|---|----------|
| 19 | Claude Code → explore website → get report |
| 20 | Claude Code → task download → confirm → get files |
| 21 | Claude Code → auto-confirm batch download |
| 22 | wait_for_completion with timeout |
| 23 | MCP + Console simultaneous access |
