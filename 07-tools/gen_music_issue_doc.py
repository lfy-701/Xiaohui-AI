"""生成《音乐播放异常排查》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\音乐播放异常排查-给成员A.docx"

ACCENT = RGBColor(0x1B, 0x6F, 0xC4)
GREY = RGBColor(0x66, 0x66, 0x66)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x1E, 0x8E, 0x5A)


def font(run, size=10.5, bold=False, color=None, mono=False):
    run.font.name = "Consolas" if mono else "微软雅黑"
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")


def para(doc, text, size=10.5, bold=False, color=None, after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    font(p.add_run(text), size=size, bold=bold, color=color)
    return p


def code(doc, text):
    for line in text.strip("\n").split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.left_indent = Cm(0.6)
        font(p.add_run(line if line else " "), size=9, mono=True,
             color=RGBColor(0x1E, 0x4A, 0x7A))
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def heading(doc, text, level=1):
    h = doc.add_heading(level=level)
    h.paragraph_format.space_before = Pt(13)
    h.paragraph_format.space_after = Pt(6)
    font(h.add_run(text), size=15 if level == 1 else 12, bold=True, color=ACCENT)
    return h


def table(doc, rows, widths):
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, val in enumerate(row):
            cells[j].text = ""
            p = cells[j].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(str(val))
            font(r, size=9.5, bold=(i == 0), color=ACCENT if i == 0 else None)
            cells[j].width = Cm(widths[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


doc = Document()
sec = doc.sections[0]
sec.left_margin = Cm(1.9)
sec.right_margin = Cm(1.9)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("音乐播放异常排查"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("接口全部成功、设备无声音 · 2026-11-20"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、现象")

para(doc, "设备语音对话完全正常（能听、能答、有声音）。但音乐播放不行：")

table(doc, [
    ["入口", "表现"],
    ["网页 /chat 点「放歌」", "接口返回 ok，设备无声音"],
    ["语音说「放首歌」", "同样无声"],
    ["偶尔一次", "听到过约 2 秒的音乐（「晴天」）"],
], [6.0, 10.0])

para(doc, "对比：TTS 语音播报有声音，音乐没有。两者都走同一条 WebSocket 音频通道。",
     bold=True, color=RED)

heading(doc, "二、我这边确认过的（已排除）")

table(doc, [
    ["检查项", "结果"],
    ["设备在线", "count=1，心跳正常"],
    ["音量", "已设为 30 / 85 / 95 多次测试，非静音"],
    ["TTS 播报", "同一通道，有声音"],
    ["音频包发送", "日志显示 499~500 帧全部发出"],
    ["解码", "服务端 ffmpeg 解码出 1.43 MB PCM，无报错"],
    ["接口返回", "{'ok': true, 'packets': 500, 'stream': true}"],
], [5.4, 11.0])

heading(doc, "三、我在用的两种音源（请分别看）")

heading(doc, "3.1 iTunes 原始地址（直连）", level=2)
code(doc, """https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview116/...
容器 MP4 / AAC，44.1 kHz，约 991 KB → 服务端 ffmpeg 转 24 kHz 单声道 PCM""")

heading(doc, "3.2 你的 8106 转码缓存（今天新接入）", level=2)
code(doc, """http://<本地模型服务器IP>:8106/audio?src=<iTunes地址>

实测返回：200, content-type: audio/mpeg, 180581 字节""")

para(doc, "需要你确认：8106 转出来的这个 MP3 本身是否正常发声？"
          "请在训练机上直接播放一次：", bold=True)
code(doc, """curl -o /tmp/t.mp3 "http://127.0.0.1:8106/audio?src=<随便一首 iTunes 试听地址>"
ffprobe /tmp/t.mp3      # 看采样率/声道/码率
ffplay /tmp/t.mp3       # 人耳确认有没有声音""")

para(doc, "如果这个 MP3 是静音或格式异常，我这边推的就是静音数据，现象完全对得上。",
     color=RED)

heading(doc, "四、我怀疑的三个方向")

heading(doc, "方向 1：8106 转码结果有问题（最可能）", level=2)
para(doc, "可能情况：转码时把音量归零、声道映射错误、或容器时间戳异常导致解码器输出静音。"
          "请用上一节的 ffprobe / ffplay 验证。")

heading(doc, "方向 2：设备不接受“服务端推送音频”，只播放自己拉取的 URL", level=2)
para(doc, "你的说明里提到「模型返回的 playback.url 已经指向局域网地址」。"
          "如果设备的设计是自己去拉这个 URL 播放，那我从服务端推 Opus 帧就是错的路径。")

para(doc, "请确认设备的音乐播放协议：", bold=True)
table(doc, [
    ["方式", "说明", "我这边要做的"],
    ["A. 服务端推 Opus 帧", "和 TTS 一样，走 WebSocket", "保持现状（已实现）"],
    ["B. 设备拉 URL", "设备收到 playback.url 后自己 HTTP 拉流", "把 URL 通过 MCP 下发给设备"],
], [5.0, 7.0, 5.0])

heading(doc, "方向 3：设备空闲会断开连接（时序竞争）", level=2)
para(doc, "日志观察到：说完话约 4 秒后连接被断开，再推音频就没有接收方。")

para(doc, "但我也看到过一次「播放结束：499 帧 / 29.9 秒」后才断开，"
          "说明有时连接能撑满 30 秒。这个行为不稳定。")

para(doc, "请确认：这个“空闲断开”是设备端做的，还是 model-service / 语音服务端的超时？"
          "如果是设备端，具体超时是多少、能否调整？")

heading(doc, "五、需要你回复的四件事")

table(doc, [
    ["#", "问题", "为什么重要"],
    ["1", "8106 转出的 MP3 本地播放有声音吗？", "排除音源问题"],
    ["2", "设备播放音乐是「服务端推流」还是「自己拉 URL」？", "决定我改哪条链路"],
    ["3", "设备空闲断开连接的机制和超时值是什么？", "决定能否网页随时点歌"],
    ["4", "8105 / 8009 能否监听 0.0.0.0？", "Tailscale 连不上，只能本机访问"],
], [1.0, 8.4, 7.0])

heading(doc, "六、我这边可以配合的")

para(doc, "只要能确认方向，我改起来都很快：")

table(doc, [
    ["若结论是", "我改什么", "耗时"],
    ["8106 音源问题", "回退直连 iTunes，或换 16 kHz 参数", "10 分钟"],
    ["要走设备拉 URL", "把 URL 通过 MCP 下发给设备，不再服务端推流", "1 小时"],
    ["连接超时太短", "服务端保持心跳 / 延长会话", "30 分钟"],
], [5.0, 8.6, 3.0])

heading(doc, "七、一个最小复现")

para(doc, "如果你能在训练机上跑一次这条，就能确定音源本身是否正常：", bold=True)
code(doc, """# 1. 取一首试听地址
curl -s "http://127.0.0.1:8102/rest/search?q=晴天&limit=1"

# 2. 过 8106 转码
curl -o /tmp/a.mp3 "http://127.0.0.1:8106/audio?src=<上一步的 preview_url>"

# 3. 看参数 + 人耳听
ffprobe -hide_banner /tmp/a.mp3
ffplay -autoexit /tmp/a.mp3""")

para(doc, "如果第 3 步听不到声音 → 问题在 8106；听到了 → 问题在设备播放协议。",
     bold=True, color=GREEN)

doc.save(OUT)
print("saved:", OUT)
