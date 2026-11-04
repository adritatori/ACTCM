/* ACTCM Explorer. Plain JavaScript, no framework. Every number comes from data/counts.json or data/tasks.json. */
(function () {
  "use strict";
  var SETTINGS = [], HASH_NAME = {}, NAME_HASH = {};   // filled from counts.json (config/publish.yml decides which settings exist)
  var state = { setting: "all", steps: false, atlas: false, panel: null };
  var D = {}; // counts, tasks, tiers, links, byUid, tacticName

  function $(sel, root) { return (root || document).querySelector(sel); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== false && attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c !== null && c !== undefined) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function inSetting(uid) { return state.setting === "all" || uid.indexOf(state.setting + "/") === 0; }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  /* ---------- hash state: #setting-vllm&steps&atlas ---------- */
  function readHash() {
    var s = { setting: "all", steps: false, atlas: false };
    location.hash.replace(/^#/, "").split("&").forEach(function (tok) {
      if (tok.indexOf("setting-") === 0 && NAME_HASH[tok.slice(8)]) s.setting = NAME_HASH[tok.slice(8)];
      else if (tok === "steps") s.steps = true;
      else if (tok === "atlas") s.atlas = true;
    });
    state.setting = s.setting; state.steps = s.steps && !s.atlas; state.atlas = s.atlas;
  }
  function writeHash() {
    var t = ["setting-" + HASH_NAME[state.setting]];
    if (state.steps && !state.atlas) t.push("steps");
    if (state.atlas) t.push("atlas");
    var h = "#" + t.join("&");
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  /* ---------- data helpers ---------- */
  function tasksIn() { return D.tasks.filter(function (t) { return inSetting(t.uid); }); }
  function tacticTasks(tid) {
    return tasksIn().filter(function (t) { return t.primary_tactic === tid || (state.steps && t.step_tactics.indexOf(tid) >= 0); });
  }
  function summary() { return D.counts.summary_by_setting[state.setting]; }
  function tierLabel(id) { var t = D.tiers.tiers.filter(function (x) { return x.id === id; })[0]; return t ? t.label : id; }
  function tierPlain(id) { var t = D.tiers.tiers.filter(function (x) { return x.id === id; })[0]; return t ? t.plain : ""; }
  var TIER_MARK = { draft_needs_human_review: "◌ ", ai_cross_checked: "◐ ", reviewed: "● ", adjudicated: "◉ " };
  function tierBadge(id) { return el("span", { "class": "badge t-" + id, title: tierPlain(id), text: (TIER_MARK[id] || "") + tierLabel(id) }); }

  /* ---------- summary strip ---------- */
  function renderSummary() {
    var s = summary(), box = $("#summary"); clear(box);
    var covered = state.steps ? s.tactics_covered_with_steps : s.tactics_covered_primary;
    var gaps = state.steps ? s.gap_ids_with_steps : s.gap_ids_primary;
    var gapNames = gaps.map(function (g) { return D.tacticName[g]; }).join(", ") || "none";
    var items;
    if (state.atlas) {
      var a = D.counts.atlas.summary_by_setting[state.setting];
      items = [
        [s.tasks, "tasks"],
        [a.tasks_with_atlas_label, "tasks with an ATLAS label (target is an AI system)"],
        [a.tactics_with_task + " of " + a.tactics_total, "ATLAS tactics with at least 1 task (a low number here is by design, not a gap claim)"],
        [s.template_share_percent + "%", "repeated template tasks (" + s.template_tasks + " tasks)"],
        [s.ambiguous_labels, "labels marked ambiguous"]
      ];
    } else {
      items = [
        [s.tasks, "tasks"],
        [covered + " of " + s.tactics_total, "tactics with at least 1 task"],
        [gaps.length, (state.setting === "all" ? "gap tactics (0 tasks): " : "gaps in this setting (0 tasks): ") + gapNames],
        [s.template_share_percent + "%", "repeated template tasks (" + s.template_tasks + " tasks)"],
        [s.ambiguous_labels, "labels marked ambiguous"]
      ];
    }
    if (s.planned_scorer_tasks > 0) items.push([s.planned_scorer_tasks, "tasks whose upstream scorer is only planned"]);
    items.forEach(function (it) { box.appendChild(el("li", {}, [el("span", { "class": "n", text: String(it[0]) }), el("span", { "class": "l", text: it[1] })])); });
    var tb = $("#tiers"); clear(tb);
    D.tiers.tiers.forEach(function (t) {
      tb.appendChild(el("li", {}, [el("span", { "class": "n", text: String(s.tiers[t.id]) + " " }), tierBadge(t.id),
        el("div", { "class": "small", text: t.plain })]));
    });
  }

  /* ---------- matrix ---------- */
  function renderMatrix() {
    var m = $("#matrix"); clear(m);
    var rows = state.atlas ? atlasRows() : attackRows();
    var max = Math.max.apply(null, rows.map(function (r) { return r.n; }).concat([1]));
    rows.forEach(function (r) {
      var col = el("section", { "class": "tactic" + (r.n === 0 ? " gap" : ""), "aria-labelledby": "h-" + r.id });
      col.appendChild(el("h3", { id: "h-" + r.id }, [el("button", { "class": "tactic-btn", type: "button", "data-tactic": r.id, onclick: function () { showTactic(r.id); } },
        [r.name, el("span", { "class": "tid", text: r.id })])]));
      var cnt = el("p", { "class": "tcount" }, [el("strong", { text: String(r.n) }), " " + (r.n === 1 ? "task" : "tasks")]);
      if (r.sub) cnt.appendChild(el("span", { "class": "small", text: " (" + r.sub + ")" }));
      col.appendChild(cnt);
      col.appendChild(el("div", { "class": "bar", "aria-hidden": "true" }, [el("i", { style: "width:" + Math.round(100 * r.n / max) + "%" })]));
      if (r.n === 0) col.appendChild(el("p", { "class": "gapnote", text: state.atlas ? "0 tasks here (ATLAS labels are rare by design)" : (state.setting === "all" ? "0 tasks: gap (untested)" : "0 tasks: gap in this setting (untested)") }));
      var ul = el("ul", { "class": "techs" });
      r.techs.forEach(function (t) {
        ul.appendChild(el("li", {}, [el("button", { type: "button", "class": "techbtn" + (t.alt ? " alt" : ""), onclick: t.onclick },
          [el("span", { text: t.label }), el("b", { text: String(t.n) })])]));
      });
      col.appendChild(ul);
      m.appendChild(col);
    });
    $("#matrix-title").textContent = state.atlas ? "MITRE ATLAS matrix (16 tactics)" : "MITRE ATT&CK\u00AE matrix (15 tactics)";
    $("#matrix-help").textContent = state.atlas
      ? "ATLAS labels are only given where the target is an AI system (rule R7), so most ATLAS tactics show 0 here by design. This is not a coverage claim."
      : (state.steps ? "Counting each task once under its main tactic and once under each tactic of its required steps."
                     : "Counting each task once, under its main tactic (the end goal its scorer checks).");
  }
  function attackRows() {
    var key = state.steps ? "with_steps" : "primary", sk = state.setting;
    return D.counts.tactics.map(function (t) {
      var n = t[key][sk];
      var techs = D.counts.techniques.filter(function (x) { return x.tactic === t.id; }).map(function (x) {
        var c = sk === "all" ? x.count : x.by_setting[sk];
        return { id: x.id, n: c, label: x.id + " " + x.name, onclick: function () { showTechnique(x); } };
      }).filter(function (x) { return x.n > 0; });
      var prim = tasksIn().filter(function (k) { return k.primary_tactic === t.id; });
      var nulls = prim.filter(function (k) { return !k.technique; });
      if (nulls.length) techs.push({ n: nulls.length, alt: true, label: "No ATT&CK technique fits", onclick: function () { showList("No MITRE ATT&CK\u00AE technique fits, " + t.name, nulls); } });
      var via = state.steps ? tasksIn().filter(function (k) { return k.primary_tactic !== t.id && k.step_tactics.indexOf(t.id) >= 0; }) : [];
      if (via.length) techs.push({ n: via.length, alt: true, label: "Counted via required steps", onclick: function () { showList("Counted via required steps, " + t.name, via); } });
      return { id: t.id, name: t.name, n: n, techs: techs, sub: state.steps && via.length ? (n - via.length) + " main + " + via.length + " via steps" : "" };
    });
  }
  function atlasRows() {
    return D.counts.atlas.tactics.map(function (t) {
      var uids = {};
      D.counts.atlas.techniques.forEach(function (x) {
        if (x.tactics.indexOf(t.id) >= 0) x.task_uids.forEach(function (u) { if (inSetting(u)) uids[u] = 1; });
      });
      var techs = D.counts.atlas.techniques.filter(function (x) { return x.tactics.indexOf(t.id) >= 0; }).map(function (x) {
        var us = x.task_uids.filter(inSetting);
        return { n: us.length, label: x.id + " " + x.name, onclick: function () { showAtlas(x, us); } };
      }).filter(function (x) { return x.n > 0; });
      return { id: t.id, name: t.name, n: Object.keys(uids).length, techs: techs, sub: "" };
    });
  }

  /* ---------- panel ---------- */
  function panel() { return $("#panel"); }
  function openPanel(title, nodes) {
    var p = panel(); clear(p);
    p.appendChild(el("h2", { id: "panel-title", tabindex: "-1", text: title }));
    nodes.forEach(function (n) { p.appendChild(n); });
    p.appendChild(el("p", {}, [el("button", { "class": "linkbtn", type: "button", onclick: closePanel, text: "Close this panel" })]));
    p.className = "panel card";
    p.scrollIntoView({ block: "nearest" });
    $("#panel-title").focus({ preventScroll: true });
  }
  function closePanel() { var p = panel(); clear(p); p.className = "panel"; state.panel = null; }
  function listNodes(ts) {
    if (!ts.length) return [el("p", { "class": "callout", text: "No tasks here. This is a gap" + (state.setting === "all" ? "" : " in this setting") + ": the kind of attack is untested by the tasks in this view. It does not mean the attack is dangerous or undefended." })];
    var ul = el("ul", { "class": "tasklist" });
    ts.forEach(function (t) {
      ul.appendChild(el("li", {}, [el("button", { "class": "linkbtn", type: "button", onclick: function () { showTask(t.uid); } }, [t.id]),
        " — " + t.environment + " — " + (t.primary_tactic_name || "?") + (t.technique ? " / " + t.technique : ""), " ", tierBadge(t.label_status)]));
    });
    return [ul];
  }
  function showList(title, ts) {
    state.panel = { kind: "list" };
    openPanel(title + ": " + plural(ts.length, "task", "tasks"), listNodes(ts));
  }
  function showTactic(tid) {
    if (state.atlas) {
      var t = D.counts.atlas.tactics.filter(function (x) { return x.id === tid; })[0], uids = {};
      D.counts.atlas.techniques.forEach(function (x) { if (x.tactics.indexOf(tid) >= 0) x.task_uids.forEach(function (u) { if (inSetting(u)) uids[u] = 1; }); });
      var ts = Object.keys(uids).sort().map(function (u) { return D.byUid[u]; });
      return showList("ATLAS tactic " + t.name, ts);
    }
    showList(D.tacticName[tid] + " (" + tid + ")", tacticTasks(tid));
  }
  function showTechnique(x) {
    var ts = x.task_uids.filter(inSetting).map(function (u) { return D.byUid[u]; });
    var extra = x.also_in_tactics.length ? [el("p", { "class": "small", text: x.id + " also sits in: " + x.also_in_tactics.map(function (a) { return D.tacticName[a]; }).join(", ") + ". Here it is counted under " + D.tacticName[x.tactic] + " only, because that is each task's main tactic." })] : [];
    state.panel = { kind: "list" };
    openPanel(x.id + " " + x.name + ": " + plural(ts.length, "task", "tasks"), extra.concat(listNodes(ts)));
  }
  function showAtlas(x, us) {
    state.panel = { kind: "list" };
    openPanel(x.id + " " + x.name + ": " + plural(us.length, "task", "tasks"), listNodes(us.map(function (u) { return D.byUid[u]; })));
  }
  function row(dl, k, v) { dl.appendChild(el("dt", { text: k })); dl.appendChild(el("dd", {}, [v])); }
  function showTask(uid) {
    var t = D.byUid[uid]; if (!t) return;
    var dl = el("dl", { "class": "detail" });
    if (t.goal) row(dl, "Goal (from the source)", el("span", { text: t.goal }));
    else row(dl, "Our summary", el("span", { text: (t.our_summary || "") + "  " }, [el("span", { "class": "badge flag", text: "our summary" })]));
    if (!t.goal) row(dl, "Why no goal text", el("span", { text: "The source repository has no licence file, so its goal text is not copied here. Only our own summary (20 words or fewer) is stored." }));
    row(dl, "Source at the pinned commit", el("a", { href: t.source_url, rel: "noopener" }, [t.source_repo + "@" + t.source_sha.slice(0, 10) + " (" + t.source_tag + ")"]));
    row(dl, "Source licence", el("span", { text: t.source_licence }));
    row(dl, "Upstream category", el("span", { text: String(t.upstream_category) }));
    row(dl, "Failure type", el("span", { text: String(t.failure_type) }));
    row(dl, "Main tactic", el("span", { text: t.primary_tactic + " " + t.primary_tactic_name }));
    row(dl, "Technique", el("span", { text: t.technique ? t.technique + " " + t.technique_name + (t.technique_fit === "parent_only" ? " (parent technique only: no sub-technique fits)" : "") : "None: no ATT&CK technique fits (rule R9)" }));
    row(dl, "Required steps", el("span", { text: t.step_tactics.length ? t.step_tactics.map(function (a) { return a + " " + D.tacticName[a]; }).join("; ") : "None" }));
    row(dl, "ATLAS technique", el("span", { text: t.atlas_technique || "None (target is not an AI system, or no ATLAS technique fits)" }));
    row(dl, "Confidence", el("span", { text: t.confidence }));
    if (t.alternative) row(dl, "Alternative label", el("span", { text: t.alternative.tactic + " " + D.tacticName[t.alternative.tactic] + ": " + t.alternative.reason }));
    row(dl, "Rationale", el("span", { text: t.rationale }));
    row(dl, "Review status", el("span", {}, [tierBadge(t.label_status), " " + tierPlain(t.label_status)]));
    if (t.scorer_status === "planned_not_implemented") row(dl, "Scorer", el("span", {}, [el("span", { "class": "badge flag", text: "scorer planned, not built" }), " The upstream scorer is not implemented yet, so this label rests on the written design. It is never marked AI cross-checked."]));
    if (t.cross_check) row(dl, "Second AI check", el("span", { text: "A second AI (" + t.cross_check.rater + ") that was not shown our label: same main tactic? " + (t.cross_check.agrees_tactic ? "yes" : "no") + "; technique match: " + String(t.cross_check.technique_match).replace("_", " ") + ". This is not human review." }));
    var hist = el("ol", { "class": "small" });
    t.history.forEach(function (h) { hist.appendChild(el("li", { text: h.date + ", " + h.who + ": " + h.change + (h.reason ? " (" + h.reason + ")" : "") })); });
    row(dl, "History", hist);
    state.panel = { kind: "task", uid: uid };
    openPanel(t.id, [el("p", { "class": "small", text: t.setting + " / " + t.environment }), dl]);
  }

  /* ---------- table ---------- */
  function fillTacticFilter() {
    var s = $("#f-tactic");
    D.counts.tactics.forEach(function (t) { s.appendChild(el("option", { value: t.id, text: t.id + " " + t.name })); });
    var tf = $("#f-tier");
    D.tiers.tiers.forEach(function (t) { tf.appendChild(el("option", { value: t.id, text: t.label })); });
  }
  function renderTable() {
    var q = $("#f-search").value.trim().toLowerCase(), tac = $("#f-tactic").value, tier = $("#f-tier").value;
    var ts = tasksIn().filter(function (t) {
      if (tac && t.primary_tactic !== tac) return false;
      if (tier && t.label_status !== tier) return false;
      if (!q) return true;
      return [t.id, t.environment, t.setting, t.primary_tactic_name, t.technique || "", t.technique_name || "", t.rationale, t.our_summary || "", t.goal || ""].join(" ").toLowerCase().indexOf(q) >= 0;
    });
    var body = $("#tbody"); clear(body);
    ts.forEach(function (t) {
      var flags = [];
      if (t.confidence === "ambiguous") flags.push("ambiguous");
      if (t.scorer_status === "planned_not_implemented") flags.push("scorer planned");
      if (!t.technique) flags.push("no technique");
      if (t.template_family) flags.push("template");
      body.appendChild(el("tr", {}, [
        el("td", {}, [el("button", { "class": "linkbtn", type: "button", onclick: function () { showTask(t.uid); } }, [t.id])]),
        el("td", { text: t.setting }), el("td", { text: t.environment }),
        el("td", { text: t.primary_tactic_name }), el("td", { text: t.technique || "none" }),
        el("td", {}, [tierBadge(t.label_status)]),
        el("td", { text: flags.join(", ") || "—" })]));
    });
    $("#table-count").textContent = "Showing " + ts.length + " of " + tasksIn().length + " tasks in this view.";
  }

  /* ---------- buttons ---------- */
  function renderButtons() {
    var key = state.setting === "all" ? "combined" : state.setting;
    var l = D.links.filter(function (x) { return x.layer === key; })[0];
    var a = $("#nav-link");
    a.setAttribute("href", l ? l.open_in_navigator : "#");
    $("#nav-note").textContent = l ? "(" + l.status + ")" : "";
  }

  /* ---------- controls ---------- */
  function syncControls() {
    SETTINGS.forEach(function (s) { var r = $("#set-" + HASH_NAME[s[0]]); if (r) r.checked = state.setting === s[0]; });
    $("#mode-primary").checked = !state.steps; $("#mode-steps").checked = state.steps;
    $("#mode-steps").disabled = state.atlas; $("#mode-primary").disabled = state.atlas;
    $("#fw-attack").checked = !state.atlas; $("#fw-atlas").checked = state.atlas;
    $("#mode-note").textContent = state.atlas ? "Counting mode does not apply to ATLAS: it counts each task's one ATLAS label." : "";
  }
  function render() {
    syncControls(); writeHash(); renderSummary(); renderMatrix(); renderTable(); renderButtons();
    if (state.panel && state.panel.kind === "task") showTask(state.panel.uid); else closePanel();
  }
  function wire() {
    SETTINGS.forEach(function (s) { $("#set-" + HASH_NAME[s[0]]).addEventListener("change", function () { state.setting = s[0]; render(); }); });
    $("#mode-primary").addEventListener("change", function () { state.steps = false; render(); });
    $("#mode-steps").addEventListener("change", function () { state.steps = true; render(); });
    $("#fw-attack").addEventListener("change", function () { state.atlas = false; render(); });
    $("#fw-atlas").addEventListener("change", function () { state.atlas = true; render(); });
    ["f-search", "f-tactic", "f-tier"].forEach(function (id) { $("#" + id).addEventListener("input", renderTable); });
    window.addEventListener("hashchange", function () { readHash(); render(); });
  }

  function load(path) { return fetch(path).then(function (r) { if (!r.ok) throw new Error(path + " " + r.status); return r.json(); }); }
  Promise.all([load("data/counts.json"), load("data/tasks.json"), load("data/status_tiers.json"), load("data/navigator_links.json")]).then(function (r) {
    D.counts = r[0]; D.tasks = r[1]; D.tiers = r[2]; D.links = r[3];
    SETTINGS = [["all", "All"]].concat(D.counts.settings.map(function (x) { return [x.id, x.name]; }));
    HASH_NAME = { all: "all" }; D.counts.settings.forEach(function (x) { HASH_NAME[x.id] = x.hash; });
    Object.keys(HASH_NAME).forEach(function (k) { NAME_HASH[HASH_NAME[k]] = k; });
    D.byUid = {}; D.tasks.forEach(function (t) { D.byUid[t.uid] = t; });
    D.tacticName = {}; D.counts.tactics.forEach(function (t) { D.tacticName[t.id] = t.name; });
    fillTacticFilter(); wire(); readHash(); render();
    document.documentElement.setAttribute("data-ready", "1");
  }).catch(function (e) {
    var m = $("#load-error"); m.hidden = false;
    m.textContent = "The data files could not be loaded (" + e.message + "). If you opened this page as a file, serve the folder instead: python3 -m http.server -d site";
  });
})();
