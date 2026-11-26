"""生成《GitHub 接入指南反馈》docx。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\GitHub接入指南反馈.docx"

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
tr = title.add_run("GitHub 接入指南 · 反馈")
set_font(tr, size=22, bold=True, color=ACCENT)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("回复《MEMBER_B_GITHUB_ONBOARDING》· 2026-11-09")
set_font(sr, size=10.5, color=GREY)

doc.add_paragraph()

heading(doc, "一、总体评价")

para(doc, "文档结构完整，流程是标准做法，以下几点写得尤其清楚：", bold=True)
table(doc, [
    ["做得好", "说明"],
    ["安全边界明确", "不把 Token / 密码发到聊天、文档、源码；提交前逐项检查"],
    ["防止覆盖他人代码", "每次先 fetch、合并前看 diff、冲突保留双方逻辑"],
    ["责任边界清晰", "成员 A 不代为修改尚未提供的源码"],
    ["分支与 PR 流程规范", "feature 分支 → 自测 → PR → 审核 → 合并"],
], widths=[4.6, 12.2])

doc.add_paragraph()
para(doc, "但有一处会直接失败的环境问题，以及几处需要按我们的实际情况调整。", bold=True, color=RED)

heading(doc, "二、硬阻塞：这台机器访问不到 GitHub")

para(doc, "实测结果（2026-11-09 12:40）：")
table(doc, [
    ["域名", "443 端口", "说明"],
    ["github.com", "不可达", "第 3 步 git clone 会失败"],
    ["api.github.com", "不可达", "第 2 步 gh auth login 会失败"],
    ["codeload.github.com", "不可达", "下载仓库包也会失败"],
    ["gitee.com", "可达", "可作为替代通路"],
], widths=[5.2, 3.2, 8.4])

para(doc, "结论：文档第 1、2、3 步在我们侧全部无法执行——注册、2FA、邀请接受、clone 都不行。"
          "这不是配置问题，是网络策略限制。")

heading(doc, "2.1 三个可选方案", level=2)
table(doc, [
    ["方案", "做法", "代价"],
    ["A. Gitee 私有镜像（推荐长期）",
     "我方在 Gitee 建私有仓库并推送；成员 A 从 Gitee 拉取，或在可访问 GitHub 的环境做一次同步",
     "多一个远端，需要一次对齐"],
    ["B. 本地 bundle 交接（推荐先做）",
     "我方本地 git init + 提交，导出 git bundle 单文件，经共享盘或 Tailscale 传给成员 A，"
     "他直接 git clone xxx.bundle",
     "零网络依赖，今天就能交付"],
    ["C. 成员 A 提供代理",
     "提供可用代理，或在一台能上 GitHub 的机器上代为操作",
     "取决于可用资源"],
], widths=[4.6, 9.2, 3.0])

para(doc, "建议 A + B 组合：先用 bundle 把代码交出去，再建 Gitee 镜像作为长期协作入口。", bold=True)

heading(doc, "三、需要修正的细节")

heading(doc, "3.1 仓库名不统一", level=2)
para(doc, "文档写的是 xiaoxiao-ai，但项目已经整体改名为「小慧控制台」，此前的报告里还出现过 "
          "model-service 与 knowledge_base。如果这三个名字指同一个私有仓库，建议在文档里"
          "统一说明一次，否则我方可能 clone 到错误的仓库。")

heading(doc, "3.2 固件不能整目录复制", level=2)
para(doc, "我方固件目录实测体积：")
table(doc, [
    ["范围", "文件数", "体积"],
    ["整个目录", "15588", "1.1 GB"],
    ["仅源码（排除 build/ 与 managed_components/）", "1754", "9.5 MB"],
], widths=[9.4, 3.4, 4.0])

para(doc, "build/ 与 managed_components/ 占了 99% 的体积。若按文档第 4 步执行 "
          "Copy-Item -Recurse，会把 1.1 GB 塞进仓库。")
para(doc, "建议只提交：", bold=True)
code(doc, """
firmware/
├── boards/esp32-dog-wangcai/   板级代码（config.h / dog_board.cc / servo / leds / display）
├── patches/                    相对上游 xiaozhi-esp32 的改动说明
└── README.md                   构建步骤与必要配置项
""")

heading(doc, "3.3 固件基于上游 fork，注意许可证", level=2)
para(doc, "我方固件基于 78/xiaozhi-esp32。建议在 firmware/README.md 注明上游地址与所用 tag，"
          "并保留上游 LICENSE。把上游全量代码放进私有仓库，既占体积也容易产生合规争议。")

heading(doc, "3.4 密钥卫生：我方目前有两处硬编码", level=2)
table(doc, [
    ["位置", "内容", "处理方式"],
    ["console/app/main.py", "DEVICE_TOKEN 默认值", "改为必须从环境变量读取，不设默认"],
    ["console/app/main.py", "MCP / 音乐服务的内网 IP 默认值", "移入 .env.example，实际值不入库"],
    ["start-console.ps1 等脚本", "控制台密码明文", "改为读 .env，脚本内只留占位符"],
], widths=[5.0, 6.0, 5.8])

heading(doc, "3.5 语音服务端不应入库", level=2)
para(doc, "voice-server 是上游 xiaozhi-esp32-server 的完整克隆，另含 893 MB 的 ASR 模型权重。"
          "建议作为外部依赖处理：文档给出仓库地址、需下载的模型，以及我方对上游做的三处本地修改，"
          "用 patch 形式提交：")
table(doc, [
    ["修改点", "原因"],
    ["logger 的 enqueue 改为 False", "本机环境不支持命名管道"],
    ["onnxruntime 降到 1.18.1", "1.23 在 Windows 上 DLL 初始化失败"],
    ["audio_bytes_to_data 改用 ffmpeg", "缺 ffprobe，pydub 无法读音频"],
], widths=[7.4, 9.4])

heading(doc, "四、建议补充的内容")
table(doc, [
    ["缺的东西", "为什么需要"],
    [".gitignore 模板", "我方三个目录目前都没有 gitignore，一提交就会带上 .venv、data/、.mscache"],
    ["大文件政策", "固件 bin、模型权重是否走 Git LFS 或 Releases"],
    ["自测命令", "PR 要求写「测试方式」，但没有统一标准，建议固定成几个脚本"],
    ["PR 模板", "接口变更如何描述、影响哪些模块"],
    ["分支命名规范", "目前只有一个 feature/memory-kb 示例"],
    ["回滚流程", "合并后发现问题如何处置"],
], widths=[4.6, 12.2])

heading(doc, "五、我方准备提交的内容与体积")
table(doc, [
    ["目录", "文件数（排除虚拟环境）", "体积"],
    ["console/", "17", "0.8 MB"],
    ["kb-service/", "22", "1.0 MB"],
    ["services/music-mcp/", "3", "不足 0.1 MB"],
    ["firmware/boards/", "约 10", "不足 0.1 MB"],
], widths=[5.4, 6.0, 5.4])

para(doc, "总体很小，适合直接走 Git；需要排除的只有数据目录与虚拟环境。")

heading(doc, "六、建议的 .gitignore")
code(doc, """
# 虚拟环境
.venv/
node_modules/

# 运行时数据
data/
*.db
*.db-wal
*.db-shm
*.log
tmp/

# 模型与缓存
models/
.mscache/
.hfhome/
.piptmp/

# 固件构建产物
build/
managed_components/
*.bin

# 密钥
.env
*.pem
""")

heading(doc, "七、需要成员 A 确认的三件事")
table(doc, [
    ["序号", "事项", "我方建议"],
    ["1", "GitHub 访问方案选 A / B / C 哪个", "先 B 交付，再 A 建镜像"],
    ["2", "仓库名最终用哪个", "xiaohui-ai（与「小慧」一致）"],
    ["3", "固件是否接受「只提交板级代码 + 补丁」", "接受，避免 1.1 GB 入库与许可证问题"],
], widths=[1.4, 8.0, 7.4])

heading(doc, "八、我方可立即执行的动作")

para(doc, "确认方案后，我方可在当天完成：")
table(doc, [
    ["步骤", "内容"],
    ["1", "按上表生成 .gitignore"],
    ["2", "本地 git init，按 console / kb-service / services / firmware 组织提交"],
    ["3", "导出 xiaohui-member-b.bundle（含完整提交历史）"],
    ["4", "补 README：目录结构、启动方式、依赖的外部服务"],
], widths=[1.4, 15.4])

para(doc, "")
para(doc, "拿到 bundle 后，成员 A 侧只需要：", bold=True)
code(doc, """
git clone xiaohui-member-b.bundle xiaohui-ai
cd xiaohui-ai
git remote add origin https://github.com/<owner>/xiaohui-ai.git
git push -u origin main
""")

para(doc, "")
para(doc, "以上。文档主干没有问题，主要是通路和固件目录结构需要对齐。", bold=True)

doc.save(OUT)
print("saved:", OUT)
