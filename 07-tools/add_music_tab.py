"""给控制台加「音乐」页签（HTML + JS）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

# 1) 页签按钮
anchor = '<div class="tab" data-tab="mcp" onclick="switchTab(\'mcp\')">MCP 工具</div>'
if anchor in t and 'data-tab="music"' not in t:
    t = t.replace(anchor, anchor + '\n      <div class="tab" data-tab="music" onclick="switchTab(\'music\')">音乐</div>')

# 2) 切换列表与加载
t = t.replace("'fw', 'mcp'].forEach", "'fw', 'mcp', 'music'].forEach")
if "if (t === 'music') loadMusic();" not in t:
    t = t.replace("  if (t === 'mcp') loadMcp();",
                  "  if (t === 'mcp') loadMcp();\n  if (t === 'music') loadMusic();")

# 3) 页面区块：插在 MCP section 结束之后
SECTION = '''
  <section id="tab-music" style="display:none">
    <div class="card">
      <div class="row" style="gap:10px;flex-wrap:wrap">
        <b>音乐</b>
        <span class="hint" id="musicStatus">检查中…</span>
      </div>
      <div class="row" style="gap:8px;margin-top:12px">
        <input id="musicQuery" placeholder="歌名 / 歌手 / 关键词" style="flex:1"
               onkeydown="if(event.key==='Enter')searchMusic()">
        <select id="musicLimit" style="width:80px">
          <option>5</option><option>10</option><option>20</option>
        </select>
        <button class="primary" onclick="searchMusic()">搜索</button>
      </div>
      <div class="presets" style="margin-top:10px">
        <span class="chip" onclick="recommendMusic('放松')">放松</span>
        <span class="chip" onclick="recommendMusic('专注')">专注</span>
        <span class="chip" onclick="recommendMusic('运动')">运动</span>
        <span class="chip" onclick="recommendMusic('睡前')">睡前</span>
        <span class="chip" onclick="recommendMusic('开心')">开心</span>
        <span class="chip" onclick="recommendMusic('怀旧')">怀旧</span>
      </div>
    </div>
    <div id="musicResults"></div>
    <audio id="musicPlayer" style="display:none"></audio>
  </section>
'''
if 'id="tab-music"' not in t:
    t = t.replace('  <div id="newAgentModal"', SECTION + '\n  <div id="newAgentModal"')

# 4) JS
JS = '''
// ---------------- 音乐 ----------------
let musicList = [];

async function loadMusic() {
  const st = document.getElementById('musicStatus');
  try {
    const s = await api('/api/music/status');
    if (s.online) {
      st.textContent = '已连接 · ' + s.base + ' · ' + (s.tools || 4) + ' 个工具';
      st.style.color = 'var(--ok)';
    } else {
      st.textContent = '未连接 · ' + (s.reason || '');
      st.style.color = 'var(--warn)';
    }
  } catch (e) {
    st.textContent = '状态检查失败：' + e.message;
    st.style.color = 'var(--danger)';
  }
}

function renderMusic(d) {
  const box = document.getElementById('musicResults');
  const songs = d.songs || [];
  musicList = songs;
  if (!songs.length) {
    box.innerHTML = '<div class="empty">没有找到可试听的歌曲</div>';
    return;
  }
  box.innerHTML = songs.map((s, i) => `
    <div class="chunk">
      <div class="chunk-head">
        <span class="badge-score">${i + 1}</span>
        <b style="flex:1">${escapeHtml(s.title)}</b>
        <span class="hint">${escapeHtml(s.artist || '')}</span>
      </div>
      <div class="hint">${escapeHtml(s.album || '')}${s.duration_seconds ? ' · ' + s.duration_seconds + 's' : ''}${s.genre ? ' · ' + escapeHtml(s.genre) : ''}</div>
      <div style="margin-top:8px">
        <button onclick="playMusic(${i})">▶ 试听</button>
        <a href="${s.store_url || '#'}" target="_blank" rel="noopener" style="text-decoration:none">
          <button>商店页 ↗</button></a>
      </div>
    </div>`).join('');
}

async function searchMusic() {
  const q = document.getElementById('musicQuery').value.trim();
  const limit = document.getElementById('musicLimit').value;
  const box = document.getElementById('musicResults');
  if (!q) { box.innerHTML = '<div class="empty">先输入歌名或歌手</div>'; return; }
  box.innerHTML = '<div class="empty">搜索中…</div>';
  try {
    renderMusic(await api('/api/music/search?q=' + encodeURIComponent(q) + '&limit=' + limit));
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
  }
}

async function recommendMusic(mood) {
  const box = document.getElementById('musicResults');
  box.innerHTML = '<div class="empty">推荐中…</div>';
  try {
    renderMusic(await api('/api/music/recommend?mood=' + encodeURIComponent(mood) + '&limit=5'));
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
  }
}

function playMusic(i) {
  const s = musicList[i];
  if (!s || !s.preview_url) return;
  const p = document.getElementById('musicPlayer');
  p.src = s.preview_url;
  p.play().catch(e => alert('播放失败：' + e.message));
}
'''
if 'function playMusic' not in t:
    t = t.replace("// ---------------- MCP 工具 ----------------", JS + "\n// ---------------- MCP 工具 ----------------")

F.write_text(t, encoding="utf-8")
print("页签:", 'data-tab="music"' in t)
print("区块:", 'id="tab-music"' in t)
print("JS  :", 'function playMusic' in t)
print("切换:", "if (t === 'music') loadMusic();" in t)
