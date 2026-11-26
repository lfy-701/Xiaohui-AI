/* ===== P0 补丁：注入 CSS 与 JS ===== */
(function () {
  var F = 'D:\\AI-Companion-shared\\xiaohui-ai\\console\\static\\index.html';
  var fs = require('fs');
  var CSSFILE = 'C:\\Users\\53487\\Documents\\deepseek-harness\\default-workspace\\xiaohui_p0.css';
  var css = fs.readFileSync(CSSFILE, 'utf8');
  var html = fs.readFileSync(F, 'utf8');

  if (html.indexOf('xh-toasts') >= 0) {
    console.log('已存在，跳过');
    return;
  }

  var style = '<style>\n' + css + '\n</style>\n';

  var js = [
    '<script>',
    '(function(){',
    '  // ---------- Toast ----------',
    '  function toast(msg, kind, ms){',
    '    var box = document.getElementById("xh-toasts");',
    '    if(!box){ box = document.createElement("div"); box.id="xh-toasts"; document.body.appendChild(box); }',
    '    var el = document.createElement("div");',
    '    el.className = "xh-toast " + (kind || "info");',
    '    el.textContent = msg;',
    '    box.appendChild(el);',
    '    setTimeout(function(){ el.classList.add("out"); setTimeout(function(){ el.remove(); }, 220); }, ms || 2600);',
    '  }',
    '  window.xhToast = toast;',
    '',
    '  // ---------- 请求失败自动提示 ----------',
    '  var _fetch = window.fetch;',
    '  window.fetch = function(){',
    '    return _fetch.apply(this, arguments).then(function(r){',
    '      if(!r.ok && r.status >= 400 && r.status !== 401){',
    '        var p = (r.url || "").replace(location.origin, "");',
    '        if(p.indexOf("/api/") === 0){',
    '          r.clone().json().then(function(d){',
    '            toast((d && d.detail) || ("请求失败 " + r.status), "err", 3600);',
    '          }).catch(function(){ toast("请求失败 " + r.status, "err", 3600); });',
    '        }',
    '      }',
    '      return r;',
    '    });',
    '  };',
    '',
    '  // ---------- 按钮加载态 ----------',
    '  document.addEventListener("click", function(e){',
    '    var b = e.target.closest && e.target.closest("button");',
    '    if(!b || b.disabled || b.classList.contains("xh-busy")) return;',
    '    if(!/保存|绑定|上传|测试|刷新|发送/.test(b.textContent || "")) return;',
    '    b.classList.add("xh-busy");',
    '    setTimeout(function(){ b.classList.remove("xh-busy"); }, 1200);',
    '  }, true);',
    '',
    '  // ---------- Ctrl+S 保存 ----------',
    '  document.addEventListener("keydown", function(e){',
    '    if((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")){',
    '      e.preventDefault();',
    '      try{',
    '        if(typeof saveConfigNow === "function"){ saveConfigNow(); toast("正在保存…", "info", 1200); }',
    '        else { var btn = document.querySelector(".cfg-actions button"); if(btn) btn.click(); }',
    '      }catch(err){ toast("保存失败：" + err.message, "err"); }',
    '    }',
    '  });',
    '',
    '  // ---------- 未保存离开提醒 ----------',
    '  var dirty = false;',
    '  document.addEventListener("input", function(e){',
    '    if(e.target.closest && e.target.closest("#page-config, .cfg-card, .card")) dirty = true;',
    '  }, true);',
    '  document.addEventListener("change", function(e){',
    '    if(e.target.closest && e.target.closest("#page-config, .cfg-card, .card")) dirty = true;',
    '  }, true);',
    '  window.addEventListener("beforeunload", function(e){',
    '    if(dirty){ e.preventDefault(); e.returnValue = ""; return ""; }',
    '  });',
    '  document.addEventListener("click", function(e){',
    '    var b = e.target.closest && e.target.closest("button");',
    '    if(b && /保存/.test(b.textContent || "")) setTimeout(function(){ dirty = false; }, 1500);',
    '  }, true);',
    '',
    '  // ---------- 健康横幅 ----------',
    '  function checkHealth(){',
    '    fetch("/api/stats", {cache:"no-store"}).then(function(r){ return r.json(); }).then(function(d){',
    '      var off = [];',
    '      var llm = d.llm_online;',
    '      if(llm === undefined && d.llm && typeof d.llm === "object") llm = d.llm.online;',
    '      if(llm === false) off.push("模型服务离线（对话会超时）");',
    '      if(d.music_online === false) off.push("音乐服务未启动");',
    '      if(d.kb_online === false) off.push("知识库未启动");',
    '      var bar = document.getElementById("xh-health");',
    '      if(!bar){ bar = document.createElement("div"); bar.id = "xh-health"; document.body.appendChild(bar); }',
    '      if(off.length){ bar.textContent = "⚠ " + off.join(" · "); bar.classList.add("show"); document.body.style.paddingTop = "38px"; }',
    '      else { bar.classList.remove("show"); document.body.style.paddingTop = ""; }',
    '    }).catch(function(){',
    '      var bar = document.getElementById("xh-health");',
    '      if(!bar){ bar = document.createElement("div"); bar.id = "xh-health"; document.body.appendChild(bar); }',
    '      bar.textContent = "⚠ 控制台接口无响应"; bar.classList.add("show");',
    '    });',
    '  }',
    '  setTimeout(checkHealth, 1200);',
    '  setInterval(checkHealth, 20000);',
    '})();',
    '</script>'
  ].join('\n');

  html = html.replace('</head>', style + '</head>');
  html = html.replace('</body>', js + '\n</body>');
  fs.writeFileSync(F, html, 'utf8');
  console.log('P0 补丁已注入');
})();
