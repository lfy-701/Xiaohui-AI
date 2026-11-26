"""生成「听音乐」表情的 6 个设计方案预览（含两帧，示意节奏变化）。"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\表情风格预览")
OUT.mkdir(parents=True, exist_ok=True)

W, H = 128, 64
SCALE = 3
BG = (8, 12, 22)
FG = (120, 220, 255)


def font(size):
    for name in ("msyh.ttc", "simhei.ttf"):
        p = Path(r"C:\Windows\Fonts") / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def note(d, x, y, size=12, fill=FG):
    """八分音符：符头 + 符干 + 符尾。"""
    r = size * 0.28
    d.ellipse([x - r, y + size * 0.5 - r, x + r, y + size * 0.5 + r], fill=fill)
    d.line([x + r, y + size * 0.5, x + r, y], fill=fill, width=max(2, int(size * 0.14)))
    d.line([x + r, y, x + r + size * 0.42, y + size * 0.18],
           fill=fill, width=max(2, int(size * 0.14)))


def heart(d, cx, cy, size, fill=FG):
    pts = []
    for i in range(0, 360, 10):
        a = math.radians(i)
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * size / 16.0, cy - y * size / 16.0))
    d.polygon(pts, fill=fill)


# ---------------- 方案 1：音符眼 ----------------
def m1(d, frame):
    for cx in (40, 88):
        note(d, cx - 5, 16, 16)
    if frame == 0:
        d.arc([50, 44, 78, 60], 20, 160, fill=FG, width=3)
    else:
        d.arc([50, 42, 78, 58], 20, 160, fill=FG, width=3)


# ---------------- 方案 2：闭眼微笑 + 飘音符 ----------------
def m2(d, frame):
    for cx in (40, 88):
        d.arc([cx - 13, 22, cx + 13, 42], 200, 340, fill=FG, width=4)
    d.arc([50, 42, 78, 58], 20, 160, fill=FG, width=3)
    if frame == 0:
        note(d, 100, 6, 11); note(d, 112, 14, 9)
    else:
        note(d, 100, 10, 11); note(d, 114, 4, 9)


# ---------------- 方案 3：耳机狗 ----------------
def m3(d, frame):
    # 耳机头梁
    d.arc([22, 8, 106, 56], 200, 340, fill=FG, width=4)
    # 耳罩
    d.rounded_rectangle([18, 26, 30, 44], radius=4, fill=FG)
    d.rounded_rectangle([98, 26, 110, 44], radius=4, fill=FG)
    # 眼睛（闭眼笑）
    for cx in (46, 82):
        d.arc([cx - 9, 26, cx + 9, 38], 200, 340, fill=FG, width=3)
    if frame == 0:
        d.arc([56, 44, 72, 54], 20, 160, fill=FG, width=3)
    else:
        d.arc([54, 42, 74, 52], 20, 160, fill=FG, width=3)


# ---------------- 方案 4：频谱眼 ----------------
def m4(d, frame):
    # 眼睛位置变成跳动的频谱柱
    heights = (10, 20, 28, 16) if frame == 0 else (18, 26, 14, 22)
    x0 = 30
    for i, h in enumerate(heights):
        x = x0 + i * 8
        d.rectangle([x, 34 - h, x + 5, 34], fill=FG)
    x0b = 74
    for i, h in enumerate(heights[::-1]):
        x = x0b + i * 8
        d.rectangle([x, 34 - h, x + 5, 34], fill=FG)
    d.arc([52, 44, 76, 58], 20, 160, fill=FG, width=3)


# ---------------- 方案 5：爱心眼 + 音符（改造版） ----------------
def m5(d, frame):
    for cx in (40, 88):
        heart(d, cx, 30, 13 if frame == 0 else 14)
    d.arc([50, 44, 78, 58], 20, 160, fill=FG, width=3)
    note(d, 106, 4, 10)


# ---------------- 方案 6：眨眼享受（一只眼闭） ----------------
def m6(d, frame):
    if frame == 0:
        d.ellipse([30, 20, 50, 40], outline=FG, width=3)
        d.ellipse([36, 26, 44, 34], fill=FG)
    else:
        d.arc([30, 24, 50, 40], 200, 340, fill=FG, width=3)
    d.arc([78, 24, 98, 40], 200, 340, fill=FG, width=3)
    d.arc([52, 44, 76, 58], 20, 160, fill=FG, width=3)
    note(d, 104, 6, 10)


DESIGNS = [
    ("music-1-note", "① 音符眼", m1),
    ("music-2-closed", "② 闭眼笑 + 飘音符", m2),
    ("music-3-headphone", "③ 戴耳机", m3),
    ("music-4-equalizer", "④ 频谱眼", m4),
    ("music-5-heart", "⑤ 爱心眼 + 音符（改造）", m5),
    ("music-6-wink", "⑥ 单眼眨 + 音符", m6),
]

GAP = 12
LABEL = 52
cw, ch = W * SCALE, H * SCALE

# 每个方案两帧
sheet_w = GAP + 2 * (cw + GAP) + 8
row_h = ch + LABEL
sheet_h = GAP + len(DESIGNS) * row_h + 40
sheet = Image.new("RGB", (sheet_w, sheet_h), (238, 242, 249))
ds = ImageDraw.Draw(sheet)
ds.text((GAP, 8), "小慧「正在听音乐」表情方案（每个方案两帧，示意节奏）",
        font=font(19), fill=(25, 55, 105))

for r, (key, title, fn) in enumerate(DESIGNS):
    y0 = 40 + r * row_h
    ds.text((GAP, y0), title, font=font(15), fill=(40, 70, 120))
    for f in range(2):
        x = GAP + f * (cw + GAP) + 20
        tile = Image.new("RGB", (W, H), BG)
        fn(ImageDraw.Draw(tile), f)
        sheet.paste(tile.resize((cw, ch), Image.NEAREST), (x, y0 + 22))
        ds.rectangle([x - 1, y0 + 21, x + cw, y0 + 22 + ch], outline=(200, 212, 230))
        ds.text((x + 4, y0 + ch + 26), f"帧 {f + 1}", font=font(12), fill=(90, 100, 115))

p = OUT / "听音乐表情方案.png"
sheet.save(p)
print("已生成:", p)
