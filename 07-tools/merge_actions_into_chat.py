"""把动作编辑并入 /chat 页面，并移除 /actions 路由。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CHAT = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
MAIN = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
ACT = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\actions.html")

h = CHAT.read_text(encoding="utf-8")

if "xhServo" in h:
    print("chat.html 已合并过")
else:
    # 1) 侧栏加宽
    h = h.replace("aside{width:230px", "aside{width:310px")

    # 2) 在「提示」区块之前插入舵机与灯珠面板
    marker = "    <h2>提示</h2>"
    panel = '''    <h2>舵机微调</h2>
    <div id="xhServos"></div>
    <div style="display:flex;gap:6px;margin:8px 0 16px">
      <input id="xhActName" placeholder="动作名" style="flex:1;min-width:0;font-size:12.5px;padding:7px 10px;border:1px solid #dbe7f5;border-radius:8px;background:#fbfdff;font-family:inherit;outline:none">
      <button type="button" onclick="xhRunPose()" style="padding:7px 10px;font-size:12.5px">执行</button>
      <button type="button" onclick="xhSaveAction()" style="padding:7px 10px;font-size:12.5px">保存</button>
    </div>

    <h2>已保存动作</h2>
    <div id="xhActList" style="margin-bottom:16px"><div class="hint">加载中…</div></div>

    <h2>灯珠</h2>
    <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px">
      <span class="xh-sw" style="background:#ff3b30" onclick="xhLed('255,0,0')"></span>
      <span class="xh-sw" style="background:#34c759" onclick="xhLed('0,255,0')"></span>
      <span class="xh-sw" style="background:#007aff" onclick="xhLed('0,0,255')"></span>
      <span class="xh-sw" style="background:#ffd60a" onclick="xhLed('255,200,0')"></span>
      <span class="xh-sw" style="background:#af52de" onclick="xhLed('180,0,255')"></span>
      <span class="xh-sw" style="background:#f2f2f7" onclick="xhLed('255,255,255')"></span>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:16px">
      <button type="button" onclick="xhLed('rainbow')" style="flex:1;padding:6px;font-size:12px">彩虹</button>
      <button type="button" onclick="xhLed('breathing')" style="flex:1;padding:6px;font-size:12px">呼吸</button>
      <button type="button" onclick="xhLed('off')" style="flex:1;padding:6px;font-size:12px">关灯</button>
    </div>

'''
    if marker in h:
        h = h.replace(marker, panel + marker, 1)
        print("已插入侧栏面板")
    else:
        print("⚠ 侧栏锚点不匹配")

    # 3) 样式
    css = '''<style>
.xh-sw{width:28px;height:28px;border-radius:8px;display:inline-block;cursor:pointer;border:2px solid #fff;box-shadow:0 0 0 1px #dbe7f5;transition:.15s}
.xh-sw:hover{transform:scale(1.08)}
.xh-sv{margin-bottom:10px}
.xh-sv label{display:flex;justify-content:space-between;font-size:12px;color:#5b7590;margin-bottom:4px}
.xh-sv label b{color:#1b6fc4}
.xh-sv input[type=range]{width:100%;height:5px;border-radius:3px;background:#e3eefb;-webkit-appearance:none;outline:none}
.xh-sv input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:15px;height:15px;border-radius:50%;background:#1b6fc4;border:2px solid #fff;box-shadow:0 1px 3px rgba(27,111,196,.4);cursor:pointer}
.xh-act{display:flex;align-items:center;gap:6px;padding:6px 0;border-bottom:1px solid #eaf1fa;font-size:12.5px}
.xh-act .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.xh-act button{padding:3px 8px;font-size:11.5px}
</style>
'''
    h = h.replace("</head>", css + "</head>", 1)

    # 4) 脚本
    js = '''
  // ---------------- 舵机 / 灯珠（并入动作编辑） ----------------
  const XH_SERVO_NAMES = ['左前', '左后', '右前', '右后'];
  let xhAngles = [90, 90, 90, 90];

  function xhRenderServos() {
    const box = document.getElementById('xhServos');
    if (!box) return;
    box.innerHTML = xhAngles.map(function (v, i) {
      return '<div class="xh-sv"><label><span>' + XH_SERVO_NAMES[i] + '</span>' +
             '<b id="xhv' + i + '">' + v + '°</b></label>' +
             '<input type="range" min="0" max="180" value="' + v + '" ' +
             'oninput="xhSlide(' + i + ', this.value)"></div>';
    }).join('');
  }

  function xhSlide(i, v) {
    xhAngles[i] = parseInt(v);
    const el = document.getElementById('xhv' + i);
    if (el) el.textContent = v + '°';
  }

  async function xhRunPose() {
    const r = await fetch('/api/device/pose', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({angles: xhAngles.join(',')})
    });
    const d = await r.json();
    add(d.ok ? ('▸ 姿态：' + d.angles) : ('✗ ' + (d.detail || '下发失败')), d.ok ? 'sys' : 'sys err');
  }

  async function xhSaveAction() {
    const el = document.getElementById('xhActName');
    const name = (el.value || '').trim();
    if (!name) { add('✗ 先填动作名', 'sys err'); return; }
    const r = await fetch('/api/actions', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name, angles: xhAngles.join(',')})
    });
    const d = await r.json();
    if (d.ok) { el.value = ''; add('✓ 已保存「' + name + '」', 'sys ok'); xhLoadActions(); }
    else add('✗ 保存失败', 'sys err');
  }

  async function xhLoadActions() {
    const box = document.getElementById('xhActList');
    if (!box) return;
    try {
      const d = await (await fetch('/api/actions')).json();
      const list = d.actions || [];
      if (!list.length) { box.innerHTML = '<div class="hint">还没有保存的动作</div>'; return; }
      box.innerHTML = list.map(function (a) {
        return '<div class="xh-act"><span class="nm">' + a.name + '</span>' +
               '<span class="hint" style="font-size:11px">' + a.angles + '</span>' +
               '<button type="button" onclick="xhExec(\\'' + a.angles + '\\',\\'' + a.name + '\\')">执行</button>' +
               '<button type="button" onclick="xhDelAction(' + a.id + ')">删</button></div>';
      }).join('');
    } catch (e) {
      box.innerHTML = '<div class="hint">加载失败</div>';
    }
  }

  async function xhExec(angles, name) {
    const r = await fetch('/api/device/pose', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({angles: angles})
    });
    const d = await r.json();
    add(d.ok ? ('▸ 执行「' + name + '」') : '✗ 执行失败', d.ok ? 'sys' : 'sys err');
  }

  async function xhDelAction(id) {
    if (!confirm('删除这个动作？')) return;
    await fetch('/api/actions/' + id, {method: 'DELETE'});
    xhLoadActions();
  }

  async function xhLed(v) {
    const r = await fetch('/api/device/led', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({value: v})
    });
    const d = await r.json();
    add(d.ok ? '▸ 灯效已下发' : '✗ 灯效失败', d.ok ? 'sys' : 'sys err');
  }

  window.xhRunPose = xhRunPose;
  window.xhSaveAction = xhSaveAction;
  window.xhSlide = xhSlide;
  window.xhExec = xhExec;
  window.xhDelAction = xhDelAction;
  window.xhLed = xhLed;

  xhRenderServos();
  xhLoadActions();
'''
    h = h.replace("</script>", js + "\n</script>", 1)

CHAT.write_text(h, encoding="utf-8")
print("chat.html 已合并动作编辑")

# ---------------- 移除 /actions 路由 ----------------
m = MAIN.read_text(encoding="utf-8")
if "/actions" in m:
    start = m.find('@app.get("/actions")')
    if start >= 0:
        end = m.find("@app.", start + 10)
        if end < 0:
            end = len(m)
        m = m[:start] + m[end:]
        MAIN.write_text(m, encoding="utf-8")
        print("已移除 /actions 路由")

if ACT.exists():
    ACT.unlink()
    print("已删除 actions.html")

ast.parse(MAIN.read_text(encoding="utf-8"))
print("语法 OK")
