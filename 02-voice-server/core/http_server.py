import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler
from core.api.console_handler import ConsoleActionHandler

TAG = __name__


class SimpleHttpServer:
    def __init__(self, config: dict, ws_server=None):
        """ws_server 用于控制台接口查找在线设备。"""
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.console_handler = ConsoleActionHandler(config, ws_server)

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """获取websocket地址

        Args:
            local_ip: 本地IP地址
            port: 端口号

        Returns:
            str: websocket地址
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def start(self):
        server_config = self.config["server"]
        host = server_config.get("ip", "0.0.0.0")
        port = int(server_config.get("http_port", 8003))

        if port:
            app = web.Application()

            read_config_from_api = server_config.get("read_config_from_api", False)

            if not read_config_from_api:
                # 如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口，用于下发websocket接口
                app.add_routes(
                    [
                        web.get("/xiaozhi/ota/", self.ota_handler.handle_get),
                        web.post("/xiaozhi/ota/", self.ota_handler.handle_post),
                        web.options("/xiaozhi/ota/", self.ota_handler.handle_post),
                    ]
                )
            # 添加路由
            app.add_routes(
                [
                    web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                    web.post("/mcp/vision/explain", self.vision_handler.handle_post),
                    web.options("/mcp/vision/explain", self.vision_handler.handle_post),
                    web.get("/api/console/status", self.console_handler.handle_status),
                    web.get("/api/console/actions", self.console_handler.handle_actions),
                    web.post("/api/console/action", self.console_handler.handle_action),
                    web.options("/api/console/action", self.console_handler.handle_options),
                    web.post("/api/console/say", self.console_handler.handle_say),
                    web.options("/api/console/say", self.console_handler.handle_options),
                    web.post("/api/console/play", self.console_handler.handle_play),
                    web.options("/api/console/play", self.console_handler.handle_options),
                    web.post("/api/console/stop", self.console_handler.handle_stop),
                    web.options("/api/console/stop", self.console_handler.handle_options),
                    web.post("/api/console/sequence", self.console_handler.handle_sequence),
                    web.options("/api/console/sequence", self.console_handler.handle_options),
                    ]
            )

            # 运行服务
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()

            # 保持服务运行
            while True:
                await asyncio.sleep(3600)  # 每隔 1 小时检查一次
