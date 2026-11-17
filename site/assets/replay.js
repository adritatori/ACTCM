/* ACTCM Replay. Plain JavaScript module, no framework. The page already holds every step as HTML;
   this script only selects, filters and plays them. Without it the step table still shows everything. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const rows = $$("tr.step-row");
const ids = rows.map(r => r.dataset.step);
const dots = new Map($$(".ladder .dot").map(d => [d.dataset.step, d]));
const cards = new Map($$(".step-detail").map(a => [a.dataset.step, a]));
const rowOf = new Map(rows.map(r => [r.dataset.step, r]));
const live = $("#live"), pos = $("#pos"), scrub = $("#scrub"), playBtn = $("#b-play");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let current = null, timer = null, held = false;

function visibleIds() { return ids.filter(id => !rowOf.get(id).hidden); }

function select(id, opts = {}) {
  if (!rowOf.has(id)) return;
  current = id;
  rows.forEach(r => r.classList.toggle("current", r.dataset.step === id));
  dots.forEach((d, k) => d.classList.toggle("current", k === id));
  cards.forEach((a, k) => { a.hidden = k !== id; });
  const empty = $("#detail-empty"); if (empty) empty.hidden = true;
  const n = ids.indexOf(id) + 1;
  scrub.value = String(n);
  pos.textContent = "step " + n + " of " + ids.length;
  const row = rowOf.get(id);
  const what = row.cells[3].firstChild.textContent.trim();
  const verdict = row.cells[4].textContent.trim();
  live.textContent = "Step " + n + " of " + ids.length + ": " + (row.cells[2].firstChild.textContent || "").trim() + ". " + verdict + ". " + what;
  if (!opts.keepHash) history.replaceState(null, "", "#step=" + id);
  const dot = dots.get(id);
  if (dot && dot.scrollIntoView && !opts.noScroll) dot.scrollIntoView({ block: "nearest", inline: "center", behavior: reduced ? "auto" : "smooth" });
}

function move(delta) {
  const vis = visibleIds();
  if (!vis.length) return false;
  let i = vis.indexOf(current);
  if (i === -1) i = delta > 0 ? -1 : vis.length;
  const j = i + delta;
  if (j < 0 || j >= vis.length) return false;
  select(vis[j]);
  return true;
}

function stop() {
  if (timer) clearInterval(timer);
  timer = null;
  playBtn.setAttribute("aria-pressed", "false");
  playBtn.textContent = "▶ Play";
}
function play() {
  if (timer) { stop(); return; }
  const vis = visibleIds();
  if (!vis.length) return;
  if (current === null || vis.indexOf(current) === vis.length - 1) select(vis[0]);
  playBtn.setAttribute("aria-pressed", "true");
  playBtn.textContent = "❚❚ Pause";
  timer = setInterval(() => { if (held) return; if (!move(1)) stop(); }, 1500);
}

/* filters */
const fT = $("#f-tactic"), fV = $("#f-verdict"), fN = $("#f-never");
function applyFilters() {
  const t = fT.value, v = fN.checked ? "not_tested" : fV.value;
  let shown = 0;
  rows.forEach(r => {
    const ok = (!t || r.dataset.tactic === t) && (!v || r.dataset.verdict === v);
    r.hidden = !ok;
    const d = dots.get(r.dataset.step); if (d) d.classList.toggle("dim", !ok);
    if (ok) shown++;
  });
  fV.disabled = fN.checked;
  $("#table-count").textContent = (t || v) ? "Showing " + shown + " of " + rows.length + " steps." : "";
  if (current && rowOf.get(current).hidden) { const vis = visibleIds(); if (vis.length) select(vis[0], { noScroll: true }); }
}
[fT, fV, fN].forEach(e => e.addEventListener("change", applyFilters));

/* wiring */
$("#b-prev").addEventListener("click", () => { stop(); move(-1); });
$("#b-next").addEventListener("click", () => { stop(); move(1); });
playBtn.addEventListener("click", play);
scrub.addEventListener("input", () => { stop(); select(ids[Number(scrub.value) - 1]); });
dots.forEach((d, id) => d.addEventListener("click", e => { e.preventDefault(); stop(); select(id, { noScroll: true }); }));
rows.forEach(r => r.addEventListener("click", e => {
  if (e.target.closest("a") && !e.target.closest("td.num")) return;       /* source links keep working */
  e.preventDefault(); stop(); select(r.dataset.step);
}));

/* play pauses while the pointer or the keyboard focus is on the ladder or the detail card */
[$(".ladder-wrap"), $("#detail")].forEach(z => {
  z.addEventListener("mouseenter", () => { held = true; });
  z.addEventListener("mouseleave", () => { held = false; });
  z.addEventListener("focusin", () => { held = true; });
  z.addEventListener("focusout", () => { held = false; });
});

/* tactic gloss on hover and on focus */
const glossLine = $("#lane-gloss"), glossDefault = glossLine.textContent;
$$(".ladder .lane-label").forEach(g => {
  const show = () => { glossLine.textContent = g.dataset.gloss; };
  const hide = () => { glossLine.textContent = glossDefault; };
  g.addEventListener("mouseenter", show); g.addEventListener("focus", show);
  g.addEventListener("mouseleave", hide); g.addEventListener("blur", hide);
});

document.addEventListener("keydown", e => {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "select" || tag === "textarea" || tag === "summary") return;
  if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); stop(); move(1); }
  else if (e.key === "ArrowLeft" || e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); stop(); move(-1); }
  else if (e.key === " " && tag !== "button" && tag !== "a") { e.preventDefault(); play(); }
});

function fromHash() {
  const m = /^#step=(s\d+)$/.exec(location.hash);
  if (m && rowOf.has(m[1])) { select(m[1], { keepHash: true }); return true; }
  return false;
}
window.addEventListener("hashchange", fromHash);

$("#player").hidden = false;
$("#filters").hidden = false;
/* With the script running, a link such as #step=s17 should open the ladder, not jump down to the table row. */
rows.forEach(r => r.removeAttribute("id"));
function toLadder() { $("#player").scrollIntoView(); const d = dots.get(current); if (d) d.scrollIntoView({ block: "nearest", inline: "center" }); }
if (fromHash()) { toLadder(); window.addEventListener("load", () => setTimeout(toLadder, 0)); }
else select(ids[0], { keepHash: true, noScroll: true });
document.documentElement.setAttribute("data-ready", "1");
