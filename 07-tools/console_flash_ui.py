"""在控制台「固件」页加入在线烧录面板。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = P.read_text(encoding="utf-8")

if "flashPanel" in t:
    print("已存在烧录面板")
    sys.exit(0)

# ---------- 1) 页面结构 ----------
PANEL = '''
    <section id="tab-fw-flash" style="display:none">
      <div class="card">
        <div class="row" style="flex-wrap:wrap;gap:10px;align-items:center">
          <b>在线烧录（USB）</b>
          <span class="hint">把设备插到本机 USB，选串口和固件即可烧录</span>
        </div>
        <div class="row" style="flex-wrap:wrap;gap:10px;margin-top:12px;align-items:center">
          <label>串口</label>
          <select id="flashPort" style="width:220px"></select>
          <button onclick="flashLoadPorts()">刷新串口</button>
          <label>固件</label>
          <select id="flashImage" style="width:280px"></select>
          <button class="primary" id="flashBtn" onclick="flashStart()">开始烧录</button>
          <span class="hint" id="flashMsg"></span>
        </div>
        <pre id="flashLog" style="margin-top:12px;max-height:320px;overflow:auto;background:#0b1020;color:#9fe8b0;padding:10px;border-radius:8px;font-size:12px;line-height:1.5">等待开始…</pre>
        <p class="hint" style="margin:10px 0 0">
          烧录用 <code>merged-binary.bin</code> 整片写入（从 0x0），约 60~90 秒。
          烧录时不要拔线；烧完设备会自动重启。
        </p>
      </div>
    </section>
'''

anchor = '    <section id="tab-mcp" style="display:none">'
if anchor in t:
    t = t.replace(anchor, PANEL + "\n" + anchor, 1)

# ---------- 2) 导航把「固件」改到该页 ----------
t = t.replace(
    '<div class="tab" data-tab="fw" onclick="switchTab(\'fw\')">固件</div>',
    '<div class="tab" data-tab="fw" onclick="switchTab(\'fw\')">固件</div>',
    1,
)

# ---------- 3) JS ----------
JS = '''
// ---------------- 在线烧录 ----------------
var flashTimer = null;

async function flashLoadPorts() {
  try {
    var r = await fetch('/api/firmware/ports');
    var d = await r.json();
    var sel = document.getElementById('flashPort');
    sel.innerHTML = (d.ports || []).map(function (p) {
      return '<option value="' + p.port + '">' + p.port + ' · ' + (p.desc || '') + '</option>';
    }).join('') || '<option value="">未检测到串口</option>';
    if (!d.esptool) document.getElementById('flashMsg').textContent = '缺少 esptool 环境';

    var r2 = await fetch('/api/firmware/images');
    var d2 = await r2.json();
    var sel2 = document.getElementById('flashImage');
    sel2.innerHTML = (d2.images || []).map(function (f) {
      return '<option value="' + f.name + '">' + f.name + ' (' + f.size_kb + ' KB)</option>';
    }).join('') || '<option value="">没有固件</option>';
  } catch (e) {
    document.getElementById('flashMsg').textContent = '加载失败: ' + e.message;
  }
}

async function flashStart() {
  var port = document.getElementById('flashPort').value;
  var image = document.getElementById('flashImage').value;
  if (!port || !image) { alert('请选择串口和固件'); return; }
  if (!confirm('确认烧录 ' + image + ' 到 ' + port + '？烧录中不要拔线。')) return;

  document.getElementById('flashBtn').disabled = true;
  document.getElementById('flashMsg').textContent = '烧录中…';
  document.getElementById('flashLog').textContent = '正在连接设备…\\n';

  try {
    var r = await fetch('/api/firmware/flash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: port, image: image })
    });
    var d = await r.json();
    if (!d.ok) {
      document.getElementById('flashMsg').textContent = d.error || '启动失败';
      document.getElementById('flashBtn').disabled = false;
      return;
    }
    flashPoll();
  } catch (e) {
    document.getElementById('flashMsg').textContent = '启动失败: ' + e.message;
    document.getElementById('flashBtn').disabled = false;
  }
}

function flashPoll() {
  if (flashTimer) clearInterval(flashTimer);
  flashTimer = setInterval(async function () {
    try {
      var r = await fetch('/api/firmware/flash/status');
      var d = await r.json();
      var box = document.getElementById('flashLog');
      box.textContent = (d.log || []).join('\\n');
      box.scrollTop = box.scrollHeight;
      if (!d.running) {
        clearInterval(flashTimer); flashTimer = null;
        document.getElementById('flashBtn').disabled = false;
        document.getElementById('flashMsg').textContent = d.ok ? '✅ 烧录成功' : '❌ 烧录失败';
      }
    } catch (e) { /* 忽略单次失败 */ }
  }, 800);
}
'''

# 插到「固件」区块 JS 之后
marker = "// ---------------- 固件 ----------------"
if marker in t:
    t = t.replace(marker, JS + "\n" + marker, 1)
else:
    t = t.replace("</script>", JS + "\n</script>", 1)

# ---------- 4) switchTab('fw') 时刷新串口列表 ----------
OLD_SW = "function switchTab(name)"
if OLD_SW in t and "flashLoadPorts()" not in t.split(OLD_SW)[1][:400]:
    t = t.replace(
        "function switchTab(name) {",
        "function switchTab(name) {\n  if (name === 'fw-flash' || name === 'fw') { setTimeout(flashLoadPorts, 100); }",
        1,
    )

# ---------- 5) 固件页加跳转按钮 ----------
t = t.replace(
    '<b>上传固件</b>',
    '<button onclick="switchTab(\'fw-flash\')">进入在线烧录 →</button>\n          <b>上传固件</b>',
    1,
)

P.write_text(t, encoding="utf-8")
print("已加入烧录面板与脚本")
