"""1) 顶部「设定」改名「配置」；2) 角色介绍用「＋」按钮添加自定义描述。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

# ---------- 1) 导航改名 ----------
t = t.replace(
    '<div class="tab" data-tab="config" onclick="switchTab(\'config\')">设定</div>',
    '<div class="tab" data-tab="config" onclick="switchTab(\'config\')">配置</div>',
    1,
)

# ---------- 2) 角色介绍块重写 ----------
start = t.index('      <div class="cfg-card">\n        <div class="cfg-row" style="justify-content:space-between;margin-bottom:10px">\n          <h4 style="margin:0">角色介绍</h4>')
end = t.index("</div>", t.index("点上面的标签套用")) + len("</div>")

NEW = '''      <div class="cfg-card">
        <div class="cfg-row" style="justify-content:space-between;margin-bottom:10px">
          <h4 style="margin:0">角色介绍</h4>
          <span class="hint" id="personaCount"></span>
        </div>

        <div class="presets" id="personaPresets" style="margin-bottom:10px">
          <span class="chip" onclick="usePreset('warm')">温柔伙伴</span>
          <span class="chip" onclick="usePreset('lively')">活泼开心果</span>
          <span class="chip" onclick="usePreset('calm')">沉稳助理</span>
          <span class="chip" onclick="usePreset('sassy')">毒舌损友</span>
          <span class="chip" onclick="usePreset('teacher')">耐心老师</span>
          <span class="chip chip-add" onclick="openPersonaAdd()">＋ 自定义</span>
        </div>

        <div id="personaAddBox" style="display:none;margin-bottom:12px;padding:12px;
             border:1px dashed #c9d4e0;border-radius:8px;background:#fbfcfe">
          <div class="cfg-row" style="margin-bottom:8px">
            <input id="personaPresetName" placeholder="名字（可选，例如：邻家姐姐）"
                   style="width:220px">
            <span class="hint">方便以后一键套用</span>
          </div>
          <textarea id="personaPresetText" rows="4"
                    style="width:100%;resize:vertical"
                    placeholder="输入描述词，例如：
温柔体贴的邻家姐姐，说话轻一点，爱用「呀」「呢」这样的语气词。&#10;遇到我情绪低落时先安慰，再给建议。"></textarea>
          <div class="cfg-row" style="justify-content:flex-end;margin-top:8px">
            <span class="hint" id="personaAddHint" style="margin-right:auto"></span>
            <button onclick="closePersonaAdd()">取消</button>
            <button class="primary" onclick="commitPersonaAdd()">添加并使用</button>
          </div>
        </div>

        <textarea id="f-persona" oninput="onPersonaInput()" rows="12"
                  style="width:100%;min-height:220px;resize:vertical"
                  placeholder="描述它叫什么、什么性格、怎么说话…"></textarea>
        <span class="hint">可以直接编辑；也可以点上面的标签套用，或点「＋ 自定义」写一段自己的描述。</span>
      </div>'''

t = t[:start] + NEW + t[end:]

# ---------- 3) JS：自定义描述管理 ----------
js_anchor = "function togglePersonaCustom() {"
js_end = t.index("function onTempChange()")
NEW_JS = '''function personaPresetsKey(id) { return 'xiaohui_persona_presets_' + (id || 'default'); }

function loadPersonaPresets() {
  try {
    return JSON.parse(localStorage.getItem(personaPresetsKey(current && current.id)) || '[]');
  } catch (e) { return []; }
}

function savePersonaPresets(list) {
  localStorage.setItem(personaPresetsKey(current && current.id), JSON.stringify(list));
}

function renderPersonaPresets() {
  const box = document.getElementById('personaPresets');
  if (!box) return;
  box.querySelectorAll('.chip-custom').forEach(e => e.remove());
  const addBtn = box.querySelector('.chip-add');
  const list = loadPersonaPresets();
  list.forEach((p, i) => {
    const el = document.createElement('span');
    el.className = 'chip chip-custom';
    el.style.position = 'relative';
    el.innerHTML = escapeHtml(p.name || ('自定义' + (i + 1))) +
      ' <span style="color:#bbb;margin-left:2px" title="删除">×</span>';
    el.onclick = (ev) => {
      if (ev.target.textContent === '×') {
        ev.stopPropagation();
        const next = loadPersonaPresets();
        next.splice(i, 1);
        savePersonaPresets(next);
        renderPersonaPresets();
        return;
      }
      applyPersonaText(p.text || '');
    };
    if (addBtn) box.insertBefore(el, addBtn); else box.appendChild(el);
  });
}

function applyPersonaText(text) {
  const ta = document.getElementById('f-persona');
  if (!ta) return;
  ta.value = text;
  onPersonaInput();
}

function openPersonaAdd() {
  document.getElementById('personaAddBox').style.display = 'block';
  document.getElementById('personaAddHint').textContent = '';
  document.getElementById('personaPresetName').focus();
}

function closePersonaAdd() {
  document.getElementById('personaAddBox').style.display = 'none';
  document.getElementById('personaPresetName').value = '';
  document.getElementById('personaPresetText').value = '';
}

function commitPersonaAdd() {
  const name = document.getElementById('personaPresetName').value.trim();
  const text = document.getElementById('personaPresetText').value.trim();
  const hint = document.getElementById('personaAddHint');
  if (!text) {
    hint.textContent = '描述不能为空';
    hint.style.color = '#c0392b';
    return;
  }
  const list = loadPersonaPresets();
  list.push({name: name || ('自定义' + (list.length + 1)), text});
  savePersonaPresets(list);
  renderPersonaPresets();
  applyPersonaText(text);
  closePersonaAdd();
  setSaveState('修改中…', 'dirty');
  saveSoon();
}

function onPersonaInput() {
  const ta = document.getElementById('f-persona');
  const c = document.getElementById('personaCount');
  if (ta && c) c.textContent = ta.value.length + ' 字';
  saveSoon();
}

'''
t = t[:t.index(js_anchor)] + NEW_JS + t[js_end:]

# ---------- 4) 选中 agent 时刷新自定义标签与字数 ----------
t = t.replace(
    "  document.getElementById('f-persona').value = current.persona || '';",
    "  document.getElementById('f-persona').value = current.persona || '';\n"
    "  renderPersonaPresets();\n"
    "  onPersonaInput();",
    1,
)

F.write_text(t, encoding="utf-8")
for k in ["配置</div>", "chip-add", "commitPersonaAdd", "renderPersonaPresets", "personaAddBox"]:
    print("  {:<22} {}".format(k, "OK" if k in t else "缺失"))
