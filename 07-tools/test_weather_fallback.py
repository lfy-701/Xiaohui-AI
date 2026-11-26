"""回归测试：open-meteo 不可用时，专区天气必须走国内源兜底。

跑法：D:\\xiaohui-large-zone\\.venv\\Scripts\\python.exe tools\\test_weather_fallback.py
"""
import sys

sys.path.insert(0, r"D:\xiaohui-large-zone")

import httpx as _real_httpx
import app.services.fast_answers as fa


class _BoomClient(_real_httpx.Client):
    """模拟 DNS 污染的 open-meteo：只有它的请求抛 ConnectError，其余照常。"""

    def get(self, url, *a, **kw):
        if "open-meteo" in str(url):
            raise _real_httpx.ConnectError("simulated DNS pollution")
        return super().get(url, *a, **kw)


def main():
    # 只替换 fast_answers 里的 httpx.Client，国内源仍走真实网络
    fa.httpx = type("Shim", (), {"Client": _BoomClient, "ConnectError": _real_httpx.ConnectError})
    fa._cache_put("weather:东莞", None) if hasattr(fa, "_cache_put") else None
    # 清缓存，确保不是缓存命中
    try:
        fa._CACHE.clear()
    except Exception:
        try:
            fa._cache = {}
        except Exception:
            pass

    out = fa.weather_answer("今天东莞天气怎么样")
    print("fallback result:", out)
    ok = bool(out) and "气温" in out and "东莞" in out
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
