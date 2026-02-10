# Architecture & Protocol

## Overview

Controller runs **two HTTP servers**. Two client types talk to the API server:

```
MCP Server ──REST──►  Controller :5900 (API)     ← Claude Code/Desktop (autonomous)
Console    ──REST──►  Controller :5900 (API)     ← Human (interactive)
Worker     ──poll──►  Controller :5901 (Worker)   ← commands + file uploads
```

### Access Methods

| Client | User | Protocol | Purpose |
|--------|------|----------|---------|
| **MCP Server** | Claude Code/Desktop | MCP stdio → REST | Autonomous control |
| **Console CLI** | Human | REST | Interactive control |
| Both use the same REST API | | | Can run simultaneously |

## Session Modes

| Mode | Trigger | Purpose |
|------|---------|---------|
| `explore` | `explore --url` / `explore --title` | Analyze and report (observe-only) |
| `task` | `task --url "..." "instruction"` / `task --title "..." "instruction"` | Execute actions (downloads, forms, scraping, automation) |

Both modes use the same protocol. Task mode unlocks additional tools and relaxes safety (with smart confirmation).

---

## Tier 1: Console → Controller (REST API, port 5900)

### Session Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create session (explore or task) |
| GET | `/sessions` | List all sessions |
| GET | `/sessions/:id` | Session status |
| DELETE | `/sessions/:id` | Stop session |
| GET | `/sessions/:id/log` | Log entries (polling) |
| GET | `/sessions/:id/report` | Final report |
| GET | `/sessions/:id/notes` | Saved notes |

### File Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions/:id/files` | List all output files (screenshots + downloads) |
| GET | `/sessions/:id/files/:filename` | Download a file |
| GET | `/sessions/:id/files/zip` | Download all files as zip |

### Confirmation Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions/:id/confirmation` | Check if confirmation is pending |
| POST | `/sessions/:id/confirmation` | Respond (approve/deny) |

### System Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/workers` | Connected Workers |
| GET | `/health` | Health check |

### `POST /sessions` — Create Session

```json
{
  "mode": "task",                                // "explore" or "task"
  "target": "https://feynmanlectures.caltech.edu",
  "instruction": "Download all lecture PDFs",     // task mode: free-form instruction
  "goal": null,                                   // explore mode: exploration goal
  "credentials": { ... },                         // optional login info
  "notifications": {                              // optional
    "telegram": {"bot_token": "...", "chat_id": "..."},
    "webhook": {"url": "https://hooks.example.com/done", "method": "POST"}
  },
  "options": {
    "max_turns": 100,
    "auto_confirm": false                         // true = skip confirmations
  }
}
```

### `GET /sessions/:id/confirmation`

```json
// No pending confirmation
{"pending": false}

// Confirmation needed
{
  "pending": true,
  "confirmation_id": "conf_001",
  "action": "batch_download",
  "description": "Download 47 PDF files (estimated 230MB)",
  "details": [
    "Vol1_Ch01.pdf", "Vol1_Ch02.pdf", "...(45 more)"
  ],
  "risk_level": "medium"                          // low | medium | high
}
```

### `POST /sessions/:id/confirmation`

```json
{"confirmation_id": "conf_001", "approved": true}
```

---

## Tier 2: Worker → Controller (Polling, port 5901)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Worker registration |
| GET | `/command` | Poll for next command |
| POST | `/result` | Send execution result |
| POST | `/upload` | Upload file (multipart) |
| GET | `/health` | Status |

### `/register` (POST)

```json
// Request
{"hostname": "OFFICE-PC-01", "has_pywinauto": true, "has_playwright": true}
// Response
{"success": true, "message": "registered"}
```

### `/command` (GET)

```json
{"action": "wait"}
// or
{"id": "cmd_0001", "action": "browser_download", "params": {"url": "...", "filename": "lecture01.pdf"}}
// or
{"action": "shutdown"}
```

### `/result` (POST)

```json
{"id": "cmd_0001", "success": true, "data": {"filename": "lecture01.pdf", "size_kb": 4500}}
```

### `/upload` (POST, multipart/form-data)

Worker uploads downloaded files to Controller:

```
POST /upload
Content-Type: multipart/form-data

Fields:
  session_id: "sess_20250210_143022"
  filename: "lecture01.pdf"
  file: <binary data>
```

Response:
```json
{"success": true, "stored_as": "lecture01.pdf", "size_kb": 4500}
```

---

## Key Flows

### File Download Flow

```
Claude: "I found 47 PDF links. I'll download them all."
  → Agent calls request_confirmation("batch_download", details)
  → Controller sets session.confirmation_pending
  → Console polls GET /confirmation → shows prompt to user
  → User approves → POST /confirmation {approved: true}
  → Agent resumes, calls browser_download for each file
  → Worker downloads file → POST /upload to Controller
  → Controller stores in session output dir
  → Console can GET /files/lecture01.pdf anytime
```

### Confirmation Flow

```
Agent (main thread)                    Console (via REST API)
       │                                      │
       │  _request_confirmation(              │
       │    action, description)               │
       │  → session.confirmation = {...}       │
       │  → confirmation_event.wait() ←blocks  │
       │                                      │
       │                              Console GET /confirmation
       │                              → returns pending confirmation
       │                              User sees: "⚠️ Download 47 files?"
       │                              User types: y
       │                              Console POST /confirmation
       │                              → confirmation_event.set()
       │                                      │
       │  ← approved = True/False              │
       │  Resume or skip action                │
```

### Notification Flow

```
Agent finishes task
  → Agent calls send_notification tool
  → Controller (not Worker) sends the notification:
     - Telegram: POST https://api.telegram.org/bot.../sendMessage
     - Webhook: POST to user-specified URL
     - Both: with task summary + file list
```

Notifications are sent from **Controller** (has network + secrets), not Worker.

### Scraping Flow

```
Claude: "I'll scrape the pricing table"
  → browser_get_dom to read table structure
  → browser_scrape_table {selector: "table.pricing"} → structured data
  → save_file {filename: "pricing.csv", content: "..."} → stored on Controller
  → (optional) send_notification with summary
```

### HTML-to-PDF Export Flow

```
Claude: "I'll save all lecture chapters as PDF"
  → browser_scrape_links {selector: "#toc a", pattern: "I_\\d+\\.html"}
  → request_confirmation("Save 52 pages as PDF")
  → User approves
  → For each chapter URL:
     → browser_navigate {url: "https://.../I_01.html"}
     → browser_save_as_pdf {filename: "I_01_Atoms_in_Motion.pdf", wait_for_selector: ".mathjax"}
     → Worker renders page to PDF via Playwright page.pdf()
     → Worker uploads PDF to Controller
  → finish_task with summary
```

---

## Synchronization

### Worker ↔ Agent

Same as before: `Queue(maxsize=1)` + `Event()` for one-command-at-a-time sync.

### Confirmation ↔ Agent

```python
# In session object
"confirmation_pending": {
    "confirmation_id": "conf_001",
    "action": "batch_download",
    "description": "...",
    ...
},
"confirmation_event": Event(),      # Agent waits on this
"confirmation_result": None,        # True/False after Console responds
```

---

## Network Scenarios

| Scenario | Console | Controller | Worker |
|----------|---------|-----------|--------|
| All same PC | `localhost:5900` | `localhost` | `127.0.0.1:5901` |
| Controller on server | `server:5900` | `0.0.0.0` | `server_ip:5901` |
| Worker behind firewall | `server:5900` | `0.0.0.0` | `server_ip:5901` (outbound only) |
