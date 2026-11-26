"""设备端MCP工具执行器"""

from typing import Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from plugins_func.register import Action, ActionResponse
from .mcp_handler import call_mcp_tool


class DeviceMCPExecutor(ToolExecutor):
    """设备端MCP工具执行器"""
    def __init__(self, conn):
        self.conn = conn

    async def execute(
        self, conn, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行设备端MCP工具"""
        if not hasattr(conn, "mcp_client") or not conn.mcp_client:
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未初始化",
            )

        if not await conn.mcp_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未准备就绪",
            )

        try:
            # 转换参数为JSON字符串
            import json

            # 屏幕提示：正在调用工具（不朗读、不影响音频）
            args_str = json.dumps(arguments) if arguments else "{}"

            # 调用设备端MCP工具
            result = await call_mcp_tool(conn, conn.mcp_client, tool_name, args_str)

            resultJson = None
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception as e:
                    pass

            # 视觉大模型不经过二次LLM处理
            if (
                resultJson is not None
                and isinstance(resultJson, dict)
                and "action" in resultJson
            ):
                return ActionResponse(
                    action=Action[resultJson["action"]],
                    response=resultJson.get("response", ""),
                )

            # 动作类工具：执行完立刻回一句短确认，省掉一次 LLM 往返。
            # 之前这里一律返回 REQLLM，等于「狗动完了还要等专区生成一句话」，
            # 体感就是动作做完好久才出声。
            quick = _canned_reply(tool_name, arguments)
            if quick:
                return ActionResponse(action=Action.RESPONSE, response=quick)

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(action=Action.NOTFOUND, response=str(e))
        except Exception as e:
            return ActionResponse(action=Action.ERROR, response=str(e))

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取所有设备端MCP工具"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return {}

        tools = {}
        mcp_tools = self.conn.mcp_client.get_available_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")

            if tool_name:
                tools[tool_name] = ToolDefinition(
                    name=tool_name, description=tool, tool_type=ToolType.DEVICE_MCP
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定的设备端MCP工具"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return False

        return self.conn.mcp_client.has_tool(tool_name)


def _canned_reply(tool_name: str, arguments: Dict[str, Any]) -> str | None:
    """动作类工具执行完直接回一句，避免再走一次 LLM。

    只覆盖「动作/姿态」这类纯肢体指令——它的确认语是固定说法，
    没必要等模型组织语言；其他工具（查询类）仍然交回 LLM 组织回答。
    """
    try:
        name = (tool_name or "").lower()
        args = arguments or {}
        if "dog_action" in name:
            from core.utils.console_actions import ACTION_REPLIES

            act = str(args.get("action") or "").strip()
            return ACTION_REPLIES.get(act)
        if name.endswith("set_pose"):
            return "好，摆好了。"
    except Exception:
        return None
    return None
