# Auto Bot

Visual automation bot สำหรับทำงานซ้ำๆ บน SAP, web browser และ desktop app โดยใช้ image matching เป็น trigger ตัดสินใจการทำงาน

## Features

- **Image Trigger** — bot จับภาพหน้าจอแล้วเทียบกับรูปที่กำหนดไว้ เมื่อเจอหน้าที่ตรงกันจะเริ่ม loop ที่ผูกไว้โดยอัตโนมัติ
- **Sequence Editor** — สร้างและแก้ไข loop ผ่าน GUI ไม่ต้องแก้ไฟล์ config เอง รวมถึง branch ซ้อน (`if_image` then/else, `switch_image` หลาย case), ตัวแปร (Variables) และ States/Triggers
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
│   ├── ocr.py               # Tesseract OCR (wait_text / repeat_key_until)
│   └── interrupt_handler.py # ESC pause / failsafe stop
└── gui/
    ├── main_window.py       # control panel
    ├── sequence_editor.py   # visual loop builder
    ├── capture_tool.py      # screen region selector
    ├── error_dialog.py      # image not found dialog
    └── log_panel.py         # real-time activity log
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

บอทมีคำสั่ง (Action) ให้เลือกใช้งานทั้งรูปแบบการสั่งงานทั่วไป (Basic Actions) และแบบเงื่อนไขขั้นสูง (Advanced / Conditional Actions) ดังนี้:

#### 1. Basic Actions (สั่งงานทั่วไป)

*   **`click_image`** — ค้นหาภาพวัตถุบนหน้าจอแล้วทำการคลิก
    *   `target`: Path ของรูปภาพ (เช่น `elements/button.png`)
    *   `timeout` (default `10`): เวลารอภาพปรากฏ (วินาที)
    *   `confidence` (default `0.85`): ความแม่นยำในการค้นหา (0.0 - 1.0)
    *   `offset_x`, `offset_y`: ปรับจุดคลิกให้เยื้องจากมุมซ้ายบนของรูปภาพ (เลือกพิกเซลผ่าน GUI ได้)
*   **`click`** — คลิกที่พิกเซลพิกัดตรงๆ
    *   `x`, `y`: พิกัดพิกเซลบนหน้าจอ
*   **`type`** — พิมพ์ข้อความอัตโนมัติ (ระบบจะแอบส่งผ่าน clipboard ctrl+v เพื่อความเร็วสำหรับ SAP / desktop app)
    *   `text`: ข้อความที่ต้องการพิมพ์ (รองรับ `{USERNAME}` ตัวแปรระบบ, `{TODAY}` วันที่วันนี้, `{csv.COLUMN_NAME}` ข้อมูลจาก CSV)
*   **`key`** — กดคีย์เดี่ยวๆ บนคีย์บอร์ด
    *   `key`: ชื่อคีย์ เช่น `enter`, `tab`, `escape`, `f1`, `backspace`, `up`, `down`, `left`, `right`
*   **`hotkey`** — กดคีย์บอร์ดร่วมกันหลายปุ่ม
    *   `keys`: คีย์ที่เชื่อมด้วยเครื่องหมาย `+` เช่น `ctrl+s`, `alt+f4`
*   **`wait`** — หน่วงเวลาหยุดนิ่งก่อนไปขั้นตอนถัดไป
    *   `seconds` (default `1`): วินาทีที่ต้องการหยุดรอ
*   **`scroll`** — สกรอลล์เมาส์เลื่อนขึ้น/ลง
    *   `x`, `y`: จุดที่ต้องการสกรอลล์
    *   `clicks`: จำนวนคลิกในการหมุน (บวก = สกรอลล์ขึ้น, ลบ = สกรอลล์ลง)
*   **`drag`** — ลากแล้ววาง (Drag and Drop)
    *   `src_x`, `src_y` / `dst_x`, `dst_y`: พิกัดเริ่มต้นและสิ้นสุด
    *   `duration` (default `0.5`): ความเร็วในการลากเมาส์
*   **`screenshot`** — บันทึกภาพหน้าจอขณะนั้น
    *   `path` (optional): โฟลเดอร์/ชื่อไฟล์ที่จะเซฟ หากไม่ใส่จะบันทึกลงโฟลเดอร์เริ่มต้น

#### 2. Advanced & Conditional Actions (เงื่อนไขและวนซ้ำ)

*   **`wait_image`** — รอจนกว่าภาพเป้าหมายจะ "ปรากฏ" หรือ "หายไป" ก่อนทำงานต่อ
    *   `target`: Path ของรูปภาพ
    *   `mode` (`appear` / `disappear`): รอให้ภาพโผล่ขึ้นมา หรือรอให้ภาพหายไปจากหน้าจอ
    *   `timeout`: เวลารอสูงสุด (วินาที)
*   **`wait_text`** — รอจนกระทั่งตรวจพบข้อความในพื้นที่ที่กำหนด (ใช้ระบบ OCR อ่านหน้าจอ)
    *   `region`: พิกัดกรอบสี่เหลี่ยม `[x, y, w, h]` (กำหนดค่าผ่าน GUI ลากกรอบได้)
    *   `mode` (`filled` / `empty`): รอจนกว่าในกรอบมีตัวอักษร หรือรอจนกว่ากรอบนั้นจะว่างเปล่า
    *   `min_chars` (default `1`): จำนวนตัวอักษรขั้นต่ำ
    *   `timeout`: เวลารอสูงสุด
*   **`repeat_key_until`** — กดปุ่มคีย์บอร์ดค้าง/ซ้ำๆ เรื่อยๆ จนกว่าเงื่อนไขบนหน้าจอจะเป็นจริง
    *   `key` (default `enter`): คีย์ที่ต้องการกดซ้ำๆ
    *   `until` (`image_appears` / `image_disappears` / `text_filled` / `text_empty`): เงื่อนไขที่ต้องการให้หยุดกด
    *   `target` / `region`: ภาพหรือพื้นที่สำหรับใช้ตรวจสอบเงื่อนไข
    *   `max_attempts` (default `20`): จำกัดจำนวนการกดสูงสุด เพื่อป้องกันลูปค้าง
    *   `delay` (default `0.5`): หน่วงเวลาการกดแต่ละรอบ (วินาที)
*   **`if_image`** — การแบ่งสาขาทำงาน (Branching) เช็กภาพบนจอเพื่อเลือกทางไปต่อ (2 ทาง)
    *   `target`: ภาพที่ใช้เช็คเงื่อนไข
    *   `then`: ลิสต์ของ Action ย่อยที่จะทำถ้า **เจอ** รูปนี้
    *   `else`: ลิสต์ของ Action ย่อยที่จะทำถ้า **ไม่เจอ** รูปนี้
    *   แก้ then/else ได้ใน Sequence Editor โดยตรง (ไม่ต้องแก้ YAML)
*   **`switch_image`** — การแบ่งสาขาแบบ **หลายทาง (3+ ทาง)** ไล่เช็ก case จากบนลงล่าง เจอรูปแรกที่ตรงรัน case นั้นแล้วจบ
    *   `cases`: ลิสต์ของ case ตามลำดับความสำคัญ แต่ละ case = `{target, confidence?, steps:[...]}`
    *   `default`: ลิสต์ Action ที่ทำเมื่อ **ไม่เข้า case ใดเลย** (ไม่ใส่ก็ได้ = ไม่ทำอะไร)
    *   `confidence`: ค่า default ที่ใช้ถ้า case ไม่ได้ระบุ confidence เอง
    *   ทำงานร่วมกับ `skip_row` / `stop_if_image` ในสาขาได้ (เช่น case "ไม่มีงาน" → `skip_row`)
*   **`stop_if_image`** — สั่งหยุดบอททันทีหากตรวจพบภาพเป้าหมายบนจอ
    *   `target`: ภาพหน้าต่างแจ้งเตือนหรือภาพ Error
    *   `message`: ข้อความแจ้งเตือนผู้ใช้งานเมื่อบอทหยุด
*   **`skip_row_if_image`** — ถ้าเจอภาพเป้าหมาย → **ข้ามแถว CSV ปัจจุบัน** ไปทำแถวถัดไป (ไม่หยุดทั้งงาน) เหมาะกับเคส "รายการนี้ไม่มีงาน ข้ามไปตัวถัดไป"
    *   `target`: ภาพที่บอกว่าควรข้ามแถวนี้ (เช่น หน้าต่าง "ไม่พบข้อมูล")
    *   `confidence`, `message`: ความแม่นยำ และหมายเหตุที่จะ log
    *   ใช้ได้เฉพาะ loop ที่มี `data_source` (CSV) — ถ้าไม่มี CSV จะจบ loop เฉยๆ
*   **`skip_row`** — ข้ามแถว CSV ปัจจุบันทันทีแบบไม่มีเงื่อนไข (step ที่เหลือในแถวจะไม่ถูกทำ) มักวางไว้ในสาขา `then`/`else` ของ `if_image`
    *   `message`: หมายเหตุที่จะ log

#### 3. Error Guards (ระบบเฝ้าระวัง Error ตลอดเวลา)
คุณสามารถใส่ `error_guards` ไว้ที่หัวข้อระดับสูงสุดของ Loop เพื่อสั่งตรวจจับหน้าต่างแจ้งเตือนหรือหน้าจอ Error ตลอดเวลาก่อนทำทุก Step
```yaml
loops:
  loop_name:
    error_guards:
      - target: "elements/sap_error_popup.png"
        message: "เกิดข้อผิดพลาดในการเปิดออเดอร์ใน SAP บอทถูกหยุดการทำงานแล้ว"
    steps:
      - ...
```

#### 4. on_row_error (นโยบายเมื่อแถว CSV ทำงานพลาด)
ตั้งค่าระดับ Loop ว่าถ้า step ใดในแถวหนึ่ง error (เช่น หาภาพไม่เจอ) จะให้ทำอย่างไร:
*   `stop` (default): หยุดทั้งงานทันที
*   `skip`: log ไว้แล้ว **ข้ามไปทำแถว CSV ถัดไป** — ทำให้ batch ไม่ล้มทั้งหมดเพราะแถวเดียวพัง
```yaml
loops:
  loop_name:
    data_source: "data/tasks.csv"
    on_row_error: skip          # แถวไหนพัง ข้ามไปทำต่อ ไม่ล้มทั้ง batch
    steps:
      - ...
```

---

## Use Cases และแนวทางการใช้งานจริง

### Usecase 1: วนอ่านข้อมูลจาก CSV เพื่อเปิด Order ใน SAP
*   **โจทย์**: มีรหัสสินค้า และ จำนวน หลายรายการในไฟล์ CSV ต้องการนำมาคีย์ลง SAP ทีละตัวจนหมด
*   **แนวทางการออกแบบ Step**:
    1. ผูกข้อมูล CSV ด้วยคำสั่ง `data_source: data/tasks.csv`
    2. คีย์รหัสสินค้าโดยใช้ `{csv.MATERIAL_CODE}`
    3. คีย์จำนวนสินค้าโดยใช้ `{csv.QTY}`
    4. กดคีย์ `enter` เพื่อโหลดหน้าต่างถัดไป
    5. เมื่อบันทึกเรียบร้อย ให้กดปุ่ม Save และสั่งให้บอทกดปุ่ม Back กลับมายังหน้าเริ่มต้นกรอกข้อมูล

### Usecase 2: กด Enter โหลดข้อมูลใน SAP จนกว่าผลลัพธ์จะแสดงผล (วันที่จบปรากฏ)
*   **โจทย์**: หลังจากกรอกรหัสสินค้าและวันที่เริ่มแล้ว ระบบ SAP ต้องกด Enter ไปเรื่อยๆ จนกว่าช่องผลลัพธ์ "วันที่จบ" จะมีการคำนวณและแสดงผลออกมา ซึ่งในบางวันอาจใช้จำนวนครั้งที่กด Enter ไม่เท่ากัน
*   **แนวทางการออกแบบ Step**:
    *   ใช้ Action: `repeat_key_until`
    *   `key`: `enter`
    *   `until`: `text_filled`
    *   `region`: `[x, y, w, h]` (พิกัดกล่องของช่องวันที่จบใน SAP)
    *   `max_attempts`: `10`
    *   `delay`: `0.8` (เผื่อเวลาให้ SAP ประมวลผล)

### Usecase 3: ป้องกันบอทค้างเมื่อมี Error แจ้งเตือนขึ้นระหว่างรันลูป
*   **โจทย์**: ระหว่างที่บอทกำลังวนคีย์ข้อมูลจำนวน 100 รายการ บางรายการอาจจะเจอรหัสสินค้าที่ไม่พบบนคลัง ทำให้ SAP เด้งหน้าต่าง Error หรือกล่องสีแดง บอทปกติจะคีย์ต่อไม่ทันและกดผิดจุดไปเรื่อยๆ
*   **แนวทางการออกแบบ Step**:
    *   ใช้ Action `stop_if_image` ตรวจจับภาพกล่องแดง `elements/error_box.png` ทันทีหลังจากส่งคำสั่ง
    *   หรือใส่รูป `elements/error_popup.png` ลงใน `error_guards` ของลูป เพื่อเช็กหน้าจอก่อนจะขยับไปทำขั้นตอนอื่นในทุกลูป

### Usecase 4: กรณีกดปุ่ม Save แล้วหน้าจอโหลดช้า
*   **โจทย์**: เมื่อกดปุ่ม Save แล้ว จะเกิด Loading indicator หรือ หน้าจอค้างไปสักพัก ก่อนจะกลับคืนหน้าจอพร้อมกรอกงานใหม่
*   **แนวทางการออกแบบ Step**:
    *   ใช้ Action `wait_image`
    *   `target`: `elements/loading_spinner.png`
    *   `mode`: `disappear`
    *   `timeout`: `30`
    *   *บอทจะหน่วงรอจนกว่าภาพหมุนๆ จะหายไปจากจอแล้วค่อยเริ่มรันงานแถวถัดไป*

---

## Interrupt

| วิธี | ผล |
|------|----|
| กด `ESC` | Pause / Resume |
| ขยับ mouse ไปมุมซ้ายบน | Stop ทันที |
| กดปุ่ม Stop | Stop |

## SAP GUI Scripting

ต้องเปิดใน SAP Logon ก่อน:
> Options → Accessibility & Scripting → Scripting → **Enable scripting**
