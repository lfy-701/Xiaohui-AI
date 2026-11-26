"""按 dog_face.cc 的坐标，用 PIL 模拟渲染 128x64 的各个表情，生成预览图。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

W, H = 128, 64
SCALE = 3

kEyeLX, kEyeRX, kEyeY = 42, 86, 24
kMouthX, kMouthY = 64, 50


def canvas():
    img = Image.new("L", (W, H), 0)
    return img, ImageDraw.Draw(img)


def circle(d, cx, cy, dia, fill=255):
    d.ellipse([cx - dia // 2, cy - dia // 2, cx + dia // 2, cy + dia // 2], fill=fill)


def arc(d, cx, cy, dia, start, end, width, color=255):
    # LVGL 角度：0=3点、逆时针；PIL：0=3点、顺时针 -> 换算
    box = [cx - dia // 2, cy - dia // 2, cx + dia // 2, cy + dia // 2]
    d.arc(box, start=360 - end, end=360 - start, fill=color, width=width)


def round_rect(d, x, y, w, h, r, color=255):
    d.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=color)


def draw_expression(name):
    img, d = canvas()

    def place(cx, cy, w, h):
        return (cx - w // 2, cy - h // 2, w, h)

    if name == "开心":
        arc(d, kEyeLX, kEyeY, 34, 200, 340, 7)
        arc(d, kEyeRX, kEyeY, 34, 200, 340, 7)
        round_rect(d, *place(16, 40, 12, 4), 2)
        round_rect(d, *place(112, 40, 12, 4), 2)
        round_rect(d, *place(kMouthX, 50, 22, 10), 5)

    elif name == "眨眼":
        circle(d, kEyeLX, kEyeY, 26)
        circle(d, kEyeLX, kEyeY, 9, fill=0)
        arc(d, kEyeRX, kEyeY, 34, 200, 340, 7)
        round_rect(d, *place(16, 40, 12, 4), 2)
        round_rect(d, *place(112, 40, 12, 4), 2)
        round_rect(d, *place(kMouthX, 50, 20, 9), 5)

    elif name == "惊讶":
        circle(d, kEyeLX, kEyeY, 30)
        circle(d, kEyeRX, kEyeY, 30)
        circle(d, kEyeLX, kEyeY, 11, fill=0)
        circle(d, kEyeRX, kEyeY, 11, fill=0)
        circle(d, kMouthX, kMouthY, 12)

    elif name == "睡觉":
        arc(d, kEyeLX, kEyeY, 34, 200, 340, 6)
        arc(d, kEyeRX, kEyeY, 34, 200, 340, 6)
        round_rect(d, *place(kMouthX, kMouthY + 2, 16, 5), 2)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        d.text((96, 2), "z Z", fill=255, font=font)

    elif name == "生气":
        circle(d, kEyeLX, kEyeY + 3, 15)
        circle(d, kEyeRX, kEyeY + 3, 15)
        circle(d, kEyeLX, kEyeY + 3, 6, fill=0)
        circle(d, kEyeRX, kEyeY + 3, 6, fill=0)
        round_rect(d, *place(kEyeLX + 3, kEyeY - 14, 18, 4), 2)
        round_rect(d, *place(kEyeRX - 3, kEyeY - 14, 18, 4), 2)
        round_rect(d, *place(kMouthX, kMouthY + 4, 20, 5), 2)

    elif name == "喜欢":
        for cx in (kEyeLX, kEyeRX):
            circle(d, cx - 6, kEyeY - 4, 13)
            circle(d, cx + 6, kEyeY - 4, 13)
            d.polygon([(cx - 12, kEyeY), (cx + 12, kEyeY), (cx, kEyeY + 14)], fill=255)
        round_rect(d, *place(kMouthX, 50, 20, 9), 5)

    elif name == "平常":
        circle(d, kEyeLX, kEyeY, 26)
        circle(d, kEyeRX, kEyeY, 26)
        circle(d, kEyeLX, kEyeY, 9, fill=0)
        circle(d, kEyeRX, kEyeY, 9, fill=0)
        round_rect(d, *place(kMouthX, kMouthY, 22, 5), 2)

    elif name == "聆听":
        circle(d, kEyeLX, kEyeY, 28)
        circle(d, kEyeRX, kEyeY, 28)
        circle(d, kEyeLX, kEyeY, 10, fill=0)
        circle(d, kEyeRX, kEyeY, 10, fill=0)
        round_rect(d, *place(kMouthX, kMouthY, 18, 8), 4)

    elif name == "说话":
        circle(d, kEyeLX, kEyeY, 26)
        circle(d, kEyeRX, kEyeY, 26)
        circle(d, kEyeLX, kEyeY, 9, fill=0)
        circle(d, kEyeRX, kEyeY, 9, fill=0)
        round_rect(d, *place(kMouthX, kMouthY, 26, 14), 6)

    elif name == "难过":
        circle(d, kEyeLX, kEyeY, 22)
        circle(d, kEyeRX, kEyeY, 22)
        circle(d, kEyeLX, kEyeY, 8, fill=0)
        circle(d, kEyeRX, kEyeY, 8, fill=0)
        round_rect(d, *place(kEyeLX - 4, kEyeY - 12, 18, 4), 2)
        round_rect(d, *place(kEyeRX + 4, kEyeY - 12, 18, 4), 2)
        arc(d, kMouthX, 52, 34, 20, 160, 5)

    elif name == "思考":
        circle(d, kEyeLX, kEyeY, 28)
        circle(d, kEyeRX, kEyeY, 18)
        circle(d, kEyeLX, kEyeY, 10, fill=0)
        circle(d, kEyeRX, kEyeY, 7, fill=0)
        round_rect(d, *place(74, kMouthY, 16, 5), 2)

    return img


names = ["平常", "开心", "眨眼", "惊讶", "睡觉", "生气", "喜欢", "聆听", "说话", "难过", "思考"]
cols = 3
rows = (len(names) + cols - 1) // cols
PAD = 10

out = Image.new("L", (cols * (W * SCALE + PAD) + PAD, rows * (H * SCALE + 28 + PAD) + PAD), 40)
d = ImageDraw.Draw(out)
font = ImageFont.load_default()

for i, n in enumerate(names):
    r, c = divmod(i, cols)
    x = PAD + c * (W * SCALE + PAD)
    y = PAD + r * (H * SCALE + 28 + PAD)
    img = draw_expression(n).resize((W * SCALE, H * SCALE), Image.NEAREST)
    out.paste(img, (x, y))
    d.text((x + 4, y + H * SCALE + 6), n, fill=255, font=font)

path = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\face_preview.png")
out.save(path)
print("saved:", path, out.size)
