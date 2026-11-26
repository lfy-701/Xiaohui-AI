"""验证三种 LLM_CHAT_URL 写法都能正确归一化。"""
import os
import importlib
import sys

sys.path.insert(0, r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console")

cases = [
    "http://<本地模型服务器IP>:8000/v1/chat/completions",
    "http://<本地模型服务器IP>:8000/v1",
    "http://<本地模型服务器IP>:8000",
    "http://<本地模型服务器IP>:8000/",
]

for url in cases:
    os.environ["LLM_CHAT_URL"] = url
    os.environ["LLM_PROVIDER"] = "openai"
    import app.llm as llm
    importlib.reload(llm)
    print(f"输入: {url}")
    print(f"  chat_endpoint -> {llm.chat_endpoint()}")
    print(f"  base_endpoint -> {llm.base_endpoint()}")
