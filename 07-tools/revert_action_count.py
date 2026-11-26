"""撤回动作次数功能（固件 + 页面）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 固件 ----------
B = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai\dog_board.cc")
t = B.read_text(encoding="utf-8")

old_parse = '''        // 支持 "walk:6" 形式：冒号后是次数/循环数
        std::string name = a;
        int count = 0;
        auto pos = a.find(':');
        if (pos != std::string::npos) {
            name = a.substr(0, pos);
            count = std::atoi(a.substr(pos + 1).c_str());
        }
        if (count < 1) count = 0;      // 0 表示用默认次数
'''
if old_parse in t:
    t = t.replace(old_parse, "", 1)
    print("固件：已移除次数解析")

repl = [
    ('if (name == "stand") { servo_.Stand(); }', 'if (a == "stand") { servo_.Stand(); }'),
    ('else if (name == "sit") { servo_.Sit(); }', 'else if (a == "sit") { servo_.Sit(); }'),
    ('else if (name == "walk") { servo_.WalkForward(count ? count : 4); }',
     'else if (a == "walk") { servo_.WalkForward(4); }'),
    ('else if (name == "back") { servo_.WalkBackward(count ? count : 4); }',
     'else if (a == "back") { servo_.WalkBackward(4); }'),
    ('else if (name == "left") { servo_.TurnLeft(count ? count : 3); }',
     'else if (a == "left") { servo_.TurnLeft(3); }'),
    ('else if (name == "right") { servo_.TurnRight(count ? count : 3); }',
     'else if (a == "right") { servo_.TurnRight(3); }'),
    ('else if (name == "dance") { servo_.Dance(count ? count : 4); }',
     'else if (a == "dance") { servo_.Dance(4); }'),
    ('else if (name == "lie") { servo_.LieDown(); }', 'else if (a == "lie") { servo_.LieDown(); }'),
    ('else if (name == "sleep") { servo_.Sleep(); }', 'else if (a == "sleep") { servo_.Sleep(); }'),
    ('else if (name == "wake") { servo_.WakeUp(); }', 'else if (a == "wake") { servo_.WakeUp(); }'),
    ('else if (name == "wag") { servo_.Wag(count ? count : 3); }',
     'else if (a == "wag") { servo_.Wag(3); }'),
    ('else if (name == "shake") { servo_.ShakeHead(count ? count : 2); }',
     'else if (a == "shake") { servo_.ShakeHead(2); }'),
    ('else { ESP_LOGW(TAG, "未知动作: %s", name.c_str()); }',
     'else { ESP_LOGW(TAG, "未知动作: %s", a.c_str()); }'),
]
for o, n in repl:
    t = t.replace(o, n, 1)
B.write_text(t, encoding="utf-8")
print("固件：动作分发已还原")

# ---------- 页面 ----------
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
c = C.read_text(encoding="utf-8")

import re
c = re.sub(r'  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12\.5px">\s*'
           r'<span>次数</span>.*?</div>\n', '', c, count=1, flags=re.S)

old_send = """            const CONT = ['walk', 'back', 'left', 'right', 'dance'];
            let act = key;
            if (CONT.indexOf(key) >= 0) {
              const rp = document.getElementById('xhRepeat');
              const n = rp ? Math.max(1, Math.min(20, parseInt(rp.value) || 4)) : 4;
              act = key + ':' + n;
              add('▸ 次数：' + n, 'sys');
            }
            const r = await fetch('/api/console/action', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({action: act})
            });"""
new_send = """            const r = await fetch('/api/console/action', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({action: key})
            });"""
if old_send in c:
    c = c.replace(old_send, new_send, 1)
    print("页面：已移除次数逻辑")

C.write_text(c, encoding="utf-8")
print("页面：已还原（次数输入框已删）")
