"""设备页：去掉狗头 emoji、未绑定设备可删除。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = F.read_text(encoding="utf-8")

# 1) 去掉下拉里的头像 emoji
old1 = "${a.avatar} ${a.name}"
if old1 in t:
    t = t.replace(old1, "${a.name}")
    print("已去掉狗头 emoji")
else:
    print("emoji 未找到（可能已去掉）")

# 2) 未绑定时显示删除按钮
old2 = ": ''}</td></tr>"
new2 = (': `<button class="danger ghost" onclick="removeDevice(\'${x.id}\')">'
        "删除</button>`}</td></tr>")
if old2 in t:
    n = t.count(old2)
    t = t.replace(old2, new2)
    print(f"已加删除按钮（替换 {n} 处）")
else:
    print("按钮锚点未找到")

# 3) 加 removeDevice 函数（放在 unbindDevice 之后）
anchor = "async function unbindDevice("
idx = t.find(anchor)
if idx >= 0 and "async function removeDevice(" not in t:
    # 找到该函数结束（下一个 "\n    }\n" 后）
    end = t.find("\n    }\n", idx)
    add = """
    async function removeDevice(id) {
      if (!confirm('确定删除这台设备吗？删除后需要重新配网才会再次出现。')) return;
      const r = await fetch('/api/devices/' + id, {method: 'DELETE'});
      if (r.ok) { loadDevices && loadDevices(); }
      else {
        const d = await r.json().catch(() => ({}));
        alert(d.detail || '删除失败');
      }
    }
"""
    t = t[: end + len("\n    }\n")] + add + t[end + len("\n    }\n"):]
    print("已加 removeDevice 函数")
else:
    print("函数锚点未找到或已存在")

F.write_text(t, encoding="utf-8")
print("完成，行数:", t.count("\n") + 1)
