"""动态工具模式 + 日期注入：闲聊走快速通道，问天气/日期/音乐走完整通道。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

# 1) 去掉客户端级默认头
t = t.replace(
    '''        _fast = os.getenv("XH_TOOL_MODE", "off")
        _headers = {"x-tool-mode": _fast} if _fast else None
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url,
                                    timeout=httpx.Timeout(self.timeout),
                                    default_headers=_headers)''',
    '''        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url,
                                    timeout=httpx.Timeout(self.timeout))''')

# 2) 加辅助函数
helper = '''

_TOOL_HINTS = (
    "天气", "气温", "温度", "下雨", "会不会冷", "穿衣", "空气", "预报",
    "日期", "几号", "今天", "明天", "昨天", "星期", "几点", "时间",
    "提醒", "闹钟", "计时", "音乐", "歌", "播放", "放首", "放一",
    "站", "坐", "走", "转", "跳", "趴", "睡", "起身", "摇", "停",
    "灯", "灯珠", "亮",
)


def _last_user_text(dialogue):
    try:
        for m in reversed(dialogue or []):
            if isinstance(m, dict) and m.get("role") == "user":
                return str(m.get("content") or "")
    except Exception:
        pass
    return ""


def _tool_mode_for(dialogue):
    """需要工具/实时信息时返回 None（走完整通道），闲聊返回 "off"。"""
    txt = _last_user_text(dialogue)
    if not txt:
        return "off"
    return None if any(k in txt for k in _TOOL_HINTS) else "off"


def _with_date(dialogue):
    """在系统提示里补当前日期，模型就不会乱猜今天几号。"""
    try:
        import datetime

        now = datetime.datetime.now()
        hint = "当前时间是{}年{}月{}日 星期{} {}:{}。涉及日期时间一律以此为准。".format(
            now.year, now.month, now.day, "一二三四五六日"[now.weekday()],
            str(now.hour).zfill(2), str(now.minute).zfill(2),
        )
        out = []
        injected = False
        for m in dialogue or []:
            if isinstance(m, dict) and m.get("role") == "system" and not injected:
                out.append({"role": "system", "content": hint + "\\n" + str(m.get("content") or "")})
                injected = True
            else:
                out.append(m)
        if not injected:
            out.insert(0, {"role": "system", "content": hint})
        return out
    except Exception:
        return dialogue

'''

idx = t.find("class LLMProvider")
if idx < 0:
    idx = t.find("class ")
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 3) response() 里使用动态头与日期
t = t.replace(
    '''                responses = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=dialogue,
                    stream=True,''',
    '''                _mode = _tool_mode_for(dialogue)
                _extra = {"x-tool-mode": _mode} if _mode else None
                responses = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=_with_date(dialogue),
                    stream=True,
                    extra_headers=_extra,''')

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加动态工具模式与日期注入")
