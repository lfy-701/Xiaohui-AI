"""把「清空记忆」按钮改成「清空聊天记录」。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\db.py")
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")

# ---------- db.py ----------
d = DB.read_text(encoding="utf-8")
if "def clear_all_chats" not in d:
    d = d.rstrip() + '''


def clear_all_chats() -> int:
    with db() as conn:
        cur = conn.execute("DELETE FROM chat_messages")
        return cur.rowcount
'''
    DB.write_text(d, encoding="utf-8")
    print("db.py: 已加 clear_all_chats")

# ---------- main.py ----------
m = M.read_text(encoding="utf-8")
if "/api/chats/clear" not in m:
    m = m.rstrip() + '''


@app.post("/api/chats/clear")
def api_chats_clear():
    n = store.clear_all_chats()
    store.add_log("system", f"清空聊天记录 {n} 条")
    return {"ok": True, "removed": n}
'''
    M.write_text(m, encoding="utf-8")
    print("main.py: 已加 /api/chats/clear")

# ---------- 前端 ----------
h = H.read_text(encoding="utf-8")

h = h.replace('onclick="xhClearMemory()" style="font-size:12px;padding:4px 10px">清空记忆</button>',
              'onclick="xhClearChats()" style="font-size:12px;padding:4px 10px">清空聊天记录</button>')

if "function xhClearChats" not in h:
    js = '''
  window.xhClearChats = async function(){
    if(!confirm('清空全部聊天记录？（不影响记忆条目）')) return;
    try{
      var r = await fetch('/api/chats/clear', {method:'POST'});
      var d = await r.json();
      if(window.xhToast) xhToast('已清空 ' + (d.removed||0) + ' 条', 'ok');
      if(window.xhLoadChats) xhLoadChats();
    }catch(e){ alert('清空失败'); }
  };
'''
    h = h.replace("</script>", js + "\n</script>", 1)

H.write_text(h, encoding="utf-8")
print("index.html: 按钮已改")

ast.parse(M.read_text(encoding="utf-8"))
print("语法 OK")
