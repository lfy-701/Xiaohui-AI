"""80 端口 TCP 转发到 8080。

背景：本机上有代理在接管 127.0.0.1:80（返回 Kestrel 404），
但局域网设备访问 192.168.x.x:80 是正常的。
所以：控制台跑在 8080（本机浏览器用），80 只做纯 TCP 转发给设备。
"""
import asyncio
import sys

LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 80
TARGET_HOST = "127.0.0.1"
TARGET_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080


async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader, client_writer):
    try:
        up_reader, up_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except Exception:
        client_writer.close()
        return
    await asyncio.gather(
        pipe(client_reader, up_writer),
        pipe(up_reader, client_writer),
    )


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", LISTEN_PORT)
    print(f"relay: 0.0.0.0:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
