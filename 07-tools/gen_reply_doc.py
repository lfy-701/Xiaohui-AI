"""生成《成员 B 排查结果回填》docx。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\成员B排查结果回填.docx"

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


def table(doc, rows, widths=None, header=True):
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
            set_font(r, size=9.5, bold=(header and i == 0))
            if header and i == 0:
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
tr = title.add_run("成员 B 排查结果回填")
set_font(tr, size=22, bold=True, color=ACCENT)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("回复《成员 B 控制台连接模型服务待办事项》 · 2026-11-08 19:01")
set_font(sr, size=10.5, color=GREY)

doc.add_paragraph()

# ---------------- 一、结论先行 ----------------
heading(doc, "一、结论先行")
para(doc, "你的服务本身没有问题，问题出在两个 Tailscale 节点之间没有互通路径。", bold=True)
para(doc, "判断依据：我对 <本地模型服务器IP> 的 8000、443、22 三个端口做了 TCP 测试，全部超时。"
          "如果是你的 Windows 防火墙在拒绝，表现应该是「连接被拒绝」（立刻返回 RST），"
          "而不是超时。三个端口一致地丢包，说明数据包在到达你的机器之前就被丢弃了。")
para(doc, "所以不需要再改你的 8000 端口规则，也不需要改模型名。")

# ---------------- 二、回填表 ----------------
heading(doc, "二、检查结果回填")

table(doc, [
    ["检查项", "通过/失败", "实际输出或备注"],
    ["Windows 主机 Test-NetConnection", "失败",
     "RemoteAddress=<本地模型服务器IP>  PingSucceeded=False  TcpTestSucceeded=False"],
    ["Windows 主机 curl /v1/models", "失败",
     "HTTP 000 in 10.016879s；curl: (28) Connection timed out after 10007 milliseconds"],
    ["Windows 主机 tailscale ping", "无法执行",
     "tailscale CLI 需要管理员权限，当前会话访问本地 API 被拒：Access is denied "
     "(\\\\.\\pipe\\ProtectedPrefix\\Administrators\\Tailscale\\tailscaled)。需要用管理员 PowerShell 补测。"],
    ["控制台后端所在环境", "Windows 原生",
     "非 Docker、非 WSL。进程为 D:\\Anaconda3\\python.exe（venv 基于 Anaconda），"
     "uvicorn 直接监听 0.0.0.0:80，PID 30688。"],
    ["后端环境内 TCP 8000", "失败",
     "用后端同一个解释器直连：TimeoutError: timed out（8.01 秒）"],
    ["后端环境内 /v1/models", "失败",
     "ConnectTimeout: timed out（10.17 秒）"],
    ["Tailscale 策略已核对", "待确认",
     "本机节点 node.tail1fbce5.ts.net / 100.100.221.34，Tailscale 网卡正常挂载。"
     "无法读取 peer 列表（CLI 需管理员），需要确认 marks 是否在同一个 tailnet。"],
    ["控制台 online 状态", "失败",
     "provider=openai，online=false，hint=连不上 http://<本地模型服务器IP>:8000/v1/models：ConnectTimeout"],
    ["普通对话", "未执行", "依赖模型连通，前置未通过"],
    ["多轮对话", "未执行", "同上"],
    ["流式输出", "未执行", "同上"],
], widths=[4.6, 2.4, 9.8])

doc.add_paragraph()
para(doc, "补充证据：多端口对照测试", bold=True)
table(doc, [
    ["目标端口", "结果", "说明"],
    ["TCP 8000", "超时", "你的模型服务"],
    ["TCP 443", "超时", "任意端口都一样"],
    ["TCP 22", "超时", "说明不是端口级拦截，而是节点级不可达"],
], widths=[3.4, 3.0, 10.4])

# ---------------- 三、原因分析 ----------------
heading(doc, "三、最可能的原因：不在同一个 tailnet")
para(doc, "Tailscale 有两种「拉通」方式，效果完全不同：")
table(doc, [
    ["方式", "效果", "适用"],
    ["同一 tailnet 内的两台设备", "默认双向互通，谁都能访问谁", "我们现在需要的"],
    ["共享单台设备（Share）", "只有被共享方能访问共享方，反向不通", "给别人用我的服务，不需要我访问他"],
], widths=[4.6, 7.2, 5.0])
para(doc, "现在的情况符合第二种：你能访问我的控制台（我这边之前验证过，你那边能打开），"
          "但我反方向访问你的 8000 端口不通。这正是单向共享的表现。", bold=False)
para(doc, "如果确实如此，解决办法是把双方放进同一个 tailnet：由一方在 "
          "admin 控制台 Invite external user 里发出邀请，另一方接受；"
          "或者双方用同一个账号登录。而不是继续用 Share。", color=RED)

# ---------------- 四、需要你确认 ----------------
heading(doc, "四、需要你在你那侧确认的两件事")
para(doc, "这两条能直接证实或排除上面的判断：")
code(doc, """
# 1) 你的节点列表里有没有我
tailscale status

# 2) 你能不能反向连上我
tailscale ping 100.100.221.34
""")
para(doc, "如果 tailscale status 里看不到 node.tail1fbce5.ts.net 或 100.100.221.34，"
          "就是不同 tailnet，按第三节处理。")
para(doc, "如果能看到、tailscale ping 也通，但 TCP 8000 仍然不行，那就转去查 ACL 的 "
          "B→A 方向授权，把 autogroup 或具体节点间的权限贴出来。")

# ---------------- 五、我这边继续做 ----------------
heading(doc, "五、我这边同步进行")
para(doc, "我会用管理员权限执行 tailscale status，把完整的 peer 列表和我节点的在线状态发你。"
          "如果确认在同一个 tailnet 而仍然不通，我会把 tailscaled 的 netcheck 结果也一并提供。")
para(doc, "在问题定位清楚之前，我这边不改任何配置——避免把变量搅在一起。")

# ---------------- 六、控制台状态 ----------------
heading(doc, "六、控制台当前状态（供你对照日志时间点）")
table(doc, [
    ["项", "值"],
    ["检查时间", "2026-11-08 19:01:09（GMT+8）"],
    ["控制台监听", "0.0.0.0:80"],
    ["模型 Provider", "openai"],
    ["请求地址", "http://<本地模型服务器IP>:8000/v1/chat/completions"],
    ["online", "false"],
    ["hint", "连不上 http://<本地模型服务器IP>:8000/v1/models：ConnectTimeout: timed out"],
    ["智能体模型", "qwen2.5:3b"],
], widths=[4.2, 12.6])

para(doc, "")
para(doc, "以上。等你确认 tailnet 归属，我这边随时配合复测。", bold=True)

doc.save(OUT)
print("saved:", OUT)
