# 给已部署控制台加 /api/console/action 代理与 /api/console/status
# 运行：pwsh -File tools\patch_console_action.ps1
$ErrorActionPreference = "Stop"
$console = "D:\AI-Companion-shared\xiaohui-ai\console"
$m = Join-Path $console "app\main.py"
$t = [IO.File]::ReadAllText($m, [Text.Encoding]::UTF8)

if ($t -notmatch 'VOICE_HTTP_BASE') {
    $anchor = 'MUSIC_BASE = os.getenv("MUSIC_BASE_URL", "http://127.0.0.1:8102").rstrip("/")'
    if (-not $t.Contains($anchor)) { throw "找不到 MUSIC_BASE 锚点" }
    $add = @"
$anchor
# 语音服务 HTTP 口（控制台动作/状态代理用）
VOICE_HTTP_BASE = os.getenv("VOICE_HTTP_BASE", "http://127.0.0.1:8003").rstrip("/")
"@
    $t = $t.Replace($anchor, $add)
    "已加 VOICE_HTTP_BASE"
} else { "VOICE_HTTP_BASE 已存在" }

if ($t -notmatch '/api/console/action') {
    $routes = @'


# ---------------------------------------------------------------- 语音服务控制

class ConsoleActionIn(BaseModel):
    action: str = ""
    tool: str = ""
    arguments: Dict[str, Any] = {}
    device_id: str = ""


@app.post("/api/console/action")
def api_console_action(body: ConsoleActionIn):
    """代理到语音服务的设备 MCP 控制接口，避免浏览器跨域。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE，无法连接语音服务")
    payload = {k: v for k, v in body.model_dump().items() if v not in ("", None, {})}
    if not payload.get("action") and not payload.get("tool"):
        raise HTTPException(400, "缺少 action 或 tool")
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/action", json=payload)
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "error": r.text[:300]}
    if r.status_code >= 400:
        if isinstance(data, dict):
            data.setdefault("ok", False)
        return JSONResponse(data, status_code=r.status_code)
    return data


@app.get("/api/console/status")
def api_console_status():
    """语音服务在线连接与设备 MCP 状态。"""
    if not VOICE_HTTP_BASE:
        return {"ok": False, "online": False, "devices": [],
                "reason": "未配置 VOICE_HTTP_BASE"}
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(f"{VOICE_HTTP_BASE}/api/console/status")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return {"ok": False, "online": False, "devices": [], "reason": str(e)}
'@
    $t = $t.TrimEnd() + "`r`n" + $routes
    "已加 /api/console/action 与 /api/console/status"
} else { "/api/console/action 已存在" }

[IO.File]::WriteAllText($m, $t, (New-Object Text.UTF8Encoding($false)))
"写入完成：$m"
Select-String -Path $m -Pattern 'VOICE_HTTP_BASE|api/console/action|api/console/status' |
    Select-Object -First 8 | ForEach-Object { "  L{0}: {1}" -f $_.LineNumber, $_.Line.Trim() }
