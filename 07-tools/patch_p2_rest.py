"""P2 收尾：MCP 工具测试面板 · 记忆时间线 · 音乐播放器。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
m = M.read_text(encoding="utf-8")

# ---------- 记忆接口（如果 kb 代理里没有）----------
if "/api/memory/list" not in m:
    extra = '''


@app.get("/api/memory/list")
async def api_memory_list(limit: int = 100):
    """记忆时间线：按时间倒序返回。"""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{KB_URL}/memory/list", params={"limit": limit})
            return r.json()
    except Exception as e:
        return {"items": [], "error": str(e)}
'''
    m = m.rstrip() + extra
    M.write_text(m, encoding="utf-8")
    print("已加 /api/memory/list")
else:
    print("记忆接口已存在")

H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
h = H.read_text(encoding="utf-8")

if "xhMcpTest" in h:
    print("前端已存在")
    sys.exit(0)

js = r'''
/* ===== P2 收尾：MCP 测试 · 记忆时间线 · 音乐播放器 ===== */
(function(){
  // 通用面板容器
  function ensurePanel(id, title, hint){
    let p = document.getElementById(id);
    if(p) return p;
    p = document.createElement('div');
    p.id = id;
    p.className = 'card';
    p.style.marginTop = '16px';
    p.innerHTML = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">' +
      '<b>' + title + '</b><span class="hint">' + (hint||'') + '</span></div><div class="xh-body"></div>';
    return p;
  }

  // ---------- MCP 工具测试 ----------
  window.xhMcpTest = async function(){
    const box = document.getElementById('xh-mcp-body');
    box.innerHTML = '<span class="hint">加载工具列表…</span>';
    try{
      const r = await fetch('/api/mcp/tools');
      const d = await r.json();
      const tools = d.tools || d.items || [];
      if(!tools.length){ box.innerHTML = '<div class="empty">没有可用工具（模型服务可能离线）</div>'; return; }
      box.innerHTML = tools.map(t => {
        const name = t.name || t.id;
        const desc = (t.description || '').slice(0, 90);
        return '<div class="cfg-row" style="align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid var(--line-soft,#eaf1fa)">' +
          '<div style="flex:1"><code>' + name + '</code><div class="hint" style="margin-top:3px">' + desc + '</div></div>' +
          '<button type="button" onclick="xhMcpCall(\'' + name + '\')">测试</button></div>';
      }).join('') + '<pre id="xh-mcp-out" class="hint" style="margin-top:12px;white-space:pre-wrap;font-size:12px"></pre>';
    }catch(e){ box.innerHTML = '<div class="empty">加载失败：' + e.message + '</div>'; }
  };

  window.xhMcpCall = async function(name){
    const out = document.getElementById('xh-mcp-out');
    if(out) out.textContent = '调用 ' + name + ' …';
    try{
      const r = await fetch('/api/mcp/tools/' + encodeURIComponent(name) + '/test', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'
      });
      const d = await r.json();
      if(out) out.textContent = JSON.stringify(d, null, 2).slice(0, 1200);
    }catch(e){ if(out) out.textContent = '失败：' + e.message; }
  };

  // ---------- 记忆时间线 ----------
  window.xhMemoryLoad = async function(){
    const box = document.getElementById('xh-mem-body');
    box.innerHTML = '<span class="hint">加载中…</span>';
    try{
      const r = await fetch('/api/memory/list?limit=100');
      const d = await r.json();
      const items = d.items || d.memories || [];
      if(!items.length){ box.innerHTML = '<div class="empty">还没有记忆</div>'; return; }
      const groups = {};
      items.forEach(it => {
        const ts = (it.created_at || it.time || 0) * (String(it.created_at||it.time||0).length > 11 ? 1 : 1);
        const dt = new Date(ts * 1000);
        const key = isNaN(dt) ? '未知时间' : dt.toLocaleDateString('zh-CN');
        (groups[key] = groups[key] || []).push(it);
      });
      box.innerHTML = Object.keys(groups).map(k =>
        '<div style="margin:8px 0 4px;font-size:12.5px;color:var(--text3,#8ba3ba)">' + k + '</div>' +
        groups[k].map(it => {
          const t = (it.text || it.content || it.value || '').slice(0, 200);
          const tm = it.created_at || it.time;
          const hh = tm ? new Date(tm * 1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}) : '';
          return '<div class="log" style="display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--line-soft,#eaf1fa)">' +
            '<span class="hint" style="flex:0 0 52px">' + hh + '</span>' +
            '<span style="flex:1">' + t + '</span></div>';
        }).join('')
      ).join('');
    }catch(e){ box.innerHTML = '<div class="empty">加载失败：' + e.message + '</div>'; }
  };

  // ---------- 音乐播放器 ----------
  let xhAudio = null, xhQueue = [], xhIdx = 0;
  window.xhMusicPlay = function(track){
    if(!track) return;
    if(!xhAudio){ xhAudio = new Audio(); xhAudio.onended = () => window.xhMusicNext(); }
    const src = '/api/music/local/' + encodeURIComponent(track).replace(/%2F/g,'/');
    xhAudio.src = src;
    xhAudio.play().catch(e => { if(window.xhToast) xhToast('播放失败：' + e.message,'err'); });
    const bar = document.getElementById('xh-music-now');
    if(bar) bar.textContent = '♪ ' + track.split('/').pop();
  };
  window.xhMusicNext = function(){
    if(!xhQueue.length) return;
    xhIdx = (xhIdx + 1) % xhQueue.length;
    window.xhMusicPlay(xhQueue[xhIdx]);
  };
  window.xhMusicPrev = function(){
    if(!xhQueue.length) return;
    xhIdx = (xhIdx - 1 + xhQueue.length) % xhQueue.length;
    window.xhMusicPlay(xhQueue[xhIdx]);
  };
  window.xhMusicStop = function(){
    if(xhAudio){ xhAudio.pause(); xhAudio.currentTime = 0; }
    const bar = document.getElementById('xh-music-now'); if(bar) bar.textContent = '已停止';
  };
  window.xhMusicSearch = async function(){
    const q = (document.getElementById('xh-music-q') || {}).value || '';
    const box = document.getElementById('xh-music-body');
    if(!box) return;
    box.innerHTML = '<span class="hint">搜索中…</span>';
    try{
      const r = await fetch('/api/music/search?q=' + encodeURIComponent(q || '轻音乐'));
      const d = await r.json();
      const list = d.results || d.tracks || [];
      xhQueue = list.map(x => x.name || x.title || '');
      if(!list.length){ box.innerHTML = '<div class="empty">没有结果</div>'; return; }
      box.innerHTML = list.slice(0,20).map((x,i) =>
        '<div style="display:flex;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line-soft,#eaf1fa)">' +
        '<span class="hint" style="flex:0 0 22px">' + (i+1) + '</span>' +
        '<span style="flex:1">' + (x.name || x.title || '') + '</span>' +
        '<span class="hint">' + (x.artist || x.singer || '') + '</span>' +
        '<button type="button" onclick="xhMusicPlay(\'' + (x.name||x.title||'').replace(/'/g,'') + '\')">▶</button></div>'
      ).join('') + '<div id="xh-music-now" class="hint" style="margin-top:10px">未播放</div>' +
        '<div style="display:flex;gap:8px;margin-top:8px">' +
        '<button type="button" onclick="xhMusicPrev()">⏮ 上一首</button>' +
        '<button type="button" onclick="xhMusicNext()">⏭ 下一首</button>' +
        '<button type="button" onclick="xhMusicStop()">⏹ 停止</button></div>';
    }catch(e){ box.innerHTML = '<div class="empty">搜索失败：' + e.message + '</div>'; }
  };

  // ---------- 挂载到对应标签页 ----------
  function mount(){
    const pages = {
      'page-mcp': ['xh-mcp', 'MCP 工具测试', '点「测试」直接调用，不用经过语音', window.xhMcpTest],
      'page-memory': ['xh-mem', '记忆时间线', '按日期分组', window.xhMemoryLoad],
      'page-music': ['xh-music', '在线试听', '搜索并播放', null]
    };
    for(const pid in pages){
      const page = document.getElementById(pid);
      if(!page) continue;
      const [id, title, hint, loader] = pages[pid];
      let panel = document.getElementById(id);
      if(!panel){
        panel = ensurePanel(id, title, hint);
        if(id === 'xh-music'){
          panel.querySelector('.xh-body').innerHTML =
            '<div style="display:flex;gap:8px;margin-bottom:10px">' +
            '<input id="xh-music-q" placeholder="搜索歌曲，如：轻音乐" style="flex:1">' +
            '<button type="button" onclick="xhMusicSearch()">搜索</button></div>' +
            '<div id="xh-music-body" class="hint">点「搜索」找歌</div>';
        } else {
          panel.querySelector('.xh-body').id = id + '-body';
          panel.querySelector('.xh-body').innerHTML = '<span class="hint">点上面的标签加载</span>';
        }
        page.appendChild(panel);
      }
      if(loader){
        loader();
        setInterval(loader, 30000);
      }
    }
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(mount, 600));
  else setTimeout(mount, 600);
  document.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('.tab');
    if(t) setTimeout(mount, 300);
  }, true);
})();
</script>
'''

h = h.replace("</body>", "<script>" + js.replace("</script>\n", "") + "\n</body>", 1)
H.write_text(h, encoding="utf-8")
print("已注入 MCP 测试 / 记忆时间线 / 音乐播放器")
print("行数:", h.count("\n") + 1)
