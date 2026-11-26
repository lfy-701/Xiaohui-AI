"""在 /chat 页面加「动作编排」面板：拖姿态→加步骤→试播→保存。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = P.read_text(encoding="utf-8")

if 'id="seqPanel"' in t:
    print("已存在编排面板")
    raise SystemExit(0)

PANEL = '''
    <h2>动作编排（连续动作）</h2>
    <div id="seqPanel" style="border:1px solid #cfe3f7;border-radius:10px;padding:10px;background:#f7fbff">
      <div style="display:flex;gap:6px;align-items:center;margin-bottom:8px">
        <input id="seqName" placeholder="动作名，例如 我的舞蹈" style="flex:1;padding:6px;border:1px solid #cfe3f7;border-radius:8px">
        <span style="font-size:12px">循环</span>
        <input id="seqLoops" type="number" min="1" max="20" value="3" style="width:56px;padding:6px;border:1px solid #cfe3f7;border-radius:8px">
      </div>
      <div style="display:flex;gap:6px;margin-bottom:8px">
        <button onclick="seqAddStep()" style="flex:1">＋ 添加当前姿态</button>
        <button onclick="seqPlay()">▶ 试播</button>
        <button onclick="seqSave()">💾 保存</button>
      </div>
      <div id="seqSteps" style="font-size:12px;color:#41556b;margin-bottom:8px">还没有步骤</div>
      <div id="seqList" style="font-size:12.5px"></div>
    </div>
'''

anchor = '    <h2>舵机微调</h2>'
if anchor in t:
    t = t.replace(anchor, PANEL + "\n" + anchor, 1)
    print("已插入编排面板")
else:
    print("⚠ 未找到舵机微调锚点")

JS = '''
// ---------------- 动作编排 ----------------
var seqSteps = [];

function seqCurrentAngles() {
  var v = [];
  for (var i = 0; i < 4; i++) {
    var el = document.getElementById('xhr' + i);
    v.push(el ? el.value : '90');
  }
  return v.join(',');
}

function seqRender() {
  var box = document.getElementById('seqSteps');
  if (!seqSteps.length) { box.textContent = '还没有步骤'; return; }
  box.innerHTML = seqSteps.map(function (s, i) {
    return '<div style="display:flex;justify-content:space-between;padding:2px 0">'
      + '<span>步骤' + (i + 1) + '：' + s.angles + ' <b>' + s.ms + 'ms</b></span>'
      + '<a href="javascript:seqDel(' + i + ')" style="color:#c0392b">删除</a></div>';
  }).join('');
}

function seqAddStep() {
  var ms = prompt('这一步持续多少毫秒？（100~1000）', '250');
  if (ms === null) return;
  ms = parseInt(ms, 10);
  if (isNaN(ms) || ms < 50) ms = 250;
  seqSteps.push({ angles: seqCurrentAngles(), ms: Math.min(ms, 3000) });
  seqRender();
}

function seqDel(i) { seqSteps.splice(i, 1); seqRender(); }

async function seqPlay() {
  var name = document.getElementById('seqName').value.trim();
  var steps = seqSteps;
  if (!steps.length) { alert('先添加步骤'); return; }
  if (name) { await seqSave(true); }
  var target = name || '';
  if (!target) { alert('先填动作名再试播'); return; }
  var r = await fetch('/api/actions/sequences/play', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: target })
  });
  var d = await r.json();
  if (!d.ok) alert(d.error || '播放失败');
}

async function seqSave(silent) {
  var name = document.getElementById('seqName').value.trim();
  var loops = parseInt(document.getElementById('seqLoops').value, 10) || 1;
  if (!name) { alert('请输入动作名'); return; }
  if (!seqSteps.length) { alert('先添加步骤'); return; }
  var r = await fetch('/api/actions/sequences', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, steps: seqSteps, loops: loops })
  });
  var d = await r.json();
  if (!d.ok) { alert(d.error || '保存失败'); return; }
  if (!silent) alert('已保存：' + name);
  seqLoadList();
}

async function seqLoadList() {
  try {
    var r = await fetch('/api/actions/sequences');
    var d = await r.json();
    var seqs = d.sequences || {};
    var names = Object.keys(seqs);
    var box = document.getElementById('seqList');
    if (!names.length) { box.innerHTML = '<span style="color:#889">还没有保存的动作</span>'; return; }
    box.innerHTML = names.map(function (n) {
      var s = seqs[n];
      return '<div style="display:flex;justify-content:space-between;padding:3px 0;border-top:1px dashed #dbeafe">'
        + '<span>' + n + '（' + s.steps.length + ' 步 × ' + (s.loops || 1) + '）</span>'
        + '<span><a href="javascript:seqPlayName(\\'' + n + '\\')">播放</a> · '
        + '<a href="javascript:seqDelName(\\'' + n + '\\')" style="color:#c0392b">删除</a></span></div>';
    }).join('');
  } catch (e) { /* ignore */ }
}

async function seqPlayName(name) {
  var r = await fetch('/api/actions/sequences/play', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name })
  });
  var d = await r.json();
  if (!d.ok) alert(d.error || '播放失败');
}

async function seqDelName(name) {
  if (!confirm('删除动作「' + name + '」？')) return;
  await fetch('/api/actions/sequences/' + encodeURIComponent(name), { method: 'DELETE' });
  seqLoadList();
}

setTimeout(seqLoadList, 600);
'''

t = t.replace("</script>", JS + "\n</script>", 1)
P.write_text(t, encoding="utf-8")
print("编排脚本已插入")
