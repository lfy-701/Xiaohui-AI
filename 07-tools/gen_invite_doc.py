"""生成《邀请成员 B 加入私有仓库》操作文档，发给成员 A。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\成员B仓库邀请-给成员A.docx"

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
        font(p.add_run(line if line else " "), size=9, mono=True, color=RGBColor(0x1E, 0x4A, 0x7A))
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
font(p.add_run("邀请成员 B 加入私有仓库"), size=21, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("需要成员 A 执行的操作 · 2026-11-10"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、需要做的事")

para(doc, "成员 B 已在 GitHub 注册账号并开启双重认证，用户名如下：", bold=True)
table(doc, [
    ["项目", "值"],
    ["GitHub 用户名", "lfy-701"],
    ["仓库", "hdaefadhj/xiaoxiao-ai（Private）"],
    ["需要的权限", "Write（可推送分支，不能改仓库设置）"],
], [4.2, 12.6])

para(doc, "")
para(doc, "请在仓库设置里邀请该账号：", bold=True)
code(doc, """1. 打开 https://github.com/hdaefadhj/xiaoxiao-ai/settings/access
2. 点右上角「Add people」
3. 搜索框输入：lfy-701
4. 权限选择：Write
5. 点「Add lfy-701 to this repository」""")

para(doc, "邀请发出后，成员 B 会在下面两处收到通知：", bold=True)
code(doc, """https://github.com/notifications
注册邮箱里的 GitHub 邀请邮件""")

para(doc, "成员 B 点击接受后，即可访问仓库。")

heading(doc, "二、权限建议")

table(doc, [
    ["权限", "是否建议", "说明"],
    ["Read", "不够", "只能看代码，无法推送分支"],
    ["Write", "推荐", "可推送功能分支、开 PR，不能改仓库设置"],
    ["Admin", "不建议", "能改仓库设置与删除仓库，超出协作需要"],
], [3.0, 3.4, 10.4])

para(doc, "成员 B 只需要提交功能分支并开 PR，Write 已足够；合并仍由你审核后操作。",
     color=GREEN)

heading(doc, "三、邀请后的分工")

table(doc, [
    ["环节", "谁做"],
    ["接受邀请、配置本机 SSH 密钥", "成员 B（公钥已备好）"],
    ["推送 feature/memory-kb、开 PR", "成员 B"],
    ["审核 PR、合并到 main", "成员 A"],
    ["开启 main 分支保护、禁止强推", "成员 A（仓库管理员）"],
], [9.4, 7.4])

heading(doc, "四、成员 B 当前的提交状态")

para(doc, "由于之前没有仓库访问权限，成员 B 的改动一直没能推上去。目前本地已有两个提交：")
table(doc, [
    ["提交", "说明"],
    ["2b150a0", "首版：控制台 / 知识库 / 音乐 MCP / 固件板级代码"],
    ["3e58704", "配置页、语音设置、表情界面、运行时唤醒词（7 文件 / +1455 行）"],
], [3.4, 13.4])

para(doc, "邀请到位后，成员 B 会按手册第 5 节先合并 origin/main，再推送 feature/memory-kb。")

heading(doc, "五、如果暂时不方便邀请：离线交接")

para(doc, "成员 B 已经导出可直接导入的 bundle，你可以先导入、再代为推送，不必等邀请流程：")
code(doc, """xiaohui-member-b.bundle          301 KB
xiaohui-member-b.bundle.sha256""")

table(doc, [
    ["项目", "值"],
    ["分支", "feature/memory-kb"],
    ["最新提交", "3e58704"],
    ["SHA-256", "6b12f9529629af7e5c4883e8fe74e468dde0f19a5e56792cc89c8e05d41a434a"],
], [3.0, 13.8])

para(doc, "导入步骤：", bold=True)
code(doc, """git clone xiaohui-member-b.bundle xiaoxiao-ai
cd xiaoxiao-ai
git remote add origin https://github.com/hdaefadhj/xiaoxiao-ai.git
git push origin feature/memory-kb""")

heading(doc, "六、常见问题")

table(doc, [
    ["现象", "原因与处理"],
    ["搜不到 lfy-701", "确认拼写，需要完整用户名（含连字符），不要填邮箱"],
    ["对方说仓库打不开、返回 404", "邀请未被接受，或接受的不是 lfy-701 这个账号"],
    ["邀请链接过期", "在 Settings → Access 里重新发送邀请"],
    ["对方能克隆但推送被拒", "权限是 Read，改成 Write"],
], [6.0, 10.8])

doc.add_paragraph()
para(doc, "以上。邀请完成后告知一声即可，成员 B 会立即验证访问并推送分支。", bold=True)

doc.save(OUT)
print("saved:", OUT)
