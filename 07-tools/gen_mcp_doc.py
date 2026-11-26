"""生成《MCP 接入完成说明与反馈》docx。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\MCP接入完成说明与反馈.docx"

ACCENT = RGBColor(0x1B, 0x6F, 0xC4)
GREY = RGBColor(0x66, 0x66, 0x66)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x1E, 0x8E, 0x5A)


def set_font(run, name="微软雅黑", size=10.5, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def para(doc, text, size=10.5, bold=False, color=None, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    set_font(r, size=size, bold=bold, color=color)
    return p


def code(doc, text):
    for line in text.strip("\n").split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run(line if line else " ")
        set_font(r, name="Consolas", size=8.5)
        r.font.color.rgb = RGBColor(0x1E, 0x4A, 0x7A)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def heading(doc, text, level=1):
    h = doc.add_heading(level=level)
    h.paragraph_format.space_before = Pt(14)
    h.paragraph_format.space_after = Pt(6)
    r = h.add_run(text)
    set_font(r, size=15 if level == 1 else 12, bold=True, color=ACCENT)
    return h


def table(doc, rows, widths=None):
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, val in enumerate(row):
            cell = cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(str(val))
            set_font(r, size=9.5, bold=(i == 0))
            if i == 0:
                r.font.color.rgb = ACCENT
            if widths:
                cell.width = Cm(widths[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


doc = Document()
sec = doc.sections[0]
sec.left_margin = Cm(2.0)
sec.right_margin = Cm(2.0)

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
tr = title.add_run("MCP 接入完成说明与反馈")
set_font(tr, size=22, bold=True, color=ACCENT)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("回复《MEMBER_B_MCP_INTEGRATION》· 2026-11-09")
set_font(sr, size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、结论")

para(doc, "MCP 已经接入控制台，采用的是你文档里的方案三（控制台后端代理），"
          "并用真实天气问题做了端到端验证，工具调用成功、数据真实来自 Open-Meteo。", bold=True)
para(doc, "控制台新增了「MCP 工具」页签，可以查看 Server 状态、已注册工具、调用记录，"
          "并支持重连 / 启用停用 / 只读测试。同时保留了右上角「打开管理页」入口，"
          "可直接跳到你原生的 /mcp-admin。")

heading(doc, "二、先澄清三个环境问题")

para(doc, "你文档里提到「控制台 /api/models 显示上游为 127.0.0.1:8100，"
          "怀疑是需要确认的隧道映射」——这里要更正：")

table(doc, [
    ["你的疑问", "实际情况"],
    ["127.0.0.1:8100 是否是到 8000 的安全隧道",
     "不是。那是我为了让语音链路在你服务离线期间也能跑通，临时起的本地模拟 LLM 服务。"
     "现已停用。"],
    ["该隧道重启后是否自动恢复",
     "不存在隧道。控制台现在直连 http://<本地模型服务器IP>:8000"],
    ["控制台聊天是否仍发 /v1/chat/completions",
     "是，未改动，仍是标准 OpenAI 兼容格式"],
    ["远程浏览器能否访问 /mcp-admin",
     "可以。但已经不需要 iframe 了，控制台内置页面更安全"],
], widths=[6.6, 10.2])

para(doc, "另外说明：控制台密码已从 xiaoxiao2026 改为 xiaohui2026（项目整体改名为「小慧控制台」）。"
          "你之前遇到「密码不对」是正常的。", color=GREY)

heading(doc, "三、控制台新增的代理接口")

para(doc, "所有请求由控制台后端转发，浏览器不接触你的 service 地址，令牌也不下发前端：")
code(doc, """
GET   /api/mcp/status                 汇总：连通性、Server 数、工具数
GET   /api/mcp/servers                Server 列表与状态
GET   /api/mcp/tools                  工具与 Schema
GET   /api/mcp/calls?limit=N          调用记录
GET   /api/mcp/events?limit=N         连接与错误日志
POST  /api/mcp/servers/{id}/refresh   重新连接
PATCH /api/mcp/servers/{id}           启用 / 停用
POST  /api/mcp/tools/{name}/test      只读工具测试
""")
para(doc, "后端配置了两个环境变量：MCP_BASE_URL（默认 http://<本地模型服务器IP>:8000）和 "
          "MCP_ADMIN_TOKEN。后者只在控制台后端拼接成 X-MCP-Admin-Token 请求头，"
          "不进浏览器、不进模型提示词，符合你文档里的安全边界要求。")

heading(doc, "四、实际接入结果")

table(doc, [
    ["项目", "结果"],
    ["连通性", "online = true"],
    ["Server", "1 个：Open-Meteo 天气（status=online）"],
    ["工具", "3 个：get_current_weather / get_weather_alert / get_weather_forecast"],
    ["只读标记", "3 个工具均标记为只读"],
], widths=[3.6, 13.2])

doc.add_paragraph()
para(doc, "控制台内提问「深圳现在天气怎么样」，模型自主调用工具并给出：", bold=True)
code(doc, """
深圳现在的温度是 24°C，体感温度 22°C，天气晴朗，
湿度 46%，风速 22.5 km/h。
""")
para(doc, "对应调用记录（控制台可直接查看）：")
code(doc, """
tool      : get_current_weather
arguments : {"city": "深圳"}
status    : success
duration  : 2591 ms
""")
para(doc, "回答中的温度、体感、湿度、风速均来自工具返回，不是模型编造。", color=GREEN)

heading(doc, "五、需要你关注的一个问题")

para(doc, "第二个问题表现异常。", bold=True, color=RED)
para(doc, "控制台内提问「帮我查一下北京明天的天气」，模型回复：")
code(doc, """
我会为您查询北京明天的天气情况。
""")
para(doc, "然后就结束了。调用记录里没有这次请求，说明 get_weather_forecast 没有被调用。"
          "从控制台侧看，请求正常发出、正常返回，不是控制台的超时或截断。")

para(doc, "可能的原因，按我的判断排序：")
table(doc, [
    ["排序", "可能原因", "建议排查方向"],
    ["1", "工具描述里对「未来天气」的触发条件不够强，模型没选择调用",
     "在 get_weather_forecast 的 description 里明确「涉及明天/未来 N 天必须调用」"],
    ["2", "模型把「明天」当成了不可推断的参数，先决定「告知用户要去查」",
     "在 system prompt 里加一条：需要实时数据时必须先调用工具再回答"],
    ["3", "工具结果回送后模型没有复述，最终回答被截断",
     "检查 MCP_MAX_TOOL_ROUNDS 与最终回答的 max_tokens"],
    ["4", "get_weather_forecast 调用失败但错误被吞掉",
     "把调用失败的 error 也写进 /api/mcp/calls，便于定位"],
], widths=[1.4, 7.4, 8.0])

para(doc, "另外，调用记录里有一条历史 error：", space_after=2)
code(doc, """
04:12:59  get_current_weather  error  2040ms
""")
para(doc, "如果能提供那次的具体错误信息，我可以一并确认是不是同类问题。")

heading(doc, "六、需要你确认的")

table(doc, [
    ["序号", "事项"],
    ["1", "get_weather_forecast 未触发的问题，是否按上面第 1、2 条调整工具描述或提示词"],
    ["2", "如果设置了 MCP_ADMIN_TOKEN，把值告诉我，我配到控制台后端即可启用写操作"],
    ["3", "确认 /api/mcp/calls 返回的字段名（我目前按 tool_name、arguments、status、duration_ms 解析）"],
    ["4", "是否还有其他 MCP Server 计划接入，我预留了列表渲染，加配置即可自动显示"],
], widths=[1.4, 15.4])

heading(doc, "七、控制台访问方式")

table(doc, [
    ["入口", "地址"],
    ["本机", "http://127.0.0.1"],
    ["域名", "http://xiaohui.me"],
    ["Tailscale", "http://100.100.221.34"],
    ["密码", "xiaohui2026"],
], widths=[3.6, 13.2])

para(doc, "")
para(doc, "以上。工具链路的后端闭环没有问题，剩下的主要是「何时该调用 forecast」这一层的策略。", bold=True)

doc.save(OUT)
print("saved:", OUT)
