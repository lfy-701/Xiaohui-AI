"""过滤嵌入模型，避免在对话模型下拉框里选到 bge 之类的向量模型。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

if "isChatModel" in t:
    print("已存在过滤逻辑，跳过")
    sys.exit(0)

start = t.index("  async function loadModels() {")
end = t.index("\n  }", t.index("hint.style.color = 'var(--ok)';", start)) + len("\n  }")

NEW = '''  async function loadModels() {
    try {
      llmStatus = await api('/api/models');
      availableModels = llmStatus.models || [];
    } catch (e) { llmStatus = {online: false, provider: 'none', hint: '读取模型列表失败'}; }

    // 嵌入/重排模型不能用来对话，选了会报错，这里过滤掉
    const isChatModel = (m) => !/bge|embed|rerank|embedding/i.test(m);
    const chatModels = availableModels.filter(isChatModel);
    const hiddenModels = availableModels.filter(m => !isChatModel(m));

    const sel = document.getElementById('f-model');
    const hint = document.getElementById('modelHint');
    if (!availableModels.length) {
      sel.innerHTML = `<option value="${current ? (current.model || '') : ''}">（暂无可用模型）</option>`;
      hint.textContent = llmStatus.hint || '';
      hint.style.color = 'var(--warn)';
    } else if (!chatModels.length) {
      sel.innerHTML = '<option value="">（没有可用的对话模型）</option>';
      hint.textContent = `只找到嵌入模型：${hiddenModels.join(', ')}`;
      hint.style.color = 'var(--warn)';
    } else {
      const cur = current ? current.model : '';
      const list = chatModels.slice();
      if (cur && !list.includes(cur) && isChatModel(cur)) list.unshift(cur);
      sel.innerHTML = list.map(m => `<option ${m === cur ? 'selected' : ''}>${m}</option>`).join('');
      const extra = hiddenModels.length ? `，已隐藏 ${hiddenModels.length} 个嵌入模型` : '';
      hint.textContent = `已接入 ${llmStatus.provider}（${chatModels.length} 个对话模型${extra}）`;
      hint.style.color = 'var(--ok)';
    }
  }'''

t = t[:start] + NEW + t[end:]
F.write_text(t, encoding="utf-8")

print("已替换 loadModels")
for k in ["isChatModel", "已隐藏", "对话模型"]:
    print("  {:<12} {}".format(k, "OK" if k in t else "缺失"))

m = re.search(r"<script>(.*?)</script>", t, re.S)
js = m.group(1)
print("  JS 括号:", {a: js.count(a) - js.count(b) for a, b in [("{", "}"), ("(", ")"), ("[", "]")]})
