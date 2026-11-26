"""默认动作可自定义：点「调」→ 拖滑块实时调到满意 → 保存，之后点该动作就用保存的角度。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "xhTuneAction" in t:
    print("已存在")
    sys.exit(0)

# 1) 给每个默认动作按钮加「调」
old_btns = '''  <div class="acts">
    <button data-a="walk">前进</button>
    <button data-a="back">后退</button>
    <button data-a="left">左转</button>
    <button data-a="right">右转</button>
    <button data-a="sit">坐下</button>
    <button data-a="lie">趴下</button>
    <button data-a="stand">起身</button>
    <button data-a="dance">跳舞</button>
  </div>'''

new_btns = '''  <div class="acts">
    <button data-a="walk">前进</button>
    <button data-a="back">后退</button>
    <button data-a="left">左转</button>
    <button data-a="right">右转</button>
    <button data-a="sit">坐下</button>
    <button data-a="lie">趴下</button>
    <button data-a="stand">起身</button>
    <button data-a="dance">跳舞</button>
  </div>
  <div id="xhTuneBar" style="display:none;margin:6px 0 12px;padding:8px 10px;border:1px solid #cfe3f7;border-radius:8px;background:#f2f8ff">
    <div style="font-size:12.5px;margin-bottom:6px">正在调整「<b id="xhTuneName"></b>」：拖动下面的滑块，角度满意后保存</div>
    <div style="display:flex;gap:6px">
      <button type="button" onclick="xhTuneSave()" style="flex:1;font-size:12px;padding:6px">保存为这个动作</button>
      <button type="button" onclick="xhTuneCancel()" style="font-size:12px;padding:6px">取消</button>
    </div>
  </div>'''

if old_btns in t:
    t = t.replace(old_btns, new_btns, 1)
    print("已加调整栏")
else:
    print("⚠ 动作按钮未匹配")

js = '''
  // ---------------------------------------------------- 默认动作自定义
  window.__xhOverrides = {};   // key -> angles
  window.__xhTune = null;      // 当前正在调整的动作 key

  const XH_ACTION_LABELS = {
    walk: '前进', back: '后退', left: '左转', right: '右转',
    sit: '坐下', lie: '趴下', stand: '起身', dance: '跳舞'
  };

  async function xhLoadOverrides() {
    try {
      const d = await (await fetch('/api/actions')).json();
      const map = {};
      (d.actions || []).forEach(function (a) {
        if (XH_ACTION_LABELS[a.name]) map[a.name] = a.angles;
      });
      window.__xhOverrides = map;
      // 标记哪些已自定义
      document.querySelectorAll('.acts button[data-a]').forEach(function (b) {
        const key = b.dataset.a;
        const base = XH_ACTION_LABELS[key] || key;
        b.textContent = map[key] ? base + ' *' : base;
      });
    } catch (e) {}
  }

  function xhTuneAction(key) {
    window.__xhTune = key;
    const bar = document.getElementById('xhTuneBar');
    const nm = document.getElementById('xhTuneName');
    if (nm) nm.textContent = XH_ACTION_LABELS[key] || key;
    if (bar) bar.style.display = 'block';
    add('▸ 调整「' + (XH_ACTION_LABELS[key] || key) + '」：拖滑块 → 保存', 'sys');
    const box = document.getElementById('xhTuneBar');
    if (box && box.scrollIntoView) box.scrollIntoView({behavior: 'smooth', block: 'center'});
  }

  function xhTuneCancel() {
    window.__xhTune = null;
    const bar = document.getElementById('xhTuneBar');
    if (bar) bar.style.display = 'none';
  }

  async function xhTuneSave() {
    const key = window.__xhTune;
    if (!key) return;
    const angles = window.xhAngles.join(',');
    try {
      const list = (await (await fetch('/api/actions')).json()).actions || [];
      const exist = list.find(function (a) { return a.name === key; });
      if (exist) await fetch('/api/actions/' + exist.id, {method: 'DELETE'});
      const r = await fetch('/api/actions', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: key, angles: angles})
      });
      const d = await r.json();
      if (d.ok || d.id) {
        add('✓ 已保存「' + (XH_ACTION_LABELS[key] || key) + '」：' + angles, 'sys ok');
        xhTuneCancel();
        xhLoadOverrides();
      } else {
        add('✗ 保存失败：' + (d.error || d.detail || ''), 'sys err');
      }
    } catch (e) { add('✗ 保存失败：' + e.message, 'sys err'); }
  }

  // 覆盖点击行为：有自定义就发角度，否则发预置动作
  function xhBindActions() {
    document.querySelectorAll('.acts button[data-a]').forEach(function (b) {
      b.onclick = async function () {
        const key = b.dataset.a;
        const label = XH_ACTION_LABELS[key] || key;
        const angles = window.__xhOverrides[key];
        b.disabled = true;
        add('▸ 指令：' + label + (angles ? '（自定义）' : ''), 'sys');
        try {
          let d = {};
          if (angles) {
            const r = await fetch('/api/device/pose', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({angles: angles})
            });
            d = await r.json();
            d = {ok: d.ok, tip: '已按自定义角度执行'};
          } else {
            const r = await fetch('/api/console/action', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({action: key})
            });
            try { d = await r.json(); } catch (e) {}
          }
          add(d.ok ? ('✓ ' + (d.tip || label)) : ('✗ ' + (d.error || d.detail || '失败')),
              d.ok ? 'sys ok' : 'sys err');
        } catch (e) { add('✗ 网络错误：' + e.message, 'sys err'); }
        finally { b.disabled = false; }
      };
      // 长按 / 右键进入调整
      b.oncontextmenu = function (ev) { ev.preventDefault(); xhTuneAction(b.dataset.a); };
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    xhBindActions();
    xhLoadOverrides();
  });
'''

t = t.replace("</script>", js + "\n</script>", 1)
F.write_text(t, encoding="utf-8")
print("已加入动作自定义逻辑")
