"""扩展动作：睡觉/醒来/摇尾/摇头/灯光秀 等。

1) 网页动作按钮补齐
2) 语音关键词补齐（睡觉、醒来、摇尾巴、摇头）
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 1) 网页按钮 ----------
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
h = H.read_text(encoding="utf-8")

old = '''      <button data-a="dance">跳舞</button>
    </div>'''
new = '''      <button data-a="dance">跳舞</button>
      <button data-a="sleep">睡觉</button>
      <button data-a="wake">醒来</button>
      <button data-a="wag">摇尾巴</button>
      <button data-a="shake">摇摇头</button>
    </div>'''

if old in h and 'data-a="sleep"' not in h:
    h = h.replace(old, new, 1)
    H.write_text(h, encoding="utf-8")
    print("网页：已加 睡觉/醒来/摇尾/摇头")
else:
    print("网页按钮未改（可能已存在）")

# ---------- 2) 语音关键词 ----------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

oldv = '''              "摇尾巴": "wag", "摇摇头": "shake",
              "停下": "stop",'''
newv = '''              "摇尾巴": "wag", "摇摇尾巴": "wag", "摇尾": "wag",
              "摇摇头": "shake", "摇摇头吧": "shake", "摇头": "shake",
              "睡觉": "sleep", "睡一会": "sleep", "睡一下": "sleep", "休息": "sleep",
              "醒来": "wake", "起床": "wake", "睡醒": "wake",
              "停下": "stop", "别动": "stop", "停": "stop",'''

if oldv in v and '"睡觉": "sleep"' not in v:
    v = v.replace(oldv, newv, 1)
    V.write_text(v, encoding="utf-8")
    ast.parse(v)
    print("语音：已加 睡觉/醒来/摇尾/摇头/别动")
else:
    print("语音词表未改（可能已存在）")
