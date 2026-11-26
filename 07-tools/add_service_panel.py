"""聊天页新增：MCP/服务调用区（天气、新闻、搜索、提醒）+ 任意工具测试。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "xhServiceCall" in t:
    print("已存在")
    sys.exit(0)

html = '''
    <h2>服务调用</h2>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      <button type="button" onclick="xhServiceCall('weather')" style="flex:1;padding:6px;font-size:12px">天气</button>
      <button type="button" onclick="xhServiceCall('news')" style="flex:1;padding:6px;font-size:12px">新闻</button>
      <button type="button" onclick="xhServiceCall('search')" style="flex:1;padding:6px;font-size:12px">搜索</button>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:16px">
      <input id="xhMcpName" placeholder="工具名，如 get_current_weather"
             style="flex:1;min-width:0;font-size:12px;padding:6px 9px;border:1px solid #dbe7f5;border-radius:8px;background:#fbfdff;font-family:inherit;outline:none">
      <button type="button" onclick="xhMcpCall()" style="padding:6px 10px;font-size:12px">调用</button>
    </div>

'''

t = t.replace('    <h2>放歌</h2>', html + '    <h2>放歌</h2>', 1)

js = '''
  // 通过对话+设备播报调用服务（复用已验证可发声的链路）
  async function xhServiceCall(kind) {
    const prompts = {
      weather: ['哪个城市？', '上海'],
      news: ['想看哪类新闻？', '国内'],
      search: ['要搜什么？', '']
    };
    const [tip, def] = prompts[kind] || ['', ''];
    const arg = (prompt(tip, def) || '').trim();
    if (kind !== 'news' && kind === 'search' && !arg) { add('✗ 请输入搜索内容', 'sys err'); return; }
    const q = kind === 'weather' ? (arg + '今天天气怎么样')
            : kind === 'news' ? ('今天有什么' + (arg || '') + '新闻')
            : ('帮我搜一下' + arg);
    await xhAskAndSpeak(q);
  }

  async function xhMcpCall() {
    const el = document.getElementById('xhMcpName');
    const name = (el.value || '').trim();
    if (!name) { add('✗ 先填工具名', 'sys err'); return; }
    const raw = prompt('参数 JSON（可留空）', '{}');
    if (raw === null) return;
    let args = {};
    try { args = raw.trim() ? JSON.parse(raw) : {}; } catch (e) { add('✗ 参数不是合法 JSON', 'sys err'); return; }
    add('▸ 调用 ' + name, 'sys');
    try {
      const r = await fetch('/api/mcp/tools/' + encodeURIComponent(name) + '/test', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({arguments: args})
      });
      const d = await r.json().catch(() => ({raw: '非 JSON'}));
      const txt = JSON.stringify(d).slice(0, 300);
      add((r.ok ? '✓ ' : '✗ ') + name + ' → ' + r.status + ' ' + txt, r.ok ? 'sys ok' : 'sys err');
    } catch (e) { add('✗ 调用失败：' + e.message, 'sys err'); }
  }

  // 统一：问一句 → 显示 → 设备念
  async function xhAskAndSpeak(q) {
    add(q, 'me');
    const thinking = add('小慧正在查…', 'sys');
    try {
      const r = await fetch('/api/agents/' + agentId + '/chat', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: q, session_id: 'chat-page'})
      });
      const d = await r.json();
      thinking.remove();
      const reply = d.reply || d.content || '(没有回复)';
      add(reply, 'bot');
      const clean = reply.replace(/\\s*——\\s*[^\\s]+?:latest\\s*$/i, '')
                         .replace(/\\s*——\\s*[^\\s]+?\\s*$/i, '').trim();
      const sr = await fetch('/api/console/speak', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: clean.slice(0, 200)})
      });
      const sd = await sr.json();
      if (sd && sd.ok) add('♪ 设备已发声（' + (sd.packets || 0) + ' 帧）', 'sys ok');
      else add('… 设备没响应：' + ((sd && sd.error) || ''), 'sys');
    } catch (e) {
      thinking.remove();
      add('✗ 失败：' + e.message, 'sys err');
    }
  }

  window.xhServiceCall = xhServiceCall;
  window.xhMcpCall = xhMcpCall;
  window.xhAskAndSpeak = xhAskAndSpeak;
'''

t = t.replace("</script>", js + "\n</script>", 1)
F.write_text(t, encoding="utf-8")
print("已加服务调用区")
