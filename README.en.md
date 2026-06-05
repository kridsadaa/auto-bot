# Auto Bot

[![CI](https://github.com/kridsadaa/auto-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/kridsadaa/auto-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇬🇧 English (this file) · 🇹🇭 [ภาษาไทย](README.md)

A visual automation bot for repetitive tasks on SAP, web browsers, and desktop apps — using on-screen **image matching** as the trigger and decision engine.

> **Open source (MIT)** — runs 100% locally, your data never leaves the machine, and the code is fully auditable by IT/Basis. Ideal for SAP work where data confidentiality matters.

## Why this exists

Most open-source RPA tools (TagUI, rpaframework, SikuliX, AutoHotkey) are **code-first** — you have to write scripts. Auto Bot is **GUI-first**: ordinary, non-technical users build bots the way they already think about their screen — *"when I see this, I click that"* — with no XPath, CSS selectors, or programming required.

## Features

- **Image Trigger** — the bot captures the screen and compares it against reference images; when a matching screen appears, it automatically starts the loop bound to it.
- **Sequence Editor** — build and edit loops through a GUI (no config files): nested branching (`if_image` then/else, multi-case `switch_image`), variables, and states/triggers.
- **Capture Tool** — drag a box on screen to capture a trigger / element image. Images captured while editing a loop are auto-saved to `elements/<loop name>/`.
- **Data Source** — static values, automatic dates, and row-by-row iteration over CSV/XLSX.
- **Live Debugger** — when a step fails (image not found / action error), the bot pauses and opens a Debug Console for live recovery: Retry / Skip Step / **Restart Row** / **Inject recovery command then Retry** / Recapture / Stop.
- **Two modes** — Copilot (confirm before each action) and Agent (fully automatic).
- **UI Automation** — target elements via UIA selectors (pywinauto) instead of images — robust to resolution/theme/zoom changes (`click_element`, `set_element_text`, `wait_element`), plus a "pick element" button that finds selectors for you.
- **File I/O** — read `.xlsx`/`.csv` as a data source and write results directly to `.xlsx`/`.csv` (`write_row`) without typing through the screen.
- **Recorder** — record clicks/typing into steps automatically (press F10 to stop).
- **Scheduling** — schedule loops via Windows Task Scheduler + a `--run-loop` CLI mode.
- **Interrupt** — press ESC (from any window) to stop the bot; move the mouse to the top-left corner for an instant failsafe stop; pause/resume from the GUI.

## Supported targets

| Type | Method |
|------|--------|
| SAP GUI | Image matching + UI Automation (pywinauto) + keyboard/mouse simulation |
| Web browser | PyAutoGUI + image matching (Playwright is bundled for future web work) |
| Generic desktop app | PyAutoGUI + image matching / UI Automation |

> **Note:** the bot currently drives SAP by *looking at the screen* (image + UIA), which works with **any program on screen** — it does not yet use the SAP GUI Scripting API directly (see [Roadmap](#roadmap)).

## Install

**Easiest (recommended)** — one script creates `.venv` and installs dependencies, Chromium, and Tesseract-OCR:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

<details>
<summary>Or install manually</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium          # only if you'll automate the web
```

**OCR** (the `wait_text` / text-based `repeat_key_until` features) requires the separate Tesseract engine: install from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and set the `TESSERACT_CMD` env var to point at `tesseract.exe` if it isn't on your PATH.

</details>

> **Windows only** — `pywin32` and `pywinauto` are Windows-specific.
>
> 💡 Always use a **virtual environment (.venv)** — it avoids the `Access is denied` permission errors you hit when pip-installing into a system-wide Python.

## First-time setup

```powershell
copy config\bot_config.example.yaml config\bot_config.yaml
```

Edit `config/bot_config.yaml` and fill in your username and values.

## Usage

```powershell
python main.py
```

### Building a new bot

1. Click **+ Capture Trigger** → drag a box over a unique part of the screen (page title, logo).
2. Click **+ Capture Element** → capture a button or field the bot must click.
3. Click **Sequence Editor** → create a loop and add steps.
4. Add a state in `config/bot_config.yaml` linking the trigger to the loop.
5. Click **Start** → choose Agent mode → the bot runs.

## Config format

```yaml
variables:
  USERNAME: "your_user"
  COMPANY_CODE: "1000"
  PASSWORD: ""              # empty = bot asks at Start

states:
  - name: "SAP Login"
    trigger:
      type: image
      file: "triggers/sap_login.png"
      confidence: 0.85
      timeout: 15
    loop: "loop_login"

loops:
  loop_login:
    steps:
      - action: click_image
        target: "elements/username_field.png"
      - action: type
        text: "{USERNAME}"
      - action: key
        key: "tab"
      - action: type
        text: "{PASSWORD}"
      - action: key
        key: "enter"

  loop_po_entry:
    data_source: "data/tasks.csv"   # iterate row by row
    steps:
      - action: type
        text: "{TODAY}"             # today's date, DD.MM.YYYY
      - action: type
        text: "{csv.MATERIAL_CODE}" # a CSV column
```

### Actions overview

**Basic:** `click_image`, `click`, `type` (paste/type method, `clear_first`), `key`, `hotkey`, `wait`, `scroll`, `drag`, `screenshot`

**Advanced / conditional:**
- `wait_image` — wait until an image appears/disappears
- `wait_text` — wait until OCR detects text in a region is filled/empty
- `repeat_key_until` — press a key repeatedly until a screen condition becomes true
- `if_image` — two-way branch on whether an image is present (`then`/`else`)
- `switch_image` — multi-way branch over ordered `cases` with a `default`
- `stop_if_image` — stop the bot if an image (e.g. an error popup) appears
- `skip_row_if_image` / `skip_row` — skip the current CSV row and move to the next

**UI Automation:** `click_element`, `set_element_text`, `wait_element` (target by UIA selector)

**File I/O:** `write_row` — append a row to a `.csv`/`.xlsx` directly

**Loop-level guards:** `error_guards` (watch for error screens before every step), `on_row_error: stop|skip` (per-row failure policy)

See the [Thai README](README.md#actions-ที่รองรับ) for the full per-action parameter reference.

## CLI / Scheduling

Run a loop headless (for scheduled tasks):

```
python main.py --run-loop <loop name> [--config config/bot_config.yaml]
```

Use the **🕒 Schedule** button in the main window to create a Windows Task Scheduler task (names prefixed `AutoBot_`).

## Export / Import a loop

In the Sequence Editor:
- **⬆ Export loop** — packs the selected loop (all element/trigger images + the states pointing to it) into a single `*.botpack` file you can share.
- **⬇ Import loop** — opens a `.botpack`, extracts images into `elements/<loop>/`, and adds the loop/state to your config — ready to run.

Variable values (USERNAME/PASSWORD) are **never** bundled; CSV/XLSX data files prompt before being included; name collisions are auto-renamed.

## Interrupt

| Method | Effect |
|--------|--------|
| Press `ESC` (any window) | Stop the bot (panic stop) |
| Move mouse to top-left corner | Instant stop (failsafe) |
| Pause / Resume button (GUI) | Pause / continue |
| Stop button (GUI) | Stop |

## Roadmap

- [ ] **SAP GUI Scripting backend** — add `sap_set_field` / `sap_press` / `sap_read_status` actions that talk to SAP through the Scripting API (`win32com` → `GetScriptingEngine`) directly: more reliable than image matching, and able to read order numbers from the status bar without OCR. The recorder will auto-capture element IDs so users still never deal with technical IDs.
- [ ] **AI self-healing** — when an image isn't found, fall back to AI vision to locate the closest matching element (see `concepts/design_philosophy_and_ai.md`).
- [ ] Real web automation via Playwright (currently bundled but not yet wired into the engine).

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md). Set up your dev environment with `scripts\setup.ps1`, then run `pytest -q`.

## License

[MIT](LICENSE) © 2026 kridsadaa
