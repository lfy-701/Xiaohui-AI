"""生成《成员 A 模型服务接入指南》docx。"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

OUT = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\成员A模型服务接入指南.docx"

ACCENT = RGBColor(0x1B, 0x6F, 0xC4)
GREY = RGBColor(0x66, 0x66, 0x66)


def set_font(run, name="微软雅黑", size=10.5, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def para(doc, text, size=10.5, bold=False, color=None, space_after=6, align=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
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
    return t


doc = Document()
sec = doc.sections[0]
sec.left_margin = Cm(2.2)
sec.right_margin = Cm(2.2)

# ---------------- 标题 ----------------
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
tr = title.add_run("成员 A 模型服务接入指南")
set_font(tr, size=22, bold=True, color=ACCENT)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("xiaohui.me 控制台联调 · 2026 年 11 月 8 日")
set_font(sr, size=10.5, color=GREY)

doc.add_paragraph()

table(doc, [
    ["项目", "内容"],
    ["接收人", "成员 A"],
    ["发送人", "成员 B"],
    ["文档用途", "说明模型服务侧需要完成的三步操作、接口契约与验收方法"],
    ["当前状态", "控制台已配置完成，仅等待模型服务在 Tailscale 地址上可达"],
], widths=[3.2, 12.0])

# ---------------- 一 ----------------
heading(doc, "一、现在的情况")
para(doc, "控制台这一侧已经按你上一份建议全部改完并自测通过，配置如下：")
code(doc, """
LLM_PROVIDER = openai
LLM_CHAT_URL = http://<本地模型服务器IP>:8000/v1/chat/completions
智能体模型   = qwen2.5:3b
请求超时     = 120 秒
""")
para(doc, "控制台当前自检结果：")
code(doc, """
provider : openai
online   : false
hint     : 连不上 http://<本地模型服务器IP>:8000/v1/models: ConnectTimeout
""")
para(doc, "也就是说：控制台侧不需要再改任何东西，唯一阻塞点是你的服务还没监听在 Tailscale 地址上。"
          "你完成下面三步，我这边刷新页面就能看到模型。", bold=False)

# ---------------- 二 ----------------
heading(doc, "二、你需要做的三步")

heading(doc, "第 1 步：让服务监听 Tailscale 地址", level=2)
para(doc, "你的服务现在只在 127.0.0.1:8000 上，那个地址只对你本机有效。必须改成监听全部网卡，"
          "或者直接监听 <本地模型服务器IP>。三种常见情况：")
table(doc, [
    ["你的服务", "怎么改", "验证命令"],
    ["uvicorn / FastAPI", "--host 0.0.0.0 --port 8000", "curl http://<本地模型服务器IP>:8000/v1/models"],
    ["Ollama", "set OLLAMA_HOST=0.0.0.0:11434 后重启", "curl http://<本地模型服务器IP>:11434/api/tags"],
    ["自己写的 Python", "app.run(host=\"0.0.0.0\", port=8000)", "curl http://<本地模型服务器IP>:8000/v1/models"],
], widths=[3.6, 7.0, 5.2])
para(doc, "注意：绑定 0.0.0.0 意味着所有网卡都能访问，所以第 2 步的防火墙限制是必须的，不是可选项。",
     color=RGBColor(0xC0, 0x39, 0x2B))

heading(doc, "第 2 步：防火墙只放通 Tailscale 网段", level=2)
para(doc, "以管理员身份打开 PowerShell，整条复制执行（显示上可能折行，实际是一行）：")
code(doc, """
netsh advfirewall firewall add rule name="llm-8000-tailnet" dir=in action=allow protocol=TCP localport=8000 remoteip=100.64.0.0/10
""")
para(doc, "如果嫌命令长，也可以在「高级安全 Windows 防火墙 → 入站规则 → 新建规则」里手动加："
          "端口 TCP 8000，作用域远程 IP 填 100.64.0.0/10，动作允许。")
para(doc, "这条规则只允许 Tailscale 网段（100.64.0.0/10）访问 8000 端口，"
          "公网和普通局域网都访问不到。如果你还需要本机调试，可以再加一条 localport=8000 的本地规则，"
          "但绝对不要对 remoteip=any 放行。")

heading(doc, "第 3 步：自测并通知我", level=2)
para(doc, "在你自己的机器上执行，确认两个地址都能通：")
code(doc, """
# 1) 本机回环（验证服务本身正常）
curl http://127.0.0.1:8000/v1/models

# 2) Tailscale 地址（验证绑定成功）
curl http://<本地模型服务器IP>:8000/v1/models
""")
para(doc, "两条都应该返回包含 qwen2.5:3b 的模型列表。第 2 条不通就是没绑定成功，"
          "回去检查第 1 步和防火墙。")
para(doc, "通了之后告诉我，我立即跑真实联调。")

# ---------------- 三 ----------------
heading(doc, "三、接口契约（必须对齐的部分）")
para(doc, "我只依赖下面两个端点，字段名按标准 OpenAI 格式。如果你的实现有差异，请提前说明，我来适配。")

heading(doc, "3.1 模型列表", level=2)
code(doc, """
GET /v1/models

响应 200：
{
  "object": "list",
  "data": [
    {"id": "qwen2.5:3b", "object": "model"}
  ]
}
""")
para(doc, "关键点：id 必须是 qwen2.5:3b，和控制台智能体配置的模型名完全一致，否则会报模型不存在。")

heading(doc, "3.2 对话（非流式）", level=2)
code(doc, """
POST /v1/chat/completions

请求：
{
  "model": "qwen2.5:3b",
  "messages": [
    {"role": "system", "content": "角色设定 + 用户画像 + 知识片段"},
    {"role": "user", "content": "上一轮问题"},
    {"role": "assistant", "content": "上一轮回答"},
    {"role": "user", "content": "本轮问题"}
  ],
  "temperature": 0.7,
  "stream": false
}

响应 200：
{
  "id": "chatcmpl-xxx",
  "model": "qwen2.5:3b",
  "choices": [
    {"index": 0,
     "message": {"role": "assistant", "content": "回答文本"},
     "finish_reason": "stop"}
  ]
}
""")
para(doc, "说明：messages 里已经有完整的多轮历史和 system 上下文，你直接透传给模型即可，不需要再做拼接。")

heading(doc, "3.3 对话（流式）", level=2)
para(doc, "请求同上，把 stream 设为 true，响应改为 SSE：")
code(doc, """
Content-Type: text/event-stream

data: {"choices":[{"index":0,"delta":{"content":"你"},"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
""")
para(doc, "我只解析 choices[0].delta.content 和结束标记 [DONE]。如果你的服务忽略了 stream 参数、"
          "直接返回整段 JSON，控制台也能兼容（会自动回退成非流式），只是没有打字机效果。")

heading(doc, "3.4 错误返回", level=2)
code(doc, """
HTTP 404
{"error": {"message": "model 'xxx' not found", "type": "invalid_request_error"}}
""")
para(doc, "控制台会把 HTTP 状态码和错误信息原样显示在界面上，方便定位问题。"
          "请不要在出错时返回 200 + 空内容，那样我看不出问题在哪。")

# ---------------- 四 ----------------
heading(doc, "四、联调验收清单")
para(doc, "你绑定好之后，我会按下面这张表逐项验证，结果实时同步给你。")
table(doc, [
    ["序号", "检查项", "通过条件", "负责方"],
    ["1", "网络可达", "控制台节点能访问 http://<本地模型服务器IP>:8000/v1/models", "A"],
    ["2", "Provider", "/api/models 返回 provider=openai 且 online=true", "B"],
    ["3", "模型列表", "返回列表包含 qwen2.5:3b", "两者"],
    ["4", "普通对话", "控制台出现真实回复，不再是「未接入模型」", "两者"],
    ["5", "多轮上下文", "连续两轮，第二轮能引用第一轮内容", "两者"],
    ["6", "流式输出", "控制台收到 SSE 分块，以 [DONE] 结束", "两者"],
    ["7", "错误处理", "模型不存在时显示明确错误，不是静默失败", "两者"],
    ["8", "超时保护", "服务无响应时 120 秒内返回超时提示，不卡死", "B"],
], widths=[1.4, 3.0, 9.4, 1.8])

# ---------------- 五 ----------------
heading(doc, "五、常见问题")

faq = [
    ("控制台一直显示 online=false",
     "控制台节点访问不到你的地址。先在你本机 curl <本地模型服务器IP>:8000 试，不通就是没绑定或防火墙拦了。"),
    ("报 model 'xxx' not found",
     "控制台配置的模型名和你 /v1/models 返回的 id 不一致。两边都必须是 qwen2.5:3b。"),
    ("有回复但流式没效果",
     "你的服务可能忽略了 stream 参数。控制台会回退成非流式，功能正常但没打字机效果，"
     "可以在日志里确认是否收到 text/event-stream。"),
    ("一切正常但很慢",
     "3B 模型首次加载会慢一些，之后正常。超过 120 秒控制台会主动断开并提示超时。"),
    ("Windows 防火墙改完还是不生效",
     "规则生效需要对端重新发起连接。让控制台刷新页面重试，或者重启一次你的服务。"),
]
for q, a in faq:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Q：" + q)
    set_font(r, bold=True, size=10)
    para(doc, "A：" + a, size=10, color=GREY, space_after=8)

# ---------------- 六 ----------------
heading(doc, "六、附：一键自检脚本")
para(doc, "把下面内容存成 check_llm.ps1，在你电脑上运行，三项全绿再通知我。")
code(doc, """
$base = "http://<本地模型服务器IP>:8000"

Write-Host "1) 本机回环"
try {
  $r = Invoke-RestMethod "$base/v1/models" -TimeoutSec 5
  Write-Host "   模型: " ($r.data.id -join ", ") -ForegroundColor Green
} catch { Write-Host "   失败: $_" -ForegroundColor Red }

Write-Host "2) 推理测试"
try {
  $body = @{ model="qwen2.5:3b"; messages=@(@{role="user";content="你好"}) } | ConvertTo-Json -Depth 5
  $r2 = Invoke-RestMethod "$base/v1/chat/completions" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
  Write-Host "   回复: " $r2.choices[0].message.content -ForegroundColor Green
} catch { Write-Host "   失败: $_" -ForegroundColor Red }

Write-Host "3) 防火墙规则"
netsh advfirewall firewall show rule name="llm-8000-tailnet" |
  Select-String "已启用|Enabled|本地端口|LocalPort" | ForEach-Object { $_.Line.Trim() }
""")

doc.add_paragraph()
para(doc, "以上。你三步做完告诉我，我这边不用改配置、不用重启，刷新就能联调。", bold=True)

doc.save(OUT)
print("saved:", OUT)
