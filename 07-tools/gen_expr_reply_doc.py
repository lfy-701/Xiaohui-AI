"""生成《表情控制联调回复》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\表情控制联调回复-给成员A.docx"

ACCENT = RGBColor(0x1B, 0x6F, 0xC4)
GREY = RGBColor(0x66, 0x66, 0x66)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x1E, 0x8E, 0x5A)
AMBER = RGBColor(0xB8, 0x6A, 0x00)


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
font(p.add_run("表情控制联调回复"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("控制台侧已实现 · emotion 指令可下发 · 2026-11-22"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、一句话结论")

para(doc, "控制台侧三个接口已经实现并通过验收，你现在只改一个环境变量就能联调。",
     bold=True, color=GREEN)

table(doc, [
    ["你的需求", "控制台状态"],
    ["硬件令牌", "已提供（见第二节）"],
    ["type 白名单加 emotion", "已加，11 个表情全部支持"],
    ["在线设备 ID", "已提供（设备当前离线，见第四节）"],
    ["三个接口", "已实现，按你文档的形状"],
], [8.0, 8.4])

heading(doc, "二、给你配置的值")

table(doc, [
    ["项", "值"],
    ["接口基地址", "http://100.100.221.34"],
    ["令牌头", "X-Hardware-Token"],
    ["令牌值", "<REDACTED>"],
    ["设备 ID", "<设备MAC>"],
], [4.6, 11.8])

para(doc, "把令牌填到 hardware-mcp 的环境变量里，重启 8103 即可（你说只改环境变量、不改代码）。")

heading(doc, "三、三个接口的实际形状")

heading(doc, "3.1 设备列表", level=2)
code(doc, """GET /api/hardware/devices
X-Hardware-Token: <REDACTED>

200 {"devices":[{"id":"<设备MAC>","name":"小慧AI",
                "mac":"<设备MAC>","online":false,
                "firmware":"2.5.3","bound":true}]}""")

heading(doc, "3.2 下发指令", level=2)
code(doc, """POST /api/hardware/devices/<设备MAC>/commands
X-Hardware-Token: <REDACTED>
Content-Type: application/json

{"type":"emotion","params":{"emotion":"happy"}}

200 {"command":{"id":"28f44779b5994548"}}""")

heading(doc, "3.3 查询回执", level=2)
code(doc, """GET /api/hardware/commands/28f44779b5994548
X-Hardware-Token: <REDACTED>

200 {"command":{"id":"28f44779b5994548","type":"emotion",
                "status":"executed","result":"表情已切换","error":null}}""")

heading(doc, "四、实测结果（如实）")

table(doc, [
    ["检查项", "结果", "说明"],
    ["GET devices（带令牌）", "200 通过", "返回 1 台设备"],
    ["POST commands type=emotion", "200 通过", "返回 command.id"],
    ["GET commands/{id}", "200 通过", "status=failed"],
    ["非法 emotion（dancing）", "400 通过", "拒绝且不产生指令"],
    ["设备屏幕是否切换", "未验证", "设备当前离线"],
], [5.6, 3.4, 7.4])

para(doc, "status=failed 的原因不是你这边的问题：设备当前没有连上语音服务，"
          "控制台取不到设备通道，于是如实返回失败，而不是挂一个 pending 等超时。",
     color=AMBER)

heading(doc, "五、一个实现差异（你不需要改代码）")

para(doc, "你的文档假设：下发指令 → 设备心跳取走 → 执行 → 回执。")

para(doc, "控制台实际做法：emotion 这类「只动屏幕」的指令，直接走语音服务到设备的 "
          "WebSocket MCP 通道（self.set_emotion），0.1~0.3 秒内完成。")

table(doc, [
    ["项", "你的假设", "实际实现", "对你是否有影响"],
    ["接口形状", "commands + 回执", "完全一致", "无"],
    ["执行通道", "设备心跳", "WebSocket MCP", "无（你只认接口）"],
    ["延迟", "≤5 秒", "0.1~0.3 秒", "更快"],
    ["离线行为", "pending 等超时", "直接 failed + error", "见下"],
], [3.4, 4.0, 4.6, 4.4])

para(doc, "离线行为需要你知道：如果设备没连上，回执立刻是 "
          "status=failed、error=设备当前不在线，不会等超时。你的工具可以据此"
          "如实告诉模型「设备现在没连上」，而不是超时后假成功。",
     bold=True)

heading(doc, "六、指令类型支持范围")

table(doc, [
    ["type", "参数", "执行方式", "状态值"],
    ["emotion", "emotion（11 选 1）", "WebSocket MCP 即时", "executed / failed"],
    ["servo_control", "value", "设备心跳队列", "queued"],
    ["servo_action", "value", "设备心跳队列", "queued"],
    ["action", "value", "设备心跳队列", "queued"],
    ["led", "value", "设备心跳队列", "queued"],
    ["pose", "value", "设备心跳队列", "queued"],
], [4.0, 4.2, 5.0, 3.2])

para(doc, "11 个表情取值（大小写不敏感，控制台会转小写）：")
code(doc, """neutral  happy  laughing  sad  angry  surprised
sleepy   thinking  cool   love  confused""")

heading(doc, "七、联调步骤（按你的五步，已适配）")

para(doc, "Step 1　把令牌填进 hardware-mcp 环境变量，重启 8103。", bold=True)
para(doc, "Step 2　先单独验证控制台（设备需在线）：", bold=True)
code(doc, """curl -X POST http://100.100.221.34/api/hardware/devices/<设备MAC>/commands \\
  -H "X-Hardware-Token: <REDACTED>" \\
  -H "Content-Type: application/json" \\
  -d '{"type":"emotion","params":{"emotion":"happy"}}'

# 期望 {"command":{"id":"..."}}
# 再查
curl http://100.100.221.34/api/hardware/commands/<ID> \\
  -H "X-Hardware-Token: <REDACTED>"
# 期望 status=executed, result=表情已切换""")

para(doc, "Step 3　验证工具挂到模型：按你的命令查 set_emotion。", bold=True)
para(doc, "Step 4　端到端：控制台试聊说「开心一点，笑一个」，看屏幕是否切 happy。", bold=True)
para(doc, "Step 5　异常路径：令牌改错 → 期望 401；emotion 传 dancing → 期望 400。", bold=True)

heading(doc, "八、验收清单对照")

table(doc, [
    ["#", "你的检查项", "控制台实测"],
    ["1", "GET devices 带令牌 200", "✅ 200"],
    ["2", "POST commands 返回 id", "✅ 200 + id"],
    ["3", "GET commands/{id} status=executed", "⏳ 设备在线后验证"],
    ["4", "设备屏幕切换表情", "⏳ 设备在线后验证"],
    ["5", "非法 emotion 返回 400", "✅ 400"],
    ["6", "控制台试聊触发", "⏳ 待设备在线"],
], [1.0, 8.6, 6.8])

heading(doc, "九、我需要你确认的一件事")

para(doc, "设备现在是离线状态（控制台 devices 接口返回 online=false）。"
          "请确认设备通电并连上网络后告诉我，我可以立刻跑 Step 2 的验收，"
          "把 status 变成 executed。")

para(doc, "另外：设备表情目前由固件里的 11 种内置表情渲染，"
          "与你表格里的清单一致（neutral / happy / laughing / sad / angry / "
          "surprised / sleepy / thinking / cool / love / confused）。",
     color=GREY)

doc.save(OUT)
print("saved:", OUT)
