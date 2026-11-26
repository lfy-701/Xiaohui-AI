"""极简登录保护：设了 CONSOLE_PASSWORD 才启用。

- 未设置密码：完全开放（仅限本机开发）
- 设置了密码：所有页面/API 需要先登录，cookie 有效 30 天
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "kx_session"
PASSWORD = os.getenv("CONSOLE_PASSWORD", "")
_MAX_AGE = 30 * 24 * 3600


def enabled() -> bool:
    return bool(PASSWORD)


def _token() -> str:
    return hmac.new(PASSWORD.encode(), b"xiaohui-console-v1", hashlib.sha256).hexdigest()


def is_authed(request: Request) -> bool:
    if not enabled():
        return True
    cookie = request.cookies.get(COOKIE, "")
    return hmac.compare_digest(cookie, _token())


LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小慧控制台 · 登录</title>
<style>
 body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
      background:linear-gradient(180deg,#eef6ff,#e2efff);
      font:14px/1.6 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#1e2a3a}
 .box{background:#fff;padding:34px 36px;border-radius:16px;box-shadow:0 8px 30px rgba(61,155,255,.18);
      width:320px;text-align:center}
 .logo{font-size:20px;font-weight:700;color:#1b6fc4;margin-bottom:4px}
 .logo span{color:#3d9bff}
 .sub{color:#6b8299;font-size:12px;margin-bottom:22px}
 input{width:100%;padding:11px 13px;border:1px solid #c2daf2;border-radius:10px;font:inherit;
       box-sizing:border-box;margin-bottom:14px}
 input:focus{outline:none;border-color:#3d9bff;box-shadow:0 0 0 3px rgba(61,155,255,.15)}
 button{width:100%;padding:11px;border:none;border-radius:10px;color:#fff;font:inherit;cursor:pointer;
        background:linear-gradient(135deg,#3d9bff,#67b6ff);box-shadow:0 2px 8px rgba(61,155,255,.3)}
 .err{color:#e5484d;font-size:12px;min-height:18px;margin-bottom:6px}
</style></head><body>
<form class="box" method="post" action="/login">
  <div class="logo">小慧<span>控制台</span></div>
  <div class="sub">请输入访问密码</div>
  <div class="err">__ERR__</div>
  <input type="password" name="password" placeholder="访问密码" autofocus>
  <button type="submit">进入控制台</button>
</form>
</body></html>"""


def login_page(error: str = "") -> HTMLResponse:
    return HTMLResponse(LOGIN_HTML.replace("__ERR__", error))
