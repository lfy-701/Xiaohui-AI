"""把自检面板挂到概览页。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CSS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\xiaohui_diag.css").read_text(encoding="utf-8")
H = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
h = H.read_text(encoding="utf-8")

if "xh-diag" in h:
    print("已存在")
    sys.exit(0)

js = r'''
<script>
(function(){
  var CSS_ADDED = false;
  function style(){ if(CSS_ADDED) return; CSS_ADDED = true; }
  function row(it){
    var ico = it.ok ? '✅' : '❌';
    var tag = it.ok ? '<span class="xh-diag-tag ok">正常</span>'
                    : '<span class="xh-diag-tag bad">异常</span>';
    return '<div class="xh-diag-row"><span class="xh-diag-ico">' + ico + '</span>' +
           '<span class="xh-diag-name">' + it.name + '</span>' +
           '<span class="xh-diag-detail">' + (it.detail || '') + '</span>' + tag + '</div>';
  }
  function cfgRow(c){
    var ico = c.ok ? '✅' : '⚠️';
    return '<div class="xh-diag-cfg"><span>' + ico + '</span>' +
           '<span style="flex:0 0 76px">' + c.name + '</span>' +
           '<code>' + (c.live || '-') + '</code>' +
           (c.ok ? '' : '<span style="color:#c0392b">（保存的是 ' + (c.saved || '-') + '）</span>') +
           '</div>';
  }
  window.xhDiagnose = async function(){
    var box = document.getElementById('xh-diag');
    if(!box) return;
    var body = box.querySelector('.xh-diag-body');
    body.innerHTML = '<div class="xh-diag-detail">检查中…</div>';
    try{
      var r = await fetch('/api/diagnose');
      var d = await r.json();
      var bad = d.items.filter(function(x){ return !x.ok; }).length;
      body.innerHTML =
        d.items.map(row).join('') +
        '<div style="margin:14px 0 6px;font-size:13px;font-weight:600;color:var(--xh-text,#1f3548)">配置生效校验</div>' +
        d.config.map(cfgRow).join('') +
        '<div class="xh-diag-detail" style="margin-top:10px">语音服务目录：' + (d.voice_dir || '-') + '</div>';
      var tag = box.querySelector('.xh-diag-sum');
      if(tag) tag.textContent = bad ? (bad + ' 项异常') : '全部正常';
      if(tag) tag.style.color = bad ? '#c0392b' : '#1a8a5c';
    }catch(e){
      body.innerHTML = '<div class="xh-diag-detail" style="color:#c0392b">检查失败：' + e.message + '</div>';
    }
  };
  function mount(){
    var page = document.getElementById('page-overview') || document.querySelector('.page.active') || document.body;
    if(document.getElementById('xh-diag')) return;
    var div = document.createElement('div');
    div.id = 'xh-diag';
    div.className = 'xh-diag';
    div.innerHTML = '<h3>🩺 系统自检 <span class="sub">点刷新重新检查</span>' +
      '<span class="xh-diag-sum" style="margin-left:auto;font-size:12.5px"></span>' +
      '<button type="button" onclick="xhDiagnose()" style="margin-left:10px;font-size:12px;padding:4px 10px">刷新</button></h3>' +
      '<div class="xh-diag-body"></div>';
    page.appendChild(div);
    xhDiagnose();
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ setTimeout(mount, 900); });
  else setTimeout(mount, 900);
  document.addEventListener('click', function(e){
    var t = e.target.closest && e.target.closest('.tab');
    if(t) setTimeout(mount, 300);
  }, true);
  setInterval(function(){ if(document.getElementById('xh-diag')) xhDiagnose(); }, 60000);
})();
</script>
'''

h = h.replace("</head>", "<style>\n" + CSS + "\n</style>\r\n</head>", 1)
h = h.replace("</body>", js + "\r\n</body>", 1)
H.write_text(h, encoding="utf-8")
print("自检面板已注入")
print("行数:", h.count("\n") + 1)
