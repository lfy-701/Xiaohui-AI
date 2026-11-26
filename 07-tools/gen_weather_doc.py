"""生成《天气工具异常排查》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\天气工具异常排查-给成员A.docx"

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
font(p.add_run("天气工具异常排查"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("模型调用了工具，但工具返回失败 · 2026-11-17"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、现象")

para(doc, "用户问「上海天气怎么样」，控制台的回答是：")
code(doc, """我查不到上海的天气，请问您是想知道今天还是明天？""")

para(doc, "另一台设备上问「东莞今天天气怎么样」，回答：")
code(doc, """很抱歉，当前东莞的天气数据无法获取。
这可能是由于服务器临时故障导致的问题。请稍后再试一次。""")

para(doc, "关键点：模型确实发起了工具调用，是工具执行返回了失败。所以不是"
          "「没有工具」或「没有透传」，而是工具本身报错。", bold=True, color=RED)

heading(doc, "二、实测证据")

para(doc, "直接向模型服务发请求，带 get_current_weather 工具：", bold=True)

para(doc, "请求一（无特殊头）：", size=10)
code(doc, """POST http://<本地模型服务器IP>:8000/v1/chat/completions
{"model": "xiaohui-r5:latest",
 "messages": [{"role": "user", "content": "东莞今天天气怎么样"}],
 "tools": [{"type": "function", "function": {
   "name": "get_current_weather",
   "description": "查询城市当前天气",
   "parameters": {"type": "object",
     "properties": {"city": {"type": "string"}},
     "required": ["city"]}}}],
 "tool_choice": "auto"}

HTTP 200
message.content = "很抱歉，当前东莞的天气数据无法获取。
                  这可能是由于服务器临时故障导致的问题。"  """)

para(doc, "请求二（x-tool-mode: auto）：", size=10)
code(doc, """HTTP 200
message.content = "我正尝试查询东莞今天的天气，但好像遇到了一点问题。
                  您可以在稍后再次问我这个问题。"  """)

para(doc, "两次都返回 200，模型都在「转述工具失败」，说明失败发生在工具执行阶段，"
          "错误被模型消化成了自然语言。", color=GREEN)

heading(doc, "三、需要检查的四个地方")

table(doc, [
    ["#", "检查项", "怎么查"],
    ["1", "天气 API 的密钥/额度是否有效", "用同一把 key 直接 curl 上游天气接口"],
    ["2", "训练机能否访问外网天气服务", "在训练机上 curl 上游域名，看是否超时/被墙"],
    ["3", "工具实现的异常日志", "看 model-service 日志里 get_current_weather 的 traceback"],
    ["4", "城市名参数是否被正确传入", "日志里看 arguments 是 {\"city\":\"东莞\"} 还是空"],
], [1.2, 7.4, 8.6])

para(doc, "最可能的情况：训练机在 Tailscale 内网环境中，出网受限，"
          "天气 API 请求超时后被工具捕获成「查询失败」。", color=GREY)

heading(doc, "四、建议的修法")

para(doc, "① 工具失败时返回结构化错误，别让模型自由发挥", bold=True)
code(doc, """{"ok": false, "error": "upstream_timeout",
 "message": "天气服务连接超时"}""")

para(doc, "这样模型可以说「天气服务暂时连不上」，而不是编造「服务器临时故障」。")

para(doc, "② 加一层缓存 + 降级", bold=True)
code(doc, """命中缓存（10 分钟内）→ 直接返回
上游超时 → 返回最近一次成功的数据 + 标注「可能不是最新」""")

para(doc, "③ 暴露一个自检接口，我这边可以定时探测", bold=True)
code(doc, """GET /v1/tools/health
{"get_current_weather": {"ok": true, "latency_ms": 320},
 "get_weather_alert":  {"ok": false, "error": "upstream_timeout"}}""")

para(doc, "有了这个，控制台可以在天气工具不可用时自动降级回答，"
          "而不是每次都要用户碰运气。", color=GREEN)

heading(doc, "五、我这边已经做的事")

table(doc, [
    ["项", "状态"],
    ["模型切到 xiaohui-r5:latest", "已完成"],
    ["人设替换为训练用系统提示词", "已完成"],
    ["人设加身份声明（不是通义千问）", "已完成"],
    ["语音侧人设与试聊同步", "已完成"],
    ["按意图分流：闲聊走快速通道，天气/动作走工具通道", "已完成"],
    ["日期注入系统提示（今天几号不再乱答）", "已完成"],
], [10.2, 7.0])

para(doc, "所以现在只剩天气工具本身的执行问题。修好之后，"
          "语音问天气、问日期、让它做动作应该都能正常。", bold=True)

heading(doc, "六、复现我给的两条命令")

para(doc, "你可以直接跑这两条，对比修复前后的返回：", bold=True)
code(doc, """curl -s -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"xiaohui-r5:latest",
       "messages":[{"role":"user","content":"东莞今天天气怎么样"}]}' \\
  | head -c 400""")

para(doc, "如果返回里出现「天气数据无法获取」「遇到了一点问题」，说明上游还是失败的；"
          "修好后应当返回具体温度、天气状况。", color=GREEN)

doc.save(OUT)
print("saved:", OUT)
