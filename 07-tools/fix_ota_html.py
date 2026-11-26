"""修复配网页面 OTA 地址区块的 HTML 结构。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\xiaozhi-esp32-2.5.2\managed_components\78__esp-wifi-connect\assets\wifi_configuration.html")
t = F.read_text(encoding="utf-8")

start = t.index('<div id="ota_url_row"')
end = t.index("<!-- Max TX Power -->")

BLOCK = '''<div id="ota_url_row" style="display: none;">
                      <label for="ota_url" data-lang="ota_url">Custom OTA URL:</label>
                      <div style="display: flex; align-items: center; gap: 10px;">
                          <input type="text" id="ota_url" name="ota_url" style="flex: 1;" placeholder="http://192.168.1.10/ota/">
                          <button type="button" class="icon-btn" onclick="clearOtaUrl()" aria-label="Clear">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                          </button>
                      </div>
                      <p class="hint" style="font-size:12px;color:#888;margin:6px 0 0;">
                          填你电脑的地址，例如 http://192.168.1.10/ota/ ；留空则使用固件内置地址。
                      </p>
                  </div>

                  '''

old = t[start:end]
t = t[:start] + BLOCK + t[end:]
F.write_text(t, encoding="utf-8")

print("替换前片段长度:", len(old))
print("替换后：")
seg = t[t.index('<div id="ota_url_row"'): t.index("<!-- Max TX Power -->")]
for line in seg.splitlines()[:14]:
    print("  " + line)

# 简单的结构自检
opens = len(re.findall(r"<div\b", seg))
closes = len(re.findall(r"</div>", seg))
print(f"\ndiv 开合: {opens} 开 / {closes} 闭 -> {'平衡' if opens == closes else '不平衡'}")
