"""修两处：ffmpeg 推流记录错误 + 回应音频改走 ffmpeg 转 wav（绕开 ffprobe）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

# ---------- 1) 推流：捕获 stderr ----------
C = VS / "core" / "api" / "console_handler.py"
c = C.read_text(encoding="utf-8")

old_popen = '''                proc = subprocess.Popen(
                    [ffmpeg, "-v", "quiet", "-nostdin",
                     "-reconnect", "1", "-reconnect_streamed", "1",
                     "-i", url,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "24000", "-ac", "1", "pipe:1"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    bufsize=0,
                )'''
new_popen = '''                proc = subprocess.Popen(
                    [ffmpeg, "-v", "error", "-nostdin",
                     "-reconnect", "1", "-reconnect_streamed", "1",
                     "-i", url,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "24000", "-ac", "1", "pipe:1"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=0,
                )'''

if old_popen in c:
    c = c.replace(old_popen, new_popen, 1)

# 结束时若 0 帧，把 ffmpeg 的错误打出来
old_tail = '''                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")'''
new_tail = '''                if sent == 0:
                    try:
                        err = (proc.stderr.read() or b"")[:400].decode("utf-8", "ignore")
                        conn.logger.bind(tag="Play").warning(f"ffmpeg 无输出，stderr: {err}")
                    except Exception:
                        pass
                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")'''

if old_tail in c:
    c = c.replace(old_tail, new_tail, 1)

C.write_text(c, encoding="utf-8")
ast.parse(c)
print("已加 ffmpeg 错误记录")

# ---------- 2) 回应音频：mp3 -> wav ----------
R = VS / "core" / "handle" / "receiveAudioHandle.py"
r = R.read_text(encoding="utf-8")

old_ack = '''        packets, _ = audio_to_data(path)'''
new_ack = '''        # pydub 需要 ffprobe，环境里只有 ffmpeg：先转成 wav 再解码
        import subprocess as _sp

        wav_path = path + ".wav"
        try:
            import imageio_ffmpeg as _iio
            _ff = _iio.get_ffmpeg_exe()
        except Exception:
            _ff = "ffmpeg"
        _p = _sp.run([_ff, "-v", "quiet", "-y", "-i", path,
                      "-ar", "24000", "-ac", "1", "-acodec", "pcm_s16le", wav_path],
                     capture_output=True, timeout=30)
        src = wav_path if _p.returncode == 0 else path
        packets, _ = audio_to_data(src)'''

if old_ack in r:
    r = r.replace(old_ack, new_ack, 1)
    R.write_text(r, encoding="utf-8")
    ast.parse(r)
    print("回应音频已改为 ffmpeg 转 wav")
else:
    print("⚠ 未找到 audio_to_data 调用")
