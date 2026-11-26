"""把 openai provider 的 response 方法整体重写为正确缩进的版本。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

start = t.index("    def response(self, session_id, dialogue, **kwargs):")
end = t.index("    def response_with_functions(")

NEW = '''    def response(self, session_id, dialogue, **kwargs):
        # 上游重启或长连接失效时会断开；未产出任何内容前重试一次，
        # 否则设备会一直停在「说话中」状态。
        for attempt in range(2):
            yielded = False
            try:
                responses = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=dialogue,
                    stream=True,
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    temperature=kwargs.get("temperature", self.temperature),
                    top_p=kwargs.get("top_p", self.top_p),
                    frequency_penalty=kwargs.get(
                        "frequency_penalty", self.frequency_penalty
                    ),
                )

                is_active = True
                for chunk in responses:
                    try:
                        delta = (
                            chunk.choices[0].delta
                            if getattr(chunk, "choices", None)
                            else None
                        )
                        content = delta.content if hasattr(delta, "content") else ""
                    except IndexError:
                        content = ""
                    if content:
                        if "<think>" in content:
                            is_active = False
                            content = content.split("<think>")[0]
                        if "</think>" in content:
                            is_active = True
                            content = content.split("</think>")[-1]
                        if is_active:
                            yielded = True
                            yield content
                return

            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Error in response generation (attempt {attempt + 1}): {e}"
                )
                if yielded or attempt == 1:
                    return
                time.sleep(0.6)

'''

t = t[:start] + NEW + t[end:]
if "import time" not in t:
    t = t.replace("import httpx", "import time\nimport httpx", 1)
F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("已重写并通过语法检查")
