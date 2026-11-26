"""把「＋ 自定义」的输入区从内联块改成弹层，不再挤压下面的编辑框。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

# ---------- 1) 摘掉内联块 ----------
pat = re.compile(
    r'\s*<div id="personaAddBox"[^>]*>.*?添加并使用</button>\s*</div>\s*</div>',
    re.S,
)
m = pat.search(t)
if not m:
    print("⚠ 未找到内联块")
    sys.exit(1)

t = t[:m.start()] + "\n" + t[m.end():]
print("内联块已移除")

# ---------- 2) 插入弹层 ----------
MODAL = '''  <div id="personaAddBox" class="modal" style="display:none"
       onclick="if(event.target===this)closePersonaAdd()">
    <div class="modal-box" style="width:640px">
      <h3 style="margin:0 0 14px">自定义角色介绍</h3>
      <div class="field">
        <label>名字（可选，方便以后一键套用）</label>
        <input id="personaPresetName" placeholder="例如：邻家姐姐">
      </div>
      <div class="field" style="margin-top:14px">
        <label>描述词</label>
        <textarea id="personaPresetText" rows="8" style="width:100%;resize:vertical"
                  placeholder="例如：&#10;温柔体贴的邻家姐姐，说话轻一点，爱用「呀」「呢」这样的语气词。&#10;遇到我情绪低落时先安慰，再给建议。"></textarea>
      </div>
      <div class="row" style="justify-content:flex-end;gap:8px;margin-top:16px">
        <span class="hint" id="personaAddHint" style="margin-right:auto"></span>
        <button onclick="closePersonaAdd()">取消</button>
        <button class="primary" onclick="commitPersonaAdd()">添加并使用</button>
      </div>
    </div>
  </div>

'''

anchor = '  <div id="newAgentModal" class="modal" style="display:none">'
if anchor in t:
    t = t.replace(anchor, MODAL + anchor, 1)
    print("弹层已插入")
else:
    print("⚠ 弹层锚点未匹配")

# ---------- 3) 显隐改为 flex ----------
t = t.replace(
    "document.getElementById('personaAddBox').style.display = 'block';",
    "document.getElementById('personaAddBox').style.display = 'flex';",
)
t = t.replace(
    """function openPersonaAdd() {
  document.getElementById('personaAddBox').style.display = 'flex';""",
    """function openPersonaAdd() {
  document.getElementById('personaAddBox').style.display = 'flex';""",
)

F.write_text(t, encoding="utf-8")

for k in ['class="modal" style="display:none"\n       onclick=', "personaPresetText",
          "display = 'flex'", "closePersonaAdd"]:
    print("  {:<30} {}".format(k.split("\n")[0][:28], "OK" if k in t else "缺失"))
print("  内联块是否残留:", "有" if 'margin-bottom:12px;padding:12px;\n             border:1px dashed' in t else "无")
