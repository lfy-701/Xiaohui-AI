import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=40)
c.post("/login", data={"password": "xiaohui2026"})

print("=== MCP Server ===")
for s in c.get("/api/mcp/servers").json()["servers"]:
    print("  {:<20} {:<8} 工具 {}  启用 {}".format(
        s["name"], s["status"], s["tool_count"], s["enabled"]))

print("\n=== 已注册工具 ===")
for t in c.get("/api/mcp/tools").json()["tools"]:
    print("  {:<28} {}".format(t["exposed_name"], t["description"][:34]))

print("\n=== 最近调用 ===")
for x in c.get("/api/mcp/calls?limit=3").json()["calls"]:
    ts = (x.get("timestamp") or "")[11:19]
    print("  {}  {:<26} {:<8} {}ms".format(
        ts, x["tool_name"], x["status"], x.get("duration_ms")))
