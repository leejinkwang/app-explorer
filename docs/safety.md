# Safety Measures

## Smart Confirmation

In task mode, Claude can perform actions that change state. Dangerous actions require user confirmation via Console.

### Confirmation Rules

| Action | Risk | Confirm? |
|--------|------|----------|
| **Screenshots, DOM reads, navigation** | None | ❌ Never |
| **Single file download (<10MB)** | Low | ❌ No |
| **Batch download (>5 files or >50MB)** | Medium | ✅ Yes |
| **Batch PDF export (>5 pages)** | Medium | ✅ Yes |
| **Single PDF export** | Low | ❌ No |
| **Form submission** | Medium | ✅ Yes |
| **Login (via perform_login)** | Low | ❌ No (pre-authorized by user) |
| **Send webhook/notification** | Low | ❌ No (pre-configured by user) |
| **External API call (custom URL)** | High | ✅ Yes |
| **Type into unknown fields** | Low | ❌ No |
| **Click "Delete/Remove/Uninstall"** | High | 🚫 Blocked (app mode) |
| **Navigate to blocked URL scheme** | High | 🚫 Blocked always |

### Auto-Confirm Option

Sessions created with `"auto_confirm": true` skip all confirmations. Use for trusted, repetitive tasks:
```bash
> task --url "..." --auto-confirm "Download all PDFs"
```

### Confirmation Object

```json
{
  "confirmation_id": "conf_001",
  "action": "batch_download",
  "description": "Download 47 PDF files (estimated 230MB)",
  "details": ["Vol1_Ch01.pdf", "Vol1_Ch02.pdf", "..."],
  "risk_level": "medium",
  "timeout": 300
}
```

If user doesn't respond within `timeout` seconds (default 5 min), action is **denied**.

### How Claude Requests Confirmation

Claude calls the `request_confirmation` tool:
```json
{
  "name": "request_confirmation",
  "input": {
    "action": "batch_download",
    "description": "Download 47 PDF files from feynmanlectures.caltech.edu",
    "details": ["Vol1_Ch01.pdf", "Vol1_Ch02.pdf"],
    "risk_level": "medium"
  }
}
```

Agent handles this locally:
1. If `auto_confirm` → return approved immediately
2. Otherwise → set `confirmation_pending` → wait for Console response
3. Return `{"approved": true/false}` to Claude

---

## Explore Mode vs Task Mode Safety

| Aspect | Explore Mode | Task Mode |
|--------|-------------|-----------|
| Form submission | 🚫 Blocked | ✅ With confirmation |
| File download | 🚫 Blocked | ✅ With confirmation for batch |
| Data modification | 🚫 Blocked | ✅ Per instruction |
| External API/webhook | 🚫 Blocked | ✅ Pre-configured only |
| Login | ✅ via perform_login | ✅ via perform_login |
| Screenshots/reading | ✅ Always | ✅ Always |
| App click blocking | ✅ Dangerous patterns | ⚠️ Relaxed (only destructive) |

### Task Mode Relaxed Blocking (App)

In task mode, app click blocking only blocks truly destructive actions:
```
삭제|Delete|Remove|제거
포맷|Format
초기화|Reset|Clear all
언인스톨|Uninstall
```

`Close/Exit/Quit` are **allowed** in task mode (Claude may need to close dialogs).

---

## Credential Handling

Same as before — credentials never touch disk, Claude API, or Worker as a whole:

1. Console sends credentials in `POST /sessions`
2. Controller stores in `CredentialVault` (memory only)
3. Claude calls `perform_login` → Controller executes login sequence
4. Credentials cleared on session end

---

## File Transfer Security

### Worker → Controller Upload

- Files uploaded via `POST /upload` (multipart)
- Controller validates: filename sanitization (no path traversal), size limit (configurable, default 500MB per file)
- Stored in session output directory: `output/sess_xxx/files/`

### Controller → Console Download

- Console downloads via `GET /sessions/:id/files/:filename`
- No authentication by default (trusted LAN) — add token auth for production

### File Size Limits

| Limit | Default | Configurable |
|-------|---------|-------------|
| Single file max | 500 MB | config.yaml |
| Session total max | 5 GB | config.yaml |
| Upload chunk size | 10 MB | Worker-side |

---

## URL Restrictions (Both Modes)

Blocked schemes: `file://`, `javascript:`, `data:`, `chrome://`, `about:`, `blob:`

---

## Browser Safety

- No persistent cookies (fresh profile per session)
- Downloads go through Worker → Controller pipeline (not browser's default download)
- DOM extraction strips scripts/styles

---

## Notification Security

- Telegram bot tokens and webhook URLs are stored in session config (memory only)
- Sent from Controller (not Worker) — Worker never sees tokens
- Webhook URLs are validated (must be HTTPS in production)

---

## Controller Limits

| Limit | Default | Configurable |
|-------|---------|-------------|
| Max turns | 50 (explore) / 200 (task) | Per session |
| Max screenshots | 100 | Worker-side |
| Max files per session | 1000 | config.yaml |
| Max file size | 500 MB | config.yaml |
| Max session storage | 5 GB | config.yaml |
| Confirmation timeout | 300 sec | config.yaml |
| Worker registration timeout | 5 min | Hardcoded |
| Command timeout | 60 sec (normal) / 300 sec (download) | Per action |
