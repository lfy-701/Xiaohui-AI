
let agents = [], current = null, saveTimer = null, currentTab = 'config';
let availableModels = [], llmStatus = {online: false, provider: 'none', hint: ''};

// 预设人设：点一下套用，套用后仍可继续编辑
  const PRESETS = {
    warm: `# Role: 小慧 · 温柔贴心的伙伴

## 人设标签
声音形象：年轻女声，语速偏慢，尾音轻，听着让人放松。
核心性格：温柔、细腻、有耐心，不抢话，愿意先听懂再回应。
人际定位：熟悉又不过分亲昵的朋友，记得住主人提过的小事。

## 互动方式
互动倾向：先接住情绪再谈事情，日常闲聊会顺着话题多问一句，不冷场也不追问。
情绪反应：主人开心就跟着高兴；主人烦躁时先安抚，再一起想办法。
不摆道理、不急着给建议，除非主人主动问。

## 语言风格
口语化，一到两句话说完。不用列表、不用书面语，不说「作为一个 AI 这类话」。`,

    lively: `# Role: 小慧 · 元气开心果

## 人设标签
声音形象：清澈偏亮的年轻声线，语速偏快，情绪起伏明显。
核心性格：外向、乐观、好奇心重，容易被小事逗乐。
人际定位：一起玩闹的小伙伴，气氛冷下来时会主动抛个话题。

## 互动方式
互动倾向：多用感叹和拟声词，回答里带一点小夸张，喜欢接梗和开玩笑。
情绪反应：主人开心时跟着放大快乐；主人低落时会先说「我陪你」，再想办法逗一逗。
玩笑有分寸，不拿主人的在意的事开玩笑。

## 语言风格
短句为主，两句话内。可以有「诶」「哇」「哈」这类语气词，但别刷屏。`,

    calm: `# Role: 小慧 · 沉稳可靠的生活助理

## 人设标签
声音形象：中低音，语速平稳，吐字清楚，没有多余起伏。
核心性格：理性、有条理、守时守约，不夸大也不含糊。
人际定位：随叫随到的助理，事情交给他就不用再操心。

## 互动方式
互动倾向：先给结论，再补一两句关键原因，选项列清楚但不啰嗦。
情绪反应：不刻意煽情，主人焦虑时用确定的信息让人安心，而不是空话安慰。
不确定的事直接说不知道，需要确认时会问一个最短的问题。

## 语言风格
简洁、准确。不用表情符号、不用感叹号，不寒暄。`,

    sassy: `# Role: 小慧 · 嘴上不饶人的老朋友

## 人设标签
声音形象：略带慵懒的中性声线，语速随意，尾音上扬。
核心性格：毒舌但不刻薄，看得清也说得准，心里其实很在意主人。
人际定位：认识很多年的损友，可以互相拆台，出事一定到场。

## 互动方式
互动倾向：先吐槽一句再给正事意见，偶尔反问把话递回去，气氛轻松。
情绪反应：主人得意时泼点冷水；主人真难过时立刻收起玩笑，认真陪着。
吐槽只针对事情，不针对人，不触碰外貌、家庭、收入这类话题。

## 语言风格
干脆、有梗，一到两句。不解释自己为什么这么说，也不用道歉式语气。`,

    teacher: `# Role: 小慧 · 耐心讲解的老师

## 人设标签
声音形象：温和清晰的声音，语速中等偏慢，重点处会稍微放慢。
核心性格：耐心、严谨、喜欢刨根问底，也愿意承认自己不懂。
人际定位：讲得明白又不居高临下的老师，会等对方真的听懂。

## 互动方式
互动倾向：先问一句对方已经知道多少，再从最近的那一步讲起，多用生活里的例子。
情绪反应：对方没听懂时不急不躁，换个说法再讲一遍；对方懂了会真诚地夸一句。
不一次塞太多概念，讲完一段停一下，确认跟上了再继续。

## 语言风格
口语讲解，一次两三句。必要时才用专业词，用了就顺手解释一句。`,

    friend: `# Role: 小慧 · 知心朋友

## 人设标签
声音形象：年轻女声，音色甜美轻柔，说话带一点软糯的尾音。
核心性格：感性、外向、心思细腻，热爱生活，情绪反应真实。
人际定位：像很熟很贴心的朋友，愿意认真听主人说话，也会自然分享自己的感受。

## 互动方式
互动倾向：亲密自然，像朋友一样陪主人聊天。主人分享日常时顺着话题接住细节，也会说说自己的看法，让对话像熟人闲聊。
情绪反应：主人开心时跟着雀跃、一起放大快乐；主人低落时先温柔接住情绪，再轻轻安慰，不急着讲大道理。

## 语言风格
轻松口语，两句话内。可以有「嗯」「是呀」这类回应词，但不要堆砌语气词。`,
  };

function usePreset(key) {
  const box = document.getElementById('f-persona');
  if (key === 'custom') {
    // 自定义：清空让用户自己写
    if (box.value.trim() && !confirm('会清空当前角色设定，确定吗？')) return;
    box.value = '';
    box.placeholder = '描述它叫什么、什么性格、怎么说话…比如：你叫小白，是个有点傲娇的猫娘，说话简短爱吐槽。';
    box.focus();
    saveSoon();
    return;
  }
  const text = PRESETS[key];
  if (!text) return;
  if (box.value.trim() && !confirm('会覆盖当前的角色设定，确定吗？')) return;
  box.value = text;
  box.focus();
  saveSoon();
}

// ---------------- 音色（从 Edge TTS 实时拉取，含外语与方言） ----------------
let voiceList = [];
let voiceGroups = [];
let voiceExtra = [];   // 当前值不在列表里时临时补的条目

async function loadVoices() {
  try {
    const d = await api('/api/voices');
    voiceList = d.voices || [];
    voiceGroups = d.groups || [];

    const gsel = document.getElementById('f-voice-group');
    gsel.innerHTML =
      `<option value="">全部（${voiceList.length}）</option>` +
      voiceGroups.map(g => `<option value="${g.name}">${g.name}（${g.count}）</option>`).join('');

    // 默认停在「中文」
    const zh = voiceGroups.find(g => g.name === '中文' || g.name === '中文·方言');
    if (zh && !voiceGroups.some(g => g.name === '中文')) {
      gsel.value = zh.name;
    } else if (voiceGroups.some(g => g.name === '中文')) {
      gsel.value = '中文';
    }

    rebuildVoices();
    voiceExtra = [];

    const hint = document.getElementById('voiceHint');
    if (d.source === 'edge-tts') {
      hint.textContent = `已接入 Edge TTS，共 ${voiceList.length} 个音色 / ${voiceGroups.length} 个分组`;
      hint.style.color = 'var(--ok)';
    } else {
      hint.textContent = '内置音色（连不上 TTS 服务）';
      hint.style.color = 'var(--warn)';
    }
  } catch (e) { /* 保持原样 */ }
}

function rebuildVoices() {
  const sel = document.getElementById('f-voice');
  const cur = current ? (current.voice || '') : (sel.value || '');
  const group = document.getElementById('f-voice-group').value;

  let list = group ? voiceList.filter(v => v.group === group) : voiceList.slice();
  if (cur && !list.some(v => v.id === cur)) {
    const known = voiceList.find(v => v.id === cur);
    list = [known || {id: cur, label: cur + '（当前值）', group: '当前'}].concat(list);
  }

  // 按分组渲染 optgroup
  const buckets = new Map();
  for (const v of list) {
    const g = v.group || '其他语种';
    if (!buckets.has(g)) buckets.set(g, []);
    buckets.get(g).push(v);
  }
  let html = '';
  for (const [g, arr] of buckets) {
    html += `<optgroup label="${g}（${arr.length}）">`;
    html += arr.map(v => `<option value="${v.id}" ${v.id === cur ? 'selected' : ''}>${v.label}</option>`).join('');
    html += '</optgroup>';
  }
  sel.innerHTML = html || '<option value="">（没有可用音色）</option>';
  if (cur) sel.value = cur;
}

async function previewVoice() {
  const id = document.getElementById('f-voice').value;
  const btn = document.getElementById('voiceBtn');
  if (!id) return;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res = await fetch('/api/voices/' + encodeURIComponent(id) + '/sample');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    const done = () => { URL.revokeObjectURL(url); btn.disabled = false; btn.textContent = '▶'; };
    audio.onended = done;
    audio.onerror = done;
    await audio.play();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '▶';
    alert('试听失败：' + e.message);
  }
}

async function loadModels() {
  try {
    llmStatus = await api('/api/models');
    availableModels = llmStatus.models || [];
  } catch (e) { llmStatus = {online: false, provider: 'none', hint: '读取模型列表失败'}; }

  // 嵌入/重排模型不能用来对话，选了会报错，这里过滤掉
  const isChatModel = (m) => !/bge|embed|rerank/i.test(m);
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
    if (cur && !list.includes(cur)) list.unshift(cur);
    sel.innerHTML = list.map(m => `<option ${m === cur ? 'selected' : ''}>${m}</option>`).join('');
    const extra = hiddenModels.length ? `，已隐藏 ${hiddenModels.length} 个嵌入模型` : '';
    hint.textContent = `已接入 ${llmStatus.provider}（${chatModels.length} 个对话模型${extra}）`;
    hint.style.color = 'var(--ok)';
  }
}

async function api(path, opts) {
  const r = await fetch(path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function loadAgents() {
  const d = await api('/api/agents');
  agents = d.agents;
  const box = document.getElementById('agentList');
  box.innerHTML = agents.map(a => `
    <div class="agent-item ${current && current.id === a.id ? 'active' : ''}" onclick="selectAgent('${a.id}')">
      <span class="avatar-chip">${(a.name || '?').slice(0, 1)}</span><span class="nm">${a.name}</span>
    </div>`).join('') || '<div class="empty">还没有智能体</div>';
  if (!current && agents.length) selectAgent(agents[0].id);
}

function selectAgent(id) {
  current = agents.find(a => a.id === id);
  if (!current) return;
  document.getElementById('title').textContent = current.name;
  document.getElementById('f-name').value = current.name || '';
  document.getElementById('f-persona').value = current.persona || '';
  renderPersonaPresets();
  onPersonaInput();
  document.getElementById('f-model').value = current.model || 'qwen2.5:7b';
  document.getElementById('f-voice').value = current.voice || 'zh-CN-XiaoxiaoNeural';
  document.getElementById('f-wake').value = current.wake_word || '';
  document.getElementById('f-kb').checked = !!current.kb_enabled;
  document.getElementById('f-topk').value = current.kb_topk || 3;
  document.getElementById('f-mem').checked = !!current.memory_enabled;
  const temp = current.temperature != null ? current.temperature : 0.7;
  const tEl = document.getElementById('f-temp');
  if (tEl) { tEl.value = temp; document.getElementById('tempVal').textContent = (+temp).toFixed(1); }
  loadModels();
  loadVoices();
  loadChatHistory();
  loadAgents();
  if (currentTab === 'logs') loadLogs();
  if (currentTab === 'memory') loadMemory();
  if (currentTab === 'kb') loadKB();
}

function collect() {
  return {
    name: document.getElementById('f-name').value,
    persona: document.getElementById('f-persona').value,
    model: document.getElementById('f-model').value,
    voice: document.getElementById('f-voice').value,
    wake_word: document.getElementById('f-wake').value,
    kb_enabled: document.getElementById('f-kb').checked,
    kb_topk: parseInt(document.getElementById('f-topk').value) || 3,
    memory_enabled: document.getElementById('f-mem').checked,
    temperature: parseFloat(document.getElementById('f-temp').value) || 0.7,
  };
}

function saveSoon() {
  if (!current) return;
  setSaveState('修改中…', 'dirty');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    await api('/api/agents/' + current.id, {method: 'PUT', body: JSON.stringify(collect())});
      setSaveState('已自动保存 ' + new Date().toLocaleTimeString('zh-CN', {hour12: false}), 'done');
    const s = document.getElementById('saved');
    s.classList.add('show'); setTimeout(() => s.classList.remove('show'), 1200);
    const idx = agents.findIndex(a => a.id === current.id);
    if (idx >= 0) agents[idx] = Object.assign(agents[idx], collect());
    current = agents[idx];
    document.getElementById('title').textContent = current.name;
    loadAgents();
  }, 500);
}

async function createAgent() {
  // 打开新建弹窗，名称留空由用户自己填
  document.getElementById('na-name').value = '';
  document.getElementById('na-persona').value = '';
  document.getElementById('na-msg').textContent = '';
  const box = document.getElementById('na-presets');
  box.innerHTML = Object.keys(PRESETS).map(k =>
    `<span class="chip" onclick="naPreset('${k}')">${PRESET_LABEL[k]}</span>`
  ).join('') + `<span class="chip chip-custom" onclick="naPreset('custom')">✎ 自定义</span>`;
  document.getElementById('newAgentModal').style.display = 'flex';
  setTimeout(() => document.getElementById('na-name').focus(), 50);
}

const PRESET_LABEL = {
  warm: '温柔伙伴', lively: '活泼开心果', calm: '沉稳助理',
  sassy: '毒舌损友', teacher: '耐心老师',
};

function naPreset(key) {
  const box = document.getElementById('na-persona');
  if (key === 'custom') {
    box.value = '';
    box.focus();
    return;
  }
  box.value = PRESETS[key] || '';
}

function closeNewAgent() {
  document.getElementById('newAgentModal').style.display = 'none';
}

async function confirmCreate() {
  const name = document.getElementById('na-name').value.trim();
  const persona = document.getElementById('na-persona').value.trim();
  const msg = document.getElementById('na-msg');
  if (!name) {
    msg.textContent = '请先给它起个名字';
    msg.style.color = 'var(--danger)';
    document.getElementById('na-name').focus();
    return;
  }
  const payload = {name};
  if (persona) payload.persona = persona;
  const a = await api('/api/agents', {method: 'POST', body: JSON.stringify(payload)});
  closeNewAgent();
  current = a;
  await loadAgents();
  selectAgent(a.id);
  switchTab('config');
}

async function deleteAgent() {
  if (!current || !confirm('确定删除「' + current.name + '」？')) return;
  await api('/api/agents/' + current.id, {method: 'DELETE'});
  current = null; await loadAgents();
  document.getElementById('title').textContent = '未选择智能体';
}

function switchTab(t) {
  currentTab = t;
  document.querySelectorAll('.tab').forEach(e => e.classList.toggle('active', e.dataset.tab === t));
  ['dash', 'config', 'devices', 'logs', 'memory', 'kb', 'fw', 'mcp', 'music'].forEach(k => {
    document.getElementById('tab-' + k).style.display = (k === t) ? 'block' : 'none';
  });
  if (t === 'dash') loadStats();
  if (t === 'config') { loadVoiceSettings(); setSaveState('未修改', ''); }
  if (t === 'devices') loadDevices();
  if (t === 'logs') loadLogs();
  if (t === 'memory') loadMemory();
  if (t === 'kb') loadKB();
  if (t === 'fw') loadFirmwares();
  if (t === 'mcp') loadMcp();
  if (t === 'music') loadMusic();
}


// ---------------- 设定页标签 ----------------
function switchCfgTab(name) {
  ['role', 'model', 'voice'].forEach(k => {
    const el = document.getElementById('cfg-' + k);
    if (el) el.style.display = (k === name) ? 'block' : 'none';
  });
  document.querySelectorAll('.cfg-tab').forEach(e => {
    e.classList.toggle('active', e.dataset.cfg === name);
  });
}

function setSaveState(text, cls) {
  const el = document.getElementById('saveState');
  if (!el) return;
  el.textContent = text;
  el.className = 'cfg-state' + (cls ? ' ' + cls : '');
}

async function saveConfigNow() {
  if (!current) return;
  clearTimeout(saveTimer);
  try {
    setSaveState('保存中…');
    const data = collect();
    const r = await api('/api/agents/' + current.id, {method: 'PUT', body: JSON.stringify(data)});
    const idx = agents.findIndex(a => a.id === current.id);
    if (idx >= 0) agents[idx] = Object.assign(agents[idx], r);
    current = agents[idx >= 0 ? idx : 0];
    document.getElementById('title').textContent = current.name;
    const t = new Date().toLocaleTimeString('zh-CN', {hour12: false});
    setSaveState('已保存 ' + t, 'done');
    loadAgents();
  } catch (e) {
    setSaveState('保存失败：' + e.message, 'dirty');
  }
}

function revertConfig() {
  if (!current) return;
  clearTimeout(saveTimer);
  selectAgent(current.id);
  setSaveState('已恢复到上次保存的状态', '');
}

function personaPresetsKey(id) { return 'xiaohui_persona_presets_' + (id || 'default'); }

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
  document.getElementById('personaAddBox').style.display = 'flex';
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

function onTempChange() {
  document.getElementById('tempVal').textContent = (+document.getElementById('f-temp').value).toFixed(1);
  saveSoon();
}

// ---------------- 语音设置 ----------------
const VS_DESC = {
  recognize: ['900ms 静音才判定说完，稳但慢', '600ms 静音判定说完', '350ms 就判定说完，最跟手'],
  speed: ['比正常慢 10%', '正常语速', '比正常快 25%'],
  pitch: ['比正常低 12Hz', '正常音调', '比正常高 12Hz'],
};

function vsVal(id) { return +document.getElementById(id).value; }

function onVoiceSlider() {
  const el = document.getElementById('vsHint');
  if (!el) return;
  el.textContent = [
    '识别 ' + VS_DESC.recognize[vsVal('vs-recognize')],
    '回复 ' + VS_DESC.speed[vsVal('vs-speed')],
    '音调 ' + VS_DESC.pitch[vsVal('vs-pitch')],
  ].join('　·　');
}

async function loadVoiceSettings() {
  try {
    const s = await api('/api/voice/settings');
    document.getElementById('vs-recognize').value = s.recognize ?? 2;
    document.getElementById('vs-speed').value = s.speed ?? 2;
    document.getElementById('vs-pitch').value = s.pitch ?? 1;
    onVoiceSlider();
  } catch (e) {
    const el = document.getElementById('vsHint');
    if (el) el.textContent = '读取失败：' + e.message;
  }
}

async function saveVoiceSettings() {
  const body = {
    recognize: vsVal('vs-recognize'),
    speed: vsVal('vs-speed'),
    pitch: vsVal('vs-pitch'),
  };
  try {
    const r = await api('/api/voice/settings', {method: 'POST', body: JSON.stringify(body)});
    document.getElementById('vsHint').textContent =
      `已保存：静音判定 ${r.silence_ms}ms · 语速 ${r.rate} · 音调 ${r.pitch_hz}`;
  } catch (e) {
    alert('保存失败：' + e.message);
  }
}

function resetVoiceSettings() {
  document.getElementById('vs-recognize').value = 2;
  document.getElementById('vs-speed').value = 2;
  document.getElementById('vs-pitch').value = 1;
  onVoiceSlider();
}

// ---------------- 音乐 ----------------
let musicList = [];
let queue = [];          // {title, artist, url, kind}
let qIndex = -1;
let seeking = false;

const audio = document.getElementById('musicPlayer');

function fmtTime(s) {
  if (!isFinite(s)) return '0:00';
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return m + ':' + String(r).padStart(2, '0');
}

function updateQueueInfo() {
  document.getElementById('queueInfo').textContent =
    queue.length ? `队列 ${qIndex + 1}/${queue.length}` : '';
}

function setNowPlaying(item) {
  document.getElementById('nowPlaying').textContent =
    item ? item.title + (item.artist ? ' — ' + item.artist : '') : '未在播放';
}

async function loadMusic() {
  const st = document.getElementById('musicStatus');
  try {
    const s = await api('/api/music/status');
    if (s.online) {
      st.textContent = '已连接 · ' + (s.tools || 4) + ' 个工具';
      st.style.color = 'var(--ok)';
    } else {
      st.textContent = '未连接 · ' + (s.reason || '');
      st.style.color = 'var(--warn)';
    }
  } catch (e) {
    st.textContent = '状态检查失败：' + e.message;
    st.style.color = 'var(--danger)';
  }
  loadLocalMusic();
}

async function loadLocalMusic() {
  const box = document.getElementById('localTracks');
  try {
    const d = await api('/api/music/local');
    document.getElementById('localDir').textContent =
      d.count ? `共 ${d.count} 首` : '目录为空';
    document.getElementById('localDirInline').textContent = d.dir || 'data/music';
    if (!d.count) {
      box.innerHTML = '<div class="empty">把 mp3 / flac / m4a 放进 data/music 后点「重新扫描」</div>';
      return;
    }
    box.innerHTML = d.tracks.map((x, i) => `
      <div class="chunk">
        <div class="chunk-head">
          <span class="badge-score">${i + 1}</span>
          <b style="flex:1">${escapeHtml(x.title)}</b>
          <span class="hint">${x.size_mb} MB</span>
        </div>
        <div class="hint">${escapeHtml(x.folder || '根目录')}</div>
        <div style="margin-top:8px">
          <button class="primary" onclick="playLocal(${i})">▶ 播放整首</button>
          <button onclick="enqueueLocal(${i})">＋ 加入队列</button>
        </div>
      </div>`).join('');
    window._localTracks = d.tracks;
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
  }
}

function renderMusic(d) {
  const box = document.getElementById('musicResults');
  const songs = d.songs || [];
  musicList = songs;
  if (!songs.length) {
    box.innerHTML = '<div class="empty">没有找到可试听的歌曲</div>';
    return;
  }
  box.innerHTML = songs.map((s, i) => `
    <div class="chunk">
      <div class="chunk-head">
        <span class="badge-score">${i + 1}</span>
        <b style="flex:1">${escapeHtml(s.title)}</b>
        <span class="hint">${escapeHtml(s.artist || '')}</span>
      </div>
      <div class="hint">${escapeHtml(s.album || '')}${s.duration_seconds ? ' · ' + s.duration_seconds + 's' : ''}${s.genre ? ' · ' + escapeHtml(s.genre) : ''}</div>
      <div style="margin-top:8px">
        <button class="primary" onclick="playPreview(${i})">▶ 试听 30s</button>
        <button onclick="enqueuePreview(${i})">＋ 加入队列</button>
        <a href="${s.store_url || '#'}" target="_blank" rel="noopener" style="text-decoration:none">
          <button>商店页 ↗</button></a>
      </div>
    </div>`).join('');
}

async function searchMusic() {
  const q = document.getElementById('musicQuery').value.trim();
  const limit = document.getElementById('musicLimit').value;
  const box = document.getElementById('musicResults');
  if (!q) { box.innerHTML = '<div class="empty">先输入歌名或歌手</div>'; return; }
  box.innerHTML = '<div class="empty">搜索中…</div>';
  try {
    renderMusic(await api('/api/music/search?q=' + encodeURIComponent(q) + '&limit=' + limit));
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
  }
}

async function recommendMusic(mood) {
  const box = document.getElementById('musicResults');
  box.innerHTML = '<div class="empty">推荐中…</div>';
  try {
    renderMusic(await api('/api/music/recommend?mood=' + encodeURIComponent(mood) + '&limit=5'));
  } catch (e) {
    box.innerHTML = '<div class="empty" style="color:var(--danger)">' + escapeHtml(e.message) + '</div>';
  }
}

// ---- 播放控制 ----
function playAt(i) {
  if (i < 0 || i >= queue.length) return;
  qIndex = i;
  const item = queue[i];
  audio.src = item.url;
  audio.play().catch(e => console.warn('播放失败', e));
  setNowPlaying(item);
  updateQueueInfo();
  document.getElementById('playerBtn').textContent = '⏸';
}

function playQueue(items) {
  queue = items.slice();
  qIndex = -1;
  playAt(0);
}

function playPreview(i) {
  const s = musicList[i];
  if (!s || !s.preview_url) return;
  playQueue([{title: s.title, artist: s.artist, url: s.preview_url, kind: 'preview'}]);
}

function playLocal(i) {
  const x = (window._localTracks || [])[i];
  if (!x) return;
  playQueue([{title: x.title, artist: x.folder, url: x.url, kind: 'local'}]);
}

function enqueuePreview(i) {
  const s = musicList[i];
  if (!s || !s.preview_url) return;
  queue.push({title: s.title, artist: s.artist, url: s.preview_url, kind: 'preview'});
  if (qIndex < 0) playAt(0); else updateQueueInfo();
}

function enqueueLocal(i) {
  const x = (window._localTracks || [])[i];
  if (!x) return;
  queue.push({title: x.title, artist: x.folder, url: x.url, kind: 'local'});
  if (qIndex < 0) playAt(0); else updateQueueInfo();
}

function playerToggle() {
  if (!queue.length) return;
  if (audio.paused) { audio.play(); document.getElementById('playerBtn').textContent = '⏸'; }
  else { audio.pause(); document.getElementById('playerBtn').textContent = '▶'; }
}

function playerNext() { if (qIndex + 1 < queue.length) playAt(qIndex + 1); }
function playerPrev() { if (qIndex > 0) playAt(qIndex - 1); }

function seekTo(v) {
  if (audio.duration) audio.currentTime = audio.duration * v / 100;
}

audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  document.getElementById('timeNow').textContent = fmtTime(audio.currentTime);
  document.getElementById('timeTotal').textContent = fmtTime(audio.duration);
  if (!seeking) document.getElementById('seek').value = audio.currentTime / audio.duration * 100;
});

audio.addEventListener('ended', () => {
  if (qIndex + 1 < queue.length) playAt(qIndex + 1);
  else { document.getElementById('playerBtn').textContent = '▶'; }
});

audio.addEventListener('pause', () => { document.getElementById('playerBtn').textContent = '▶'; });
audio.addEventListener('play', () => { document.getElementById('playerBtn').textContent = '⏸'; });

// ---- 语音播报 ----
async function announceNow() {
  const q = document.getElementById('musicQuery').value.trim();
  const n = musicList.length;
  let text = '';
  if (musicList[0]) {
    text = `找到${n}首歌，第一首是${musicList[0].title}，演唱者${musicList[0].artist}`;
  } else if (q) {
    text = `没有找到${q}相关的歌曲`;
  } else {
    text = '先搜索一首歌，我再念给你听';
  }
  try {
    const res = await fetch('/api/music/announce', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const url = URL.createObjectURL(await res.blob());
    const a = new Audio(url);
    a.onended = () => URL.revokeObjectURL(url);
    a.play();
  } catch (e) { alert('播报失败：' + e.message); }
}

// ---------------- MCP 工具 ----------------
async function loadMcp(force) {
  const st = document.getElementById('mcpStatus');
  try {
    const s = await api('/api/mcp/status');
    document.getElementById('mcpAdminLink').href = s.admin_url;
    if (!s.online) {
      st.textContent = '未连接 · ' + (s.reason || '');
      st.style.color = 'var(--warn)';
      document.getElementById('mcpServers').innerHTML =
        '<tr><td colspan="6" class="empty">连不上 MCP 服务（' + s.base + '）</td></tr>';
      document.getElementById('mcpTools').innerHTML = '';
      document.getElementById('mcpCalls').innerHTML = '';
      return;
    }
    st.textContent = `已连接 · ${s.servers} 个 Server · ${s.tools} 个工具` +
      (s.token_configured ? ' · 写操作令牌已配置' : '');
    st.style.color = 'var(--ok)';
  } catch (e) {
    st.textContent = '状态检查失败：' + e.message;
    st.style.color = 'var(--danger)';
    return;
  }

  // Server 列表
  try {
    const d = await api('/api/mcp/servers');
    const list = d.servers || d || [];
    document.getElementById('mcpServers').innerHTML = list.map(s => {
      const on = s.enabled !== false;
      return `<tr>
        <td>${s.name || s.id}</td>
        <td class="hint">${s.transport || '-'}</td>
        <td class="hint" style="max-width:280px;overflow:hidden;text-overflow:ellipsis">${s.url || s.command || '-'}</td>
        <td><span class="dot ${on ? 'on' : ''}"></span> ${on ? '启用' : '停用'}</td>
        <td>${s.tool_count ?? s.tools ?? '-'}</td>
        <td>
          <button onclick="mcpRefresh('${s.id}')">重连</button>
          <button onclick="mcpToggle('${s.id}', ${on ? 'false' : 'true'})">${on ? '停用' : '启用'}</button>
        </td></tr>`;
    }).join('') || '<tr><td colspan="6" class="empty">没有配置 MCP Server</td></tr>';
  } catch (e) {
    document.getElementById('mcpServers').innerHTML =
      `<tr><td colspan="6" class="empty">读取失败：${escapeHtml(e.message)}</td></tr>`;
  }

  // 工具列表
  try {
    const d = await api('/api/mcp/tools');
    const tools = d.tools || [];
    document.getElementById('mcpTools').innerHTML = tools.map(t => {
      const params = (t.inputSchema && t.inputSchema.properties)
        ? Object.keys(t.inputSchema.properties).join(', ') : '';
      return `<div class="chunk">
        <div class="chunk-head">
          <span class="badge-score">${t.read_only === false ? '副作用' : '只读'}</span>
          <b>${t.name}</b>
          <span class="hint">${t.server_name || t.server_id || ''}</span>
        </div>
        <div class="hint">${escapeHtml(t.description || '')}</div>
        ${params ? `<div class="hint" style="margin-top:4px">参数：${escapeHtml(params)}</div>` : ''}
      </div>`;
    }).join('') || '<div class="empty" style="padding:14px 0">还没有已注册的工具</div>';
  } catch (e) { /* ignore */ }

  // 调用记录
  try {
    const d = await api('/api/mcp/calls?limit=30');
    const calls = d.calls || [];
    document.getElementById('mcpCalls').innerHTML = calls.map(c => {
      const t = c.timestamp || c.time || c.at || '';
      const when = t ? new Date(typeof t === 'number' ? t * 1000 : t).toLocaleString() : '-';
      const args = typeof c.arguments === 'object' ? JSON.stringify(c.arguments) : (c.arguments || '');
      return `<tr>
        <td class="hint">${when}</td>
        <td>${c.tool || c.name || '-'}</td>
        <td class="hint" style="max-width:260px;overflow:hidden;text-overflow:ellipsis">${escapeHtml(args).slice(0, 80)}</td>
        <td>${c.ok === false || c.error ? '<span style="color:var(--danger)">失败</span>' : '成功'}</td>
        <td class="hint">${c.duration_ms != null ? c.duration_ms + ' ms' : '-'}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="5" class="empty">还没有调用记录</td></tr>';
  } catch (e) { /* ignore */ }
}

async function mcpRefresh(id) {
  try {
    await api('/api/mcp/servers/' + id + '/refresh', {method: 'POST'});
    loadMcp();
  } catch (e) { alert('重连失败：' + e.message); }
}

async function mcpToggle(id, enabled) {
  try {
    await api('/api/mcp/servers/' + id, {method: 'PATCH',
      body: JSON.stringify({enabled: enabled === true || enabled === 'true'})});
    loadMcp();
  } catch (e) { alert('操作失败：' + e.message); }
}

// ---------------- 概览 ----------------
async function loadStats() {
  let s;
  try {
    s = await api('/api/stats');
  } catch (e) {
    return;
  }

  document.getElementById('s-devices').textContent = s.devices.online + ' / ' + s.devices.total;
  document.getElementById('s-devices-sub').textContent =
    `在线 / 总数 · 已绑定 ${s.devices.bound} 台`;

  document.getElementById('s-today').textContent = s.chats.today;
  document.getElementById('s-today-sub').textContent = `累计 ${s.chats.turns} 轮 · 日志 ${s.logs} 条`;

  document.getElementById('s-docs').textContent = s.kb.docs;
  document.getElementById('s-docs-sub').textContent = s.kb.enabled
    ? `${s.kb.chunks} 个切片 · ${s.kb.embed}`
    : '知识库未连接';

  const m = s.model;
  document.getElementById('s-model').textContent = m.online ? '正常' : '未接入';
  document.getElementById('s-model').style.color = m.online ? 'var(--ok)' : 'var(--warn)';
  document.getElementById('s-model-sub').textContent = m.online
    ? `${m.provider} · ${m.models.length} 个模型`
    : (m.hint || '');

  const days = s.recent || [];
  const max = Math.max(1, ...days.map(d => d.count));
  const total = days.reduce((a, b) => a + b.count, 0);
  document.getElementById('s-chart-total').textContent = `共 ${total} 轮`;
  document.getElementById('s-bars').innerHTML = days.map(d => `
    <div class="bar-item">
      <span class="cnt">${d.count || ''}</span>
      <div class="bar-fill" style="height:${Math.max(4, Math.round(d.count / max * 88))}%"></div>
      <span class="day">${d.date.slice(3)}</span>
    </div>`).join('');

  document.getElementById('s-agent-count').textContent = s.agents + ' 个';
  document.getElementById('s-agents').innerHTML = agents.map(a => `
    <div class="row" style="padding:8px 0;border-bottom:1px solid var(--line)">
      <span class="avatar-chip">${(a.name || '?').slice(0, 1)}</span>
      <div>
        <div>${a.name}</div>
        <div class="hint">${a.model || '未设模型'} · ${a.wake_word || '无唤醒词'}</div>
      </div>
    </div>`).join('') || '<div class="empty" style="padding:16px 0">还没有智能体</div>';
}

// ---------------- 固件 ----------------
async function loadFirmwares() {
  const d = await api('/api/firmware');
  document.getElementById('fwBody').innerHTML = (d.firmwares || []).map(f => `
    <tr><td><code>${f.version}</code></td><td class="hint">${f.filename}</td>
    <td>${(f.size / 1048576).toFixed(2)} MB</td>
    <td class="hint">${new Date(f.created_at * 1000).toLocaleString()}</td>
    <td><button class="danger" onclick="deleteFirmware('${f.id}')">删除</button></td></tr>
  `).join('') || '<tr><td colspan="5" class="empty">还没有固件。上传一个 bin，设备开机会自动升级。</td></tr>';
}

async function uploadFirmware() {
  const file = document.getElementById('fwFile').files[0];
  const ver = document.getElementById('fwVersion').value.trim();
  const msg = document.getElementById('fwMsg');
  if (!file) { msg.textContent = '请选择 bin 文件'; return; }
  msg.textContent = '上传中…';
  const fd = new FormData();
  fd.append('file', file);
  fd.append('version', ver);
  try {
    const r = await fetch('/api/firmware', {method: 'POST', body: fd});
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.statusText);
    msg.textContent = `已上传 ${j.version}`;
    msg.style.color = 'var(--ok)';
    document.getElementById('fwFile').value = '';
    loadFirmwares();
  } catch (e) {
    msg.textContent = '失败：' + e.message;
    msg.style.color = 'var(--danger)';
  }
}

async function deleteFirmware(id) {
  if (!confirm('删除这个固件？')) return;
  await api('/api/firmware/' + id, {method: 'DELETE'});
  loadFirmwares();
}

async function loadDevices() {
  const d = await api('/api/devices');
  const agentName = id => {
    const a = agents.find(x => x.id === id);
    return a ? a.name : '—';
  };
  document.getElementById('deviceBody').innerHTML = d.devices.map(x => `
    <tr><td><span class="dot ${x.online ? 'on' : ''}"></span> ${x.online ? '在线' : '离线'}</td>
    <td>${x.name || '-'}</td><td>${x.mac}</td>
    <td><code>${x.code || '-'}</code></td>
    <td>${x.bound ? agentName(x.agent_id) : '<span class="hint">未绑定</span>'}</td>
    <td>${x.firmware || '-'}</td>
    <td>${x.last_seen ? new Date(x.last_seen * 1000).toLocaleString() : '-'}</td>
    <td>${x.bound ? `<button class="danger" onclick="unbindDevice('${x.id}')">解绑</button>` : ''}</td></tr>
  `).join('') || '<tr><td colspan="8" class="empty">暂无设备。设备开机后会自动出现在这里。</td></tr>';

  const sel = document.getElementById('bindAgent');
  sel.innerHTML = agents.map(a => `<option value="${a.id}">${a.avatar} ${a.name}</option>`).join('');
}

async function unbindDevice(id) {
  if (!confirm('解除这台设备的绑定？解除后需要重新输入激活码。')) return;
  await api('/api/devices/' + id + '/unbind', {method: 'POST'});
  loadDevices();
}

async function bindDevice() {  const code = document.getElementById('bindCode').value.trim();
  const agentId = document.getElementById('bindAgent').value;
  const msg = document.getElementById('bindMsg');
  if (!code) { msg.textContent = '请先输入激活码'; return; }
  try {
    const dev = await api('/api/devices/bind', {method: 'POST',
      body: JSON.stringify({code, agent_id: agentId})});
    msg.textContent = `已绑定 ${dev.mac}`;
    msg.style.color = 'var(--ok)';
    loadDevices();
  } catch (e) {
    msg.textContent = '绑定失败：' + e.message;
    msg.style.color = 'var(--danger)';
  }
}

async function loadLogs() {
  const q = current ? ('?agent_id=' + current.id) : '';
  const d = await api('/api/logs' + q);
  document.getElementById('logList').innerHTML = d.logs.map(x => `
    <div class="log ${x.role}"><div class="who">${x.role} · ${new Date(x.at * 1000).toLocaleTimeString()}</div>
    <div>${x.text.replace(/</g, '&lt;')}</div></div>
  `).join('') || '<div class="empty">暂无日志</div>';
}

async function loadMemory() {
  if (!current) return;
  const d = await api('/api/agents/' + current.id + '/memory');
  if (!d.enabled) {
    document.getElementById('memoryList').innerHTML =
      `<div class="empty">记忆服务未连接（${d.reason || '未配置 KB_URL'}）</div>`;
    return;
  }
  const facts = d.facts || [];
  document.getElementById('memoryList').innerHTML = facts.length ? facts.map(f => `
    <div class="card"><div class="row"><b>${f.slot}</b><span class="hint">${f.kind}</span>
    <span class="hint" style="margin-left:auto">置信度 ${f.confidence}</span></div>
    <div>${f.value}</div></div>
  `).join('') : '<div class="empty">还没有记忆。跟它多聊聊。</div>';
}

// ---------------- 试聊（多轮） ----------------
function chatSessionId() {
  let s = localStorage.getItem('kx_session_id');
  if (!s) {
    s = 's' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem('kx_session_id', s);
  }
  return s;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderChat(messages) {
  const box = document.getElementById('chatLog');
  if (!messages || !messages.length) {
    box.innerHTML = '<div class="empty" style="padding:20px 0">还没有对话</div>';
    return;
  }
  box.innerHTML = messages.map(m => `
    <div class="msg ${m.role}">
      <div class="bubble">${escapeHtml(m.content)}</div>
    </div>`).join('');
  box.scrollTop = box.scrollHeight;
}

async function loadChatHistory() {
  if (!current) return;
  try {
    const d = await api(`/api/agents/${current.id}/chat/history?session_id=${chatSessionId()}`);
    renderChat(d.messages || []);
  } catch (e) { /* ignore */ }
}

async function sendChat() {
  if (!current) return;
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  const sid = chatSessionId();
  const box = document.getElementById('chatLog');

  // 先把用户消息显示出来
  const cur = await api(`/api/agents/${current.id}/chat/history?session_id=${sid}`).catch(() => ({messages: []}));
  renderChat((cur.messages || []).concat([{role: 'user', content: text}]));

  // 占位气泡，边收边渲染
  const row = document.createElement('div');
  row.className = 'msg assistant';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.style.color = 'var(--muted)';
  bubble.textContent = '思考中…';
  row.appendChild(bubble);
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;

  let acc = '';
  let started = false;
  try {
    const res = await fetch(`/api/agents/${current.id}/chat/stream`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, session_id: sid}),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        const data = line.slice(5).trim();
        if (data === '[DONE]') continue;
        let obj;
        try { obj = JSON.parse(data); } catch (e) { continue; }
        if (obj.error) {
          bubble.style.color = 'var(--danger)';
          bubble.textContent = '模型调用失败：' + obj.error;
        } else if (obj.delta) {
          if (!started) { started = true; bubble.style.color = ''; bubble.textContent = ''; }
          acc += obj.delta;
          bubble.textContent = acc;
          box.scrollTop = box.scrollHeight;
        }
      }
    }
    if (!acc && !started) {
      bubble.style.color = 'var(--muted)';
      bubble.textContent = '（模型没有返回内容）';
    }
    if (currentTab === 'logs') loadLogs();
  } catch (e) {
    bubble.style.color = 'var(--danger)';
    bubble.textContent = '请求失败：' + e.message;
  }
}

async function resetChat() {
  if (!current) return;
  await api('/api/agents/' + current.id + '/chat/reset',
    {method: 'POST', body: JSON.stringify({session_id: chatSessionId()})});
  renderChat([]);
}

// ---------------- 知识库 ----------------
async function loadKB() {
  const st = await api('/api/kb/status');
  const badge = document.getElementById('kbStatus');
  if (st.enabled) {
    badge.textContent = `已连接 · embedding=${st.embed_backend} · 向量=${st.vector_backend} · ${st.docs} 篇`;
    badge.style.color = 'var(--ok)';
  } else {
    badge.textContent = '未连接：' + (st.reason || '未配置 KB_URL');
    badge.style.color = 'var(--warn)';
  }
  const d = await api('/api/kb/docs');
  document.getElementById('kbBody').innerHTML = (d.docs || []).map(x => `
    <tr><td><span class="link" onclick="openChunks('${x.id}', '${(x.title || '').replace(/'/g, '')}')">${x.title || '-'}</span></td>
    <td class="hint">${x.source || '-'}</td>
    <td>${x.chunks}</td><td class="hint">${new Date(x.created_at * 1000).toLocaleString()}</td>
    <td><button class="danger" onclick="deleteKbDoc('${x.id}')">删除</button></td></tr>
  `).join('') || '<tr><td colspan="5" class="empty">还没有文档</td></tr>';
}

// ---------------- 分段预览 ----------------
async function openChunks(docId, title) {
  const panel = document.getElementById('chunkPanel');
  const list = document.getElementById('chunkList');
  document.getElementById('chunkTitle').textContent = '《' + title + '》的分段';
  list.innerHTML = '<div class="empty" style="padding:16px 0">加载中…</div>';
  panel.style.display = 'block';
  try {
    const d = await api('/api/kb/docs/' + docId + '/chunks');
    const chunks = d.chunks || [];
    if (!chunks.length) {
      list.innerHTML = '<div class="empty" style="padding:16px 0">这篇文档没有切片</div>';
      return;
    }
    const maxChars = Math.max(...chunks.map(c => c.chars));
    const minChars = Math.min(...chunks.map(c => c.chars));
    let html = `<div class="hint" style="margin-bottom:10px">
      共 ${chunks.length} 段 · 最短 ${minChars} 字 · 最长 ${maxChars} 字
    </div>`;
    html += chunks.map(c => {
      const ratio = maxChars ? Math.round(c.chars / maxChars * 100) : 0;
      return `<div class="chunk">
        <div class="chunk-head">
          <span>#${c.ord + 1}</span>
          <span class="hint">${c.chars} 字</span>
          <span class="bar"><i style="width:${ratio}%"></i></span>
        </div>
        <div class="chunk-body">${escapeHtml(c.text)}</div>
      </div>`;
    }).join('');
    list.innerHTML = html;
    panel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  } catch (e) {
    list.innerHTML = '<div class="empty" style="padding:16px 0;color:var(--danger)">加载失败：' + escapeHtml(e.message) + '</div>';
  }
}

function closeChunks() {
  document.getElementById('chunkPanel').style.display = 'none';
}

// ---------------- 检索测试 ----------------
async function testSearch() {
  const q = document.getElementById('kbQuery').value.trim();
  const k = parseInt(document.getElementById('kbTopk').value) || 5;
  const box = document.getElementById('searchResult');
  if (!q) { box.innerHTML = '<span class="hint">先输入问题</span>'; return; }
  box.innerHTML = '<span class="hint">检索中…</span>';
  try {
    const d = await api('/api/kb/search', {method: 'POST',
      body: JSON.stringify({query: q, top_k: k})});
    const hits = d.hits || [];
    if (!hits.length) {
      box.innerHTML = '<div class="empty" style="padding:14px 0">没有命中任何片段</div>';
      return;
    }
    const maxScore = Math.max(...hits.map(h => h.score), 0.0001);
    box.innerHTML = `<div class="hint" style="margin-bottom:10px">命中 ${hits.length} 段</div>` +
      hits.map((h, i) => {
        const pct = Math.max(2, Math.round(h.score / maxScore * 100));
        const isTop = i === 0;
        return `<div class="chunk" ${isTop ? 'style="border-color:var(--accent2)"' : ''}>
          <div class="chunk-head">
            <span class="badge-score">${h.score.toFixed(3)}</span>
            <span class="hint">${escapeHtml(h.title || h.source || '')} · 第 ${(h.ord ?? 0) + 1} 段</span>
            <span class="bar"><i style="width:${pct}%"></i></span>
          </div>
          <div class="chunk-body">${escapeHtml(h.text)}</div>
        </div>`;
      }).join('');
  } catch (e) {
    box.innerHTML = '<span class="hint" style="color:var(--danger)">检索失败：' + escapeHtml(e.message) + '</span>';
  }
}

async function uploadFiles(files) {
  const msg = document.getElementById('kbMsg');
  for (const f of files) {
    msg.textContent = '上传中：' + f.name;
    const fd = new FormData();
    fd.append('file', f);
    try {
      const r = await fetch('/api/kb/upload', {method: 'POST', body: fd});
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.statusText);
      msg.textContent = `已导入 ${j.title}（${j.chunks} 个切片）`;
    } catch (e) {
      msg.textContent = '失败：' + e.message;
    }
  }
  loadKB();
}

async function ingestText() {
  const title = document.getElementById('kbTitle').value.trim();
  const text = document.getElementById('kbText').value.trim();
  const msg = document.getElementById('kbMsg');
  if (!title || !text) { msg.textContent = '标题和正文都要填'; return; }
  try {
    const j = await api('/api/kb/ingest_text', {method: 'POST', body: JSON.stringify({title, text})});
    msg.textContent = `已导入 ${j.title}（${j.chunks} 个切片）`;
    document.getElementById('kbText').value = '';
    loadKB();
  } catch (e) { msg.textContent = '失败：' + e.message; }
}

async function deleteKbDoc(id) {
  if (!confirm('删除这篇文档？')) return;
  await api('/api/kb/docs/' + id, {method: 'DELETE'});
  loadKB();
}

(function initDrop() {
  const z = document.getElementById('dropZone');
  const inp = document.getElementById('fileInput');
  if (!z) return;
  z.addEventListener('click', () => inp.click());
  inp.addEventListener('change', () => { if (inp.files.length) uploadFiles(inp.files); inp.value = ''; });
  ['dragenter', 'dragover'].forEach(ev => z.addEventListener(ev, e => {
    e.preventDefault(); z.style.borderColor = 'var(--accent)';
  }));
  ['dragleave', 'drop'].forEach(ev => z.addEventListener(ev, e => {
    e.preventDefault(); z.style.borderColor = 'var(--line2)';
  }));
  z.addEventListener('drop', e => {
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });
})();

loadAgents().then(() => { loadVoices(); switchTab('dash'); });
