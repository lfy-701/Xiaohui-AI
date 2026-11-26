"""把「设定」页改造成标签式布局：角色 / 模型与记忆 / 语音设置。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\static\index.html")
t = F.read_text(encoding="utf-8")

start = t.index('  <section id="tab-config" style="display:none">')
end = t.index("</section>", start) + len("</section>")

NEW = '''  <section id="tab-config" style="display:none">
    <style>
      .cfg-tabs { display:flex; gap:8px; border-bottom:1px solid #e3e8ef; margin-bottom:16px; }
      .cfg-tab { padding:9px 16px; cursor:pointer; font-size:14px; color:#5a6b7b;
                 border-bottom:2px solid transparent; margin-bottom:-1px; }
      .cfg-tab.active { color:#1B6FC4; border-bottom-color:#1B6FC4; font-weight:600; }
      .cfg-card { border:1px solid #e3e8ef; border-radius:10px; padding:16px 18px; margin-bottom:14px; background:#fff; }
      .cfg-card h4 { margin:0 0 12px; font-size:14px; font-weight:600; color:#2b3a4a; }
      .cfg-card .hint { font-size:12px; color:#8a97a5; }
      .cfg-row { display:flex; align-items:center; gap:10px; }
      .cfg-switch { position:relative; display:inline-block; width:40px; height:22px; }
      .cfg-switch input { display:none; }
      .cfg-slider { position:absolute; inset:0; background:#cfd8e3; border-radius:22px; transition:.2s; }
      .cfg-slider:before { content:""; position:absolute; width:18px; height:18px; left:2px; top:2px;
                           background:#fff; border-radius:50%; transition:.2s; }
      .cfg-switch input:checked + .cfg-slider { background:#1B6FC4; }
      .cfg-switch input:checked + .cfg-slider:before { transform:translateX(18px); }
    </style>

    <div class="cfg-tabs">
      <div class="cfg-tab active" data-cfg="role" onclick="switchCfgTab('role')">角色</div>
      <div class="cfg-tab" data-cfg="model" onclick="switchCfgTab('model')">模型与记忆</div>
      <div class="cfg-tab" data-cfg="voice" onclick="switchCfgTab('voice')">语音设置</div>
    </div>

    <!-- ---------------- 角色 ---------------- -->
    <div id="cfg-role">
      <div class="cfg-card">
        <h4>角色音色</h4>
        <div class="cfg-row" style="flex-wrap:wrap">
          <select id="f-voice-group" onchange="rebuildVoices()" style="width:150px"></select>
          <select id="f-voice" onchange="saveSoon()" style="flex:1;min-width:240px">
            <option value="">— 加载中 —</option>
          </select>
          <button onclick="previewVoice()" id="voiceBtn" title="试听">▶ 试听</button>
        </div>
        <span class="hint" id="voiceHint" style="display:block;margin-top:8px"></span>
      </div>

      <div class="cfg-card">
        <div class="cfg-row" style="justify-content:space-between;margin-bottom:10px">
          <h4 style="margin:0">角色介绍</h4>
          <div class="cfg-row">
            <span class="hint">自定义</span>
            <label class="cfg-switch">
              <input type="checkbox" id="f-persona-custom" checked onchange="togglePersonaCustom()">
              <span class="cfg-slider"></span>
            </label>
          </div>
        </div>
        <div class="presets" style="margin-bottom:10px">
          <span class="chip" onclick="usePreset('warm')">温柔伙伴</span>
          <span class="chip" onclick="usePreset('lively')">活泼开心果</span>
          <span class="chip" onclick="usePreset('calm')">沉稳助理</span>
          <span class="chip" onclick="usePreset('sassy')">毒舌损友</span>
          <span class="chip" onclick="usePreset('teacher')">耐心老师</span>
        </div>
        <textarea id="f-persona" oninput="saveSoon()" rows="10"
                  style="width:100%;min-height:200px;resize:vertical"
                  placeholder="描述它叫什么、什么性格、怎么说话…"></textarea>
        <span class="hint">点上面的标签套用，套用后还能继续改。</span>
      </div>

      <div class="cfg-card">
        <h4>基本</h4>
        <div class="grid" style="max-width:none">
          <div class="field"><label>名称</label><input id="f-name" oninput="saveSoon()"></div>
          <div class="field"><label>唤醒词</label><input id="f-wake" oninput="saveSoon()"></div>
        </div>
      </div>
    </div>

    <!-- ---------------- 模型与记忆 ---------------- -->
    <div id="cfg-model" style="display:none">
      <div class="cfg-card">
        <h4>对话模型</h4>
        <div class="grid" style="max-width:none">
          <div class="field"><label>模型</label>
            <select id="f-model" onchange="saveSoon()">
              <option value="">— 加载中 —</option>
            </select>
            <span class="hint" id="modelHint"></span></div>
          <div class="field"><label>温度 <span class="hint" id="tempVal">0.7</span></label>
            <input type="range" id="f-temp" min="0" max="1.5" step="0.1" value="0.7"
                   style="accent-color:#1B6FC4" oninput="onTempChange()">
            <span class="hint">越低越稳定，越高越有发散</span></div>
        </div>
        <span class="hint" id="modelSyncHint"></span>
      </div>

      <div class="cfg-card">
        <h4>知识库与记忆</h4>
        <div class="grid" style="max-width:none">
          <div class="field"><label>知识库</label>
            <div class="switch">
              <input type="checkbox" id="f-kb" onchange="saveSoon()">
              <span class="hint">对话时检索文档，返回</span>
              <input id="f-topk" type="number" min="1" max="10" style="width:64px"
                     oninput="saveSoon()">
              <span class="hint">条</span>
            </div></div>
          <div class="field"><label>长期记忆</label>
            <div class="switch"><input type="checkbox" id="f-mem" onchange="saveSoon()">
              <span class="hint">注入用户画像与历史事实</span></div></div>
        </div>
      </div>
    </div>

    <!-- ---------------- 语音设置 ---------------- -->
    <div id="cfg-voice" style="display:none">
      <div class="cfg-card">
        <h4>响应与音调</h4>
        <div class="grid" style="grid-template-columns:repeat(3,1fr);gap:24px;max-width:none">
          <div class="field">
            <label>识别速度</label>
            <input type="range" id="vs-recognize" min="0" max="2" step="1" value="2"
                   style="accent-color:#1B6FC4" oninput="onVoiceSlider()">
            <div class="row" style="justify-content:space-between;font-size:11px;color:#888">
              <span>慢</span><span>标准</span><span>快</span>
            </div>
          </div>
          <div class="field">
            <label>回复速度</label>
            <input type="range" id="vs-speed" min="0" max="2" step="1" value="2"
                   style="accent-color:#1B6FC4" oninput="onVoiceSlider()">
            <div class="row" style="justify-content:space-between;font-size:11px;color:#888">
              <span>慢</span><span>标准</span><span>快</span>
            </div>
          </div>
          <div class="field">
            <label>回复音调</label>
            <input type="range" id="vs-pitch" min="0" max="2" step="1" value="1"
                   style="accent-color:#1B6FC4" oninput="onVoiceSlider()">
            <div class="row" style="justify-content:space-between;font-size:11px;color:#888">
              <span>低</span><span>标准</span><span>高</span>
            </div>
          </div>
        </div>
        <div class="cfg-row" style="justify-content:space-between;align-items:center;margin-top:14px">
          <span class="hint" id="vsHint"></span>
          <span class="cfg-row">
            <button onclick="resetVoiceSettings()">恢复默认</button>
            <button class="primary" onclick="saveVoiceSettings()">保存</button>
          </span>
        </div>
        <span class="hint" style="display:block;margin-top:8px">
          识别速度决定「说完多久判定结束」，回复速度控制语速。保存后下一轮对话生效。
        </span>
      </div>
    </div>

    <h3 class="sec">试聊</h3>
    <div class="card" id="chatLog" style="max-height:340px;overflow-y:auto;min-height:80px">
      <div class="empty" style="padding:20px 0">还没有对话</div>
    </div>
    <div class="chatbox">
      <input id="chatInput" placeholder="输入一句话，验证知识库/记忆/多轮上下文" onkeydown="if(event.key==='Enter')sendChat()">
      <button class="primary" onclick="sendChat()">发送</button>
      <button onclick="resetChat()">新对话</button>
    </div>
  </section>'''

t = t[:start] + NEW + t[end:]
F.write_text(t, encoding="utf-8")

# 校验
for k in ["cfg-tabs", "cfg-role", "cfg-model", "cfg-voice", "f-temp", "f-persona-custom",
          "vs-recognize", "chatLog"]:
    print(f"  {k:<20} {'OK' if k in t else '缺失'}")
