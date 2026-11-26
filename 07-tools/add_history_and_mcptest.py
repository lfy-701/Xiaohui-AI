"""控制台增强：配置变更历史/回滚 + MCP 工具测试按钮。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console")
DB = CON / "app" / "db.py"
M = CON / "app" / "main.py"
H = CON / "static" / "index.html"

# ---------------- 1) db.py ----------------
d = DB.read_text(encoding="utf-8")
if "config_history" not in d:
    d = d.rstrip() + '''


def init_config_history() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at REAL NOT NULL,
                agent_id TEXT,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                source TEXT
            )
            """
        )


def add_config_history(agent_id: str, field: str, old: str, new: str,
                       source: str = "console") -> None:
    import time

    init_config_history()
    with db() as conn:
        conn.execute(
            "INSERT INTO config_history (at, agent_id, field, old_value, new_value, source)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), agent_id, field, old, new, source),
        )


def list_config_history(limit: int = 50) -> list:
    init_config_history()
    with db() as conn:
        rows = conn.execute(
            "SELECT id, at, agent_id, field, old_value, new_value, source"
            " FROM config_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_config_history(hid: int):
    init_config_history()
    with db() as conn:
        row = conn.execute(
            "SELECT id, at, agent_id, field, old_value, new_value, source"
            " FROM config_history WHERE id=?", (hid,)
        ).fetchone()
    return dict(row) if row else None
'''
    DB.write_text(d, encoding="utf-8")
    print("db.py: 已加 config_history")

# ---------------- 2) main.py ----------------
m = M.read_text(encoding="utf-8")

# 2.1 记录变更：放在 update_agent 里
old_fn = '''def api_update_agent(agent_id: str, body: AgentIn):
    # 模型为空时保留原值，避免界面误存把配置清空
    _body = body.model_dump()
    _cur = store.get_agent(agent_id)'''
new_fn = '''def api_update_agent(agent_id: str, body: AgentIn):
    # 模型为空时保留原值，避免界面误存把配置清空
    _body = body.model_dump()
    _cur = store.get_agent(agent_id)'''

if "add_config_history" not in m:
    # 插入记录逻辑：在 a = store.update_agent(...) 之后
    anchor = '''    a = store.update_agent(agent_id, _body)'''
    inject = '''    a = store.update_agent(agent_id, _body)
    # 记录配置变更，支持回滚
    try:
        _watched = ("persona", "model", "voice", "wake_word", "temperature",
                    "kb_enabled", "kb_topk", "memory_enabled")
        for _f in _watched:
            if _f not in _body:
                continue
            _old = (_cur or {}).get(_f)
            _new = _body.get(_f)
            if _old != _new:
                store.add_config_history(agent_id, _f,
                                         "" if _old is None else str(_old),
                                         "" if _new is None else str(_new))
    except Exception:
        pass'''
    if anchor in m:
        m = m.replace(anchor, inject, 1)
        print("main.py: 已加变更记录")

    # 2.2 历史与回滚接口
    extra = '''


@app.get("/api/config/history")
def api_config_history(limit: int = 50):
    return {"history": store.list_config_history(limit)}


class RollbackIn(BaseModel):
    id: int


@app.post("/api/config/rollback")
def api_config_rollback(body: RollbackIn):
    h = store.get_config_history(body.id)
    if not h:
        raise HTTPException(404, "记录不存在")
    agent_id = h.get("agent_id")
    a = store.get_agent(agent_id) if agent_id else None
    if not a:
        raise HTTPException(404, "智能体不存在")
    field = h.get("field")
    old = h.get("old_value")
    if field == "temperature":
        try:
            old = float(old or 0)
        except Exception:
            old = 0.0
    elif field in ("kb_enabled", "memory_enabled"):
        old = str(old).lower() in ("1", "true", "yes")
    elif field == "kb_topk":
        try:
            old = int(old or 3)
        except Exception:
            old = 3
    payload = {k: a.get(k) for k in ("name", "persona", "model", "voice", "wake_word",
                                      "kb_enabled", "kb_topk", "memory_enabled",
                                      "temperature")}
    payload[field] = old
    try:
        inst = AgentIn(**payload)
    except Exception:
        inst = AgentIn()
    api_update_agent(agent_id, inst)
    store.add_config_history(agent_id, field, str(a.get(field)), str(old), source="rollback")
    return {"ok": True, "field": field, "value": old}
'''
    if "/api/config/history" not in m:
        m = m.rstrip() + extra
        print("main.py: 已加历史与回滚接口")

    M.write_text(m, encoding="utf-8")
    ast.parse(m)
    print("main.py 语法 OK")
else:
    print("main.py: 已存在")

# ---------------- 3) 前端 ----------------
h = H.read_text(encoding="utf-8")

if "cfgHistory" not in h:
    # 3.1 配置页底部加「最近修改」卡片
    anchor = '<div class="cfg-actions">'
    card = '''      <div class="card" id="cfgHistoryCard" style="margin-top:16px">
        <div class="row" style="justify-content:space-between;align-items:center">
          <b>最近修改</b>
          <span class="hint">点「恢复」可回滚到修改前的值</span>
          <button type="button" onclick="loadCfgHistory()" style="font-size:12px;padding:4px 10px">刷新</button>
        </div>
        <div id="cfgHistory" style="margin-top:8px"><div class="hint">加载中…</div></div>
      </div>

'''
    if anchor in h:
        h = h.replace(anchor, card + anchor, 1)

    # 3.2 JS
    js = '''
  async function loadCfgHistory() {
    const box = document.getElementById('cfgHistory');
    if (!box) return;
    try {
      const d = await api('/api/config/history?limit=20');
      const list = d.history || [];
      if (!list.length) { box.innerHTML = '<div class="hint">还没有修改记录</div>'; return; }
      const names = {persona:'角色设定', model:'模型', voice:'音色', wake_word:'唤醒词',
                     temperature:'温度', kb_enabled:'知识库', kb_topk:'检索条数', memory_enabled:'记忆'};
      box.innerHTML = list.map(x => {
        const t = new Date(x.at * 1000).toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
        const oldV = String(x.old_value || '').slice(0, 40).replace(/</g,'&lt;');
        const newV = String(x.new_value || '').slice(0, 40).replace(/</g,'&lt;');
        return `<div style="display:flex;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line-soft,#eaf1fa)">
          <span class="hint" style="flex:0 0 96px">${t}</span>
          <span style="flex:0 0 84px">${names[x.field] || x.field}</span>
          <span class="hint" style="flex:1;overflow:hidden;text-overflow:ellipsis">${oldV} → ${newV}</span>
          <button type="button" onclick="rollbackCfg(${x.id})" style="font-size:11.5px;padding:3px 9px">恢复</button>
        </div>`;
      }).join('');
    } catch (e) {
      box.innerHTML = '<div class="hint">加载失败：' + e.message + '</div>';
    }
  }

  async function rollbackCfg(id) {
    if (!confirm('恢复到这条记录修改前的值？')) return;
    try {
      const r = await fetch('/api/config/rollback', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || '回滚失败');
      if (window.xhToast) xhToast('已恢复 ' + d.field, 'ok');
      loadCfgHistory();
      if (typeof loadAgent === 'function') loadAgent();
    } catch (e) { alert('回滚失败：' + e.message); }
  }
  window.loadCfgHistory = loadCfgHistory;
  window.rollbackCfg = rollbackCfg;
'''
    h = h.replace("</script>", js + "\n</script>", 1)

    # 切到配置页时加载
    if "loadCfgHistory()" in h and "if (t === 'config')" in h:
        h = h.replace("if (t === 'config') {", "if (t === 'config') {\n      setTimeout(loadCfgHistory, 120);", 1)

    H.write_text(h, encoding="utf-8")
    print("index.html: 已加最近修改卡片")

# 3.3 MCP 工具测试按钮
h = H.read_text(encoding="utf-8")
if "mcpTestTool" not in h:
    old_card = '''          <div class="hint">${escapeHtml(t.description || '')}</div>'''
    new_card = '''          <div class="hint">${escapeHtml(t.description || '')}</div>
          <div style="margin-top:6px"><button type="button" style="font-size:11.5px;padding:3px 9px"
            onclick="mcpTestTool('${t.name}')">测试</button></div>'''
    if old_card in h:
        h = h.replace(old_card, new_card, 1)

    js2 = '''
  async function mcpTestTool(name) {
    let raw = prompt('输入参数 JSON（没有参数就留空）', '{}');
    if (raw === null) return;
    let args = {};
    try { args = raw.trim() ? JSON.parse(raw) : {}; }
    catch (e) { alert('参数不是合法 JSON'); return; }
    const t0 = performance.now();
    try {
      const r = await fetch('/api/mcp/tools/' + encodeURIComponent(name) + '/test', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({arguments: args})
      });
      const ms = Math.round(performance.now() - t0);
      const d = await r.json().catch(() => ({raw: '非 JSON 响应'}));
      alert(name + ' → ' + r.status + ' (' + ms + 'ms)\\n\\n' + JSON.stringify(d).slice(0, 900));
    } catch (e) {
      alert(name + ' 调用失败：' + e.message);
    }
  }
  window.mcpTestTool = mcpTestTool;
'''
    h = h.replace("</script>", js2 + "\n</script>", 1)
    H.write_text(h, encoding="utf-8")
    print("index.html: 已加 MCP 测试按钮")
