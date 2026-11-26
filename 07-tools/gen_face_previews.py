"""生成表情风格预览图：4 种风格 × 7 种情绪，128x64 OLED 模拟。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\表情风格预览")
OUT.mkdir(parents=True, exist_ok=True)

W, H = 128, 64
SCALE = 3  # 放大显示
PAD = 14
LABEL_H = 26
GAP = 10

EMOTIONS = [
    ("neutral", "平常"),
    ("happy", "开心"),
    ("sad", "难过"),
    ("angry", "生气"),
    ("surprised", "惊讶"),
    ("love", "喜欢"),
    ("sleepy", "困了"),
]

BG = (8, 12, 22)
FG = (120, 220, 255)


def font(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        for base in (r"C:\Windows\Fonts", "/usr/share/fonts"):
            p = Path(base) / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except Exception:
                    pass
    return ImageFont.load_default()


def draw_heart(d, cx, cy, size=10, fill=True):
    """矢量爱心（不依赖字体字形）。"""
    pts = []
    import math
    for i in range(0, 360, 8):
        a = math.radians(i)
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * size / 16.0, cy - y * size / 16.0))
    if fill:
        d.polygon(pts, fill=FG)
    else:
        d.polygon(pts, outline=FG)


# ---------------- 四种风格 ----------------

def draw_dots(d, emo):
    """A. 圆眼豆豆（当前风格）"""
    left, right = (40, 30), (88, 30)
    r = 11
    for cx, cy in (left, right):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=FG, width=3)
    if emo == "happy":
        for cx, cy in (left, right):
            d.arc([cx - r, cy - 6, cx + r, cy + 12], 200, 340, fill=FG, width=3)
        d.arc([48, 40, 80, 58], 20, 160, fill=FG, width=3)
    elif emo == "sad":
        for cx, cy in (left, right):
            d.arc([cx - r, cy - 12, cx + r, cy + 6], 20, 160, fill=FG, width=3)
        d.arc([48, 46, 80, 62], 200, 340, fill=FG, width=3)
    elif emo == "angry":
        for cx, cy in (left, right):
            d.line([cx - r, cy - 12, cx + r, cy - 4], fill=FG, width=3)
        d.arc([48, 44, 80, 60], 200, 340, fill=FG, width=3)
    elif emo == "surprised":
        for cx, cy in (left, right):
            d.ellipse([cx - 5, cy - 6, cx + 5, cy + 6], fill=FG)
        d.ellipse([56, 42, 72, 58], outline=FG, width=3)
    elif emo == "love":
        for cx, cy in (left, right):
            draw_heart(d, cx, cy, 13)
        d.arc([48, 38, 80, 56], 20, 160, fill=FG, width=3)
    elif emo == "sleepy":
        for cx, cy in (left, right):
            d.line([cx - r, cy, cx + r, cy], fill=FG, width=3)
        d.line([54, 48, 74, 48], fill=FG, width=3)
        d.text((96, 12), "z", font=font(14), fill=FG)
    else:  # neutral
        for cx, cy in (left, right):
            d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=FG)
        d.line([54, 48, 74, 48], fill=FG, width=3)


def draw_square(d, emo):
    """B. 方形电子眼（科技感）"""
    for cx in (40, 88):
        d.rounded_rectangle([cx - 13, 18, cx + 13, 42], radius=4, outline=FG, width=3)
    if emo == "happy":
        for cx in (40, 88):
            d.line([cx - 8, 34, cx, 26], fill=FG, width=3)
            d.line([cx, 26, cx + 8, 34], fill=FG, width=3)
        d.rectangle([52, 48, 76, 54], fill=FG)
    elif emo == "sad":
        for cx in (40, 88):
            d.line([cx - 8, 26, cx + 8, 34], fill=FG, width=3)
        d.rectangle([52, 52, 76, 56], fill=FG)
    elif emo == "angry":
        for cx in (40, 88):
            d.line([cx - 10, 20, cx + 10, 30], fill=FG, width=3)
        d.rectangle([52, 52, 76, 56], fill=FG)
    elif emo == "surprised":
        for cx in (40, 88):
            d.rectangle([cx - 6, 24, cx + 6, 36], fill=FG)
        d.rounded_rectangle([56, 44, 72, 58], radius=3, outline=FG, width=3)
    elif emo == "love":
        for cx in (40, 88):
            draw_heart(d, cx, 30, 12)
        d.rectangle([52, 48, 76, 54], fill=FG)
    elif emo == "sleepy":
        for cx in (40, 88):
            d.rectangle([cx - 10, 30, cx + 10, 34], fill=FG)
        d.line([54, 50, 74, 50], fill=FG, width=3)
        d.text((98, 10), "Z", font=font(13), fill=FG)
    else:
        for cx in (40, 88):
            d.rectangle([cx - 5, 26, cx + 5, 36], fill=FG)
        d.line([54, 50, 74, 50], fill=FG, width=3)


def draw_bigeyes(d, emo):
    """C. 大眼萌（大椭圆 + 高光）"""
    for cx in (40, 88):
        d.ellipse([cx - 15, 14, cx + 15, 44], outline=FG, width=3)
        d.ellipse([cx - 6, 24, cx + 2, 34], fill=FG)   # 高光/瞳孔
    if emo == "happy":
        for cx in (40, 88):
            d.arc([cx - 13, 20, cx + 13, 40], 200, 340, fill=FG, width=3)
        d.arc([50, 44, 78, 60], 20, 160, fill=FG, width=3)
    elif emo == "sad":
        for cx in (40, 88):
            d.ellipse([cx - 4, 30, cx + 4, 42], fill=FG)
        d.arc([50, 50, 78, 64], 200, 340, fill=FG, width=3)
    elif emo == "angry":
        for cx in (40, 88):
            d.line([cx - 14, 16, cx + 14, 24], fill=FG, width=3)
        d.arc([50, 48, 78, 62], 200, 340, fill=FG, width=3)
    elif emo == "surprised":
        for cx in (40, 88):
            d.ellipse([cx - 8, 20, cx + 8, 40], fill=FG)
        d.ellipse([57, 44, 71, 60], outline=FG, width=3)
    elif emo == "love":
        for cx in (40, 88):
            draw_heart(d, cx, 28, 15)
        d.arc([50, 42, 78, 60], 20, 160, fill=FG, width=3)
    elif emo == "sleepy":
        for cx in (40, 88):
            d.arc([cx - 13, 26, cx + 13, 42], 200, 340, fill=FG, width=3)
        d.line([56, 50, 72, 50], fill=FG, width=3)
        d.text((100, 8), "z", font=font(16), fill=FG)
    else:
        for cx in (40, 88):
            d.ellipse([cx - 6, 22, cx + 6, 38], fill=FG)
        d.arc([56, 46, 72, 56], 20, 160, fill=FG, width=3)


def draw_line(d, emo):
    """D. 极简线条（横线眼）"""
    for cx in (40, 88):
        d.line([cx - 14, 30, cx + 14, 30], fill=FG, width=4)
    if emo == "happy":
        for cx in (40, 88):
            d.arc([cx - 14, 18, cx + 14, 38], 200, 340, fill=FG, width=4)
        d.arc([48, 42, 80, 60], 20, 160, fill=FG, width=4)
    elif emo == "sad":
        for cx in (40, 88):
            d.arc([cx - 14, 22, cx + 14, 42], 20, 160, fill=FG, width=4)
        d.arc([48, 50, 80, 66], 200, 340, fill=FG, width=4)
    elif emo == "angry":
        for cx in (40, 88):
            d.line([cx - 14, 22, cx + 14, 30], fill=FG, width=4)
        d.arc([48, 50, 80, 64], 200, 340, fill=FG, width=4)
    elif emo == "surprised":
        for cx in (40, 88):
            d.ellipse([cx - 5, 24, cx + 5, 36], outline=FG, width=3)
        d.ellipse([57, 44, 71, 58], outline=FG, width=3)
    elif emo == "love":
        for cx in (40, 88):
            draw_heart(d, cx, 28, 13)
        d.line([50, 50, 78, 50], fill=FG, width=4)
    elif emo == "sleepy":
        for cx in (40, 88):
            d.line([cx - 10, 30, cx + 10, 32], fill=FG, width=3)
        d.line([56, 50, 72, 50], fill=FG, width=3)
        d.text((98, 10), "z", font=font(15), fill=FG)
    else:
        for cx in (40, 88):
            d.line([cx - 10, 30, cx + 10, 30], fill=FG, width=3)
        d.line([54, 50, 74, 50], fill=FG, width=3)


STYLES = [
    ("style-a-dots", "方案 A · 圆眼豆豆（当前风格）", draw_dots),
    ("style-b-square", "方案 B · 方形电子眼（科技感）", draw_square),
    ("style-c-bigeyes", "方案 C · 大眼萌（可爱风）", draw_bigeyes),
    ("style-d-line", "方案 D · 极简线条（干净）", draw_line),
]


def render_style(key, title, fn):
    cols = len(EMOTIONS)
    cw = W * SCALE
    ch = H * SCALE
    img_w = cw * cols + GAP * (cols + 1)
    img_h = LABEL_H + ch + GAP * 2 + 30
    canvas = Image.new("RGB", (img_w, img_h), (240, 244, 250))
    d0 = ImageDraw.Draw(canvas)
    d0.text((GAP, 6), title, font=font(18), fill=(30, 60, 110))

    for idx, (emo, cn) in enumerate(EMOTIONS):
        x = GAP + idx * (cw + GAP)
        y = LABEL_H + 6
        # OLED 屏幕底
        tile = Image.new("RGB", (W, H), BG)
        td = ImageDraw.Draw(tile)
        fn(td, emo)
        canvas.paste(tile.resize((cw, ch), Image.NEAREST), (x, y))
        # 标注
        d0.rectangle([x - 1, y - 1, x + cw, y + ch], outline=(190, 205, 225))
        d0.text((x + 4, y + ch + 4), f"{cn} {emo}", font=font(13), fill=(70, 80, 95))

    path = OUT / f"{key}.png"
    canvas.save(path)
    return path


made = []
for key, title, fn in STYLES:
    p = render_style(key, title, fn)
    made.append(p)
    print("已生成:", p.name)

# 汇总对比图（4 行）
rows = len(STYLES)
cw, ch = W * SCALE, H * SCALE
sheet_w = cw * len(EMOTIONS) + GAP * (len(EMOTIONS) + 1)
row_h = ch + 34
sheet_h = rows * row_h + GAP * 2 + 34
sheet = Image.new("RGB", (sheet_w, sheet_h), (238, 242, 249))
ds = ImageDraw.Draw(sheet)
ds.text((GAP, 8), "小慧表情风格对比（4 方案 × 7 情绪）", font=font(19), fill=(25, 55, 105))

for r, (key, title, fn) in enumerate(STYLES):
    y0 = 34 + r * row_h
    ds.text((GAP, y0 - 16), title, font=font(13), fill=(40, 70, 120))
    for c, (emo, cn) in enumerate(EMOTIONS):
        x = GAP + c * (cw + GAP)
        tile = Image.new("RGB", (W, H), BG)
        fn(ImageDraw.Draw(tile), emo)
        sheet.paste(tile.resize((cw, ch), Image.NEAREST), (x, y0))
        ds.rectangle([x - 1, y0 - 1, x + cw, y0 + ch], outline=(200, 212, 230))

sheet_path = OUT / "对比总览.png"
sheet.save(sheet_path)
print("已生成对比图:", sheet_path)
