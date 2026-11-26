"""生成《MCP 服务扩展与工具透传》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\MCP服务扩展与工具透传-给成员A.docx"

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
font(p.add_run("MCP 服务扩展与工具透传"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("需要成员 A 支持的两件事 · 2026-11-13"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、当前卡在哪里")

para(doc, "设备侧 11 个 MCP 工具已经全部注册成功，语音服务能正常调用：")
code(doc, """客户端MCP服务器信息: name=esp32-dog-wangcai
客户端设备支持的工具数量: 11
所有工具已获取，MCP客户端准备就绪""")

para(doc, "但只要把这些工具随请求发给 model-service，整个请求就被拒绝：", bold=True)
code(doc, """POST /v1/chat/completions
{"tools": [{"function": {"name": "self.dog_action", ...}}]}

HTTP 400
{"error": {"message": "只允许调用后端已注册的工具；未注册工具：self.dog_action",
           "code": "unregistered_tool"}}""")

para(doc, "结果是：模型永远看不到设备工具，用户说「站起来」它只会聊天，不会动。",
     color=RED)

heading(doc, "二、第一件事：放开 tools 透传")

para(doc, "需要 model-service 在收到带 tools 的请求时：", bold=True)
table(doc, [
    ["步骤", "要求"],
    ["1", "把请求里的 tools 原样传给底层模型，不要做白名单校验"],
    ["2", "模型返回 tool_calls 时原样返回给调用方（不要自己执行）"],
    ["3", "工具名以 self. 开头的直接放行，视为调用方自定义工具"],
], [2.2, 14.6])

para(doc, "为什么这样安全：真正的执行不在 model-service，而在语音服务——它拿到 "
          "tool_calls 后通过 WebSocket 把调用发给设备，由设备执行。"
          "model-service 只是中转，不承担执行责任。", color=GREEN)

para(doc, "改法示意（伪代码）：", bold=True)
code(doc, """tools = body.get("tools") or []
resp = client.chat.completions.create(
    model=body["model"],
    messages=body["messages"],
    tools=tools if tools else NOT_GIVEN,     # 原样透传，不校验
    tool_choice="auto" if tools else NOT_GIVEN,
)
return resp          # tool_calls 原样返回，不要本地执行""")

para(doc, "如果担心被滥用，可以加开关，默认关闭：", bold=True)
code(doc, """if request.headers.get("X-Tools-Passthrough") == "1":
    passthrough = True""")

heading(doc, "三、第二件事：多提供一些 MCP 服务")

para(doc, "现在设备侧只有 11 个自研工具（舵机、灯、表情）。"
          "希望 model-service 侧再提供一批通用服务，让小狗能做更多事。")

para(doc, "优先级最高的四个：", bold=True)
table(doc, [
    ["服务", "工具名", "用途", "优先级"],
    ["天气", "get_weather", "「今天热不热」「要带伞吗」", "P0"],
    ["计时提醒", "set_timer / list_timers", "「十分钟后提醒我」", "P0"],
    ["音乐", "search_music / play_music", "「放首轻音乐」", "P1"],
    ["知识问答", "kb_search", "接现有的知识库服务", "P1"],
], [3.0, 5.2, 6.6, 2.0])

para(doc, "接口形式可以二选一：", bold=True)
table(doc, [
    ["方案", "说明", "适合"],
    ["A. 提供 MCP Server", "标准 JSON-RPC，语音服务直接接", "推荐，扩展性最好"],
    ["B. 提供 REST + tools schema", "语音服务包装成工具", "改动小，够用"],
], [5.4, 7.8, 3.6])

para(doc, "每个工具需要三样东西：", bold=True)
code(doc, """{
  "name": "get_weather",
  "description": "查询指定城市的当前天气和今天预报",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {"type": "string", "description": "城市名，如 东莞"}
    },
    "required": ["city"]
  }
}""")

heading(doc, "四、验收方式")

para(doc, "改完后用这条命令自测（IP 换成实际地址）：", bold=True)
code(doc, """curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d "{\\"model\\":\\"qwen2.5:3b\\",
       \\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"站起来\\"}],
       \\"tools\\":[{\\"type\\":\\"function\\",\\"function\\":{
         \\"name\\":\\"self.dog_action\\",
         \\"description\\":\\"控制机器狗动作\\",
         \\"parameters\\":{\\"type\\":\\"object\\",
           \\"properties\\":{\\"action\\":{\\"type\\":\\"string\\"}},
           \\"required\\":[\\"action\\"]}}}],
       \\"tool_choice\\":\\"auto\\"}""")

para(doc, "期望返回：", bold=True)
code(doc, """"finish_reason": "tool_calls",
"message": {"tool_calls": [{"function": {
    "name": "self.dog_action",
    "arguments": "{\\"action\\": \\"stand\\"}"}}]}""")

para(doc, "看到 tool_calls 就说明透传成功，我这边接上就能用语音控制动作。",
     color=GREEN)

heading(doc, "五、当前分工现状")

table(doc, [
    ["能力", "谁负责", "状态"],
    ["设备注册、心跳、OTA", "成员 B 控制台", "已完成"],
    ["舵机 / 灯 / 表情 11 个工具", "成员 B 固件", "已完成"],
    ["控制台直接调用工具", "成员 B", "可用，0.4 秒"],
    ["模型调用工具（语音控制）", "成员 A model-service", "被白名单拦住"],
    ["通用服务（天气/计时/音乐）", "成员 A model-service", "待开发"],
], [7.2, 5.4, 4.2])

heading(doc, "六、如果暂时来不及")

para(doc, "我这边可以先做「关键词兜底」：识别到「站起来」「左转」「跳舞」等固定说法时，"
          "不经过模型直接调工具。这样常用指令今天就能用，"
          "但自然语言（「你能站起来一下吗」）仍然需要透传。")

para(doc, "所以透传这件事，长期还是要做。", bold=True)

doc.save(OUT)
print("saved:", OUT)
