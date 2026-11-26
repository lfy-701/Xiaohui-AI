"""撤回上一轮新增的动作入口（保留网页可自定义姿态）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 1) 网页：删掉 sleep/wake/wag/shake 按钮
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
lines = H.read_text(encoding="utf-8").split("\n")
kept = [ln for ln in lines if not any(f'data-a="{a}"' in ln for a in ("sleep", "wake", "wag", "shake"))]
removed = len(lines) - len(kept)
H.write_text("\n".join(kept), encoding="utf-8")
print(f"网页：已删除 {removed} 个按钮")

# 2) 语音：恢复原来的动作词表
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

start = v.find('              "摇尾巴": "wag"')
end = v.find('              "停下": "stop",', start)
if start > 0 and end > start:
    end = v.find("\n", end) + 1
    original = (
        '              "摇尾巴": "wag", "摇摇头": "shake",\n'
        '              "停下": "stop",\n'
    )
    v = v[:start] + original + v[end:]
    V.write_text(v, encoding="utf-8")
    ast.parse(v)
    print("语音：已恢复原词表")
else:
    print("语音：未匹配，当前词表片段：")
    i = v.find("actions = {")
    print(v[i : i + 600])
