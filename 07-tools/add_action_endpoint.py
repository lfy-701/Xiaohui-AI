"""给最小版 console_handler 补回 handle_action（MCP 工具调用，走 WS 即时执行）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "handle_action" in t:
    print("已存在")
    sys.exit(0)

code = '''
    async def handle_action(self, request):
        """调用设备 MCP 工具（动作/舵机/灯珠），走 WebSocket 即时执行。"""
        import time as _t

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        body = body or {}
        tool = str(body.get("tool") or "").strip()
        action = str(body.get("action") or "").strip()
        arguments = body.get("arguments") or {}

        # 只给 action 时，默认调动作工具
        if not tool and action:
            tool = "self.dog_action"
            arguments = {"action": action}
        if not tool:
            return self._respond({"ok": False, "error": "缺少 tool 或 action"}, 400)

        conn = await self._pick_connection(str(body.get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        started = _t.perf_counter()
        try:
            from core.providers.tools.device_mcp import call_mcp_tool
            from core.utils.util import sanitize_tool_name

            result = await asyncio.wait_for(
                call_mcp_tool(
                    conn,
                    conn.mcp_client,
                    sanitize_tool_name(tool),
                    json.dumps(arguments, ensure_ascii=False),
                    timeout=8,
                ),
                timeout=10,
            )
        except Exception as e:
            return self._respond({"ok": False, "error": f"调用失败: {e}"}, 500)

        latency = int((_t.perf_counter() - started) * 1000)
        return self._respond(
            {"ok": True, "tool": tool, "arguments": arguments,
             "latency_ms": latency, "result": result}
        )

'''

idx = t.find("    async def handle_play(self, request):")
if idx < 0:
    print("⚠ 未找到插入点")
    sys.exit(1)
t = t[:idx] + code + t[idx:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加 handle_action；语法 OK")

# 注册路由
H = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\http_server.py")
h = H.read_text(encoding="utf-8")
if "/api/console/action" not in h:
    h = h.replace(
        'web.post("/api/console/say", self.console_handler.handle_say),',
        'web.post("/api/console/action", self.console_handler.handle_action),\n'
        '                    web.options("/api/console/action", self.console_handler.handle_options),\n'
        '                    web.post("/api/console/say", self.console_handler.handle_say),',
        1,
    )
    H.write_text(h, encoding="utf-8")
    ast.parse(h)
    print("已注册 /api/console/action 路由")
