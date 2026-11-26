"""按行插入新动作（按钮与语音关键词），避免缩进不匹配。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 1) 网页按钮
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
lines = H.read_text(encoding="utf-8").split("\n")
if not any('data-a="sleep"' in ln for ln in lines):
    for i, ln in enumerate(lines):
        if 'data-a="dance"' in ln:
            indent = ln[: len(ln) - len(ln.lstrip())]
            add = [
                f'{indent}<button data-a="sleep">睡觉</button>',
                f'{indent}<button data-a="wake">醒来</button>',
                f'{indent}<button data-a="wag">摇尾巴</button>',
                f'{indent}<button data-a="shake">摇摇头</button>',
            ]
            lines[i + 1 : i + 1] = add
            print("网页：已加 4 个按钮")
            break
H.write_text("\n".join(lines), encoding="utf-8")

# 2) 语音关键词
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
vlines = V.read_text(encoding="utf-8").split("\n")
if not any('"睡觉": "sleep"' in ln for ln in vlines):
    for i, ln in enumerate(vlines):
        if '"摇尾巴": "wag"' in ln:
            indent = ln[: len(ln) - len(ln.lstrip())]
            vlines[i] = (
                f'{indent}"摇尾巴": "wag", "摇摇尾巴": "wag", "摇尾": "wag",\n'
                f'{indent}"摇摇头": "shake", "摇头": "shake",\n'
                f'{indent}"睡觉": "sleep", "睡一会": "sleep", "休息": "sleep",\n'
                f'{indent}"醒来": "wake", "起床": "wake", "睡醒": "wake",\n'
                f'{indent}"停下": "stop", "别动": "stop",'
            )
            # 去掉原来的「摇摇头/停下」行（下一行）
            if i + 1 < len(vlines) and '"停下"' in vlines[i + 1]:
                del vlines[i + 1]
            print("语音：已加 睡觉/醒来/摇尾/摇头/别动")
            break
V.write_text("\n".join(vlines), encoding="utf-8")
ast.parse("\n".join(vlines))
print("语法 OK")
