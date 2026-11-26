"""重建 http_server 的路由注册列表（加入 /api/console/sequence）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\http_server.py")
lines = P.read_text(encoding="utf-8").split("\n")

start = next(i for i, ln in enumerate(lines) if "web.get(\"/mcp/vision/explain\"" in ln)
# 结束：包含 web.options("/api/console/stop" 的那一行
end = next(i for i in range(start, len(lines)) if '/api/console/stop' in lines[i] and "web.options" in lines[i])
# 末尾的 ] 与 ) 两行在 end 之后
close1 = next(i for i in range(end, len(lines)) if lines[i].strip() == "]")
close2 = next(i for i in range(close1, len(lines)) if lines[i].strip() == ")")

ind = " " * (len(lines[start]) - len(lines[start].lstrip()))
routes = [
    f'{ind}web.get("/mcp/vision/explain", self.vision_handler.handle_get),',
    f'{ind}web.post("/mcp/vision/explain", self.vision_handler.handle_post),',
    f'{ind}web.options("/mcp/vision/explain", self.vision_handler.handle_post),',
    f'{ind}web.get("/api/console/status", self.console_handler.handle_status),',
    f'{ind}web.post("/api/console/action", self.console_handler.handle_action),',
    f'{ind}web.options("/api/console/action", self.console_handler.handle_options),',
    f'{ind}web.post("/api/console/say", self.console_handler.handle_say),',
    f'{ind}web.options("/api/console/say", self.console_handler.handle_options),',
    f'{ind}web.post("/api/console/play", self.console_handler.handle_play),',
    f'{ind}web.options("/api/console/play", self.console_handler.handle_options),',
    f'{ind}web.post("/api/console/stop", self.console_handler.handle_stop),',
    f'{ind}web.options("/api/console/stop", self.console_handler.handle_options),',
    f'{ind}web.post("/api/console/sequence", self.console_handler.handle_sequence),',
    f'{ind}web.options("/api/console/sequence", self.console_handler.handle_options),',
]
lines[start:close1 + 1] = routes
text = "\n".join(lines)
P.write_text(text, encoding="utf-8")
ast.parse(text)
print("http_server 路由已重建，语法 OK")
