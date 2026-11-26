"""给设定页加「保存 / 取消」操作栏，并让保存状态常显。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

# ---------- 1) 操作栏 HTML（放在试聊之后、section 结束之前） ----------
anchor = '''    <div class="chatbox">
      <input id="chatInput" placeholder="输入一句话，验证知识库/记忆/多轮上下文" onkeydown="if(event.key==='Enter')sendChat()">
      <button class="primary" onclick="sendChat()">发送</button>
      <button onclick="resetChat()">新对话</button>
    </div>
  </section>'''

new_block = '''    <div class="chatbox">
      <input id="chatInput" placeholder="输入一句话，验证知识库/记忆/多轮上下文" onkeydown="if(event.key==='Enter')sendChat()">
      <button class="primary" onclick="sendChat()">发送</button>
      <button onclick="resetChat()">新对话</button>
    </div>

    <div class="cfg-actions">
      <span class="cfg-state" id="saveState">未修改</span>
      <span class="cfg-actions-btns">
        <button onclick="revertConfig()">取消</button>
        <button class="primary" onclick="saveConfigNow()">保存</button>
      </span>
    </div>
  </section>'''

if anchor in t:
    t = t.replace(anchor, new_block, 1)
    print("操作栏已插入")
else:
    print("⚠ 操作栏锚点未匹配")

# ---------- 2) 操作栏样式 ----------
style_anchor = "      .cfg-switch input:checked + .cfg-slider:before { transform:translateX(18px); }"
style_add = style_anchor + """
      .cfg-actions { position:sticky; bottom:0; display:flex; align-items:center;
                     justify-content:space-between; gap:12px; padding:12px 0;
                     background:linear-gradient(to top, #f7f9fc 60%, rgba(247,249,252,0));
                     backdrop-filter:blur(2px); margin-top:8px; }
      .cfg-actions-btns { display:flex; gap:8px; }
      .cfg-state { font-size:12px; color:#8a97a5; }
      .cfg-state.dirty { color:#c47d00; }
      .cfg-state.done { color:#1e8e5a; }"""
if ".cfg-actions {" not in t:
    t = t.replace(style_anchor, style_add, 1)
    print("样式已插入")

# ---------- 3) JS ----------
js_anchor = "function togglePersonaCustom() {"
js_new = '''function setSaveState(text, cls) {
  const el = document.getElementById('saveState');
  if (!el) return;
  el.textContent = text;
  el.className = 'cfg-state' + (cls ? ' ' + cls : '');
}

async function saveConfigNow() {
  if (!current) return;
  clearTimeout(saveTimer);
  try {
    setSaveState('保存中…');
    const data = collect();
    const r = await api('/api/agents/' + current.id, {method: 'PUT', body: JSON.stringify(data)});
    const idx = agents.findIndex(a => a.id === current.id);
    if (idx >= 0) agents[idx] = Object.assign(agents[idx], r);
    current = agents[idx >= 0 ? idx : 0];
    document.getElementById('title').textContent = current.name;
    const t = new Date().toLocaleTimeString('zh-CN', {hour12: false});
    setSaveState('已保存 ' + t, 'done');
    loadAgents();
  } catch (e) {
    setSaveState('保存失败：' + e.message, 'dirty');
  }
}

function revertConfig() {
  if (!current) return;
  clearTimeout(saveTimer);
  selectAgent(current.id);
  setSaveState('已恢复到上次保存的状态', '');
}

function togglePersonaCustom() {'''

if js_anchor in t and "function saveConfigNow" not in t:
    t = t.replace(js_anchor, js_new, 1)
    print("保存函数已插入")
else:
    print("⚠ JS 锚点未匹配或已存在")

# ---------- 4) 自动保存时也给出可见反馈 ----------
old_toast = """      await api('/api/agents/' + current.id, {method: 'PUT', body: JSON.stringify(collect())});
      const s = document.getElementById('saved');"""
new_toast = """      await api('/api/agents/' + current.id, {method: 'PUT', body: JSON.stringify(collect())});
      setSaveState('已自动保存 ' + new Date().toLocaleTimeString('zh-CN', {hour12: false}), 'done');
      const s = document.getElementById('saved');"""
if old_toast in t:
    t = t.replace(old_toast, new_toast, 1)
    print("自动保存反馈已接入")
else:
    print("⚠ 自动保存锚点未匹配")

# ---------- 5) 改字段时标记为「未保存」 ----------
old_collect = "function saveSoon() {\n  if (!current) return;"
new_collect = "function saveSoon() {\n  if (!current) return;\n  setSaveState('修改中…', 'dirty');"
if old_collect in t:
    t = t.replace(old_collect, new_collect, 1)
    print("修改状态提示已接入")

F.write_text(t, encoding="utf-8")

for k in ["cfg-actions", "saveConfigNow", "revertConfig", "setSaveState", "已自动保存"]:
    print(f"  {k:<20} {'OK' if k in t else '缺失'}")
