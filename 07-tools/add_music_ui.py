"""聊天页：音乐搜索列表 + 暂停按钮。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "xhMusicSearch" in t:
    print("已存在")
    sys.exit(0)

old = '''    <h2>放歌</h2>
    <div style="display:flex;gap:6px;margin-bottom:16px">
      <input id="xhSongQ" placeholder="歌名，如：晴天" style="flex:1;min-width:0;font-size:12.5px;padding:7px 10px;border:1px solid #dbe7f5;border-radius:8px;background:#fbfdff;font-family:inherit;outline:none">
      <button type="button" onclick="xhPlayMusic()" style="padding:7px 12px;font-size:12.5px">播放</button>
    </div>
'''

new = '''    <h2>放歌</h2>
    <div style="display:flex;gap:6px;margin-bottom:8px">
      <input id="xhSongQ" placeholder="歌名，如：晴天" style="flex:1;min-width:0;font-size:12.5px;padding:7px 10px;border:1px solid #dbe7f5;border-radius:8px;background:#fbfdff;font-family:inherit;outline:none"
             onkeydown="if(event.key==='Enter')xhMusicSearch()">
      <button type="button" onclick="xhMusicSearch()" style="padding:7px 12px;font-size:12.5px">搜索</button>
    </div>
    <div id="xhSongList" style="margin-bottom:8px"></div>
    <div style="display:flex;gap:6px;margin-bottom:16px">
      <button type="button" onclick="xhMusicStop()" style="flex:1;padding:6px;font-size:12px">暂停播放</button>
    </div>
'''

if old in t:
    t = t.replace(old, new, 1)
    print("已替换放歌区块")
else:
    print("⚠ 未匹配放歌区块")

js = '''
  // 搜索并列出结果（点歌名即播放）
  async function xhMusicSearch() {
    const q = (document.getElementById('xhSongQ').value || '').trim();
    if (!q) { add('✗ 先输入歌名', 'sys err'); return; }
    const box = document.getElementById('xhSongList');
    box.innerHTML = '<div class="hint">搜索中…</div>';
    try {
      const r = await fetch('/api/music/search?q=' + encodeURIComponent(q) + '&limit=5');
      const d = await r.json();
      const songs = d.songs || [];
      if (!songs.length) { box.innerHTML = '<div class="hint">没找到，换个关键词试试</div>'; return; }
      box.innerHTML = songs.map(function (s, i) {
        const name = (s.title || '').replace(/</g, '&lt;');
        const artist = (s.artist || '').replace(/</g, '&lt;');
        return '<div style="display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid #eaf1fa">' +
          '<span style="flex:1;font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          name + ' <span class="hint" style="font-size:11.5px">' + artist + '</span></span>' +
          '<button type="button" style="font-size:11.5px;padding:3px 9px" onclick="xhPlaySong(' + i + ')">播放</button>' +
          '</div>';
      }).join('');
      window.__xhSongs = songs;
    } catch (e) {
      box.innerHTML = '<div class="hint">搜索失败：' + e.message + '</div>';
    }
  }

  async function xhPlaySong(idx) {
    const s = (window.__xhSongs || [])[idx];
    if (!s) return;
    add('▸ 播放：' + (s.title || ''), 'sys');
    try {
      const r = await fetch('/api/music/play_url', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: s.preview_url, title: s.title || '', artist: s.artist || ''})
      });
      const d = await r.json();
      if (d && d.ok) add('♪ 已开始播放', 'sys ok');
      else add('✗ ' + ((d && d.error) || '播放失败'), 'sys err');
    } catch (e) { add('✗ 播放失败：' + e.message, 'sys err'); }
  }

  async function xhMusicStop() {
    try {
      const r = await fetch('/api/music/stop', {method: 'POST'});
      const d = await r.json();
      add(d && d.ok ? '▸ 已暂停播放' : '✗ 暂停失败', d && d.ok ? 'sys ok' : 'sys err');
    } catch (e) { add('✗ 暂停失败', 'sys err'); }
  }

  window.xhMusicSearch = xhMusicSearch;
  window.xhPlaySong = xhPlaySong;
  window.xhMusicStop = xhMusicStop;
'''

t = t.replace("</script>", js + "\n</script>", 1)
F.write_text(t, encoding="utf-8")
print("已加搜索列表与暂停")
