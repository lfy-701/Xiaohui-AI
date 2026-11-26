"""打字对话里拦截灯珠/灯效命令，直接下发并返回话术。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = F.read_text(encoding="utf-8").split("\n")

# 找 agent chat 接口
idx = None
for i, ln in enumerate(lines):
    if '"/api/agents/{agent_id}/chat"' in ln:
        idx = i
        break
if idx is None:
    print("⚠ 未找到 chat 接口")
    sys.exit(1)

# 找函数体第一个 docstring 或首个语句后插入
fn = None
for i in range(idx, min(idx + 8, len(lines))):
    if lines[i].lstrip().startswith("def "):
        fn = i
        break
if fn is None:
    print("⚠ 未找到函数定义")
    sys.exit(1)

# 插入到函数体第一行（跳过 docstring 行）
insert_at = fn + 1
if insert_at < len(lines) and lines[insert_at].strip().startswith('"""'):
    # 单行或跨行 docstring
    if lines[insert_at].strip().count('"""') < 2:
        j = insert_at + 1
        while j < len(lines) and '"""' not in lines[j]:
            j += 1
        insert_at = j + 1
    else:
        insert_at += 1

indent = " " * 4
block = [
    indent + "# 灯珠/灯效直通：不走模型，直接下发到设备心跳队列",
    indent + "try:",
    indent + "    _led_val, _led_say = _led_command_from_text(str((body or {}).get('text') or ''))",
    indent + "    if _led_val:",
    indent + "        _devs = store.list_devices() or []",
    indent + "        _devs = sorted(_devs, key=lambda d: (bool(d.get('bound')), d.get('last_seen') or 0), reverse=True)",
    indent + "        if _devs:",
    indent + "            store.push_command(_devs[0]['mac'], 'led', _led_val)",
    indent + "        store.add_chat('console', str((body or {}).get('text') or ''), _led_say, '')",
    indent + "        return {'reply': _led_say, 'model': 'led', 'session_id': (body or {}).get('session_id') or ''}",
    indent + "except Exception:",
    indent + "    pass",
]

if "灯珠/灯效直通" not in "\n".join(lines):
    lines[insert_at:insert_at] = block
    F.write_text("\n".join(lines), encoding="utf-8")
    ast.parse(F.read_text(encoding="utf-8"))
    print("已插入打字灯珠拦截（行", insert_at + 1, "）")
else:
    print("已存在")
