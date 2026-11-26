"""8106 音频缓存转发：本机 0.0.0.0:8106 → 成员 A <本地模型服务器IP>:8106。

设备在 192.168.200.x 网段，拉不到 Tailscale 地址，所以在本机做一层转发。
支持 Range（音频拖动/分段拉取）。
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import urllib.error
import urllib.request

UPSTREAM = "http://<本地模型服务器IP>:8106"
PORT = 8106

sys.stdout.reconfigure(encoding="utf-8")


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method: str):
        target = UPSTREAM + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        req = urllib.request.Request(target, data=body, method=method)
        for h in ("Content-Type", "Range", "Accept"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("content-length", "transfer-encoding",
                                     "connection", "content-encoding"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            payload = e.read()[:300]
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            msg = ("upstream error: " + str(e))[:200].encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        self._proxy("GET")

    def do_HEAD(self):
        self._proxy("HEAD")

    def log_message(self, fmt, *args):
        pass


class Threaded(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Threaded(("0.0.0.0", PORT), Proxy) as httpd:
        print(f"8106 relay started: 0.0.0.0:{PORT} -> {UPSTREAM}", flush=True)
        httpd.serve_forever()
