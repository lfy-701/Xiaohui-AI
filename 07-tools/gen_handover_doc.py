"""生成《成员 B 源码交接说明》docx。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\成员B源码交接说明.docx"

ACCENT = RGBColor(0x1B, 0x6F, 0xC4)
GREY = RGBColor(0x66, 0x66, 0x66)
GREEN = RGBColor(0x1E, 0x8E, 0x5A)


def set_font(run, name="微软雅黑", size=10.5, bold=False, color=None, mono=False):
    run.font.name = "Consolas" if mono else name
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def para(doc, text, size=10.5, bold=False, color=None, after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    set_font(p.add_run(text), size=size, bold=bold, color=color)
    return p


def code(doc, text):
    for line in text.strip("\n").split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.left_indent = Cm(0.5)
        set_font(p.add_run(line if line else " "), size=8.5, mono=True,
                 color=RGBColor(0x1E, 0x4A, 0x7A))
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def heading(doc, text, level=1):
    h = doc.add_heading(level=level)
    h.paragraph_format.space_before = Pt(12)
    h.paragraph_format.space_after = Pt(6)
    set_font(h.add_run(text), size=15 if level == 1 else 12, bold=True, color=ACCENT)
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
            set_font(r, size=9.5, bold=(i == 0), color=ACCENT if i == 0 else None)
            cells[j].width = Cm(widths[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


doc = Document()
sec = doc.sections[0]
sec.left_margin = Cm(2.0)
sec.right_margin = Cm(2.0)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run("成员 B 源码交接说明"), size=22, bold=True, color=ACCENT)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run("feature/memory-kb · 2026-11-09"), size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、交接信息")
table(doc, [
    ["项目", "内容"],
    ["基线提交", "main @ 639cc73"],
    ["分支", "feature/memory-kb"],
    ["提交", "2b150a0"],
    ["交接文件", "xiaohui-member-b.bundle + .sha256"],
    ["SHA-256", "79eceb035dc0694beb04307910180c3f43b93e9a7177f910070c2be85d2e4fb5"],
], [3.4, 13.4])

heading(doc, "二、提交内容")

table(doc, [
    ["目录", "内容", "文件数"],
    ["console/", "控制台前后端、启动脚本、配置模板", "10"],
    ["kb-service/", "知识库与长期记忆服务", "10"],
    ["services/music-mcp/", "音乐 MCP 服务（MCP + REST 两套接口）", "4"],
    ["firmware/boards/esp32-dog-wangcai/", "板级代码", "9"],
    ["firmware/patches/", "相对上游的修改说明", "2"],
    [".gitignore", "追加本项目忽略规则", "—"],
], [5.6, 9.2, 2.0])

heading(doc, "三、必须知道的三条接口约定")

heading(doc, "3.1 控制台调用模型服务", level=2)
para(doc, "控制台只发送朴素 messages，不做工具注入；工具由模型服务处理，最终返回自然语言。")
code(doc, '{"model": "...", "messages": [...], "stream": true}')

heading(doc, "3.2 OTA 响应：已绑定时不能带 activation", level=2)
table(doc, [
    ["设备状态", "返回字段"],
    ["未绑定", "activation: {code, message, timeout_ms}"],
    ["已绑定", "websocket: {url, token, version}"],
], [4.0, 12.8])
para(doc, "固件一旦看到 activation 字段就认为还需激活，会进入重试循环，无法连接语音服务。"
          "这一条在真机上踩过坑，请务必保持。", color=RGBColor(0xC0, 0x39, 0x2B))

heading(doc, "3.3 设备心跳鉴权", level=2)
para(doc, "设备心跳携带 X-Device-Token，与控制台环境变量 DEVICE_TOKEN 比对。"
          "未配置时接口返回 503，不做空令牌放行。")

heading(doc, "四、配置项（全部走环境变量）")
table(doc, [
    ["变量", "用途"],
    ["CONSOLE_PASSWORD", "控制台登录密码"],
    ["DEVICE_TOKEN", "设备接入令牌，须与固件一致"],
    ["KB_URL", "知识库服务地址"],
    ["LLM_CHAT_URL", "模型服务地址"],
    ["MCP_BASE_URL / MCP_ADMIN_TOKEN", "MCP 管理接口与远程写令牌（仅后端）"],
    ["WS_URL", "语音服务 WebSocket，OTA 下发给设备"],
    ["MUSIC_BASE_URL", "音乐 MCP 服务地址"],
], [6.2, 10.6])

heading(doc, "五、已清理的硬编码")
table(doc, [
    ["位置", "原值", "现状"],
    ["console/app/main.py", "DEVICE_TOKEN 默认值", "无默认值，缺失时设备接口 503"],
    ["console/app/main.py", "MCP 地址写死内网 IP", "无默认值，未配置时返回未配置提示"],
    ["console/start-console.ps1", "密码与令牌明文", "改为读取 .env"],
    ["firmware/.../dog_board.cc", "真实内网 IP + 真实令牌", "示例地址 + 占位令牌"],
    ["services/music-mcp/README.md", "真实内网 IP", "占位符"],
], [5.4, 5.4, 6.0])

heading(doc, "六、测试记录")
table(doc, [
    ["模块", "检查项", "结果"],
    ["console", "python -c \"import app.main\"", "通过"],
    ["console", "uvicorn 启动 + 登录页", "HTTP 200"],
    ["console", "未设 DEVICE_TOKEN 时设备注册", "HTTP 503（拒绝而非放行）"],
    ["kb-service", "python -c \"import app.main\"", "通过"],
    ["music-mcp", "MCP 客户端握手 + tools/list", "成功，4 个只读工具"],
    ["music-mcp", "search_music(\"周杰伦\")", "返回 3 首，含可播放链接"],
    ["firmware", "idf.py build", "通过，xiaozhi.bin 2.47 MB"],
], [3.0, 8.0, 5.8])

para(doc, "未执行项：")
table(doc, [
    ["项目", "未执行原因"],
    ["固件真机联调", "需实体 ESP32-S3 与同局域网语音服务，属部署环境验证"],
    ["voice-server 测试", "该项目含 893 MB 模型权重，按约定不入库"],
], [5.0, 11.8])

heading(doc, "七、外部依赖（不入库）")
table(doc, [
    ["依赖", "说明"],
    ["78/xiaozhi-esp32 v2.5.2", "固件上游，MIT；本仓库只放板级代码与 patch 说明"],
    ["xinnan-tech/xiaozhi-esp32-server", "语音服务上游；需自行下载 SenseVoiceSmall（约 893 MB）"],
    ["Edge TTS", "控制台音色与试听，在线调用，无需 Key"],
    ["iTunes Search API", "音乐 MCP 数据源，免费，无需 Key"],
], [6.0, 10.8])

heading(doc, "八、已知限制")
table(doc, [
    ["编号", "限制"],
    ["1", "esp-sr 无「你好小慧」专用唤醒词模型，改用 MultiNet 拼音自定义，识别率需真机验证"],
    ["2", "在线音乐只提供 30 秒试听；整首播放依赖本地曲库目录"],
    ["3", "设备无法访问 Tailscale 网段，需与控制台同一局域网"],
    ["4", "控制台当前为单账号，未做多用户与权限分级"],
], [1.6, 15.2])

heading(doc, "九、回滚方式")
para(doc, "采用新增提交或 GitHub Revert，不对共享 main 强推。")
code(doc, """git revert --no-commit <merge-commit>
git commit -m "revert: 撤回成员 B 首版交接\"""")

doc.add_paragraph()
para(doc, "以上。如需我补充任何模块的细节，随时说。", bold=True)

doc.save(OUT)
print("saved:", OUT)
