/* 训练数据中心：总览 / 样本列表 / 来源 / 备份 */
(function () {
  var state = { samples: [], status: "", category: "", q: "" };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function badge(status) {
    var s = String(status || "pending");
    var cls = s === "approved" || s === "accepted" ? " ok"
            : (s === "rejected" || s === "flagged" ? " warn" : "");
    var txt = { pending: "待审", approved: "通过", accepted: "通过",
                rejected: "拒绝", flagged: "告警" }[s] || s;
    return '<span class="tc-badge' + cls + '">' + esc(txt) + "</span>";
  }

  async function api(path) {
    var r = await fetch(path, { credentials: "same-origin" });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  function tile(k, v) {
    return '<div class="tc-tile"><div class="k">' + esc(k) +
           '</div><div class="v">' + esc(v) + "</div></div>";
  }

  async function loadOverview() {
    var box = document.getElementById("tcTiles");
    var path = document.getElementById("tcPath");
    if (!box) return;
    try {
      var d = await api("/api/training-center/overview");
      if (path) path.textContent = d.review_dir || "";
      var s = d.summary || {};
      var st = s.status || {};
      box.innerHTML = tile("样本总数", s.total || 0) +
                      tile("待审核", st.pending || 0) +
                      tile("已通过", (st.approved || 0) + (st.accepted || 0)) +
                      tile("已拒绝", st.rejected || 0) +
                      tile("安全告警", s.safety_warnings || 0);
      if (!d.ready) {
        var t = document.getElementById("tcBody");
        if (t) {
          t.innerHTML = '<tr><td colspan="5"><div class="tc-empty">' +
            "还没有读到审核数据。<br>请把 <code>review_queue.jsonl</code> 和 " +
            "<code>review_state.sqlite3</code> 放到<br><code>" +
            esc(d.review_dir) + "</code><br>然后点「刷新」。" +
            "</div></td></tr>";
        }
      }
    } catch (e) {
      box.innerHTML = '<div class="tc-empty">总览加载失败：' + esc(e.message) + "</div>";
    }
  }

  async function loadSamples() {
    var body = document.getElementById("tcBody");
    if (!body) return;
    var qs = new URLSearchParams();
    if (state.status) qs.set("status", state.status);
    if (state.category) qs.set("category", state.category);
    if (state.q) qs.set("q", state.q);
    qs.set("limit", "200");
    try {
      var d = await api("/api/training-center/samples?" + qs.toString());
      var items = d.items || [];
      if (!items.length) {
        body.innerHTML = '<tr><td colspan="5"><div class="tc-empty">没有符合条件的样本</div></td></tr>';
        return;
      }
      body.innerHTML = items.map(function (s) {
        var text = s.text || s.input || s.prompt || s.content || "";
        if (text.length > 160) text = text.slice(0, 160) + "…";
        var warn = (s.safety_warnings || s.warnings) ? " ⚠" : "";
        return "<tr class=\"" + "tc-row\" data-sid=\"" + esc(s.id) + "\" style=\"cursor:pointer\">" +"<td onclick=\"event.stopPropagation()\"><input type=\"checkbox\" class=\"tc-cb\" value=\"" + esc(s.id) + "\"></td>" +
          "<td>" + esc(s.id) + "</td>" +
          "<td>" + esc(s.category || s.kind || "—") + warn + "</td>" +
          "<td>" + esc(text) + "</td>" +
          "<td>" + esc(s.source || "—") + "</td>" +
          "<td>" + badge(s.status) + "</td>" +
          "</tr>";
      }).join("");
    } catch (e) {
      body.innerHTML = '<tr><td colspan="5"><div class="tc-empty">加载失败：' +
                       esc(e.message) + "</div></td></tr>";
    }
  }

  async function loadSources() {
    var box = document.getElementById("tcSources");
    if (!box) return;
    try {
      var d = await api("/api/training-center/sources");
      var list = d.sources || [];
      box.innerHTML = list.length
        ? list.map(function (x) {
            return '<div class="tc-tile" style="display:flex;justify-content:space-between">' +
                   "<span>" + esc(x.name) + "</span><b>" + x.count + "</b></div>";
          }).join("")
        : '<div class="tc-empty">暂无来源统计</div>';
    } catch (e) {
      box.innerHTML = '<div class="tc-empty">来源加载失败</div>';
    }
  }

  async function loadBackups() {
    var box = document.getElementById("tcBackups");
    if (!box) return;
    try {
      var d = await api("/api/training-center/backups");
      var list = d.backups || [];
      box.innerHTML = list.length
        ? '<table class="tc-table"><thead><tr><th>文件</th><th>大小</th><th>时间</th></tr></thead><tbody>' +
          list.map(function (b) {
            return "<tr><td>" + esc(b.name) + "</td><td>" +
                   (b.size / 1024).toFixed(1) + " KB</td><td>" + esc(b.at) + "</td></tr>";
          }).join("") + "</tbody></table>"
        : '<div class="tc-empty">还没有备份文件</div>';
    } catch (e) {
      box.innerHTML = '<div class="tc-empty">备份列表加载失败</div>';
    }
  }

  function mount() {
    if (!document.getElementById("tcTiles")) return;
    if (window.__tcMounted) { refresh(); return; }
    window.__tcMounted = true;

    var q = document.getElementById("tcQ");
    if (q) q.addEventListener("input", function () {
      state.q = q.value.trim();
      clearTimeout(window.__tcT);
      window.__tcT = setTimeout(loadSamples, 300);
    });
    var fs = document.getElementById("tcStatus");
    if (fs) fs.addEventListener("change", function () {
      state.status = fs.value; loadSamples();
    });
  }

  function refresh() {
    loadOverview(); loadSamples(); loadSources(); loadBackups();
  }


  // ---------------- 审核操作 ----------------
  var curSample = null;

  function drawer() {
    var d = document.getElementById("tcDrawer");
    if (d) return d;
    d = document.createElement("div");
    d.id = "tcDrawer";
    d.className = "tc-drawer";
    d.innerHTML =
      '<div class="tc-drawer-head"><b id="tcDrawerId">样本</b>' +
      '<span style="flex:1"></span><button type="button" onclick="tcCloseDetail()">关闭</button></div>' +
      '<div class="tc-drawer-body" id="tcDrawerBody"></div>' +
      '<div class="tc-drawer-foot">' +
      '<textarea id="tcNote" placeholder="审核备注（可选）" rows="2"></textarea>' +
      '<div class="row" style="display:flex;gap:8px;margin-top:8px">' +
      '<button type="button" class="ok-btn" onclick="tcReview(\'approved\')">通过</button>' +
      '<button type="button" class="warn-btn" onclick="tcReview(\'rejected\')">拒绝</button>' +
      '<button type="button" onclick="tcReview(\'pending\')">退回待审</button>' +
      '</div></div>';
    document.body.appendChild(d);
    return d;
  }

  async function tcOpenDetail(sid) {
    var d = drawer();
    d.classList.add("show");
    document.getElementById("tcDrawerId").textContent = sid;
    document.getElementById("tcDrawerBody").innerHTML = '<div class="hint">加载中…</div>';
    try {
      var r = await api("/api/training-center/sample/" + encodeURIComponent(sid));
      curSample = r.sample;
      var s = curSample;
      var msgs = s.messages;
      var body = "";
      if (Array.isArray(msgs)) {
        body = msgs.map(function (m) {
          var role = m.role || m.from || "";
          var txt = m.content || m.text || "";
          return '<div class="tc-msg"><div class="who">' + esc(role) + "</div><div>" +
                 esc(txt).replace(/\n/g, "<br>") + "</div></div>";
        }).join("");
      } else {
        body = '<div class="tc-msg"><div>' +
               esc(s.text || "").replace(/\n/g, "<br>") + "</div></div>";
      }
      var meta = '<div class="tc-meta">' +
        "类别 " + esc(s.category || "—") +
        " · 来源 " + esc(s.source || "—") +
        " · 状态 " + badge(s.status) +
        (s.safety_warnings ? ' · <span class="tc-badge warn">安全告警</span>' : "") +
        "</div>";
      document.getElementById("tcDrawerBody").innerHTML = meta + body;
      document.getElementById("tcNote").value = s.reviewer_notes || s.note || "";
    } catch (e) {
      document.getElementById("tcDrawerBody").innerHTML =
        '<div class="tc-empty">加载失败：' + esc(e.message) + "</div>";
    }
  }

  function tcCloseDetail() {
    var d = document.getElementById("tcDrawer");
    if (d) d.classList.remove("show");
  }

  async function tcReview(status) {
    if (!curSample) return;
    var note = (document.getElementById("tcNote").value || "").trim();
    try {
      var r = await fetch("/api/training-center/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_id: curSample.id, status: status, note: note })
      });
      var d = await r.json();
      if (!r.ok) throw new Error(d.detail || "保存失败");
      tcCloseDetail();
      refresh();
    } catch (e) {
      alert("审核失败：" + e.message);
    }
  }

  async function tcExport() {
    var r = await fetch("/api/training-center/export?status=approved");
    if (!r.ok) { alert("还没有已通过的样本"); return; }
    var blob = await r.blob();
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "review-approved.jsonl";
    a.click();
  }

  window.tcBatch = tcBatch;
  window.tcOpenDetail = tcOpenDetail;
  window.tcCloseDetail = tcCloseDetail;
  window.tcReview = tcReview;
  window.tcExport = tcExport;
  document.addEventListener("click", function (e) {
    var tr = e.target.closest && e.target.closest("tr.tc-row");
    if (tr) { var sid = tr.getAttribute("data-sid"); if (sid) tcOpenDetail(sid); }
  }, true);

  function selectedIds() {
    return Array.prototype.slice
      .call(document.querySelectorAll(".tc-cb:checked"))
      .map(function (x) { return x.value; });
  }

  function updateSelCount() {
    var n = selectedIds().length;
    var el = document.getElementById("tcSelInfo");
    if (el) el.textContent = n ? ("已选 " + n + " 条") : "";
  }

  async function tcBatch(status) {
    var ids = selectedIds();
    if (!ids.length) { alert("先勾选样本"); return; }
    if (!confirm("把选中的 " + ids.length + " 条标记为「" + status + "」？")) return;
    try {
      var r = await fetch("/api/training-center/review-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_ids: ids, status: status })
      });
      var d = await r.json();
      if (!r.ok) throw new Error(d.detail || "批量失败");
      alert("已更新 " + d.updated + " 条");
      refresh();
    } catch (e) { alert("批量审核失败：" + e.message); }
  }

  document.addEventListener("change", function (e) {
    if (e.target && e.target.id === "tcSelAll") {
      var on = e.target.checked;
      document.querySelectorAll(".tc-cb").forEach(function (c) { c.checked = on; });
      updateSelCount();
    } else if (e.target && e.target.classList && e.target.classList.contains("tc-cb")) {
      updateSelCount();
    }
  }, true);

  window.tcRefresh = refresh;
  window.tcMount = mount;

  // 切到训练页时自动加载
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest('[data-tab="training"]');
    if (t) setTimeout(mount, 60);
  }, true);
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", function () { setTimeout(mount, 800); });
  else setTimeout(mount, 800);
})();
