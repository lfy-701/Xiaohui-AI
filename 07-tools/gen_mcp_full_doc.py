"""生成《MCP 服务能力补齐清单》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\MCP服务能力补齐清单-给成员A.docx"

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
font(p.add_run("MCP 服务能力补齐清单"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("天气 / 日期 / 笑话 / 新闻 / 联网搜索 / 音乐 · 2026-11-17"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、总览：现在哪些能用，哪些不能用")

para(doc, "我在控制台机器上逐项测了 model-service（xiaohui-r5:latest，不带 tools 直接问），"
          "结果如下：", bold=True)

table(doc, [
    ["能力", "现在的表现", "结论"],
    ["天气", "回答「请提供一个具体的城市名称」，或「天气数据无法获取」", "工具存在但执行失败"],
    ["日期", "回答「今天是星期几你不知道吗？」", "模型完全不知道当前日期"],
    ["笑话", "能讲（自带知识，不需要工具）", "可用"],
    ["新闻", "「我目前无法获取今天的新闻」", "没有对应工具"],
    ["联网搜索", "「小慧无法提供实时信息」", "没有对应工具"],
    ["音乐", "「你想听什么类型的音乐？」", "没有搜索/播放工具"],
], [3.4, 9.6, 5.6])

para(doc, "结论很明确：不是模型不会说，而是它手里没有对应的工具，"
          "或者工具执行失败了。", bold=True, color=RED)

heading(doc, "二、逐项说明与需求")

heading(doc, "1. 天气：工具在，但执行失败（P0）", level=2)

para(doc, "带 tools 请求时，模型会转述失败：")
code(doc, """{"model": "xiaohui-r5:latest",
 "messages": [{"role": "user", "content": "东莞今天天气怎么样"}],
 "tools": [{"type": "function", "function": {
   "name": "get_current_weather",
   "parameters": {"type": "object",
     "properties": {"city": {"type": "string"}},
     "required": ["city"]}}}],
 "tool_choice": "auto"}

→ HTTP 200
→ "很抱歉，当前东莞的天气数据无法获取。这可能是由于服务器临时故障…\"""")

para(doc, "需要：查上游天气 API 的密钥、出网权限、工具 traceback；"
          "失败时返回结构化错误而不是让模型自由发挥。")

heading(doc, "2. 日期：模型不知道今天几号（P0）", level=2)

para(doc, "直接问「今天几号」，模型答不出来，因为上下文里没有当前时间。")

para(doc, "两个方案，选一个就行：", bold=True)
code(doc, """方案 A（推荐）：model-service 每次请求自动在 system 里注入
"当前时间：2026-11-17 星期二 15:20，涉及日期以此为准"

方案 B：提供 get_datetime 工具，返回
{"date": "2026-11-17", "weekday": "星期二", "time": "15:20"}""")

para(doc, "我这边已经在控制台/语音侧注入了日期，但直接调用模型服务的场景"
          "（比如别的客户端）仍会答错，所以最好在服务端也做。", color=GREY)

heading(doc, "3. 新闻：没有工具（P1）", level=2)

code(doc, """建议工具：get_news(topic?, limit?)
返回：[{"title": "...", "source": "...", "at": "2026-11-17 09:00",
        "url": "...", "summary": "..."}]""")

para(doc, "语音场景只需要标题 + 一句摘要，不需要全文。")

heading(doc, "4. 联网搜索：没有工具（P1）", level=2)

code(doc, """建议工具：web_search(query, limit=3)
返回：[{"title": "...", "url": "...", "snippet": "..."}]

注意：语音播报不能用 URL，请返回适合朗读的短摘要（≤80 字/条）。""")

heading(doc, "5. 音乐：能力缺失（P1）", level=2)

para(doc, "现状：我这边已经实现了设备播放（iTunes 30 秒试听，"
          "语音点歌 + 控制台播放都能用）。缺的是模型服务侧的搜索工具，"
          "导致「放首歌」这类自然语言请求没办法由模型编排。")

para(doc, "如果要对齐，建议提供：", bold=True)
code(doc, """search_music(query, limit=3)
→ [{"title": "...", "artist": "...", "preview_url": "https://...mp3",
     "duration_seconds": 30}]

约定：preview_url 必须是可直接下载的音频直链（mp3/aac），
我这边会下载后转 Opus 推给设备。""")

para(doc, "注意：不要返回需要登录或带防盗链的地址，否则设备端下载会失败。",
     color=RED)

heading(doc, "三、还需要一个「工具自检」接口（P0）")

para(doc, "现在出问题时，我只能从模型的话里猜工具坏没坏。建议加：")
code(doc, """GET /v1/tools
{"tools": [
  {"name": "get_current_weather", "ok": true,  "latency_ms": 320},
  {"name": "get_news",            "ok": false, "error": "upstream_timeout"},
  {"name": "web_search",          "ok": true,  "latency_ms": 890}
]}

GET /health
{"ok": true, "model": "xiaohui-r5:latest", "loaded": true, "queue": 0}""")

para(doc, "有了这个，控制台可以在工具不可用时自动降级回答，"
          "而不是让用户碰运气。", color=GREEN)

heading(doc, "四、工具失败时的返回约定")

para(doc, "现在失败是这样被模型转述的：")
code(doc, """「这可能是由于服务器临时故障导致的问题。请稍后再试一次。」""")

para(doc, "这句话是模型编的，用户看不出到底哪里坏了。建议工具统一返回：")
code(doc, """{"ok": false, "error": "upstream_timeout",
 "message": "天气服务连接超时", "retryable": true}""")

para(doc, "模型就会说「天气服务暂时连不上，等下再问我」，比现在的说法清楚。")

heading(doc, "五、优先级与工作量估算")

table(doc, [
    ["事项", "影响", "优先级", "预估"],
    ["日期注入 / get_datetime", "「今天几号」答错，影响最大", "P0", "0.5 小时"],
    ["天气工具修复", "天气问答全废", "P0", "1~2 小时"],
    ["/v1/tools + /health 自检", "出问题能定位", "P0", "1 小时"],
    ["工具失败结构化返回", "回答更可信", "P1", "0.5 小时"],
    ["新闻工具", "新能力", "P1", "2 小时"],
    ["联网搜索工具", "新能力", "P1", "2~3 小时"],
    ["音乐搜索工具", "语音点歌走模型", "P2", "1 小时"],
], [6.4, 6.2, 2.4, 2.6])

heading(doc, "六、我这边已经做完的（不需要你做）")

table(doc, [
    ["项", "状态"],
    ["模型切到 xiaohui-r5:latest", "已完成"],
    ["人设同步为训练用提示词 + 身份声明", "已完成"],
    ["语音侧人设/音色与试聊一致", "已完成"],
    ["按意图分流（闲聊快速通道 / 工具通道）", "已完成"],
    ["日期注入（控制台与语音侧）", "已完成"],
    ["音乐点播/推荐/查询/停止（关键词直通）", "已完成"],
    ["设备热点名改为 Xiaohui-XXXX", "已完成"],
], [10.4, 6.4])

para(doc, "所以上表 P0 的三项做完，语音问答的体验就基本完整了。", bold=True)

heading(doc, "七、怎么验收")

para(doc, "改完跑这五条，把结果发我：", bold=True)
code(doc, """# 1 日期
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" \\
  -d '{"model":"xiaohui-r5:latest","messages":[{"role":"user","content":"今天几号"}]}'

# 2 天气
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" \\
  -d '{"model":"xiaohui-r5:latest","messages":[{"role":"user","content":"上海天气怎么样"}]}'

# 3 新闻
... "messages":[{"role":"user","content":"今天有什么新闻"}]

# 4 搜索
... "messages":[{"role":"user","content":"帮我搜一下明天的限行"}]

# 5 工具自检
curl -s http://127.0.0.1:8000/v1/tools""")

para(doc, "期望：前四条都能给出具体内容（日期是今天、天气有温度、新闻有标题、"
          "搜索有摘要），第五条能看到每个工具的 ok 状态。", color=GREEN)

doc.save(OUT)
print("saved:", OUT)
