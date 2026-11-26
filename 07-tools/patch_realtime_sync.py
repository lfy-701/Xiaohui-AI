"""保存角色/唤醒词/音色时，同步写入语音服务的运行时配置。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\app\main.py")
t = F.read_text(encoding="utf-8")

# 1) 运行时设置透传 prompt / wakeup_words
old = '''    if s.get("voice"):
        out["voice"] = str(s["voice"])
    if s.get("model"):
        out["model"] = str(s["model"])
    return out'''
new = '''    if s.get("voice"):
        out["voice"] = str(s["voice"])
    if s.get("model"):
        out["model"] = str(s["model"])
    if s.get("prompt"):
        out["prompt"] = str(s["prompt"])
    if s.get("wakeup_words"):
        out["wakeup_words"] = list(s["wakeup_words"])
    return out'''
if old in t:
    t = t.replace(old, new, 1)
    print("已加入 prompt / wakeup_words 透传")
else:
    print("⚠ 透传锚点未匹配")

# 2) 新增同步函数
anchor = '''def _sync_engine_model(model_name: str) -> None:'''
addition = '''def _sync_engine_prompt(persona: str) -> None:
    """把角色介绍写进语音服务的运行时配置（下一通连接生效）。"""
    try:
        cur = _read_voice_settings()
        if cur.get("prompt") == persona:
            return
        cur["prompt"] = persona
        _write_voice_settings(cur)
        store.add_log("system", "角色设定已同步到语音服务（下一轮对话生效）")
    except Exception:
        pass


def _sync_engine_wakeup(word: str) -> None:
    """把唤醒词并入语音服务的识别列表，不覆盖设备端已支持的词。"""
    try:
        cur = _read_voice_settings()
        words = list(cur.get("wakeup_words") or [])
        if "你好小慧" not in words:
            words.insert(0, "你好小慧")
        if word and word not in words:
            words.append(word)
        if words == (cur.get("wakeup_words") or []):
            return
        cur["wakeup_words"] = words
        _write_voice_settings(cur)
        store.add_log("system", f"唤醒词列表已更新：{', '.join(words)}")
    except Exception:
        pass


def _sync_engine_model(model_name: str) -> None:'''
if anchor in t:
    t = t.replace(anchor, addition, 1)
    print("已加入 prompt / wakeup 同步函数")
else:
    print("⚠ 函数锚点未匹配")

# 3) 保存 agent 时触发同步
old3 = '''    # 音色与模型要同步给语音服务，否则设备仍用配置文件里的那些
    if a.get("voice"):
        _sync_engine_voice(a["voice"])
    if a.get("model"):
        _sync_engine_model(a["model"])
    return a'''
new3 = '''    # 音色 / 模型 / 角色设定 / 唤醒词 都要同步给语音服务，
    # 保存后下一次对话即生效，不需要重启服务或重新配网。
    if a.get("voice"):
        _sync_engine_voice(a["voice"])
    if a.get("model"):
        _sync_engine_model(a["model"])
    if a.get("persona"):
        _sync_engine_prompt(a["persona"])
    if a.get("wake_word"):
        _sync_engine_wakeup(a["wake_word"])
    return a'''
if old3 in t:
    t = t.replace(old3, new3, 1)
    print("已接入保存同步")
else:
    print("⚠ 保存锚点未匹配")

F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("语法 OK")
for k in ["_sync_engine_prompt", "_sync_engine_wakeup", "已同步到语音服务"]:
    print("  {:<24} {}".format(k, "OK" if k in t else "缺失"))
