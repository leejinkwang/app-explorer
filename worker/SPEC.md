# Worker Specification

The Worker is the **hands**. Runs on the target Windows machine. No API keys, no credentials, no decisions. Executes commands, returns results, uploads files.

## Constraint

**Single file** (`worker.py`). PyInstaller `--onefile`.  
Imports: `requests`, `pywinauto`, `pyautogui`, `Pillow`, `playwright`, Python stdlib.

Auto-detects mode from commands: `connect` → app, `browser_open` → browser.

---

## CLI

```
worker.exe <controller_host> [port] [--poll-interval 0.5]
```

---

## Internal Structure

```
worker.py
├── Global state
│   ├── App: app, window, click_delay, ...
│   ├── Browser: playwright, browser, page, ...
│   └── Shared: mode, screenshot_count, screenshots_dir, controller_url
│
├── Shared utilities
│   is_dangerous(name, mode), get_rect(element)
│
├── App utilities & handlers
│   do_connect, do_screenshot, do_ui_tree, do_list_elements,
│   do_list_windows, do_click, do_right_click, do_double_click,
│   do_type_text, do_press_key, do_scroll, do_switch_window, do_window_info
│
├── Browser utilities & handlers
│   do_browser_open, do_browser_close, do_browser_screenshot,
│   do_browser_get_dom, do_browser_get_text, do_browser_get_url,
│   do_browser_eval_js, do_browser_navigate, do_browser_back,
│   do_browser_forward, do_browser_refresh, do_browser_wait,
│   do_browser_click, do_browser_type, do_browser_select,
│   do_browser_hover, do_browser_scroll, do_browser_press_key,
│   do_browser_download, do_browser_scrape_links, do_browser_scrape_table,
│   do_browser_fill_form, do_browser_submit_form
│
├── File utilities
│   upload_file_to_controller(filepath, session_id, filename)
│
├── handle_command() dispatcher
│
└── Main polling loop
    POST /register → while: GET /command → execute → POST /result
```

---

## App Commands (same as before)

### Connection / Info

| action | params | return data |
|--------|--------|-------------|
| `connect` | `{window_title?, process_name?, click_delay?, screenshot_delay?, screenshots_dir?, session_id?}` | `{window_title, rect}` |
| `list_windows` | `{}` | `[{title, class_name}, ...]` |
| `get_window_info` | `{}` | `{title, rect, class_name}` |

### Observation

| action | params | return data |
|--------|--------|-------------|
| `screenshot` | `{label}` | `{filename, label, file_size_kb, number, image_base64}` |
| `get_ui_tree` | `{max_depth?=3}` | Recursive tree dict |
| `list_elements` | `{control_type?, name_filter?}` | `[{name, control_type, automation_id, rect, ...}, ...]` |

### Manipulation

| action | params | return data |
|--------|--------|-------------|
| `click` | `{name?, control_type?, automation_id?, index?=0}` | `{clicked, window_title_after}` |
| `right_click` | `{name?, control_type?, automation_id?}` | `{right_clicked}` |
| `double_click` | `{name?, control_type?, automation_id?}` | `{double_clicked}` |
| `type_text` | `{text, clear_first?=false}` | `{typed}` |
| `press_key` | `{key}` | `{pressed}` |
| `scroll` | `{direction, amount?=3}` | `{scrolled}` |
| `switch_window` | `{title}` | `{switched_to}` |

---

## Browser Commands — Core (same as before)

### Lifecycle

| action | params | return data |
|--------|--------|-------------|
| `browser_open` | `{url, headless?, viewport_width?, viewport_height?, screenshots_dir?, session_id?}` | `{url, title, viewport}` |
| `browser_close` | `{}` | `{closed: true}` |

### Observation

| action | params | return data |
|--------|--------|-------------|
| `browser_screenshot` | `{label, full_page?=false}` | `{filename, label, file_size_kb, number, image_base64}` |
| `browser_get_dom` | `{selector?="body", max_length?=50000}` | `{html, url, title, length}` |
| `browser_get_text` | `{selector}` | `{text, selector}` |
| `browser_get_url` | `{}` | `{url, title}` |
| `browser_eval_js` | `{expression}` | `{result}` |

### Navigation

| action | params | return data |
|--------|--------|-------------|
| `browser_navigate` | `{url}` | `{url, title, status}` |
| `browser_back` | `{}` | `{url, title}` |
| `browser_forward` | `{}` | `{url, title}` |
| `browser_refresh` | `{}` | `{url, title}` |
| `browser_wait` | `{seconds?=1}` | `{waited}` |

### Interaction

| action | params | return data |
|--------|--------|-------------|
| `browser_click` | `{selector}` | `{clicked, url_after, title_after}` |
| `browser_type` | `{selector, text, clear_first?=false}` | `{typed, selector}` |
| `browser_select` | `{selector, value}` | `{selected, selector, value}` |
| `browser_hover` | `{selector}` | `{hovered, selector}` |
| `browser_scroll` | `{direction, amount?=500, selector?}` | `{scrolled}` |
| `browser_press_key` | `{key}` | `{pressed}` |

---

## Browser Commands — Task Mode (NEW)

### File Download

| action | params | return data |
|--------|--------|-------------|
| `browser_download` | `{url, filename?}` | `{filename, size_kb, uploaded}` |
| `browser_download_batch` | `{urls: [{url, filename?}, ...]}` | `{downloaded, failed, total_size_kb, files: [...]}` |

**`browser_download` implementation**:
1. Use `page.request` (Playwright API context) or `requests.get()` to download
2. Save to temp dir
3. Upload to Controller: `POST /upload` (multipart)
4. Delete local temp file
5. Return metadata

**`browser_download_batch` implementation**:
1. For each URL: download → upload → delete temp
2. Report progress in data: `{downloaded: 15, total: 47, current: "Vol1_Ch16.pdf"}`
3. On individual failure: skip, add to `failed` list, continue

### Link/Data Extraction

| action | params | return data |
|--------|--------|-------------|
| `browser_scrape_links` | `{selector?, pattern?, attribute?="href"}` | `{links: [{text, url}, ...], count}` |
| `browser_scrape_table` | `{selector, format?="json"}` | `{headers: [...], rows: [[...], ...], row_count}` |
| `browser_scrape_text` | `{selectors: [{name, selector}, ...]}` | `{data: {name: value, ...}}` |

**`browser_scrape_links`**:
- Default: all `<a>` tags
- `selector`: CSS selector to scope (e.g., `"#content a"`)
- `pattern`: regex filter on href (e.g., `"\.pdf$"`)
- Returns: `[{text: "Chapter 1", url: "https://...ch01.pdf"}, ...]`

**`browser_scrape_table`**:
- Finds `<table>` matching selector
- Extracts headers from `<th>` or first `<tr>`
- Extracts rows from `<td>`
- format: `"json"` (array of arrays) or `"csv"` (CSV string)

**`browser_scrape_text`**:
- Extract multiple named values: `[{name: "price", selector: ".price"}, {name: "title", selector: "h1"}]`
- Returns: `{data: {price: "$29.99", title: "Product Name"}}`

### Form Automation

| action | params | return data |
|--------|--------|-------------|
| `browser_fill_form` | `{fields: [{selector, value, type?}, ...]}` | `{filled: 5, failed: 0}` |
| `browser_submit_form` | `{selector?="form", submit_selector?}` | `{submitted, url_after, title_after}` |

**`browser_fill_form`**:
- `type` can be: `"text"` (default, uses `.fill()`), `"select"` (uses `.select_option()`), `"checkbox"` (uses `.check()` / `.uncheck()`), `"radio"` (uses `.check()`)
- Fills all fields in sequence, reports count

---

## File Upload to Controller

```python
def upload_file_to_controller(filepath, session_id, filename):
    """Upload a file from Worker to Controller via POST /upload"""
    with open(filepath, 'rb') as f:
        response = requests.post(
            f"{controller_url}/upload",
            files={'file': (filename, f)},
            data={'session_id': session_id, 'filename': filename},
            timeout=300
        )
    return response.json()
```

For large files: upload in chunks or use streaming.

---

## pywinauto Reference

| Operation | Code |
|-----------|------|
| Backend | `'uia'` |
| Connect | `Application(backend='uia').connect(title_re=..., timeout=10)` |
| Find element | `window.child_window(title=..., control_type=..., auto_id=...)` |
| Screenshot | `window.capture_as_image()` |
| Keys | `pywinauto.keyboard.send_keys()` |
| Scroll | `pyautogui.scroll()` |

## Playwright Reference

| Operation | Code |
|-----------|------|
| Launch | `sync_playwright().start()` → `p.chromium.launch()` |
| Context | `browser.new_context(viewport=..., accept_downloads=True)` |
| Navigate | `page.goto(url, wait_until="domcontentloaded")` |
| Screenshot | `page.screenshot()` |
| Click | `page.locator(selector).click()` |
| Type | `page.locator(selector).fill(text)` |
| Download | `page.request.get(url)` or `requests.get(url)` |

**Note**: In task mode, `accept_downloads=True` in browser context (explore mode: `False`).

---

## Polling Loop

```
1. POST /register (retry every 2s)
2. Loop:
   GET /command
   ├─ "wait"     → sleep, continue
   ├─ "shutdown"  → exit
   └─ command    → handle_command() → POST /result
   Download commands: longer timeout (300s vs 60s)
```

---

## exe Build

```bat
pyinstaller --onefile --name worker --console ^
    --hidden-import=pywinauto ^
    --hidden-import=pywinauto.controls.common_controls ^
    --hidden-import=pywinauto.controls.uia_controls ^
    --hidden-import=comtypes ^
    worker.py
```

Playwright Chromium not bundled — run `playwright install chromium` on target.

---

## Dependencies

```
pywinauto>=0.6.8
pyautogui>=0.9.54
Pillow>=10.0.0
requests>=2.31.0
playwright>=1.40.0
pyinstaller>=6.0.0
```
