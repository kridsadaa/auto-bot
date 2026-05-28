# Auto Bot

Visual automation bot สำหรับทำงานซ้ำๆ บน SAP, web browser และ desktop app โดยใช้ image matching เป็น trigger ตัดสินใจการทำงาน

## Features

- **Image Trigger** — bot จับภาพหน้าจอแล้วเทียบกับรูปที่กำหนดไว้ เมื่อเจอหน้าที่ตรงกันจะเริ่ม loop ที่ผูกไว้โดยอัตโนมัติ
- **Sequence Editor** — สร้างและแก้ไข loop ผ่าน GUI ไม่ต้องแก้ไฟล์ config เอง
- **Capture Tool** — ลาก box บนหน้าจอเพื่อ capture trigger / element image ได้เลยไม่ต้องใช้โปรแกรมอื่น
- **Data Source** — รองรับค่า static, วันที่อัตโนมัติ และ loop ข้อมูลจาก CSV ทีละแถว
- **Error Dialog** — เมื่อหา image ไม่เจอ bot หยุดและแสดงรูปเปรียบเทียบให้ capture ใหม่ได้ทันที
- **สองโหมด** — Copilot (ยืนยันก่อนทำ) และ Agent (อัตโนมัติเต็ม)
- **Interrupt** — กด ESC เพื่อ pause, ขยับ mouse ไปมุมซ้ายบนเพื่อหยุดทันที

## รองรับ

| ประเภท | วิธี |
|--------|------|
| SAP Logon | SAP GUI Scripting (win32com) + image matching |
| Web browser | Playwright |
| Desktop app ทั่วไป | PyAutoGUI + image matching |

## ติดตั้ง

```bash
pip install -r requirements.txt
playwright install chromium
```

> **Windows เท่านั้น** — SAP GUI Scripting และ pywin32 รองรับเฉพาะ Windows

## ตั้งค่าเริ่มต้น

```bash
cp config/bot_config.example.yaml config/bot_config.yaml
```

แก้ไข `config/bot_config.yaml` ใส่ username และค่าที่ต้องการ

## วิธีใช้

```bash
python main.py
```

### ขั้นตอนสร้าง bot ใหม่

1. กด **+ Capture Trigger** → ลาก box คลุมส่วนที่เป็นเอกลักษณ์ของหน้านั้น (เช่น ชื่อหน้า, โลโก้)
2. กด **+ Capture Element** → capture ปุ่มหรือ field ที่ bot ต้องคลิก
3. กด **Sequence Editor** → สร้าง loop และเพิ่ม step
4. เพิ่ม state ใน `config/bot_config.yaml` เชื่อม trigger กับ loop
5. กด **Start** → เลือก Agent mode → bot เริ่มทำงาน

## โครงสร้างโปรเจกต์

```
auto-bot/
├── main.py                  # entry point
├── requirements.txt
├── config/
│   └── bot_config.yaml      # states, loops, variables (ไม่อยู่ใน git)
├── triggers/                # trigger images (ไม่อยู่ใน git)
├── elements/                # element images (ไม่อยู่ใน git)
├── data/                    # CSV files (ไม่อยู่ใน git)
├── engine/
│   ├── image_matcher.py     # OpenCV template matching
│   ├── actions.py           # click, type, key, drag, scroll
│   ├── data_source.py       # static / CSV / {TODAY} resolver
│   ├── loop_runner.py       # execute YAML sequences
│   ├── screen_monitor.py    # background state detection
│   └── interrupt_handler.py # ESC pause / failsafe stop
├── gui/
│   ├── main_window.py       # control panel
│   ├── sequence_editor.py   # visual loop builder
│   ├── capture_tool.py      # screen region selector
│   ├── error_dialog.py      # image not found dialog
│   └── log_panel.py         # real-time activity log
└── integrations/
    ├── sap_client.py        # SAP GUI Scripting
    └── web_client.py        # Playwright
```

## Config Format

```yaml
variables:
  USERNAME: "your_user"
  COMPANY_CODE: "1000"
  PASSWORD: ""              # เว้นว่าง = bot ถามตอน Start

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
        timeout: 5
      - action: type
        text: "{USERNAME}"
      - action: key
        key: "tab"
      - action: type
        text: "{PASSWORD}"
      - action: key
        key: "enter"

  loop_po_entry:
    data_source: "data/tasks.csv"   # loop ทีละ row
    steps:
      - action: type
        text: "{TODAY}"             # วันที่วันนี้ DD.MM.YYYY
      - action: type
        text: "{csv.MATERIAL_CODE}" # column จาก CSV
```

### Actions ที่รองรับ

| Action | พารามิเตอร์ |
|--------|------------|
| `click_image` | `target`, `timeout`, `confidence` |
| `click` | `x`, `y` |
| `type` | `text` (รองรับ `{VAR}`, `{TODAY}`, `{csv.COL}`) |
| `key` | `key` (enter, tab, escape, f1–f12 ...) |
| `hotkey` | `keys` (เช่น ctrl+s) |
| `wait` | `seconds` |
| `scroll` | `x`, `y`, `clicks` |
| `drag` | `src_x`, `src_y`, `dst_x`, `dst_y` |
| `screenshot` | `path` |

## Interrupt

| วิธี | ผล |
|------|----|
| กด `ESC` | Pause / Resume |
| ขยับ mouse ไปมุมซ้ายบน | Stop ทันที |
| กดปุ่ม Stop | Stop |

## SAP GUI Scripting

ต้องเปิดใน SAP Logon ก่อน:
> Options → Accessibility & Scripting → Scripting → **Enable scripting**
