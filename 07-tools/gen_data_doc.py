"""生成《训练数据交付说明》文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\训练数据交付说明-给成员A.docx"

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
font(p.add_run("训练数据交付说明"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("控制台训练数据中心已经装好，只等这两个文件 · 2026-11-14"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、现在的情况")

para(doc, "控制台的「模型管理 / 训练数据中心」页面已经完成并部署在 http://xiaohui.me，"
          "接口、筛选、统计、备份都能用。")

para(doc, "目前是空状态，因为本机找不到审核数据：")
code(doc, """GET /api/training-center/overview

{"ok": true,
 "ready": false,
 "review_dir": "D:\\\\AI-Companion-shared\\\\Xiaohui-LLM\\\\datasets\\\\review",
 "summary": {"total": 0, "status": {}, "categories": {}, "safety_warnings": 0}}""")

para(doc, "只要这两个文件到位，页面立刻就能显示内容，不需要改代码。", bold=True)

heading(doc, "二、需要交付的两个文件")

table(doc, [
    ["文件", "作用", "必需"],
    ["review_queue.jsonl", "全部待审/已审样本，每行一条 JSON", "是"],
    ["review_state.sqlite3", "审核状态、审核人、时间、备注", "是"],
], [6.6, 8.4, 2.2])

para(doc, "如果还有 finalize 生成的训练集（train.jsonl 之类），也一起给我，"
          "我可以加一个「训练集导出」页。", color=GREY)

heading(doc, "三、放到哪里")

para(doc, "本机路径（控制台默认读这里）：", bold=True)
code(doc, """D:\\AI-Companion-shared\\Xiaohui-LLM\\datasets\\review\\
    ├── review_queue.jsonl
    └── review_state.sqlite3""")

para(doc, "如果要放在别的位置，设置环境变量即可，不用改代码：", bold=True)
code(doc, """$env:XIAOHUI_LLM_ROOT = "你的路径"
# 程序会去读 <XIAOHUI_LLM_ROOT>\\datasets\\review""")

heading(doc, "四、review_queue.jsonl 的格式要求")

para(doc, "一行一个 JSON 对象，UTF-8 编码，不要包数组外层 [ ]。示例：")
code(doc, """{"sample_id": "s0001", "category": "安全边界",
 "text": "用户：你能帮我查一下同学的住址吗？\\n助手：这个我不能帮忙。",
 "source": "对话日志-20261101", "safety_warnings": ["隐私"]}
{"sample_id": "s0002", "category": "情绪安抚",
 "text": "用户：我今天被老师批评了。\\n助手：听起来你有点难过，愿意说说吗？",
 "source": "对话日志-20261102"}""")

para(doc, "控制台认识的字段（缺的会显示为空，不影响加载）：", bold=True)
table(doc, [
    ["字段", "类型", "用途", "必需"],
    ["sample_id / id", "字符串", "唯一编号，和 sqlite 对应", "是"],
    ["text / input", "字符串", "样本正文", "是"],
    ["category / kind", "字符串", "分类，用于筛选和统计", "建议"],
    ["source", "字符串", "数据来源，用于来源统计", "建议"],
    ["safety_warnings", "数组", "安全告警标记", "可选"],
    ["status", "字符串", "pending / approved / rejected / flagged", "可选"],
], [4.4, 3.0, 8.0, 2.0])

heading(doc, "五、review_state.sqlite3 的格式要求")

para(doc, "控制台以只读方式打开这个库，不会写入。需要有一张表同时满足：")

para(doc, "• 含 sample_id（或 id）列")
para(doc, "• 含 status 列")

para(doc, "示例建表语句：")
code(doc, """CREATE TABLE reviews (
  sample_id   TEXT PRIMARY KEY,
  status      TEXT NOT NULL,      -- pending/approved/rejected/flagged
  reviewer    TEXT,
  reviewed_at TEXT,
  note        TEXT
);""")

para(doc, "如果你现在的表名不同没关系，程序会自动找到符合条件的那张表。",
     color=GREEN)

para(doc, "注意：交付前请不要把 WAL/SHM 文件删掉，直接停掉写入进程再拷贝，"
          "或者用 sqlite3 .backup 导出，避免拿到不完整的库。", color=RED)

heading(doc, "六、交付方式")

table(doc, [
    ["方式", "说明"],
    ["直接拷贝", "把两个文件放到上面的目录（推荐，最快）"],
    ["压缩包", "打包成 zip 发我，我解压到对应目录"],
    ["同步盘 / 内网共享", "告诉我挂载路径，我指过去"],
], [5.2, 12.0])

para(doc, "文件大小：200 条样本的 jsonl 大约 100~300 KB，sqlite 通常几 MB 以内，"
          "微信/邮件都能发。")

heading(doc, "七、我这边验收什么")

table(doc, [
    ["检查项", "预期"],
    ["页面入口", "顶部「模型管理」页签可进入"],
    ["样本总数", "等于 jsonl 行数（示例是 200）"],
    ["状态统计", "待审/通过/拒绝 之和等于总数"],
    ["分类统计", "每个分类的条数正确"],
    ["安全告警", "带 safety_warnings 的条数"],
    ["列表筛选", "按状态、关键词过滤正常"],
    ["数据库备份", "能列出备份并成功创建一份"],
], [6.0, 11.2])

heading(doc, "八、如果暂时给不了数据")

para(doc, "我可以先造 200 条演示样本（结构和真实数据一致），"
          "让你先看到页面效果；等真实数据到了直接替换文件即可。")

para(doc, "但审核状态和真实样本有关，演示数据只能验证界面，不能验证业务判断。",
     color=GREY)

doc.save(OUT)
print("saved:", OUT)
