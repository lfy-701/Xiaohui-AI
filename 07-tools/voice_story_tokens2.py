"""按真实缩进修正：故事放宽 tokens，历史少带。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

old = '      payload = {"message": question, "history": history[-12:]}'
new = '''      # 故事类放宽长度，其余保持短答（降低延迟）
      _story_keys = ("故事", "讲个", "讲一", "童话", "睡前", "小说", "编一个", "编个")
      if any(k in question for k in _story_keys):
          _max_tokens = int(_os.getenv("ZONE_MAX_TOKENS_STORY", "600"))
      else:
          _max_tokens = int(_os.getenv("ZONE_MAX_TOKENS", "90"))
      payload = {
          "message": question,
          "history": history[-6:],
          "max_tokens": _max_tokens,
      }'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已应用：故事 600 / 普通 90 / 历史 6 条")
else:
    print("未匹配")
