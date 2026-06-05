# Contributing to Auto Bot

ขอบคุณที่สนใจช่วยพัฒนา Auto Bot! 🎉 — *Thanks for helping improve Auto Bot!*

โปรเจกต์นี้ตั้งใจให้ **คนทั่วไป (non-coder) สร้างบอทได้เอง** ฉะนั้นการเปลี่ยนแปลงทุกอย่างควรยึด "ความง่ายต่อผู้ใช้" เป็นหลัก
*This project exists to let ordinary, non-technical users build their own bots — keep end-user simplicity as the north star of every change.*

---

## ตั้งค่า dev environment / Dev setup

```powershell
# ครั้งเดียวจบ (สร้าง .venv + ติดตั้ง deps + Chromium + Tesseract)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

# เปิดใช้งาน venv
.\.venv\Scripts\Activate.ps1

# ติดตั้ง dev tools (pytest ฯลฯ)
pip install -e ".[dev]"
```

> **Windows เท่านั้น** — `pywin32` / `pywinauto` รองรับเฉพาะ Windows

## รันเทส / Running tests

```powershell
pytest -q
```

ทุก PR จะถูกรันเทสอัตโนมัติผ่าน GitHub Actions (`.github/workflows/ci.yml`) บน `windows-latest`
*Every PR runs the suite on `windows-latest` via GitHub Actions.*

**โค้ดใหม่ควรมาพร้อมเทส** — ดูตัวอย่างใน `tests/` (เทสส่วนใหญ่ mock การคลิก/หน้าจอ จึงรันได้โดยไม่ต้องมีจอจริง)

---

## โครงสร้างสำหรับเพิ่มฟีเจอร์ / Architecture for new features

- **`engine/actions.py`** — primitive ระดับล่าง (คลิก, พิมพ์, รอภาพ). เพิ่ม action ใหม่ที่นี่
- **`engine/loop_runner.py`** — ตัวแปล/รัน step จาก YAML. ลงทะเบียน action ใหม่ให้ runner รู้จัก
- **`gui/sequence_editor.py`** — ฟอร์มแก้ไข step. เพิ่ม UI ให้ action ใหม่ที่นี่ (ผู้ใช้ไม่ควรต้องแก้ YAML เอง)

### การเพิ่ม "backend" ใหม่ (เช่น SAP GUI Scripting)
ระบบแยก backend ของการสั่งงานไว้แล้ว — image matching (`click_image`), UIA (`click_element`).
backend ใหม่ควรเพิ่มเป็น action แยก **ไม่ใช่แทนที่ของเดิม** และยังต้องให้ recorder/picker จับค่าให้ผู้ใช้อัตโนมัติ เพื่อรักษาหลัก "ผู้ใช้ไม่ต้องรู้ศัพท์เทคนิค"

---

## แนวทาง code / Code style

- ตามสไตล์ของไฟล์รอบข้าง (naming, comment density)
- comment/log ภาษาไทยได้ — กลุ่มผู้ใช้หลักเป็นคนไทย แต่ docstring สาธารณะใส่อังกฤษคู่ได้ยิ่งดี
- ห้าม commit `config/`, `data/`, `triggers/`, `elements/` (อยู่ใน `.gitignore` แล้ว — กันข้อมูล credential/ลูกค้าหลุด)

## Pull Request

1. Fork → branch ใหม่จาก `main`
2. เพิ่มเทสให้ครอบคลุมการเปลี่ยนแปลง
3. `pytest -q` ผ่านครบในเครื่องก่อนเปิด PR
4. เขียนสรุปสั้นๆ ว่าแก้อะไร/ทำไม (ไทยหรืออังกฤษก็ได้)

## รายงานบั๊ก / Reporting bugs

เปิด Issue พร้อม: ขั้นตอนที่ทำให้เกิด, สิ่งที่คาดหวัง vs สิ่งที่เกิดจริง, เวอร์ชัน Windows/Python, และ log จาก `logs/` (ลบข้อมูลความลับออกก่อน)
