"""给「音乐」页签加上本地曲库、播放队列和语音播报。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

# ---------- 1) 替换音乐区块 ----------
start = t.index('  <section id="tab-music"')
end = t.index('</section>', start) + len('</section>')

NEW_SECTION = '''  <section id="tab-music" style="display:none">
    <div class="card" id="playerBar">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:10px">
        <div style="min-width:0">
          <div class="hint">正在播放</div>
          <div id="nowPlaying" style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:520px">未在播放</div>
        </div>
        <div class="row" style="gap:8px">
          <button onclick="playerPrev()">⏮</button>
          <button class="primary" onclick="playerToggle()" id="playerBtn">▶</button>
          <button onclick="playerNext()">⏭</button>
          <span class="hint" id="queueInfo"></span>
        </div>
      </div>
      <input type="range" id="seek" min="0" max="100" value="0" style="width:100%;margin-top:10px"
             oninput="seekTo(this.value)">
      <div class="row" style="justify-content:space-between">
        <span class="hint" id="timeNow">0:00</span>
        <span class="hint" id="timeTotal">0:00</span>
      </div>
    </div>

    <div class="card">
      <div class="row" style="gap:10px;flex-wrap:wrap">
        <b>在线搜索</b>
        <span class="hint" id="musicStatus">检查中…</span>
      </div>
      <div class="row" style="gap:8px;margin-top:12px">
        <input id="musicQuery" placeholder="歌名 / 歌手 / 关键词" style="flex:1"
               onkeydown="if(event.key==='Enter')searchMusic()">
        <select id="musicLimit" style="width:80px">
          <option>5</option><option>10</option><option>20</option>
        </select>
        <button class="primary" onclick="searchMusic()">搜索</button>
        <button onclick="announceNow()">🔊 念一下</button>
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

    <h3 class="sec">本地曲库</h3>
    <div class="card">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <span class="hint" id="localDir"></span>
        <button onclick="loadLocalMusic()">重新扫描</button>
      </div>
      <p class="hint" style="margin:8px 0 0">
        把音频文件放进 <code id="localDirInline">data/music</code> 目录（支持子文件夹），
        这里就能整首播放。
      </p>
    </div>
    <div id="localTracks"></div>

    <audio id="musicPlayer" style="display:none"></audio>
  </section>'''

t = t[:start] + NEW_SECTION + t[end:]

# ---------- 2) 替换 JS ----------
js_start = t.index("// ---------------- 音乐 ----------------")
js_end = t.index("// ---------------- MCP 工具 ----------------")

NEW_JS = '''// ---------------- 音乐 ----------------
let musicList = [];
let queue = [];          // {title, artist, url, kind}
let qIndex = -1;
let seeking = false;

const audio = document.getElementById('musicPlayer');

function fmtTime(s) {
  if (!isFinite(s)) return '0:00';
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return m + ':' + String(r).padStart(2, '0');
}

function updateQueueInfo() {
  document.getElementById('queueInfo').textContent =
    queue.length ? `队列 ${qIndex + 1}/${queue.length}` : '';
}

function setNowPlaying(item) {
  document.getElementById('nowPlaying').textContent =
    item ? item.title + (item.artist ? ' — ' + item.artist : '') : '未在播放';
}

async function loadMusic() {
  const st = document.getElementById('musicStatus');
  try {
    const s = await api('/api/music/status');
    if (s.online) {
      st.textContent = '已连接 · ' + (s.tools || 4) + ' 个工具';
      st.style.color = 'var(--ok)';
    } else {
      st.textContent = '未连接 · ' + (s.reason || '');
      st.style.color = 'var(--warn)';
    }
  } catch (e) {
    st.textContent = '状态检查失败：' + e.message;
    st.style.color = 'var(--danger)';
  }
  loadLocalMusic();
}

async function loadLocalMusic() {
  const box = document.getElementById('localTracks');
  try {
    const d = await api('/api/music/local');
    document.getElementById('localDir').textContent =
      d.count ? `共 ${d.count} 首` : '目录为空';
    document.getElementById('localDirInline').textContent = d.dir || 'data/music';
    if (!d.count) {
      box.innerHTML = '<div class="empty">把 mp3 / flac / m4a 放进 data/music 后点「重新扫描」</div>';
      return;
    }
    box.innerHTML = d.tracks.map((x, i) => `
      <div class="chunk">
        <div class="chunk-head">
          <span class="badge-score">${i + 1}</span>
          <b style="flex:1">${escapeHtml(x.title)}</b>
          <span class="hint">${x.size_mb} MB</span>
        </div>
        <div class="hint">${escapeHtml(x.folder || '根目录')}</div>
        <div style="margin-top:8px">
          <button class="primary" onclick="playLocal(${i})">▶ 播放整首</button>
          <button onclick="enqueueLocal(${i})">＋ 加入队列</button>
        </div>
      </div>`).join('');
    window._localTracks = d.tracks;
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
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
        <button class="primary" onclick="playPreview(${i})">▶ 试听 30s</button>
        <button onclick="enqueuePreview(${i})">＋ 加入队列</button>
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

// ---- 播放控制 ----
function playAt(i) {
  if (i < 0 || i >= queue.length) return;
  qIndex = i;
  const item = queue[i];
  audio.src = item.url;
  audio.play().catch(e => console.warn('播放失败', e));
  setNowPlaying(item);
  updateQueueInfo();
  document.getElementById('playerBtn').textContent = '⏸';
}

function playQueue(items) {
  queue = items.slice();
  qIndex = -1;
  playAt(0);
}

function playPreview(i) {
  const s = musicList[i];
  if (!s || !s.preview_url) return;
  playQueue([{title: s.title, artist: s.artist, url: s.preview_url, kind: 'preview'}]);
}

function playLocal(i) {
  const x = (window._localTracks || [])[i];
  if (!x) return;
  playQueue([{title: x.title, artist: x.folder, url: x.url, kind: 'local'}]);
}

function enqueuePreview(i) {
  const s = musicList[i];
  if (!s || !s.preview_url) return;
  queue.push({title: s.title, artist: s.artist, url: s.preview_url, kind: 'preview'});
  if (qIndex < 0) playAt(0); else updateQueueInfo();
}

function enqueueLocal(i) {
  const x = (window._localTracks || [])[i];
  if (!x) return;
  queue.push({title: x.title, artist: x.folder, url: x.url, kind: 'local'});
  if (qIndex < 0) playAt(0); else updateQueueInfo();
}

function playerToggle() {
  if (!queue.length) return;
  if (audio.paused) { audio.play(); document.getElementById('playerBtn').textContent = '⏸'; }
  else { audio.pause(); document.getElementById('playerBtn').textContent = '▶'; }
}

function playerNext() { if (qIndex + 1 < queue.length) playAt(qIndex + 1); }
function playerPrev() { if (qIndex > 0) playAt(qIndex - 1); }

function seekTo(v) {
  if (audio.duration) audio.currentTime = audio.duration * v / 100;
}

audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  document.getElementById('timeNow').textContent = fmtTime(audio.currentTime);
  document.getElementById('timeTotal').textContent = fmtTime(audio.duration);
  if (!seeking) document.getElementById('seek').value = audio.currentTime / audio.duration * 100;
});

audio.addEventListener('ended', () => {
  if (qIndex + 1 < queue.length) playAt(qIndex + 1);
  else { document.getElementById('playerBtn').textContent = '▶'; }
});

audio.addEventListener('pause', () => { document.getElementById('playerBtn').textContent = '▶'; });
audio.addEventListener('play', () => { document.getElementById('playerBtn').textContent = '⏸'; });

// ---- 语音播报 ----
async function announceNow() {
  const q = document.getElementById('musicQuery').value.trim();
  const n = musicList.length;
  let text = '';
  if (musicList[0]) {
    text = `找到${n}首歌，第一首是${musicList[0].title}，演唱者${musicList[0].artist}`;
  } else if (q) {
    text = `没有找到${q}相关的歌曲`;
  } else {
    text = '先搜索一首歌，我再念给你听';
  }
  try {
    const res = await fetch('/api/music/announce', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const url = URL.createObjectURL(await res.blob());
    const a = new Audio(url);
    a.onended = () => URL.revokeObjectURL(url);
    a.play();
  } catch (e) { alert('播报失败：' + e.message); }
}

'''

t = t[:js_start] + NEW_JS + t[js_end:]

F.write_text(t, encoding="utf-8")
print("区块替换:", 'id="playerBar"' in t)
print("本地曲库:", 'loadLocalMusic' in t)
print("队列控制:", 'playerNext' in t)
print("语音播报:", 'announceNow' in t)
