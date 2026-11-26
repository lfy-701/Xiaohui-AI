"""给语音服务的 LLM provider 加重试（未产出内容前重试一次）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

if "attempt" in t:
    print("已有重试逻辑，跳过")
    sys.exit(0)

if "import time" not in t:
    t = t.replace("import httpx", "import time\nimport httpx", 1)

# 在整个 response 方法体外包一层 for 循环
old_head = "    def response(self, session_id, dialogue, **kwargs):\n        try:\n"
new_head = (
    "    def response(self, session_id, dialogue, **kwargs):\n"
    "        # 上游重启或长连接失效时会断开：未产出内容前重试一次，\n"
    "        # 否则设备会一直停在「说话中」。\n"
    "        for attempt in range(2):\n"
    "            yielded = False\n"
    "            try:\n"
)
assert old_head in t, "方法头未找到"
t = t.replace(old_head, new_head, 1)

# 在 yield content 处记录已产出
t = t.replace("                    if is_active:\n                        yield content\n",
              "                    if is_active:\n                        yielded = True\n                        yield content\n", 1)

# 结尾的 except 改为重试逻辑
old_tail = (
    "        except Exception as e:\n"
    "            logger.bind(tag=TAG).error(f\"Error in response generation: {e}\")\n"
)
new_tail = (
    "                return\n"
    "            except Exception as e:\n"
    "                logger.bind(tag=TAG).error(\n"
    "                    f\"Error in response generation (attempt {attempt + 1}): {e}\"\n"
    "                )\n"
    "                if yielded or attempt == 1:\n"
    "                    return\n"
    "                time.sleep(0.6)\n"
)
assert old_tail in t, "异常块未找到"
t = t.replace(old_tail, new_tail, 1)

# 修正循环体内其余缩进（try 体内的行从 12 空格变为 16 空格）
lines = t.split("\n")
out = []
inside = False
for i, line in enumerate(lines):
    if "for attempt in range(2):" in line:
        inside = True
        out.append(line)
        continue
    if inside:
        if line.strip().startswith("return") and line.startswith("                return"):
            inside = False
            out.append(line)
            continue
        if line.startswith("            ") and line.strip() and not line.startswith("                "):
            out.append("    " + line)
            continue
    out.append(line)
t = "\n".join(out)

F.write_text(t, encoding="utf-8")
print("已写入")

# 打印改后的方法体供核对
seg = t[t.index("    def response(self, session_id"):]
seg = seg[: t.index("    def response_with_functions")]
print(seg)
