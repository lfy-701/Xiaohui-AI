"""动作次数：固件支持 "walk:6" 形式，页面加次数输入。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FW = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai")
B = FW / "dog_board.cc"
t = B.read_text(encoding="utf-8")

if "ParseCount" not in t:
    old = '''    void ExecuteAction(const std::string& a) {
        ESP_LOGI(TAG, "控制台动作: %s", a.c_str());'''
    new = '''    void ExecuteAction(const std::string& a) {
        ESP_LOGI(TAG, "控制台动作: %s", a.c_str());
        // 支持 "walk:6" 形式：冒号后是次数/循环数
        std::string name = a;
        int count = 0;
        auto pos = a.find(':');
        if (pos != std::string::npos) {
            name = a.substr(0, pos);
            try { count = std::stoi(a.substr(pos + 1)); } catch (...) { count = 0; }
        }
        if (count < 1) count = 0;      // 0 表示用默认次数'''
    t = t.replace(old, new, 1)

    # 各分支改用 name 和 count
    repl = [
        ('if (a == "stand") { servo_.Stand(); }', 'if (name == "stand") { servo_.Stand(); }'),
        ('else if (a == "sit") { servo_.Sit(); }', 'else if (name == "sit") { servo_.Sit(); }'),
        ('else if (a == "walk") { servo_.WalkForward(4); }',
         'else if (name == "walk") { servo_.WalkForward(count ? count : 4); }'),
        ('else if (a == "back") { servo_.WalkBackward(4); }',
         'else if (name == "back") { servo_.WalkBackward(count ? count : 4); }'),
        ('else if (a == "left") { servo_.TurnLeft(3); }',
         'else if (name == "left") { servo_.TurnLeft(count ? count : 3); }'),
        ('else if (a == "right") { servo_.TurnRight(3); }',
         'else if (name == "right") { servo_.TurnRight(count ? count : 3); }'),
        ('else if (a == "dance") { servo_.Dance(4); }',
         'else if (name == "dance") { servo_.Dance(count ? count : 4); }'),
        ('else if (a == "lie") { servo_.LieDown(); }', 'else if (name == "lie") { servo_.LieDown(); }'),
        ('else if (a == "sleep") { servo_.Sleep(); }', 'else if (name == "sleep") { servo_.Sleep(); }'),
        ('else if (a == "wake") { servo_.WakeUp(); }', 'else if (name == "wake") { servo_.WakeUp(); }'),
        ('else if (a == "wag") { servo_.Wag(3); }',
         'else if (name == "wag") { servo_.Wag(count ? count : 3); }'),
        ('else if (a == "shake") { servo_.ShakeHead(2); }',
         'else if (name == "shake") { servo_.ShakeHead(count ? count : 2); }'),
        ('else { ESP_LOGW(TAG, "未知动作: %s", a.c_str()); }',
         'else { ESP_LOGW(TAG, "未知动作: %s", name.c_str()); }'),
    ]
    for o, n in repl:
        t = t.replace(o, n, 1)

    B.write_text(t, encoding="utf-8")
    print("固件：已支持动作次数（walk:6）")
else:
    print("固件：已存在")

# 页面：加次数输入
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
c = C.read_text(encoding="utf-8")
if "xhRepeat" not in c:
    c = c.replace(
        '  <h2>动作控制</h2>\n  <div class="acts">',
        '  <h2>动作控制</h2>\n'
        '  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12.5px">\n'
        '    <span>次数</span>\n'
        '    <input id="xhRepeat" type="number" min="1" max="20" value="4" '
        'style="width:64px;padding:4px 8px;border:1px solid #dbe7f5;border-radius:6px">\n'
        '    <span class="hint" style="font-size:11.5px">用于前进/后退/左转/右转/跳舞</span>\n'
        '  </div>\n  <div class="acts">',
        1,
    )

    # 点击时对连续动作附加 :次数
    old_send = """            const r = await fetch('/api/console/action', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({action: key})
            });"""
    new_send = """            const CONT = ['walk', 'back', 'left', 'right', 'dance'];
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
    if old_send in c:
        c = c.replace(old_send, new_send, 1)
        print("页面：已加次数输入并附加到连续动作")
    else:
        print("⚠ 页面发送代码未匹配")

    C.write_text(c, encoding="utf-8")
else:
    print("页面：已存在")
