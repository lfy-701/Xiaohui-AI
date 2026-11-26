"""生成《语音侧工具回传支持》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\语音侧工具回传支持-给成员A.docx"

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
font(p.add_run("语音侧工具回传支持"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("为什么语音问到一半会断 · 需要成员 A 改什么 · 2026-11-13"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、现在的故障现象")

para(doc, "对设备说「东莞今天天气怎么样」，设备会说半句然后没声音了：")
code(doc, """19:04:33  发送音频: 东莞今天天气怎么样呢？让我查一下
19:04:33  发送音频: <结束>
19:04:50  客户端断开连接          ← 说完「我来查一下」就断
19:04:51  重连、重新初始化""")

para(doc, "同一句话在控制台文字聊天里是正常的，能拿到真实天气数据：", bold=True)
code(doc, """东莞今天的温度是 23.9°C，体感 29.1°C，中等毛毛雨，
湿度 97%，风速 3.6km/h。""")

para(doc, "差别只在于：文字聊天走的是 model-service 的完整链路（工具在你那边执行），"
          "语音走的是语音服务，它拿到 tool_call 后不知道该找谁执行。", color=RED)

heading(doc, "二、根本原因")

para(doc, "语音服务的对话流程是这样的：", bold=True)
code(doc, """1. 把用户的话 + 可用工具列表发给 /v1/chat/completions
2. 模型返回 tool_calls
3. 语音服务要执行这些工具
      ↓
   它手里只有「设备工具」（self.dog_action、self.set_led…）
      ↓
   没有 get_current_weather 这个工具
      ↓
   执行失败 → 本轮对话中断 → 设备端表现为「说半句就哑了」""")

para(doc, "也就是说：模型想查天气，但语音服务没有能力查。")

heading(doc, "三、需要的改动：两种工具模式")

para(doc, "请在 /v1/chat/completions 上支持一个模式开关，"
          "让调用方声明「工具由谁执行」：", bold=True)
code(doc, """POST /v1/chat/completions
Header: X-Tool-Mode: server | passthrough
   （或不传，默认 server）""")

heading(doc, "模式 A：server —— 工具由 model-service 自己执行（默认）", level=2)

para(doc, "适用于你自己的工具：天气、计时、音乐、知识库。")
code(doc, """模型返回 tool_calls
   ↓
model-service 自己执行工具
   ↓
把工具结果作为 role=tool 消息塞回对话
   ↓
再次请求模型，直到它给出最终文本
   ↓
返回最终文本给调用方（可以是流式）""")

para(doc, "关键要求：**必须返回最终文本**，不能只返回一句「我来查一下」就结束。",
     bold=True, color=GREEN)

para(doc, "如果工具执行失败，也要返回一句人类可读的说明，例如：", bold=True)
code(doc, """{"choices":[{"message":{"content":"天气服务暂时不可用，稍后再问我一次吧。"}}]}""")

heading(doc, "模式 B：passthrough —— 工具由调用方执行", level=2)

para(doc, "适用于设备工具（self.* 开头），语音服务知道怎么执行它们。")
code(doc, """模型返回 tool_calls（原样返回，不执行）
   ↓
调用方（语音服务）执行工具
   ↓
把 tool 结果再发一次请求回来
   ↓
继续保持 passthrough，直到模型给出最终文本""")

para(doc, "这一模式对应我上一份文档里说的「放开 tools 透传」。")

heading(doc, "四、怎么判断用哪种模式")

para(doc, "按工具名前缀分流即可：", bold=True)
table(doc, [
    ["工具名", "谁执行", "模式"],
    ["self.*（设备工具）", "语音服务", "passthrough"],
    ["get_weather / get_weather_alert / get_weather_forecast", "model-service", "server"],
    ["set_timer / search_music / kb_search", "model-service", "server"],
    ["未知工具", "—", "忽略，不要让整个请求失败"],
], [8.0, 4.4, 4.2])

para(doc, "最重要的一条：遇到不认识的工具时，**跳过并继续生成回答**，"
          "不要返回 400 —— 现在的 400 会让整轮语音对话直接中断。", color=RED)

heading(doc, "五、验收方式")

para(doc, "改完后跑这条命令（模拟语音服务的调用）：", bold=True)
code(doc, """curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "X-Tool-Mode: server" \\
  -d "{\\"model\\":\\"qwen2.5:3b\\",
       \\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"东莞今天天气怎么样\\"}]}\"""")

para(doc, "期望：返回一段**完整的天气描述**，而不是「让我查一下」或 400。", color=GREEN)

para(doc, "再测 passthrough：", bold=True)
code(doc, """curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "X-Tool-Mode: passthrough" \\
  -d "{\\"model\\":\\"qwen2.5:3b\\",
       \\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"站起来\\"}],
       \\"tools\\":[{\\"type\\":\\"function\\",\\"function\\":{
         \\"name\\":\\"self.dog_action\\",
         \\"description\\":\\"控制机器狗动作\\",
         \\"parameters\\":{\\"type\\":\\"object\\",
           \\"properties\\":{\\"action\\":{\\"type\\":\\"string\\"}},
           \\"required\\":[\\"action\\"]}}}]}\"""")

para(doc, "期望：返回 tool_calls（不执行），调用方执行后再发回来。")

heading(doc, "六、设备侧现有工具清单")

para(doc, "方便你判断哪些该走 passthrough：")
table(doc, [
    ["工具名", "作用"],
    ["self.dog_action", "站、坐、前进、后退、左转、右转、跳舞、趴下、睡觉、起身、摇尾、摇头、停"],
    ["self.set_servo", "直接设置某一路舵机角度（0-5，0-180 度）"],
    ["self.leg_move / self.leg_test", "单腿动作 / 逐腿校准"],
    ["self.set_emotion / self.face_expression", "屏幕表情"],
    ["self.set_led / self.led_effect", "灯珠颜色 / 灯效"],
    ["self.get_device_status", "设备状态"],
    ["self.set_volume", "音量"],
], [8.2, 8.0])

heading(doc, "七、优先级建议")

table(doc, [
    ["事项", "影响", "优先级"],
    ["未知工具不再返回 400", "语音对话不会再「说半句断掉」", "P0"],
    ["server 模式返回最终文本", "语音里问天气能听到答案", "P0"],
    ["passthrough 模式", "语音控制动作（站起来/跳舞）", "P1"],
    ["server 模式增多工具（计时/音乐/知识库）", "功能扩展", "P2"],
], [7.6, 6.2, 2.4])

para(doc, "只做前两项，语音问天气就能用了；第三项做完语音就能控制小狗动作。",
     bold=True, color=GREEN)

heading(doc, "八、我这边可以先做的兜底")

para(doc, "在你改之前，我可以在语音服务里加一层「天气关键词直通」："
          "识别到天气类问题时，用不带你工具的纯文本请求问同一模型，"
          "把答案直接念出来。这样你改完后我这层可以撤掉。")

doc.save(OUT)
print("saved:", OUT)
