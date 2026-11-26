"""固件：唤醒后用 AutoStop 模式，说完话自动回到聆听（连续对话）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\xiaozhi-esp32-2.5.2\main\application.cc")
t = F.read_text(encoding="utf-8")

# 只改 HandleWakeWord 里那两处（Idle 打开通道 + Speaking 打断）
old1 = """              SetDeviceState(kDeviceStateConnecting);
              // Schedule to let the state change be processed first (UI update)
              Schedule([this]() { ContinueOpenAudioChannel(kListeningModeManualStop); });
              return;
          }
          SetListeningMode(kListeningModeManualStop);
      } else if (state == kDeviceStateSpeaking) {
          AbortSpeaking(kAbortReasonNone);
          SetListeningMode(kListeningModeManualStop);
      }"""

new1 = """              SetDeviceState(kDeviceStateConnecting);
              // Schedule to let the state change be processed first (UI update)
              // AutoStop：说完话自动回到聆听，实现连续对话
              Schedule([this]() { ContinueOpenAudioChannel(kListeningModeAutoStop); });
              return;
          }
          SetListeningMode(kListeningModeAutoStop);
      } else if (state == kDeviceStateSpeaking) {
          AbortSpeaking(kAbortReasonNone);
          SetListeningMode(kListeningModeAutoStop);
      }"""

if old1 in t:
    t = t.replace(old1, new1, 1)
    F.write_text(t, encoding="utf-8")
    print("已改为 AutoStop（连续对话）")
else:
    print("⚠ 未匹配唤醒代码块")
