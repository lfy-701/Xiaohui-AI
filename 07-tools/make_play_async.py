"""放歌改为后台任务，避免占用连接导致后续对话无响应。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

C = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
c = C.read_text(encoding="utf-8")

start = c.find("        sent = 0\n        err = None")
end = c.find("    async def handle_action", start)
if start < 0 or end < 0:
    print("⚠ 未找到推流块")
    sys.exit(1)

new = '''        # 后台任务推流：立刻返回，不阻塞后续对话
        async def _stream(pkts, cn):
            sent = 0
            try:
                cn.client_abort = False
                await sendAudioMessage(cn, SentenceType.FIRST, [], "")
                for pkt in pkts:
                    if getattr(cn, "client_abort", False):
                        cn.logger.bind(tag="Play").info("播放被用户打断")
                        break
                    await sendAudioMessage(cn, SentenceType.MIDDLE, [pkt], None)
                    sent += 1
                    await asyncio.sleep(0.060)
                try:
                    await sendAudioMessage(cn, SentenceType.LAST, [], None)
                except Exception:
                    pass
            except Exception as e:
                cn.logger.bind(tag="Play").warning(f"推流中断: {e}")
            finally:
                cn.logger.bind(tag="Play").info(f"播放结束：{sent}/{len(pkts)} 帧")

        task = asyncio.create_task(_stream(packets, conn))
        self._play_tasks = getattr(self, "_play_tasks", set())
        self._play_tasks.add(task)
        task.add_done_callback(self._play_tasks.discard)

        return self._respond({
            "ok": True,
            "packets": len(packets),
            "seconds": round(len(packets) * 0.06, 1),
            "async": True,
        })

'''

c = c[:start] + new + c[end:]

# 确保 sendAudioMessage / SentenceType 在函数内可见（原代码在后段导入，这里前置）
if "from core.handle.sendAudioHandle import sendAudioMessage" not in c.split("async def _stream")[0].split("async def handle_play")[-1]:
    c = c.replace(
        "        # 后台任务推流：立刻返回，不阻塞后续对话",
        "        from core.handle.sendAudioHandle import sendAudioMessage\n"
        "        from core.providers.tts.dto.dto import SentenceType\n\n"
        "        # 后台任务推流：立刻返回，不阻塞后续对话",
        1,
    )

C.write_text(c, encoding="utf-8")
ast.parse(c)
print("放歌已改为后台推流")
