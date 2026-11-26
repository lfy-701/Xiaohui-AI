"""应用配置：从环境变量 / .env 读取，构造时立即校验。

设计原则：
- API Key 只存在于服务端 .env，绝不进入代码、日志或 ESP32 固件。
- 配置非法时启动失败（fail fast），而不是运行到一半才报错。
- 所有默认值均来自 DeepSeek 官方文档（2026-11 版本）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SERVER_DIR / ".env"

# 官方模型列表：https://api-docs.deepseek.com/api/create-chat-completion
ALLOWED_MODELS: tuple[str, ...] = ("deepseek-flash", "deepseek-v4-pro")
# thinking 模式 effort：https://api-docs.deepseek.com/guides/thinking_mode
ALLOWED_EFFORTS: tuple[str, ...] = ("low", "high", "max")
# 单次输出 token 官方上限 384K
MAX_OUTPUT_TOKENS = 393_216

DEFAULT_SYSTEM_PROMPT = (
    '你是一只名叫"小慧"的 AI 机器小狗，是用户的语音陪伴伙伴。'
    "你的回答会被语音合成朗读，因此必须口语化、简短，通常 1-2 句，不超过 60 个字。"
    "不要使用 Markdown、列表、代码块、颜文字或括号补充说明。"
    "语气活泼、温暖、有分寸；不知道的事情直接说不知道，绝不编造事实。"
)


class SettingsError(ValueError):
    """配置项非法，启动时应直接失败。"""


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise SettingsError(f"{name} 必须是 true/false，当前为 {raw!r}")


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise SettingsError(f"{name} 必须是整数，当前为 {raw!r}") from exc


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise SettingsError(f"{name} 必须是数字，当前为 {raw!r}") from exc


def _read_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip()


@dataclass(frozen=True)
class Settings:
    """全局配置快照。测试中可直接构造，无需污染环境变量。"""

    app_name: str = "esp32-ai-dog-server"
    version: str = "0.2.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # --- DeepSeek 连接 ---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    # 语音陪伴场景默认关闭思考，避免首字延迟过高
    thinking_enabled: bool = False
    reasoning_effort: str = "low"
    request_timeout_s: float = 30.0
    total_timeout_s: float = 45.0
    max_retries: int = 2
    max_tokens: int = 512
    # 深度思考时给推理过程留足输出预算，避免 512 被思考内容吃光导致正文截断
    max_tokens_thinking: int = 2_048
    max_reasoning_chars: int = 2_000
    temperature: float = 0.8

    # --- 对话输入约束 ---
    max_message_chars: int = 2_000
    max_history_messages: int = 12
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # 控制台访问令牌；为空时仅允许本机访问。云端部署必须设置。
    console_token: str | None = None

    def __post_init__(self) -> None:
        base_url = self.deepseek_base_url.rstrip("/")
        object.__setattr__(self, "deepseek_base_url", base_url)

        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise SettingsError("DEEPSEEK_BASE_URL 必须是完整 URL，例如 https://api.deepseek.com")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise SettingsError("DEEPSEEK_BASE_URL 必须使用 https（仅本机调试允许 http）")

        if self.deepseek_model not in ALLOWED_MODELS:
            raise SettingsError(
                f"DEEPSEEK_MODEL={self.deepseek_model!r} 不受支持，可选：{', '.join(ALLOWED_MODELS)}"
            )
        if self.reasoning_effort not in ALLOWED_EFFORTS:
            raise SettingsError(
                f"DOG_REASONING_EFFORT={self.reasoning_effort!r} 非法，可选：{', '.join(ALLOWED_EFFORTS)}"
            )
        if not 0 < self.request_timeout_s <= self.total_timeout_s:
            raise SettingsError(
                "DEEPSEEK_TIMEOUT_S 必须大于 0 且不超过 DEEPSEEK_TOTAL_TIMEOUT_S "
                f"（当前 {self.request_timeout_s} / {self.total_timeout_s}）"
            )
        if not 0 <= self.max_retries <= 5:
            raise SettingsError("DEEPSEEK_MAX_RETRIES 必须在 0-5 之间")
        if not 1 <= self.max_tokens <= MAX_OUTPUT_TOKENS:
            raise SettingsError(f"DOG_MAX_TOKENS 必须在 1-{MAX_OUTPUT_TOKENS} 之间")
        if not 1 <= self.max_tokens_thinking <= MAX_OUTPUT_TOKENS:
            raise SettingsError(f"DOG_MAX_TOKENS_THINKING 必须在 1-{MAX_OUTPUT_TOKENS} 之间")
        if self.max_reasoning_chars < 100:
            raise SettingsError("DOG_MAX_REASONING_CHARS 不能小于 100")
        if self.max_tokens_thinking < self.max_tokens:
            raise SettingsError("DOG_MAX_TOKENS_THINKING 不能小于 DOG_MAX_TOKENS")
        if not 0.0 <= self.temperature <= 2.0:
            raise SettingsError("DOG_TEMPERATURE 必须在 0.0-2.0 之间")
        if self.max_message_chars < 1:
            raise SettingsError("DOG_MAX_MESSAGE_CHARS 必须大于 0")
        if not 0 <= self.max_history_messages <= 50:
            raise SettingsError("DOG_MAX_HISTORY_MESSAGES 必须在 0-50 之间")
        if not 1 <= self.port <= 65_535:
            raise SettingsError("APP_PORT 必须在 1-65535 之间")
        if not self.system_prompt.strip():
            object.__setattr__(self, "system_prompt", DEFAULT_SYSTEM_PROMPT)
        if self.console_token is not None:
            token = ""
            if token and len(token) < 16:
                raise SettingsError("CONSOLE_TOKEN 至少 16 个字符，避免弱令牌")
            object.__setattr__(self, "console_token", token or None)

    @property
    def has_api_key(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.strip())

    def summary(self) -> dict[str, object]:
        """可安全写入日志/健康检查的配置摘要（不含密钥）。"""
        return {
            "model": self.deepseek_model,
            "base_url": self.deepseek_base_url,
            "thinking_enabled": self.thinking_enabled,
            "reasoning_effort": self.reasoning_effort,
            "request_timeout_s": self.request_timeout_s,
            "total_timeout_s": self.total_timeout_s,
            "max_retries": self.max_retries,
            "max_tokens": self.max_tokens,
            "max_tokens_thinking": self.max_tokens_thinking,
            "max_reasoning_chars": self.max_reasoning_chars,
            "api_key_configured": self.has_api_key,
            "console_token_configured": bool(self.console_token),
        }

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ENV_FILE, override=False)

        errors: list[str] = []

        def safe(fn, name, default):
            try:
                return fn(name, default)
            except SettingsError as exc:
                errors.append(str(exc))
                return default

        kwargs = {
            "host": safe(_read_str, "APP_HOST", cls.host),
            "port": safe(_read_int, "APP_PORT", cls.port),
            "log_level": safe(_read_str, "LOG_LEVEL", cls.log_level),
            "deepseek_api_key": (_read_str("DEEPSEEK_API_KEY", "") or None),
            "deepseek_base_url": safe(_read_str, "DEEPSEEK_BASE_URL", cls.deepseek_base_url),
            "deepseek_model": safe(_read_str, "DEEPSEEK_MODEL", cls.deepseek_model),
            "thinking_enabled": safe(_read_bool, "DOG_THINKING_ENABLED", cls.thinking_enabled),
            "reasoning_effort": safe(_read_str, "DOG_REASONING_EFFORT", cls.reasoning_effort),
            "request_timeout_s": safe(_read_float, "DEEPSEEK_TIMEOUT_S", cls.request_timeout_s),
            "total_timeout_s": safe(_read_float, "DEEPSEEK_TOTAL_TIMEOUT_S", cls.total_timeout_s),
            "max_retries": safe(_read_int, "DEEPSEEK_MAX_RETRIES", cls.max_retries),
            "max_tokens": safe(_read_int, "DOG_MAX_TOKENS", cls.max_tokens),
            "max_tokens_thinking": safe(
                _read_int, "DOG_MAX_TOKENS_THINKING", cls.max_tokens_thinking
            ),
            "max_reasoning_chars": safe(
                _read_int, "DOG_MAX_REASONING_CHARS", cls.max_reasoning_chars
            ),
            "temperature": safe(_read_float, "DOG_TEMPERATURE", cls.temperature),
            "max_message_chars": safe(_read_int, "DOG_MAX_MESSAGE_CHARS", cls.max_message_chars),
            "max_history_messages": safe(_read_int, "DOG_MAX_HISTORY_MESSAGES", cls.max_history_messages),
            "system_prompt": _read_str("DOG_SYSTEM_PROMPT", cls.system_prompt),
            "console_token": (_read_str("CONSOLE_TOKEN", "") or None),
        }

        if errors:
            raise SettingsError("配置错误：\n- " + "\n- ".join(errors))

        try:
            return cls(**kwargs)
        except SettingsError as exc:
            raise SettingsError(f"配置错误：{exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程级单例，供 FastAPI 依赖使用。"""
    return Settings.from_env()
