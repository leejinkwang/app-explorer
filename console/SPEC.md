# Console Specification

CLI REPL with live log, confirmation handling, and file management.

## Components

```
console/
├── SPEC.md              ← You are here
├── console.py           ← REPL entry point
├── api_client.py        ← REST API client
├── display.py           ← Formatting (Rich)
└── requirements.txt     ← requests, rich
```

---

## Screen Behavior

```
app-explorer> explore --url "https://example.com"
✅ Session started: sess_20250210_143022

  [14:30:25] ⚙️ Session started
  [14:30:26] 🔧 browser_screenshot "initial"
  [14:30:28] 💭 I see a landing page with a hero section...

app-explorer [running 3/50]> _
  [14:30:30] 🔧 browser_get_dom body
  [14:30:33] 🔧 browser_click "text=About"

app-explorer [running 5/50]> task --url "https://feynman..." "Download all PDFs"
✅ Task started: sess_20250210_150511

  [15:05:12] 🔧 browser_screenshot "initial"
  [15:05:15] 💭 I see the Feynman Lectures homepage...
  [15:05:20] 🔧 browser_scrape_links {pattern: "\\.pdf$"}

  ⚠️  CONFIRMATION REQUIRED
  │ Action: batch_download
  │ Download 47 PDF files (estimated 230MB)
  │ Files: Vol1_Ch01.pdf, Vol1_Ch02.pdf, ... (45 more)
  └ Approve? (y/n/details): y

  [15:05:35] ✅ Confirmed: batch_download
  [15:05:36] 🔧 browser_download_batch (47 files)
  [15:05:40] 📥 Vol1_Ch01.pdf (4.5MB)
  [15:05:44] 📥 Vol1_Ch02.pdf (3.8MB)
  ...
```

---

## CLI Interface

```bash
python console.py --controller http://<host>:5900
```

### Prompt Format

```
app-explorer> _                              # no session
app-explorer [running 5/50]> _               # session active
app-explorer [confirming]> _                 # waiting for confirmation
app-explorer [finished]> _                   # done
```

---

## Commands

### `explore` — Start Exploration (observe-only)

```bash
> explore --url "https://example.com"
> explore --url "https://example.com" --goal "Analyze navigation"
> explore --title "Notepad"
> explore --url "https://app.com" --login user@test.com
```

### `task` — Start Task (execute actions)

```bash
> task --url "https://feynmanlectures.caltech.edu" "Download all lecture PDFs"
> task --url "https://example.com" "Scrape pricing table to CSV"
> task --url "https://forms.example.com" "Fill survey: Name=John, Email=john@test.com"
> task --title "Excel" "Enter data into A1:A10"
> task --url "https://news.ycombinator.com" --auto-confirm "Scrape top 30 posts to CSV"

# With login
> task --url "https://app.example.com" --login user@test.com "Download all invoices"

# With notifications
> task --url "..." --telegram-token "..." --telegram-chat "..." "Download all PDFs and notify me"
```

#### Common Arguments (both explore and task)

| Arg | Description |
|-----|-------------|
| `--url` | Target URL (browser mode) |
| `--title` | Window title (app mode) |
| `--process` | Process name (app mode) |
| `--goal` | Exploration goal (explore mode) |
| `--login` | Login username/email |
| `--password` | Password (prompts if omitted) |
| `--login-url` | Login page URL |
| `--login-submit` | Submit selector |
| `--turns` | Max turns |
| `--model` | Model override |

#### Task-Only Arguments

| Arg | Description |
|-----|-------------|
| `--auto-confirm` | Skip all confirmations |
| `--telegram-token` | Telegram bot token for notifications |
| `--telegram-chat` | Telegram chat ID |
| `--webhook` | Webhook URL for notifications |

The last positional argument is the **instruction** (free-form task description).

---

### `status` — Session Status

```bash
> status

  Session:     sess_20250210_150511
  Status:      running
  Type:        task (browser)
  Target:      https://feynmanlectures.caltech.edu
  Instruction: Download all lecture PDFs
  Turn:        15/200
  Worker:      OFFICE-PC-01
  Notes:       3
  Screenshots: 4
  Files:       12 (48.5 MB)
  Started:     2025-02-10 15:05:11
```

---

### `log` — Stream Live Log

```bash
> log                     # stream mode (Ctrl+C to exit)
> log --last 20           # last 20 entries then stream
```

**Log entry icons**:

| Type | Icon | Example |
|------|------|---------|
| tool | 🔧 | `browser_click "text=About"` |
| claude | 💭 | `I see a landing page...` |
| note | 📝 | `[structure] 3 sections found` |
| screenshot | 📸 | `002_about.png (189KB)` |
| download | 📥 | `Vol1_Ch01.pdf (4.5MB)` |
| confirm | ⚠️ | `Awaiting: batch_download` |
| system | ⚙️ | `Session started` |
| error | ❌ | `Element not found` |
| notify | 📤 | `Telegram sent: task complete` |

---

### Confirmation Handling

When confirmation is pending, the Console detects it via log polling OR dedicated confirmation polling.

**Flow**:

1. Log poller sees confirmation entry → or polls `GET /sessions/:id/confirmation`
2. Display confirmation prompt (interrupts between commands):

```
  ⚠️  CONFIRMATION REQUIRED
  │ Action: batch_download
  │ Download 47 PDF files (estimated 230MB)
  │ Files: Vol1_Ch01.pdf, Vol1_Ch02.pdf, ... (45 more)
  └ Approve? (y/n/details): _
```

3. User input:
   - `y` → `POST /sessions/:id/confirmation {approved: true}`
   - `n` → `POST /sessions/:id/confirmation {approved: false}`
   - `details` → print full file list, then re-prompt

**Confirmation polling**:
- Log poller thread also checks `GET /sessions/:id/confirmation` every 1s
- If `pending: true`, sets a flag
- Main thread checks flag before each prompt
- If flag set, show confirmation prompt instead of normal prompt

---

### `stop` — Stop Session

```bash
> stop
  ⚠️ Stop current task? (y/n): y
  ✅ Session stopped.
```

---

### `report` — View/Save Report

```bash
> report                        # print to terminal
> report --save ./report.md     # save to file
```

---

### `files` — List/Download Files

```bash
> files
  screenshots/
    001_initial.png              (245 KB)
    002_about_page.png           (189 KB)
  files/
    Vol1_Ch01.pdf                (4.5 MB)
    Vol1_Ch02.pdf                (3.8 MB)
    pricing.csv                  (2 KB)
  Total: 5 files, 8.7 MB

> files --download ./output/           # download all to local dir
  Downloading 5 files...
  ✅ Saved to ./output/

> files --download ./output/ --only files/    # only downloaded files
> files --download ./output/ Vol1_Ch01.pdf    # single file
```

**Implementation**:
- List: `GET /sessions/:id/files`
- Single: `GET /sessions/:id/files/:filename` → save
- All: `GET /sessions/:id/files/zip` → unzip locally

---

### `notes`

```bash
> notes
  1. [navigation] Main nav has 5 sections      (15:05:18)
  2. [content] 3 volumes, 47 chapters total     (15:05:25)
  3. [download] All PDFs found on chapter pages  (15:05:30)
```

---

### `workers`

```bash
> workers
  OFFICE-PC-01    ✅ connected    pywinauto ✅  playwright ✅
```

---

### `help`

```bash
> help
  explore      Analyze app/website (observe-only)
  task         Execute automation task
  status       Current session status
  log          Stream live log (Ctrl+C to exit)
  stop         Stop current session
  report       View/save report
  files        List/download output files
  notes        View saved notes
  workers      Connected workers
  help         This help
  exit         Quit console
```

---

### `exit` / `quit` / Ctrl+D

Exit Console. Running sessions continue on Controller.

---

## Non-Interactive Mode

```bash
# Start task and exit
python console.py --controller http://server:5900 task --url "..." "Download PDFs"

# Check status
python console.py --controller http://server:5900 status

# Download files
python console.py --controller http://server:5900 files --download ./out/

# Get report
python console.py --controller http://server:5900 report --save ./report.md
```

---

## Threading Model

```
Main thread                    Log/Confirmation poller (daemon)
┌─────────────┐               ┌──────────────────────┐
│ REPL loop   │               │ Every 0.5s:          │
│             │               │   GET /session/:id/log│
│ 1. Check    │               │   GET .../confirmation│
│    confirm  │               │   → append log_buffer │
│    flag     │               │   → set confirm_flag  │
│ 2. Drain    │               └──────────────────────┘
│    log_buf  │                         │
│ 3. input()  │◄── shared: log_buffer (deque)
│ 4. dispatch │◄── shared: confirm_flag (Event)
│             │◄── shared: confirm_data (dict)
└─────────────┘
```

---

## api_client.py

```python
class ApiClient:
    def __init__(self, base_url: str)
    
    def create_session(self, params) -> dict
    def get_session(self, session_id) -> dict
    def list_sessions(self) -> list
    def stop_session(self, session_id) -> dict
    
    def get_log(self, session_id, after?, last?) -> list
    def get_report(self, session_id) -> str
    def get_notes(self, session_id) -> list
    
    def list_files(self, session_id) -> list
    def download_file(self, session_id, filename) -> bytes
    def download_zip(self, session_id) -> bytes
    
    def get_confirmation(self, session_id) -> dict | None
    def respond_confirmation(self, session_id, conf_id, approved) -> dict
    
    def get_workers(self) -> list
    def health(self) -> dict
```

---

## display.py

```python
def format_log_entry(entry) -> str
def format_status(session) -> str
def format_prompt(session) -> str
def format_confirmation(conf) -> str       # the ⚠️ block
def format_report(markdown)                # Rich Markdown render
def format_files(files) -> str
def format_notes(notes) -> str
```

---

## Dependencies

```
requests>=2.31.0
rich>=13.0.0
```
