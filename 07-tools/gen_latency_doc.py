"""生成《模型服务响应与稳定性》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\模型服务响应与稳定性-给成员A.docx"

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
sec.left_margin = Cm(2.0)
sec.right_margin = Cm(2.0)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("模型服务响应与稳定性"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("语音对话体验的上限，卡在 model-service 这一层 · 2026-11-13"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、用户能感知到的问题")

para(doc, "现在对设备说话，从说完到听见回答要等 4~6 秒；"
          "今天下午更严重，直接超时、连接被断开。", bold=True)

para(doc, "实测记录：")
table(doc, [
    ["时间", "现象", "耗时"],
    ["今天下午", "正常回答", "3.9 秒"],
    ["刚才", "请求超时", ">60 秒"],
    ["刚才", "Server disconnected without sending a response", "连接被断开"],
], [3.4, 10.4, 3.0])

para(doc, "语音链路里，用户说完话之后是这样排队的：", bold=True)
code(doc, """语音识别 1~2 秒
   ↓
大模型生成 3.9 秒（现在变成超时）      ← 瓶颈在这里
   ↓
TTS 合成 + 推流 0.6 秒""")

para(doc, "也就是说：语音侧再怎么优化，也没办法把这几秒拿回来。", color=RED)

heading(doc, "二、需要成员 A 配合的四件事")

heading(doc, "1. 健康检查接口（P0）", level=2)

para(doc, "需要一个能判断服务是否可用的接口，控制台和语音服务都要靠它做降级：")
code(doc, """GET /health
{"ok": true, "model": "qwen2.5:3b", "loaded": true,
 "queue": 0, "avg_latency_ms": 1800}""")

para(doc, "加载中或过载时 ok=false，并说明原因（模型加载中 / 排队过多 / GPU 不可用）。")

heading(doc, "2. 异常时返回 JSON，不要断开连接（P0）", level=2)

para(doc, "现在的表现是连接被直接掐断，调用方拿不到任何信息：")
code(doc, """httpx.RemoteProtocolError:
Server disconnected without sending a response.""")

para(doc, "期望：")
code(doc, """HTTP 503
{"error": {"code": "model_busy",
           "message": "模型正在加载，请 10 秒后重试"}}""")

para(doc, "这样语音服务可以回一句「我这边有点忙，稍等一下」，"
          "而不是让设备干等着、最后超时断线。", color=GREEN)

heading(doc, "3. 流式返回 + 首 token 时间（P0）", level=2)

para(doc, "语音场景对「第一个字什么时候出来」最敏感，对「整句多久说完」没那么敏感。"
          "如果支持 SSE 流式，语音服务可以按标点切句，边生成边播报：")
code(doc, """POST /v1/chat/completions
{"model": "qwen2.5:3b", "stream": true, ...}

data: {"choices":[{"delta":{"content":"东莞"}}]}
data: {"choices":[{"delta":{"content":"今天"}}]}
...""")

para(doc, "目标（请以你的机器实测为准）：", bold=True)
table(doc, [
    ["指标", "目标", "现在"],
    ["首 token 时间", "≤ 1.5 秒", "未知（未流式）"],
    ["整句完成", "≤ 3 秒", "3.9 秒"],
    ["超时阈值", "明确返回 503", "断连接"],
], [5.4, 5.6, 5.8])

heading(doc, "4. 进程守护与自动重启（P0）", level=2)

para(doc, "今天出现过整个服务无响应的情况。建议：")

para(doc, "• 用 systemd / NSSM / supervisor 之类的工具守护进程，崩了自动拉起")
para(doc, "• 启动后先预热模型（跑一条空请求），避免第一个真实请求承担加载耗时")
para(doc, "• 记录每次请求的耗时到日志，便于定位慢在哪里")

heading(doc, "三、可选：一个降级档（P1）")

para(doc, "如果 3b 在你机器上稳定在 3.9 秒以上，建议再加一个更小的模型做降级：")
table(doc, [
    ["档位", "模型", "用途", "期望延迟"],
    ["标准", "qwen2.5:3b", "正常对话", "≤ 3 秒"],
    ["快速", "qwen2.5:1.5b", "过载/排队时自动降级", "≤ 1.5 秒"],
], [3.0, 5.4, 6.4, 3.0])

para(doc, "请求里带一个 model 字段即可，我这边会根据 /health 的结果自动切换。")

heading(doc, "四、验收方式")

para(doc, "改完后跑这三条，把结果发我：", bold=True)

para(doc, "① 健康检查：", size=10)
code(doc, """curl http://<本地模型服务器IP>:8000/health""")

para(doc, "② 首 token 时间（流式）：", size=10)
code(doc, """curl -N -X POST http://<本地模型服务器IP>:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"qwen2.5:3b","stream":true,
       "messages":[{"role":"user","content":"你好"}]}' \\
  | head -3""")

para(doc, "观察第一条 data 出现在第几秒。")

para(doc, "③ 连续 5 次普通请求，看耗时是否稳定：", size=10)
code(doc, """for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{time_total}\\n" \\
    -X POST http://<本地模型服务器IP>:8000/v1/chat/completions \\
    -H "Content-Type: application/json" \\
    -d '{"model":"qwen2.5:3b","messages":[{"role":"user","content":"你好"}]}'
done""")

para(doc, "如果五次里有明显抖动（比如 2 秒、9 秒、2 秒），说明是排队或显存问题，"
          "也请一并告诉我。", color=GREEN)

heading(doc, "五、当前分工与依赖")

table(doc, [
    ["环节", "谁负责", "状态"],
    ["设备固件（舵机/灯/表情）", "成员 B", "已完成"],
    ["控制台 / 动作编辑 / 音乐推流", "成员 B", "已完成"],
    ["语音识别 / 合成 / 播报", "成员 B（自建服务）", "已完成"],
    ["大模型推理", "成员 A", "慢，且今天出现无响应"],
    ["工具透传（天气/动作）", "成员 A", "待改（另有两份文档）"],
], [7.4, 5.2, 4.2])

para(doc, "语音体验好不好，取决于最后一行的稳定性。前面的部分我已经压到 1~2 秒了。",
     bold=True)

doc.save(OUT)
print("saved:", OUT)
