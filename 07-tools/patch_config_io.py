"""P2：配置导出/导入。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "/api/config/export" not in t:
    routes = '''


# ---------------------------------------------------------------- 配置导出 / 导入

@app.get("/api/config/export")
def api_config_export():
    """导出当前智能体配置与语音运行时设置。"""
    import json as _json

    agents = store.list_agents()
    agent = store.get_agent(agents[0]["id"]) if agents else None
    voice = _read_voice_settings()
    payload = {
        "version": 1,
        "exported_at": int(time.time()),
        "agent": {
            k: agent.get(k)
            for k in ("name", "persona", "model", "voice", "wake_word",
                      "kb_enabled", "kb_topk", "memory_enabled", "temperature")
        } if agent else None,
        "voice": {
            k: voice.get(k)
            for k in ("recognize", "speed", "pitch", "voice", "model",
                      "prompt", "silence_ms", "wakeup_words")
        },
    }
    from fastapi.responses import Response

    body = _json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="xiaohui-config.json"'
        },
    )


class ConfigImportIn(BaseModel):
    agent: Dict[str, Any] = {}
    voice: Dict[str, Any] = {}


@app.post("/api/config/import")
def api_config_import(body: ConfigImportIn):
    """导入配置，覆盖当前智能体与语音设置。"""
    applied = []
    agents = store.list_agents()
    if body.agent and agents:
        aid = agents[0]["id"]
        cur = store.get_agent(aid)
        merged = dict(cur)
        for k, v in body.agent.items():
            if k in merged and v is not None:
                merged[k] = v
        store.update_agent(aid, merged)
        if merged.get("voice"):
            _sync_engine_voice(merged["voice"])
        if merged.get("model"):
            _sync_engine_model(merged["model"])
        if merged.get("persona"):
            _sync_engine_prompt(merged["persona"])
        if merged.get("wake_word"):
            _sync_engine_wakeup(merged["wake_word"])
        applied.append("智能体")

    if body.voice:
        cur = _read_voice_settings()
        for k, v in body.voice.items():
            if v is not None:
                cur[k] = v
        _write_voice_settings(cur)
        applied.append("语音设置")

    store.add_log("system", "导入配置：" + "、".join(applied or ["无"]))
    return {"ok": True, "applied": applied}
'''
    t = t.rstrip() + routes
    M.write_text(t, encoding="utf-8")
    print("已加导出/导入接口")
else:
    print("接口已存在")

# ---------- 前端按钮 ----------
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
h = H.read_text(encoding="utf-8")

if "xhExportConfig" not in h:
    js = '''
  // ---------------- 配置导出 / 导入 ----------------
  function xhExportConfig() {
    const a = document.createElement('a');
    a.href = '/api/config/export';
    a.download = 'xiaohui-config.json';
    document.body.appendChild(a); a.click(); a.remove();
    if (window.xhToast) xhToast('配置已导出', 'ok');
  }
  function xhImportConfig() {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.json,application/json';
    inp.onchange = () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const rd = new FileReader();
      rd.onload = async () => {
        try {
          const data = JSON.parse(rd.result);
          if (!data.agent && !data.voice) { alert('文件格式不对'); return; }
          if (!confirm('导入会覆盖当前配置，确定吗？')) return;
          const r = await fetch('/api/config/import', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
          });
          const d = await r.json();
          if (r.ok) { alert('已导入：' + (d.applied || []).join('、')); location.reload(); }
          else alert(d.detail || '导入失败');
        } catch (e) { alert('解析失败：' + e.message); }
      };
      rd.readAsText(f);
    };
    inp.click();
  }
'''
    anchor = "  // ---------------- 检索测试 ----------------"
    if anchor in h:
        h = h.replace(anchor, js + "\n" + anchor, 1)
        print("已加前端函数")
    else:
        print("⚠ 前端锚点未匹配")

    btn = ('<span class="hint" style="margin-left:12px"></span>'
           '<button onclick="xhImportConfig()" style="margin-left:8px">导入配置</button>'
           '<button onclick="xhExportConfig()">导出配置</button>')
    marker = '<div class="cfg-actions-btns">'
    if marker in h:
        h = h.replace(marker, marker + btn, 1)
        print("已加按钮")
    else:
        print("⚠ 按钮锚点未匹配")

    H.write_text(h, encoding="utf-8")
else:
    print("前端已存在")
