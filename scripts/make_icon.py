"""
สร้าง icon.ico ของ Auto Bot — หุ่นยนต์โทนน้ำเงิน/เทอร์ควอยซ์ตามธีม GUI
วาดที่ความละเอียดสูงแล้วย่อ (supersampling) ให้ขอบเนียน

รัน:  python scripts/make_icon.py
ผลลัพธ์: icon.ico (หลายขนาด) + assets/icon_preview.png
"""
import os

from PIL import Image, ImageDraw

S = 1024  # canvas ความละเอียดสูง (จะย่อเหลือ 256)

# สีตามธีม GUI
BG_TOP = (17, 119, 187)     # #1177bb
BG_BOT = (10, 70, 120)      # #0a4678
HEAD = (235, 238, 241)      # หัวสีอ่อน
HEAD_EDGE = (200, 206, 212)
ACCENT = (78, 201, 176)     # #4ec9b0 teal — ตา/เสาอากาศ
DARK = (14, 99, 156)        # #0e639c — ปาก


def rrect(draw, box, r, **kw):
    draw.rounded_rectangle(box, radius=r, **kw)


def build() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # พื้นหลัง gradient แนวตั้ง บน rounded square
    margin = int(S * 0.04)
    grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        gd.line([(0, y), (S, y)], fill=col + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [margin, margin, S - margin, S - margin], radius=int(S * 0.17), fill=255)
    img.paste(grad, (0, 0), mask)

    # antenna (เสาอากาศ)
    cx = S // 2
    head_top = int(S * 0.30)
    d.line([(cx, head_top - int(S * 0.07)), (cx, head_top + 10)],
           fill=ACCENT, width=int(S * 0.022))
    rb = int(S * 0.035)
    d.ellipse([cx - rb, head_top - int(S * 0.115), cx + rb, head_top - int(S * 0.115) + 2 * rb],
              fill=ACCENT)

    # หัวหุ่นยนต์
    hw, hh = int(S * 0.56), int(S * 0.50)
    hx0, hy0 = cx - hw // 2, head_top
    hx1, hy1 = cx + hw // 2, head_top + hh
    rrect(d, [hx0, hy0, hx1, hy1], r=int(S * 0.10),
          fill=HEAD, outline=HEAD_EDGE, width=int(S * 0.008))

    # หู (สองข้าง)
    ew, eh = int(S * 0.05), int(S * 0.14)
    ey = (hy0 + hy1) // 2 - eh // 2
    rrect(d, [hx0 - ew, ey, hx0 + 4, ey + eh], r=int(S * 0.02), fill=ACCENT)
    rrect(d, [hx1 - 4, ey, hx1 + ew, ey + eh], r=int(S * 0.02), fill=ACCENT)

    # ตา (สองดวง) + ไฮไลต์
    er = int(S * 0.072)
    eye_y = hy0 + int(hh * 0.36)
    for ox in (-int(hw * 0.21), int(hw * 0.21)):
        ecx = cx + ox
        d.ellipse([ecx - er, eye_y - er, ecx + er, eye_y + er], fill=DARK)
        d.ellipse([ecx - er, eye_y - er, ecx + er, eye_y + er], outline=ACCENT,
                  width=int(S * 0.012))
        hr = int(er * 0.32)
        d.ellipse([ecx - hr - int(er * 0.25), eye_y - hr - int(er * 0.25),
                   ecx - int(er * 0.25), eye_y - int(er * 0.25)], fill=(255, 255, 255))

    # ปาก (กริด/ฟัน)
    mw, mh = int(hw * 0.46), int(S * 0.045)
    mx0 = cx - mw // 2
    my0 = hy0 + int(hh * 0.66)
    rrect(d, [mx0, my0, mx0 + mw, my0 + mh], r=int(S * 0.012), fill=DARK)
    for i in range(1, 4):
        x = mx0 + mw * i // 4
        d.line([(x, my0), (x, my0 + mh)], fill=HEAD, width=int(S * 0.006))

    return img.resize((256, 256), Image.LANCZOS)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img = build()
    ico_path = os.path.join(root, "icon.ico")
    img.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32),
                              (48, 48), (64, 64), (128, 128), (256, 256)])
    assets = os.path.join(root, "assets")
    os.makedirs(assets, exist_ok=True)
    img.save(os.path.join(assets, "icon_preview.png"))
    print(f"wrote {ico_path}")
    print(f"wrote {os.path.join(assets, 'icon_preview.png')}")


if __name__ == "__main__":
    main()
