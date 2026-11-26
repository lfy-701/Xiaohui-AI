"""方案 C：控制台把唤醒词下发给设备（心跳携带），固件运行时重建命令表。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\app\main.py")
t = F.read_text(encoding="utf-8")

# ---------- 1) 拼音转换 + 唤醒词清单 ----------
anchor = '''@app.post("/api/devices/heartbeat")'''
helper = '''def _to_pinyin(text: str) -> str:
    """中文转不带声调的拼音，MultiNet 需要这种格式。"""
    try:
        from pypinyin import lazy_pinyin

        parts = lazy_pinyin((text or "").strip())
        return " ".join(p for p in parts if p.strip()).lower()
    except Exception:
        return ""


def _wake_words_for(cfg: dict) -> list:
    """给设备下发的唤醒词清单：固定保留「你好小慧」作为保底词。"""
    words = [{"pinyin": "ni hao xiao hui", "display": "你好小慧"}]
    agent = (cfg or {}).get("agent") or {}
    w = (agent.get("wake_word") or "").strip()
    if w and w != "你好小慧":
        py = _to_pinyin(w)
        if py:
            words.append({"pinyin": py, "display": w})
    return words


@app.post("/api/devices/heartbeat")'''
if anchor in t:
    t = t.replace(anchor, helper, 1)
    print("已加入拼音转换与唤醒词清单")
else:
    print("⚠ 心跳锚点未匹配")

# ---------- 2) 心跳响应带上 wake_words ----------
old = '''      cfg = store.device_config(body.mac) or {}
      return {**dev, "config": cfg}'''
new = '''      cfg = store.device_config(body.mac) or {}
      cfg = dict(cfg)
      # 设备据此在本地重建唤醒词命令表（运行时生效，无需重刷固件）
      cfg["wake_words"] = _wake_words_for(cfg)
      return {**dev, "config": cfg}'''
if old in t:
    t = t.replace(old, new, 1)
    print("心跳响应已带 wake_words")
else:
    print("⚠ 心跳响应锚点未匹配")

F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("语法 OK")
for k in ["_to_pinyin", "_wake_words_for", "wake_words"]:
    print("  {:<18} {}".format(k, "OK" if k in t else "缺失"))
