"""智能体删除：加 removeAgent 函数与按钮样式。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = F.read_text(encoding="utf-8")

# 1) 函数
if "async function removeAgent(" not in t:
    anchor = "  function selectAgent(id) {"
    fn = """  async function removeAgent(id, name) {
    if (!confirm('删除智能体「' + (name || '') + '」？\\n\\n对话记录和记忆不会一起删除。')) return;
    const r = await fetch('/api/agents/' + id, {method: 'DELETE'});
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      alert(d.detail || '删除失败');
      return;
    }
    if (current && current.id === id) current = null;
    location.reload();
  }

"""
    t = t.replace(anchor, fn + anchor, 1)
    print("已加 removeAgent 函数")
else:
    print("函数已存在")

# 2) 样式
if ".del-agent" not in t:
    css = """
.agent-item .del-agent {
  border: 0; background: transparent; color: var(--text3, #8ba3ba);
  font-size: 16px; line-height: 1; width: 22px; height: 22px; border-radius: 6px;
  cursor: pointer; opacity: 0; transition: .15s ease; flex: 0 0 auto;
}
.agent-item:hover .del-agent { opacity: 1; }
.agent-item .del-agent:hover { background: #fdecea; color: #c0392b; }
"""
    t = t.replace("</head>", "<style>" + css + "</style>\r\n</head>", 1)
    print("已加按钮样式")

F.write_text(t, encoding="utf-8")
print("完成，行数:", t.count("\n") + 1)
