"""修正 say 接口的音频编码：直接用 ffmpeg 出 PCM，再用 pcm_to_data 转 Opus。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

start_mark = "        try:\n            from core.utils.util import audio_bytes_to_data"
end_mark = "        try:\n            from core.handle.sendAudioHandle import sendAudioMessage"

i = t.find(start_mark)
j = t.find(end_mark)
if i < 0 or j < 0:
    print("⚠ 找不到编码块")
    sys.exit(1)

new_block = '''        # MP3 -> 16k 单声道 PCM -> Opus（避开 pydub 对 ffprobe 的依赖）
        try:
            import subprocess
            import tempfile
            import os as _os

            ffmpeg = None
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg = "ffmpeg"

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                fp.write(audio)
                tmp_path = fp.name

            try:
                proc = subprocess.run(
                    [ffmpeg, "-v", "quiet", "-nostdin", "-i", tmp_path,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "16000", "-ac", "1", "-"],
                    capture_output=True, timeout=30,
                )
                if proc.returncode != 0 or not proc.stdout:
                    raise RuntimeError((proc.stderr or b"")[:200].decode("utf-8", "ignore"))
                pcm = proc.stdout
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass

            from core.utils.util import pcm_to_data
            opus_packets = pcm_to_data(pcm)
        except Exception as e:
            return self._respond({"ok": False, "error": f"编码失败：{e}"}, 500)

'''

t = t[:i] + new_block + t[j:]
F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("已替换编码逻辑，语法 OK")
