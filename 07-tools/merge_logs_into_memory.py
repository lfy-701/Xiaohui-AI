"""记忆页：并入聊天记录，移除日志页。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\db.py")
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")

# ---------- db.py：最近对话 ----------
d = DB.read_text(encoding="utf-8")
if "def recent_chats" not in d:
    d = d.rstrip() + '''


def recent_chats(limit: int = 200) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role, content, at FROM chat_messages ORDER BY at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_memories() -> int:
    """清空错误记忆（仅清理 memory 表，不动聊天记录）。"""
    with db() as conn:
        try:
            cur = conn.execute("DELETE FROM memories")
            return cur.rowcount
        except Exception:
            return 0
'''
    DB.write_text(d, encoding="utf-8")
    print("db.py: 已加 recent_chats")

# ---------- main.py：接口 ----------
m = M.read_text(encoding="utf-8")
if "/api/chats/recent" not in m:
    m = m.rstrip() + '''


@app.get("/api/chats/recent")
def api_chats_recent(limit: int = 200):
    return {"chats": store.recent_chats(limit)}


@app.post("/api/memory/clear")
def api_memory_clear():
    n = store.clear_memories()
    store.add_log("system", f"清空记忆 {n} 条")
    return {"ok": True, "removed": n}
'''
    M.write_text(m, encoding="utf-8")
    print("main.py: 已加 /api/chats/recent")

# ---------- 前端：合并日志到记忆 ----------
h = H.read_text(encoding="utf-8")
if "xhChatRecs" not in h:
    # 1) 隐藏「日志」标签
    h = h.replace('<span class="tab" data-page="logs">', '<span class="tab" data-page="logs" style="display:none">')
    h = h.replace("<span class=\"tab\" data-page=\"logs\"", "<span class=\"tab\" data-page=\"logs\" style=\"display:none\"")
    # 兼容不同写法
    for pat in ['data-page="logs"', "data-page='logs'"]:
        if pat in h:
            h = h.replace(pat, pat + ' style="display:none"', 1)

    # 2) 记忆页顶部插入聊天记录区
    js = '''
/* ===== 记忆页：聊天记录 + 记忆条目 ===== */
(function(){
  function fmt(t){
    try { var d = new Date(t*1000); return d.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}); }
    catch(e){ return ''; }
  }
  window.xhLoadChats = async function(){
    var box = document.getElementById('xhChatRecs');
    if(!box) return;
    box.innerHTML = '<div class="hint">加载中…</div>';
    try{
      var d = await (await fetch('/api/chats/recent?limit=200')).json();
      var list = (d.chats||[]).slice().reverse();
      if(!list.length){ box.innerHTML = '<div class="empty">还没有聊天记录</div>'; return; }
      box.innerHTML = list.map(function(x){
        var isUser = x.role === 'user';
        return '<div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line-soft,#eaf1fa)">' +
          '<span class="hint" style="flex:0 0 110px">' + fmt(x.at) + '</span>' +
          '<span style="flex:0 0 44px;color:' + (isUser?'#1b6fc4':'#1a8a5c') + '">' + (isUser?'我':'小慧') + '</span>' +
          '<span style="flex:1;word-break:break-word">' + (x.content||'').slice(0,300) + '</span></div>';
      }).join('');
    }catch(e){ box.innerHTML = '<div class="empty">加载失败</div>'; }
  };

  window.xhClearMemory = async function(){
    if(!confirm('清空所有记忆条目？（不影响聊天记录）')) return;
    var r = await fetch('/api/memory/clear', {method:'POST'});
    var d = await r.json();
    if(window.xhToast) xhToast('已清理 ' + (d.removed||0) + ' 条', 'ok');
    setTimeout(function(){ location.reload(); }, 800);
  };

  function mount(){
    var page = document.getElementById('page-memory') || document.getElementById('memory');
    if(!page || document.getElementById('xhChatRecs')) return;
    var wrap = document.createElement('div');
    wrap.className = 'card';
    wrap.style.marginBottom = '16px';
    wrap.innerHTML =
      '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">' +
        '<b>聊天记录</b><span class="hint">最近 200 条</span>' +
        '<span style="flex:1"></span>' +
        '<button type="button" onclick="xhLoadChats()" style="font-size:12px;padding:4px 10px">刷新</button>' +
        '<button type="button" onclick="xhClearMemory()" style="font-size:12px;padding:4px 10px">清空记忆</button>' +
      '</div><div id="xhChatRecs"><div class="hint">加载中…</div></div>';
    page.insertBefore(wrap, page.firstChild);
    window.xhLoadChats();
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ setTimeout(mount, 900); });
  else setTimeout(mount, 900);
  document.addEventListener('click', function(e){
    var t = e.target.closest && e.target.closest('.tab');
    if(t) setTimeout(mount, 300);
  }, true);
})();
'''
    h = h.replace("</body>", "<script>" + js + "</script>\r\n</body>", 1)
    H.write_text(h, encoding="utf-8")
    print("index.html: 已合并聊天记录到记忆页")
else:
    print("index.html: 已存在")

ast.parse(M.read_text(encoding="utf-8"))
print("语法 OK")
