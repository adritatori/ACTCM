/* ACTCM home page tool. Plain JavaScript module, no framework.
   The matrix, the detail cards and the gap list are already in the page as HTML (they work without this script).
   This script adds: picking a box, filters, and "my own coverage" (ticks kept in this browser, shareable by link or file).
   Anything read from the address, from storage or from a loaded file is treated as untrusted: only known box keys are kept. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const mx = $("#mx");
const cells = $$(".cell", mx);
const KEYS = new Set(cells.map(c => c.dataset.key));
const cellOf = new Map(cells.map(c => [c.dataset.key, c]));
const boxes = new Map($$('.cell .mine input', mx).map(i => [i.dataset.key, i]));
const tacticBoxes = $$('.mine.all input', mx);
const cards = new Map($$(".cell-detail").map(a => [a.dataset.key, a]));
const rows = $$("#gaps .gap-row");
const live = $("#mx-live");
const STORE = "actcm-my-coverage-v1";
const MAX_FILE = 200 * 1024;
let mineOn = false;
let mine = new Set();

/* ---------- untrusted input ---------- */
function cleanKeys(list) {
  if (!Array.isArray(list)) return null;
  const out = new Set();
  for (const k of list.slice(0, 2000)) if (typeof k === "string" && KEYS.has(k)) out.add(k);
  return out;
}
function parseSaved(text) {
  let obj;
  try { obj = JSON.parse(text); } catch (e) { return null; }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return null;
  return cleanKeys(obj.covered);
}
function fromHash() {
  const m = /^#mine=([A-Za-z0-9/.,_-]*)$/.exec(location.hash);
  return m ? cleanKeys(m[1].split(",").filter(Boolean)) : null;
}
function load() { try { return parseSaved(localStorage.getItem(STORE) || ""); } catch (e) { return null; } }
function save() { try { localStorage.setItem(STORE, JSON.stringify({ version: 1, covered: Array.from(mine).sort() })); } catch (e) { /* private window: the ticks last for this visit only */ } }

/* ---------- drawing ---------- */
function isGap(c) { return Number(c.dataset.steps) > 0 && (mineOn ? !mine.has(c.dataset.key) : Number(c.dataset.tasks) === 0); }

function render() {
  document.body.classList.toggle("mine-on", mineOn);
  let gaps = 0;
  cells.forEach(c => {
    const g = isGap(c);
    c.classList.toggle("is-gap", g);
    c.classList.toggle("mine-yes", mineOn && mine.has(c.dataset.key));
    if (g) gaps++;
    const b = boxes.get(c.dataset.key); if (b) b.checked = mine.has(c.dataset.key);
  });
  tacticBoxes.forEach(tb => {
    const ks = cells.filter(c => c.dataset.key.indexOf(tb.dataset.tactic + "/") === 0).map(c => c.dataset.key);
    tb.checked = ks.length > 0 && ks.every(k => mine.has(k));
  });
  rows.forEach(r => { r.hidden = mineOn ? mine.has(r.dataset.key) : Number(r.dataset.tasks) > 0; });
  $("#mine-card").hidden = !mineOn;
  $("#mine-tools").hidden = !mineOn;
  $("#n-mine-gap").textContent = String(gaps);
  $("#gaps-title").textContent = mineOn ? "Real behaviours you do not cover" : "Real behaviours with no public test";
  $("#gaps-note").textContent = mineOn
    ? "Each line is something an AI agent did in a documented incident that you have not ticked. Tick a box in the matrix when one of your tests, monitors or guardrails covers it."
    : "Each line is something an AI agent did in a documented incident that no public test task has as its goal. Untested does not mean undefended.";
  $("#gaps-count").textContent = gaps + (gaps === 1 ? " behaviour" : " behaviours") + " listed.";
  const b = $("#b-mine");
  b.setAttribute("aria-pressed", String(mineOn));
  b.textContent = mineOn ? "Back to public tests" : "Check my own coverage";
}

function pick(key) {
  if (!cards.has(key)) return;
  cards.forEach((a, k) => { a.hidden = k !== key; });
  cells.forEach(c => c.classList.toggle("current", c.dataset.key === key));
  $("#cell-empty").hidden = true;
}

function setMine(next, why) { mine = next; save(); render(); if (why) live.textContent = why; }

/* ---------- wiring ---------- */
cells.forEach(c => $(".cellbtn", c).addEventListener("click", () => { pick(c.dataset.key); $("#cell-panel").scrollIntoView({ block: "nearest" }); }));
boxes.forEach((input, key) => input.addEventListener("change", () => {
  const next = new Set(mine); if (input.checked) next.add(key); else next.delete(key);
  setMine(next, (input.checked ? "Marked as covered: " : "Unmarked: ") + key);
}));
tacticBoxes.forEach(tb => tb.addEventListener("change", () => {
  const next = new Set(mine);
  cells.forEach(c => { if (c.dataset.key.indexOf(tb.dataset.tactic + "/") === 0) { if (tb.checked) next.add(c.dataset.key); else next.delete(c.dataset.key); } });
  setMine(next, (tb.checked ? "Marked the whole tactic as covered: " : "Unmarked the whole tactic: ") + tb.dataset.tactic);
}));
$$('input[name="show"]').forEach(r => r.addEventListener("change", () => {
  mx.classList.toggle("show-real", r.value === "real" && r.checked);
  mx.classList.toggle("show-gap", r.value === "gap" && r.checked);
}));
$("#b-mine").addEventListener("click", () => { mineOn = !mineOn; render(); live.textContent = mineOn ? "Tick the boxes your own tests, monitors or guardrails cover." : "Showing public tests."; });
$("#b-reset").addEventListener("click", () => setMine(new Set(), "Cleared your ticks."));

function download(name, type, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
$("#b-export").addEventListener("click", () => download("actcm-my-coverage.json", "application/json",
  JSON.stringify({ version: 1, note: "Boxes ticked on the ACTCM matrix (tactic/technique).", covered: Array.from(mine).sort() }, null, 1) + "\n"));
$("#f-import").addEventListener("change", ev => {
  const f = ev.target.files && ev.target.files[0];
  ev.target.value = "";
  if (!f) return;
  if (f.size > MAX_FILE) { live.textContent = "That file is too large to be a saved coverage file. Nothing was changed."; return; }
  f.text().then(t => {
    const got = parseSaved(t);
    if (!got) { live.textContent = "That file is not a saved coverage file. Nothing was changed."; return; }
    mineOn = true; setMine(got, "Loaded " + got.size + " ticked boxes.");
  }).catch(() => { live.textContent = "That file could not be read. Nothing was changed."; });
});
$("#b-link").addEventListener("click", () => {
  const url = location.origin + location.pathname + "#mine=" + Array.from(mine).sort().join(",");
  history.replaceState(null, "", url);
  const done = () => { live.textContent = "Link copied. Anyone who opens it sees your ticks."; };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, () => { live.textContent = "The link is now in the address bar. Copy it from there."; });
  else live.textContent = "The link is now in the address bar. Copy it from there.";
});

/* a spreadsheet would run a cell that starts with = + - or @, so such a cell gets a quote in front */
function cell(v) {
  v = String(v == null ? "" : v);
  if (/^[=+@]/.test(v) || /^-\D/.test(v)) v = "'" + v;
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}
$("#b-csv").addEventListener("click", () => {
  const lines = [["tactic", "technique_id", "technique", "public_tests", "incident", "step", "verdict", "what_happened", "source_url"].join(",")];
  rows.filter(r => !r.hidden).forEach(r => $$("ul li", r).forEach(li => lines.push([
    r.dataset.tactic, r.dataset.technique, r.dataset.name, r.dataset.tasks, li.dataset.incident, li.dataset.step, li.dataset.verdict,
    $(".what", li).textContent, li.dataset.url].map(cell).join(","))));
  download(mineOn ? "actcm-my-gaps.csv" : "actcm-public-test-gaps.csv", "text/csv", lines.join("\n") + "\n");
});

/* old Explorer links pointed at this page */
function forward() { if (/^#setting-/.test(location.hash)) location.replace("explorer.html" + location.hash); }
window.addEventListener("hashchange", () => { forward(); const h = fromHash(); if (h) { mineOn = true; setMine(h, "Loaded " + h.size + " ticked boxes from the link."); } });
forward();

const shared = fromHash();
const stored = load();
if (shared) { mineOn = true; mine = shared; save(); }
else if (stored) mine = stored;
$("#mx-tools").hidden = false;
$("#b-csv").hidden = false;
render();
document.documentElement.setAttribute("data-ready", "1");
