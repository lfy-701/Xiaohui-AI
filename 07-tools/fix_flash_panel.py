"""补插烧录面板 + 修正 switchTab 参数名（宽松匹配）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = P.read_text(encoding="utf-8")

# 1) 参数名修正（宽松）
t2 = re.sub(r"if \(name === 'fw-flash' \|\| name === 'fw'\)", "if (t === 'fw-flash' || t === 'fw')", t)
if t2 != t:
    t = t2
    print("已修正参数名")
else:
    t = t.replace("function switchTab(t) {", "function switchTab(t) {\n  if (t === 'fw-flash') { setTimeout(flashLoadPorts, 100); }", 1)
    print("已按新方式插入刷新")

# 2) 插入面板
if 'id="tab-fw-flash"' not in t:
    PANEL = '''    <section id="tab-fw-flash" style="display:none">
      <div class="card">
        <div class="row" style="flex-wrap:wrap;gap:10px;align-items:center">
          <b>在线烧录（USB）</b>
          <span class="hint">设备插本机 USB，选串口和固件即可烧录</span>
        </div>
        <div class="row" style="flex-wrap:wrap;gap:10px;margin-top:12px;align-items:center">
          <label>串口</label>
          <select id="flashPort" style="width:220px"></select>
          <button onclick="flashLoadPorts()">刷新</button>
          <label>固件</label>
          <select id="flashImage" style="width:280px"></select>
          <button class="primary" id="flashBtn" onclick="flashStart()">开始烧录</button>
          <span class="hint" id="flashMsg"></span>
        </div>
        <pre id="flashLog" style="margin-top:12px;max-height:320px;overflow:auto;background:#0b1020;color:#9fe8b0;padding:10px;border-radius:8px;font-size:12px;line-height:1.5">等待开始…</pre>
        <p class="hint" style="margin:10px 0 0">
          用 merged-binary.bin 整片写入（0x0），约 60~90 秒。烧录中不要拔线。
        </p>
      </div>
    </section>

'''
    m = re.search(r'\n(\s*)<section id="tab-mcp"', t)
    if m:
        t = t[:m.start() + 1] + PANEL + t[m.start() + 1:]
        print("已在 tab-mcp 前插入烧录面板")
    else:
        t = t.replace("</main>", PANEL + "</main>", 1)
        print("已在 main 末尾插入烧录面板")

P.write_text(t, encoding="utf-8")
print("校验 tab-fw-flash:", 'id="tab-fw-flash"' in t,
      "| flashStart:", "flashStart" in t)
