"""模拟成员 A 的 OpenAI 兼容服务：/v1/models + /v1/chat/completions（含 SSE）。

用法：python mock_llm.py 8000
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = ["qwen2.5:3b"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            self._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in MODELS]})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            self._json(404, {"error": {"message": "not found"}})
            return

        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        model = req.get("model", "")
        messages = req.get("messages", [])
        user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        sys_p = next((m["content"] for m in messages if m.get("role") == "system"), "")
        turns = sum(1 for m in messages if m.get("role") == "user")

        if model not in MODELS:
            self._json(404, {"error": {"message": f"model '{model}' not found", "type": "invalid_request_error"}})
            return

        reply = (f"我是 {model}。收到「{user}」。"
                 f"（system {len(sys_p)} 字，本轮是第 {turns} 轮）")

        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for ch in [reply[i:i + 6] for i in range(0, len(reply), 6)]:
                chunk = {"id": "chatcmpl-mock", "object": "chat.completion.chunk", "model": model,
                         "choices": [{"index": 0, "delta": {"content": ch}, "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.03)
            done = {"id": "chatcmpl-mock", "object": "chat.completion.chunk", "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(("data: " + json.dumps(done) + "\n\n").encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
        else:
            self._json(200, {
                "id": "chatcmpl-mock", "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": reply},
                             "finish_reason": "stop"}],
            })


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"mock openai-compatible server on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
