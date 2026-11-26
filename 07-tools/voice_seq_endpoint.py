"""语音服务：新增 /api/console/sequence 接口，逐帧下发动作序列。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 1) console_handler 加 handle_sequence ----------
H = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
h = H.read_text(encoding="utf-8")

if "handle_sequence" not in h:
    CODE = '''

    async def handle_sequence(self, conn, steps, loops=1):
        """逐帧播放动作序列（调用固件 self.set_pose）。"""
        import asyncio as _aio
        import json as _json

        from core.providers.tools.device_mcp import call_mcp_tool

        total = 0
        for _ in range(max(1, min(int(loops or 1), 20))):
            for step in steps or []:
                angles = str(step.get("angles") or "").strip()
                if not angles:
                    continue
                ms = int(step.get("ms") or 250)
                try:
                    await call_mcp_tool(conn, conn.mcp_client, "self.set_pose",
                                        _json.dumps({"angles": angles}), timeout=3)
                    total += 1
                except Exception as e:
                    self._log.warning(f"序列步骤失败: {e}")
                    break
                await _aio.sleep(max(0.05, ms / 1000.0))
        return {"ok": True, "frames": total}
'''
    # 插到类的末尾（最后一个 res 行之后追加方法）
    idx = h.rfind("\n")
    h = h.rstrip() + "\n" + CODE
    H.write_text(h, encoding="utf-8")
    ast.parse(h)
    print("console_handler：已加 handle_sequence")

# ---------- 2) http_server 加路由 ----------
S = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\http_server.py")
s = S.read_text(encoding="utf-8")

if "/api/console/sequence" not in s:
    anchor = 'if path == "/api/console/action":'
    code = '''            if path == "/api/console/sequence":
                return await self._handle_console(handler, self.console_handler.handle_sequence)
'''
    if anchor in s:
        s = s.replace(anchor, code + "            " + anchor, 1)
        S.write_text(s, encoding="utf-8")
        ast.parse(s)
        print("http_server：已加 /api/console/sequence 路由")
    else:
        print("路由锚点未匹配，现有路径：")
        for i, ln in enumerate(s.split("\n")):
            if "/api/console/" in ln:
                print("   ", i + 1, ln.strip())
