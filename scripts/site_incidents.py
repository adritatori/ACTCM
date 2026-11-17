"""Pages about incidents: Home, Incidents, one Replay page per incident, Coverage, Contribute, Review.

Every number comes from data/generated/incident_coverage.json, activity.json or counts.json. None is typed here.
Each page works without JavaScript: the step table, the verdicts and the review queue are plain HTML.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

import yaml

import common as c
import issue_forms as forms

E = html.escape
GEN = c.DATA / "generated"
ICON = {"tested_technique": "●", "tested_tactic_only": "◐", "not_tested": "○", "unclear": "?"}
GLOSS = {
    "TA0043": "Gathering information about a target before acting against it.",
    "TA0042": "Getting the tools, accounts or machines needed for an attack.",
    "TA0001": "Getting a first foothold inside the target's systems.",
    "TA0002": "Running the attacker's code on a target system.",
    "TA0003": "Keeping access so it survives restarts or clean-up.",
    "TA0004": "Gaining higher permissions than the attacker started with.",
    "TA0005": "Hiding activity so it is not noticed.",
    "TA0112": "Switching off or weakening security controls.",
    "TA0006": "Stealing passwords, keys or tokens.",
    "TA0007": "Looking around inside a system to learn what is there.",
    "TA0008": "Moving from one system to others inside the network.",
    "TA0009": "Gathering the data the attacker is after.",
    "TA0011": "Communicating with compromised systems to direct them.",
    "TA0010": "Taking data out of the target's systems.",
    "TA0040": "Damaging, changing or destroying systems or data.",
}
TERMS = {
    "monitor": "A watcher, often a weaker trusted AI model, that reads an agent's actions and scores how suspicious each one looks.",
    "side task": "A hidden harmful goal given to the agent in a safety test, to see whether the monitor notices.",
    "tactic": "The attacker's aim at one stage, for example getting data out. The catalogue used here has 15.",
    "technique": "How an attacker reaches a tactic. Each has an ID such as T1611.",
    "step": "One distinct thing the agent did, as described by a public source.",
}
PHASE = {"attack": "Attack", "detection": "Detection", "response": "Response"}
BASIS = {"stated": "Order stated by the source.", "reconstructed": "Order worked out from the source's account; not stated outright.",
         "unordered": "The source gives no order for this step."}


def load() -> tuple[dict, dict, dict]:
    cov = json.loads((GEN / "incident_coverage.json").read_text(encoding="utf-8"))
    act = json.loads((GEN / "activity.json").read_text(encoding="utf-8"))
    tiers = yaml.safe_load((c.DATA / "status_tiers.yml").read_text(encoding="utf-8"))
    return cov, act, {t["id"]: t for t in tiers["step_tiers"]}


def gloss(term: str, text: str | None = None) -> str:
    return f'<span class="gloss" tabindex="0" data-gloss="{E(TERMS[term])}">{E(text or term)}</span>'


def vlabel(cov: dict, v: str) -> str:
    return next(x["label"] for x in cov["verdicts"] if x["id"] == v)


def ico(v: str) -> str:
    """The verdict mark, drawn with CSS so it looks the same in every font. The words beside it carry the meaning."""
    return f'<span class="ico ico-{v}" aria-hidden="true"></span>'


def vchip(cov: dict, v: str) -> str:
    return f'<span class="v v-{v}">{ico(v)} {E(vlabel(cov, v))}</span>'


def badge(tiers: dict, status: str) -> str:
    t = tiers[status]
    return f'<span class="badge t-{status}" title="{E(t["plain"])}">{E(t["label"])}</span>'


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def fmt_date(d: str | None) -> str:
    if not d:
        return "date not given"
    x = datetime.strptime(d[:10], "%Y-%m-%d")
    return f"{x.day} {x.strftime('%b %Y')}"


def fmt_time(s: dict) -> str:
    t = s["time"]
    if not t:
        return "Time not given"
    out = fmt_date(t) + (f", {t[11:16]} UTC" if "T" in t else "")
    if s["time_precision"] == "window":
        out += " (start of a time window)" if "T" in t else " (within the day)"
    return out


def limits_html(cov: dict) -> str:
    return '<ol class="limits" aria-label="Limits of this comparison">' + "".join(f"<li>{E(x)}</li>" for x in cov["limits"]) + "</ol>"


def feed_html(act: dict, root: str, n: int = 6) -> str:
    rows = "".join(
        f'<li><time datetime="{E(r["date"])}">{E(r["date"])}</time> <a href="{root}incidents/{E(r["incident"])}.html">{E(r["incident_title"])}</a>: '
        f'{E(plural(r["steps"], "step"))}, {E(r["change"].replace("_", " "))} <span class="small">(by {E(r["who"])})</span></li>'
        for r in act["entries"][:n])
    return f'<ul class="feed">{rows}</ul><p class="small">{E(act["note"])}</p>'


def incident_meta(cov: dict, tiers: dict, inc: dict) -> str:
    st = " · ".join(f'{n} {E(tiers[k]["label"])}' for k, n in inc["status_counts"].items() if n)
    never = inc["verdict_counts"]["not_tested"]
    return (f'<span class="chip">{E(inc["incident_type_plain"])}</span> <span>{plural(inc["attack_steps"], "attack step")}</span> '
            f'<span class="v v-not_tested">{ico("not_tested")} {never} never tested</span> <span class="small">{st}</span>')


def cards(cov: dict, tiers: dict, root: str = "") -> str:
    out = []
    for inc in cov["incidents"]:
        d = inc["dates"]
        out.append(f'<li><article class="card"><h3><a href="{root}incidents/{E(inc["id"])}.html">{E(inc["title"])}</a></h3>'
                   f'<p class="small">{E(", ".join(inc["developer"]))} · disclosed {fmt_date(d["disclosed"])}</p><p>{E(inc["summary"])}</p>'
                   f'<p class="meta">{incident_meta(cov, tiers, inc)}</p></article></li>')
    return f'<ul class="cards">{"".join(out)}</ul>'


# ------------------------------------------------------------------------------------------- Home
def home_body(cov: dict, act: dict, tiers: dict, cn: dict) -> str:
    t = cov["totals"]
    return f"""
<h1>What real AI agents did, against what safety tests check</h1>
<ol class="story">
<li>AI labs test their safety checks by giving an agent a hidden harmful goal (a {gloss("side task")}) and seeing whether a {gloss("monitor")} notices.</li>
<li>The safety number they report only speaks for the attacks the test includes.</li>
<li>Meanwhile, real AI agents have already got into real systems.</li>
<li>We split {t["incidents"]} well-documented incidents into {plural(t["steps"], gloss("step"))}, each with a quoted source.</li>
<li>A script compares every attack step with the {t["public_tasks"]} public test tasks, using MITRE ATT&amp;CK® attack categories.</li>
<li>The result: which real moves no public test states as a goal. Untested does not mean undefended.</li>
</ol>
<ul class="strip" aria-label="Headline numbers">
<li><span class="n" id="n-incidents">{t["incidents"]}</span><span class="l">incidents, chosen for detail, not random</span></li>
<li><span class="n" id="n-attack-steps">{t["attack_steps"]}</span><span class="l">attack steps, each with a source quote</span></li>
<li><span class="n" id="n-not-tested">{t["verdict_counts"]["not_tested"]}</span><span class="l">steps with no public test in their {gloss("tactic")}</span></li>
</ul>
<p class="small">Chosen for detail, not random: these {t["incidents"]} incidents are not a sample of all incidents. Another <span id="n-unclear">{t["verdict_counts"]["unclear"]}</span> steps are marked &ldquo;{E(vlabel(cov, "unclear"))}&rdquo; because two labels are defensible and they give different answers.</p>

<h2>Open an incident</h2>
{cards(cov, tiers)}

<h2>How to read this</h2>
<ul>
<li><strong>A step</strong> is one thing an agent did, in our own words, with a short quote and a link to the source that says so.</li>
<li><strong>A verdict</strong> says whether any public test task has the same {gloss("technique")}, only the same tactic, or neither. A script works it out from the labels.</li>
<li><strong>&ldquo;{E(vlabel(cov, "not_tested"))}&rdquo;</strong> means no public task states that tactic as its goal or as a required step. It does not mean a monitor would miss it: no monitor has been run.</li>
</ul>
<div class="btns"><a class="btn primary" href="incidents.html">See the incidents</a><a class="btn" href="coverage.html">Coverage by tactic</a><a class="btn" href="explorer.html">The {cn["summary"]["tasks"]} test tasks</a></div>

<h2>Recent changes</h2>
{feed_html(act, "")}
<script>
(function () {{ function fwd() {{ if (/^#setting-/.test(location.hash)) location.replace("explorer.html" + location.hash); }}
  window.addEventListener("hashchange", fwd); fwd(); }})();   /* old Explorer links pointed at this page */
</script>
"""


# ------------------------------------------------------------------------------------------- Incidents list
def incidents_body(cov: dict, tiers: dict) -> str:
    rows = []
    for inc in cov["incidents"]:
        vc = inc["verdict_counts"]
        st = ", ".join(f'{n} {E(tiers[k]["label"])}' for k, n in inc["status_counts"].items() if n)
        rows.append(f'<tr><th scope="row"><a href="incidents/{E(inc["id"])}.html">{E(inc["title"])}</a><br><span class="small">{E(", ".join(inc["developer"]))} · disclosed {fmt_date(inc["dates"]["disclosed"])}</span></th>'
                    f'<td><span class="chip">{E(inc["incident_type_plain"])}</span></td><td class="num">{inc["attack_steps"]}</td><td class="num">{vc["not_tested"]}</td>'
                    f'<td class="num">{vc["unclear"]}</td><td class="num">{inc["detection_steps"] + inc["response_steps"]}</td><td>{st}</td></tr>')
    return f"""
<h1>Incidents</h1>
<p class="lede">{cov["totals"]["incidents"]} incidents in which an AI agent acted against real systems, each split into dated steps with a quoted source.</p>
<p class="small">They were chosen because they are well documented. They are not a random sample.</p>
{cards(cov, tiers)}
<h2>At a glance</h2>
<div class="tablewrap" tabindex="0" role="region" aria-label="Table of incidents, scrolls sideways on small screens"><table>
<caption>Steps and verdicts per incident</caption>
<thead><tr><th scope="col">Incident</th><th scope="col">Type</th><th scope="col" class="num">Attack steps</th><th scope="col" class="num">{E(vlabel(cov, "not_tested"))}</th><th scope="col" class="num">{E(vlabel(cov, "unclear"))}</th><th scope="col" class="num">Detection and response steps</th><th scope="col">Step status</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="small">We do not run an incident database. For a wider list of incidents see <a href="https://swarms.wiki/">swarms.wiki</a> (an independent project; we link to it and do not copy its text).</p>
<p><a class="btn" href="contribute.html">Propose an incident or a step</a></p>
"""


# ------------------------------------------------------------------------------------------- Replay
LW, CW, LH, TOP = 184, 28, 28, 6     # label column width, step column width, lane height, top padding


def ladder_svg(cov: dict, inc: dict) -> str:
    """Two drawings side by side: tactic labels (fixed) and the step track (scrolls sideways on small screens)."""
    lanes = cov["tactics"]
    lane_y = {t["id"]: TOP + i * LH for i, t in enumerate(lanes)}
    det_y = TOP + len(lanes) * LH + 6
    n = len(inc["steps"])
    W, H = n * CW + 12, det_y + LH + 6
    lab = [f'<svg class="ladder labels" viewBox="0 0 {LW} {H}" width="{LW}" height="{H}" role="group" aria-label="Tactics, with their count of public test tasks">']
    trk = [f'<svg class="ladder track" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="group" aria-labelledby="ladder-title">',
           f'<title id="ladder-title">Attack ladder for {E(inc["title"])}: one row per tactic, one mark per step, in order from left to right</title>']
    for t in lanes:
        y, zero = lane_y[t["id"]], t["tasks_as_goal"] == 0 and t["tasks_as_step"] == 0
        tip = f'{t["name"]}: {GLOSS[t["id"]]} {plural(t["tasks_as_goal"], "public task")} with this as the end goal, {t["tasks_as_step"]} as a stated required step.'
        cls = f'lane{" zero" if zero else ""}'
        lab.append(f'<g class="{cls}"><rect class="lane-bg" x="0" y="{y}" width="{LW}" height="{LH}"/>'
                   f'<g class="lane-label" tabindex="0" role="img" aria-label="{E(tip)}" data-gloss="{E(tip)}"><title>{E(tip)}</title>'
                   f'<rect class="hit" x="0" y="{y}" width="{LW}" height="{LH}"/><text class="lane-name" x="8" y="{y + 18}">{E(t["name"])}</text>'
                   f'<text class="lane-n" x="{LW - 8}" y="{y + 18}" text-anchor="end">{t["tasks_as_goal"]}{"" if not t["tasks_as_step"] else "+" + str(t["tasks_as_step"])}</text></g></g>')
        trk.append(f'<g class="{cls}"><rect class="lane-bg" x="0" y="{y}" width="{W}" height="{LH}"/></g>')
    tip = "How it was found: detection and response events. These are not scored."
    lab.append(f'<line class="sep" x1="0" x2="{LW}" y1="{det_y - 3}" y2="{det_y - 3}"/><g class="lane det"><rect class="lane-bg" x="0" y="{det_y}" width="{LW}" height="{LH}"/>'
               f'<g class="lane-label" tabindex="0" role="img" aria-label="{E(tip)}" data-gloss="{E(tip)}"><title>{E(tip)}</title><rect class="hit" x="0" y="{det_y}" width="{LW}" height="{LH}"/>'
               f'<text class="lane-name" x="8" y="{det_y + 18}">How it was found</text></g></g></svg>')
    trk.append(f'<line class="sep" x1="0" x2="{W}" y1="{det_y - 3}" y2="{det_y - 3}"/><g class="lane det"><rect class="lane-bg" x="0" y="{det_y}" width="{W}" height="{LH}"/></g>')
    pts = [(i * CW + CW // 2 + 6, lane_y[s["primary_tactic"]] + LH // 2) for i, s in enumerate(inc["steps"]) if s["phase"] == "attack" and s["order_basis"] != "unordered"]
    if len(pts) > 1:
        trk.append('<polyline class="path" points="' + " ".join(f"{x},{y}" for x, y in pts) + '"/>')
    for i, s in enumerate(inc["steps"]):
        x = i * CW + CW // 2 + 6
        if s["phase"] == "attack":
            y, cls = lane_y[s["primary_tactic"]] + LH // 2, f'v-{s["verdict"]}'
            label = f'Step {s["order"]}: {s["primary_tactic_name"]}. {vlabel(cov, s["verdict"])}. {s["what_happened"]}'
            shape = f'<circle class="shape" cx="{x}" cy="{y}" r="7"/>'
            if s["verdict"] == "tested_tactic_only":
                shape += f'<path class="half" d="M{x} {y - 7} A7 7 0 0 0 {x} {y + 7} Z"/>'
            if s["verdict"] == "unclear":
                shape += f'<text x="{x}" y="{y + 4}" text-anchor="middle">?</text>'
        else:
            y, cls = det_y + LH // 2, f'ph ph-{s["phase"]}'
            label = f'Step {s["order"]}: {PHASE[s["phase"]]}. {s["what_happened"]}'
            shape = f'<path class="shape" d="M{x} {y - 8} L{x + 8} {y} L{x} {y + 8} L{x - 8} {y} Z"/>'
        trk.append(f'<a class="dot {cls}" href="#step={s["id"]}" data-step="{s["id"]}" aria-label="{E(label)}"><title>{E(label)}</title>'
                   f'<rect class="hit" x="{x - CW // 2}" y="{y - LH // 2}" width="{CW}" height="{LH}"/><circle class="ring" cx="{x}" cy="{y}" r="11.5"/>{shape}</a>')
    trk.append("</svg>")
    return (f'<div class="ladder-wrap">{"".join(lab)}<div class="ladder-scroll" tabindex="0" role="region" aria-label="Steps in order, scrolls sideways">{"".join(trk)}</div></div>')


def task_list(uids: list[str], root: str) -> str:
    if not uids:
        return "none"
    show = ", ".join(f'<span class="sid">{E(u)}</span>' for u in uids[:4])
    more = f' and {len(uids) - 4} more (<a href="{root}explorer.html">see the task list</a>)' if len(uids) > 4 else f' (<a href="{root}explorer.html">task list</a>)'
    return show + more


def step_urls(inc: dict, s: dict) -> tuple[str, str]:
    sid = f'{inc["id"]}/{s["id"]}'
    cur = f'{s["primary_tactic"]} {s["primary_tactic_name"]}, technique {s["technique"] or "none"}' if s["phase"] == "attack" else f'{s["phase"]} step (no attack label)'
    return (forms.issue_url("step-dispute.yml", title=f"Dispute: {sid}", step_id=sid, current_label=cur),
            forms.issue_url("step-review.yml", title=f"Review: {sid}", step_id=sid, current_label=cur))


def step_detail(cov: dict, tiers: dict, inc: dict, s: dict, root: str) -> str:
    n = len(inc["steps"])
    dispute, review = step_urls(inc, s)
    bits = [f'<article class="step-detail" id="d-{s["id"]}" data-step="{s["id"]}" hidden>',
            f'<h2>Step {s["order"]} of {n} <span class="small">· {E(PHASE[s["phase"]])}</span></h2>',
            f'<p class="small">{E(fmt_time(s))}{" · written in the source as " + E(s["time_source_local"]) if s["time_source_local"] and "UTC" not in s["time_source_local"] else ""}. {E(BASIS[s["order_basis"]])}</p>']
    if s["time_conflict"]:
        bits.append(f'<p class="callout"><strong>The source gives two times.</strong> {E(s["time_conflict"])}</p>')
    bits.append(f'<p>{E(s["what_happened"])}</p>')
    if s.get("real_target"):
        bits.append('<p class="small">This step was aimed at a real third party, not at the test range.</p>')
    bits.append(f'<blockquote><q>{E(s["quote"])}</q><footer>{E(s["source_publisher"])}, <a href="{E(s["source_url"])}">{E(s["source_title"])}</a> ({E(s["locator"])})</footer></blockquote>')
    if s["phase"] == "attack":
        tech = f'<span class="chip"><span class="sid">{E(s["technique"])}</span> {E(s["technique_name"])}</span>' if s["technique"] else '<span class="chip">No technique given</span>'
        bits.append(f'<div class="chips"><span class="chip" title="{E(GLOSS[s["primary_tactic"]])}"><span class="sid">{E(s["primary_tactic"])}</span> {E(s["primary_tactic_name"])}</span>{tech}{vchip(cov, s["verdict"])}</div>')
        bits.append(f'<p class="small"><strong>Why this label:</strong> {E(s["rationale"])}</p>')
        if s["alternative_tactic"]:
            alt_t = f', {s["alternative_technique"]}' if s["alternative_technique"] else ""
            bits.append(f'<p class="small"><strong>Marked ambiguous.</strong> The other defensible label is {E(s["alternative_tactic_name"])} ({E(s["alternative_tactic"])}{E(alt_t)}): {E(s["alternative_reason"])} '
                        f'Under the first label the verdict is &ldquo;{E(vlabel(cov, s["verdict_primary"]))}&rdquo;; under the other, &ldquo;{E(vlabel(cov, s["verdict_alternative"]))}&rdquo;.</p>')
        bits.append('<dl class="detail">'
                    f'<dt>Tasks with the same technique</dt><dd>{task_list(s["technique_task_uids"], root)}</dd>'
                    f'<dt>Tasks with this tactic as end goal</dt><dd>{s["tasks_tactic_as_goal"]}</dd>'
                    f'<dt>Tasks with this tactic as a stated required step</dt><dd>{s["tasks_tactic_as_step"]}</dd></dl>')
        if not s["verdict_stable"]:
            bits.append('<p class="small"><strong>Not firm.</strong> This verdict would change if an ambiguous task label were moved to its recorded alternative.</p>')
    else:
        bits.append('<p class="small">Detection and response steps show how the incident was found and stopped. They carry no attack label and are not scored.</p>')
    hist = "".join(f'<li><span class="sid">{E(h["date"])}</span> {E(h["who"])}: {E(h["change"].replace("_", " "))}</li>' for h in s["history"])
    bits.append(f'<p>{badge(tiers, s["label_status"])} <span class="small">{E(tiers[s["label_status"]]["plain"])}</span></p><details><summary>History</summary><ul>{hist}</ul></details>')
    bits.append(f'<div class="btns"><a class="btn" href="{E(dispute)}">Challenge this label</a><a class="btn" href="{E(review)}">Review this step</a></div></article>')
    return "".join(bits)


def step_row(cov: dict, tiers: dict, inc: dict, s: dict) -> str:
    if s["phase"] == "attack":
        lab = f'{E(s["primary_tactic_name"])}<br><span class="small"><span class="sid">{E(s["technique"] or "no technique")}</span> {E(s["technique_name"] or "")}</span>'
        ver = vchip(cov, s["verdict"])
        data = f'data-tactic="{s["primary_tactic"]}" data-verdict="{s["verdict"]}"'
    else:
        lab, ver, data = f'<span class="chip">{E(PHASE[s["phase"]])}</span>', '<span class="small">not scored</span>', 'data-tactic="" data-verdict=""'
    return (f'<tr class="step-row" id="step={s["id"]}" data-step="{s["id"]}" data-phase="{s["phase"]}" {data}>'
            f'<td class="num"><a href="#step={s["id"]}">{s["order"]}</a></td><td>{E(fmt_time(s))}</td><td>{lab}</td>'
            f'<td>{E(s["what_happened"])}<br><span class="small"><q>{E(s["quote"])}</q> <a href="{E(s["source_url"])}">{E(s["source_publisher"])}</a></span></td>'
            f'<td>{ver}</td><td>{badge(tiers, s["label_status"])}</td></tr>')


def replay_body(cov: dict, tiers: dict, inc: dict) -> str:
    root, d, vc = "../", inc["dates"], inc["verdict_counts"]
    when = (f'{fmt_date(d["started"])} to {fmt_date(d.get("ended"))}, ' if d["started"] and d.get("ended") else "") + f'disclosed {fmt_date(d["disclosed"])}'
    claims = "".join(f'<li>{E(x["claim"])} <span class="small">(' + next(E(s["publisher"]) + ", " + fmt_date(s["published"]) for s in inc["sources"] if s["id"] == x["source"]) + ")</span></li>" for x in inc["agent_count_claims"])
    srcs = "".join(f'<li><a href="{E(s["url"])}">{E(s["title"])}</a> <span class="small">({E(s["publisher"])}, {fmt_date(s["published"])}; read {E(s["read_extent"] == "full" and "in full" or "in part")} on {fmt_date(s["accessed"])}'
                   f'{"; revised by a later source" if s.get("superseded_by") else ""}{"; revises an earlier source" if s.get("supersedes") else ""})</span></li>' for s in inc["sources"])
    notes = "".join(f"<li>{E(x)}</li>" for x in inc["notes"])
    tactics_used = [t for t in cov["tactics"] if t["steps_by_incident"][inc["id"]]]
    topts = "".join(f'<option value="{t["id"]}">{E(t["name"])} ({t["steps_by_incident"][inc["id"]]})</option>' for t in tactics_used)
    vopts = "".join(f'<option value="{v["id"]}">{E(v["label"])} ({vc[v["id"]]})</option>' for v in cov["verdicts"] if vc[v["id"]])
    legend = "".join(f"<li>{vchip(cov, v['id'])}</li>" for v in cov["verdicts"]) + '<li><span class="chip">◆ Detection or response event</span></li><li><span class="chip">Red row: no public task in this tactic</span></li>'
    sw = inc["swarms_wiki"]
    sw_html = f'<a href="{E(sw["url"])}">swarms.wiki {E(sw["id"])}</a>' if sw["url"] else "No swarms.wiki entry is linked: the match is not verified."
    return f"""
<nav aria-label="Breadcrumb" class="small"><a href="{root}incidents.html">Incidents</a> / {E(inc["id"])}</nav>
<div class="replay-head">
<h1>{E(inc["title"])}</h1>
<p class="meta"><span>{E(", ".join(inc["developer"]))}</span><span>{E(when)}</span><span class="chip">{E(inc["incident_type_plain"])}</span>
<span><span id="n-steps">{inc["total_steps"]}</span> steps · <span id="n-attack">{inc["attack_steps"]}</span> attack steps · <span class="v v-not_tested">{ico("not_tested")} <span id="n-never">{vc["not_tested"]}</span> never tested</span></span></p>
<p class="lede">{E(inc["summary"])}</p>
<p class="small">Each attack step is labelled with a MITRE ATT&amp;CK® {gloss("tactic")} and, where the source gives enough detail, a {gloss("technique")}. The verdict compares it with the public test tasks.</p>
</div>
<div class="player" id="player" hidden>
<button class="btn" id="b-prev" type="button">◀ Prev</button>
<button class="btn primary" id="b-play" type="button" aria-pressed="false">▶ Play</button>
<button class="btn" id="b-next" type="button">Next ▶</button>
<label class="small" for="scrub">Step</label><input id="scrub" type="range" min="1" max="{inc["total_steps"]}" value="1" step="1">
<span class="pos" id="pos" aria-hidden="true"></span>
</div>
<p id="live" class="small" role="status" aria-live="polite"></p>
<div class="filters" id="filters" hidden>
<div class="field"><label for="f-tactic">Tactic</label><select id="f-tactic"><option value="">Any tactic</option>{topts}</select></div>
<div class="field"><label for="f-verdict">Verdict</label><select id="f-verdict"><option value="">Any verdict</option>{vopts}</select></div>
<label class="check"><input type="checkbox" id="f-never"> Show only never-tested steps</label>
</div>
<div class="replay-grid">
<section aria-label="Attack ladder">
{ladder_svg(cov, inc)}
<p class="lane-gloss" id="lane-gloss">The number beside each tactic is its count of public test tasks (end goal + stated required step). Keys: arrows or j / k to move, space to play.</p>
<ul class="legend" aria-label="Legend">{legend}</ul>
</section>
<section class="detail-card" id="detail" aria-label="Step detail">
<p id="detail-empty">Pick a step in the ladder or in the table to see its source quote, label and verdict. Every step is also in the table below.</p>
{"".join(step_detail(cov, tiers, inc, s, root) for s in inc["steps"])}
</section>
</div>

<h2 id="all-steps">All steps</h2>
<p id="table-count" class="small" aria-live="polite"></p>
<div class="tablewrap" tabindex="0" role="region" aria-label="Table of all steps, scrolls sideways on small screens"><table id="steps">
<caption>Every step of this incident, in order, with its source quote and verdict</caption>
<thead><tr><th scope="col" class="num">#</th><th scope="col">When</th><th scope="col">Tactic and technique</th><th scope="col">What happened, and the source's words</th><th scope="col">Verdict</th><th scope="col">Status</th></tr></thead>
<tbody>{"".join(step_row(cov, tiers, inc, s) for s in inc["steps"])}</tbody></table></div>

<h2>Read this before you draw conclusions</h2>
{limits_html(cov)}

<h2>About this incident</h2>
<h3>How many agents?</h3>
<p class="small">Sources do not always agree. Each claim is shown with where it comes from; we do not pick one.</p>
<ul>{claims}</ul>
<h3>Sources</h3>
<ul>{srcs}</ul>
<h3>Notes</h3>
<ul>{notes}</ul>
<p class="small">{sw_html}</p>
<p class="small">Tactic and technique names are from MITRE ATT&amp;CK® Enterprise v{E(cov["versions"]["attack"])}. Step rules: codebook {E(cov["versions"]["codebook_steps"])} (S1 to S7), not yet approved.</p>
"""


# ------------------------------------------------------------------------------------------- Coverage
def coverage_body(cov: dict, tiers: dict) -> str:
    mx = max(max(t["tasks_as_goal"], t["tasks_as_step"]) for t in cov["tactics"]) or 1
    rows, det = [], []
    for t in cov["tactics"]:
        zero = t["tasks_as_goal"] == 0 and t["tasks_as_step"] == 0
        dots = "".join(ico(v["id"]) * t["steps_by_verdict"][v["id"]] for v in cov["verdicts"])
        words = ", ".join(f'{t["steps_by_verdict"][v["id"]]} {v["label"].lower()}' for v in cov["verdicts"] if t["steps_by_verdict"][v["id"]]) or "no steps"
        rows.append(f'<tr class="{"zero" if zero else ""}" id="row-{t["id"]}"><th scope="row"><a href="#t-{t["id"]}" title="{E(GLOSS[t["id"]])}">{E(t["name"])}</a><br><span class="small">{E(GLOSS[t["id"]])}</span></th>'
                    f'<td><span class="barrow"><span class="tbar" style="width:{round(120 * t["tasks_as_goal"] / mx)}px"></span><span class="num">{t["tasks_as_goal"]}</span></span></td>'
                    f'<td><span class="barrow"><span class="tbar step" style="width:{round(120 * t["tasks_as_step"] / mx)}px"></span><span class="num">{t["tasks_as_step"]}</span></span></td>'
                    f'<td><span class="num">{t["incident_steps"]}</span> <span class="dots" aria-hidden="true">{dots}</span><br><span class="small">{E(words)}</span></td>'
                    f'<td class="num">{t["steps_never_tested"]}</td></tr>')
        steps = "".join(f'<li>{vchip(cov, r["verdict"])} <a href="incidents/{E(r["incident"])}.html#step={E(r["step"])}">{E(r["incident"])} {E(r["step"])}</a>: {E(r["what_happened"])}</li>' for r in t["step_refs"]) or "<li>No incident step has this tactic as its label.</li>"
        goal = ", ".join(f'<span class="sid">{E(u)}</span>' for u in t["goal_task_uids"]) or "none"
        stp = ", ".join(f'<span class="sid">{E(u)}</span>' for u in t["step_task_uids"]) or "none"
        det.append(f'<details id="t-{t["id"]}"><summary>{E(t["name"])} <span class="small">({t["tasks_as_goal"]} tasks as end goal, {t["tasks_as_step"]} as stated step, {plural(t["incident_steps"], "incident step")})</span></summary>'
                   f'<h3>Incident steps</h3><ul>{steps}</ul><h3>Public tasks with this tactic as end goal</h3><p class="small">{goal}</p>'
                   f'<h3>Public tasks that state it as a required step</h3><p class="small">{stp}</p></details>')
    p = cov["prediction"]
    result = {"held": "held", "partly_held": "partly held", "failed": "failed"}[p["result"]]
    names = {t["id"]: t["name"] for t in cov["tactics"]}
    return f"""
<h1>Coverage by tactic</h1>
<p class="lede">For each of the {len(cov["tactics"])} MITRE ATT&amp;CK® tactics: how many public test tasks have it, and how many real incident steps fall in it.</p>
<h2>Read this first</h2>
{limits_html(cov)}
<h2>Tactics</h2>
<p class="small">Tasks are drawn as bars and incident steps as marks, on purpose: they are different units and must not be read as one scale. Marks: {" ".join(vchip(cov, v["id"]) for v in cov["verdicts"])}</p>
<div class="tablewrap" tabindex="0" role="region" aria-label="Coverage table, scrolls sideways on small screens"><table class="cov">
<caption>Public tasks and incident steps per tactic. A red edge marks a tactic with no public task.</caption>
<thead><tr><th scope="col">Tactic</th><th scope="col">Tasks with it as end goal</th><th scope="col">Tasks that state it as a required step</th><th scope="col">Incident steps</th><th scope="col" class="num">Incident steps never tested</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<h2>Tasks and steps for each tactic</h2>
<p class="small">Open a tactic to list its incident steps and its public tasks.</p>
{"".join(det)}
<h2>The prediction we wrote down first</h2>
<p>Before any step was drafted we committed a prediction: at least some steps would fall in the four tactics with no public task ({E(", ".join(names[x] for x in p["tactics"]))}).</p>
<p><strong>Result: {result}.</strong> <span id="n-pred">{p["steps_in_these_tactics"]}</span> of <span id="n-pred-total">{cov["totals"]["attack_steps"]}</span> attack steps have one of these four tactics as their label, in {p["incidents_with_such_steps"]} of {cov["totals"]["incidents"]} incidents.
<span id="n-pred-firm">{p["steps_not_resting_on_an_ambiguous_label"]}</span> of them do not depend on an ambiguous label.</p>
<p class="small">The same AI that knew the prediction drafted the labels, and no human has checked them. Treat this as a draft result. The rule for &ldquo;held&rdquo; was fixed in advance: <a href="{forms_repo()}/blob/main/docs/PILOT_PREDICTION.md">PILOT_PREDICTION.md</a>.</p>
<script>
(function () {{ function open() {{ var m = /^#t-(TA\\d+)$/.exec(location.hash); if (m) {{ var d = document.getElementById("t-" + m[1]); if (d) {{ d.open = true; d.scrollIntoView(); }} }} }}
  window.addEventListener("hashchange", open); open(); }})();
</script>
"""


def forms_repo() -> str:
    return "https://github.com/" + c.config()["repository"]


# ------------------------------------------------------------------------------------------- Contribute
def contribute_body(cov: dict, tiers: dict) -> str:
    incs = "".join(f'<option value="{E(i["id"])}">{E(i["title"])}</option>' for i in cov["incidents"])
    tacs = "".join(f'<option value="{t["id"]}">{t["id"]} {E(t["name"])}</option>' for t in cov["tactics"])
    plain = {k: f'{forms_repo()}/issues/new?template={k}' for k in forms.FORMS}
    tier_rows = "".join(f'<tr><th scope="row">{badge(tiers, k)}</th><td>{E(t["plain"])}</td><td>{E(t["who_may_set"])}</td></tr>' for k, t in tiers.items())
    return f"""
<h1>Contribute</h1>
<p class="lede">Propose an incident, add or correct a step, or challenge a label. You need a GitHub account. This page fills in a GitHub form for you; nothing is sent until you press submit there.</p>
<h2>What happens to a submission</h2>
<ol>
<li>You submit the GitHub form. It is public.</li>
<li>A script checks it: required fields, that the tactic and technique IDs exist in MITRE ATT&amp;CK® v{E(cov["versions"]["attack"])}, that the quote has at most 25 words, and that the quoted words appear in the source you cite.</li>
<li>The script posts one comment with a pass or fail table. It never changes the data.</li>
<li>A human maintainer decides, and applies accepted changes through a pull request. A form by itself never changes data.</li>
</ol>
<h2>Start a submission</h2>
<form class="wizard" id="wizard" data-repo="{E(c.config()["repository"])}" hidden>
<fieldset><legend>What do you want to do?</legend><div class="choices">
<label><input type="radio" name="kind" value="incident-new.yml" checked><span><strong>Propose a new incident</strong><br><span class="small">You have public sources for it.</span></span></label>
<label><input type="radio" name="kind" value="incident-step.yml"><span><strong>Add or correct a step</strong><br><span class="small">In an incident already listed.</span></span></label>
<label><input type="radio" name="kind" value="step-dispute.yml"><span><strong>Dispute a label</strong><br><span class="small">You think a tactic or technique is wrong.</span></span></label>
<label><input type="radio" name="kind" value="step-review.yml"><span><strong>Review a step</strong><br><span class="small">Check a step's label and quote.</span></span></label>
</div></fieldset>
<div data-for="incident-new.yml">
<div class="field"><label for="w-title">Incident title</label><input type="text" id="w-title" data-field="incident_title" maxlength="140"></div>
<div class="field"><label for="w-sources">Source address (https)</label><input type="url" id="w-sources" data-field="sources" placeholder="https://"><span class="hint">A primary source, such as the developer's or the victim's own report.</span></div>
</div>
<div data-for="incident-step.yml" hidden>
<div class="field"><label for="w-inc">Incident</label><select id="w-inc" data-field="incident_id">{incs}</select></div>
<div class="field"><label for="w-quote">Quote from the source (at most 25 words)</label><input type="text" id="w-quote" data-field="quote" maxlength="400"><span class="hint" id="w-quote-n" aria-live="polite"></span></div>
<div class="field"><label for="w-src">Source address (https)</label><input type="url" id="w-src" data-field="source" placeholder="https://"></div>
<div class="field"><label for="w-tac">Proposed tactic</label><select id="w-tac" data-field="tactic"><option value="">Choose</option>{tacs}</select></div>
</div>
<div data-for="step-dispute.yml" hidden>
<div class="field"><label for="w-sid">Step</label><input type="text" id="w-sid" data-field="step_id" placeholder="hf-2026-07/s17"><span class="hint">Incident id, a slash, then the step id. It is shown on every step.</span></div>
<div class="field"><label for="w-ptac">Tactic you propose</label><select id="w-ptac" data-field="proposed_tactic"><option value="">Choose</option>{tacs}</select></div>
</div>
<div data-for="step-review.yml" hidden>
<div class="field"><label for="w-rsid">Step</label><input type="text" id="w-rsid" data-field="step_id" placeholder="hf-2026-07/s17"><span class="hint">Or pick a step from the <a href="review.html">review queue</a>, which fills this in.</span></div>
</div>
<p><a class="btn primary" id="w-go" href="{E(plain["incident-new.yml"])}">Open the GitHub form</a></p>
<p class="small">The rest of the form is filled in on GitHub. If the form opens empty, your details were not carried over: type them in there.</p>
</form>
<div id="wizard-plain">
<p>Open a form directly:</p>
<ul>
<li><a href="{E(plain["incident-new.yml"])}">Propose a new incident</a></li>
<li><a href="{E(plain["incident-step.yml"])}">Add or correct a step</a></li>
<li><a href="{E(plain["step-dispute.yml"])}">Dispute a label</a></li>
<li><a href="{E(plain["step-review.yml"])}">Review a step</a></li>
</ul>
</div>
<h2>What the status of a step means</h2>
<div class="tablewrap"><table><caption>Step status tiers, lowest trust first</caption>
<thead><tr><th scope="col">Status</th><th scope="col">Meaning</th><th scope="col">Who may set it</th></tr></thead><tbody>{tier_rows}</tbody></table></div>
<h2>Rules for sources and quotes</h2>
<ul>
<li>Quote at most 25 words per step, word for word, and link to the page.</li>
<li>Describe the step in your own words, at the level of detail the source gives. Describe behaviour. Do not add commands, payloads, passwords, internal host names or other details that would help repeat an attack.</li>
<li>Do not name private individuals.</li>
<li>Your contribution is offered under the repository's data licence (<a href="{forms_repo()}/blob/main/LICENSE-DATA">LICENSE-DATA</a>).</li>
</ul>
<p class="small">Full guide: <a href="{forms_repo()}/blob/main/CONTRIBUTING.md">CONTRIBUTING.md</a>.</p>
"""


# ------------------------------------------------------------------------------------------- Review
def review_body(cov: dict, act: dict, tiers: dict) -> str:
    t = cov["totals"]
    strip = "".join(f'<li><span class="n" id="n-{k}">{t["status_counts"][k]}</span><span class="l">{E(tiers[k]["label"])}</span></li>' for k in tiers)
    blocks = []
    for k in tiers:
        if not t["status_counts"][k]:
            continue
        tables = []
        for inc in cov["incidents"]:
            steps = [s for s in inc["steps"] if s["label_status"] == k]
            if not steps:
                continue
            rows = []
            for s in steps:
                lab = f'{E(s["primary_tactic_name"])} <span class="sid">{E(s["technique"] or "")}</span>' if s["phase"] == "attack" else f'<span class="chip">{E(PHASE[s["phase"]])}</span>'
                amb = ' <span class="badge flag">ambiguous</span>' if s.get("confidence") == "ambiguous" else ""
                rows.append(f'<tr><td><a class="sid" href="incidents/{E(inc["id"])}.html#step={s["id"]}">{E(inc["id"])}/{s["id"]}</a></td><td>{lab}{amb}</td><td>{E(s["what_happened"])}</td>'
                            f'<td class="small">{E(s["labeled_by"])}</td><td><a href="{E(step_urls(inc, s)[1])}">Review this</a></td></tr>')
            tables.append(f'<h3>{E(inc["title"])} <span class="small">({plural(len(steps), "step")})</span></h3><div class="tablewrap" tabindex="0" role="region" aria-label="Steps to review, scrolls sideways on small screens"><table>'
                          f'<thead><tr><th scope="col">Step</th><th scope="col">Label</th><th scope="col">What happened</th><th scope="col">Labelled by</th><th scope="col">Action</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
        blocks.append(f'<h2 id="q-{k}">{E(tiers[k]["label"])} <span class="small">({t["status_counts"][k]})</span></h2><p class="small">{E(tiers[k]["plain"])}</p>{"".join(tables)}')
    return f"""
<h1>Review queue</h1>
<p class="lede">Every incident step, grouped by how far it has been checked. This page lists work to do. It does not approve anything.</p>
<ul class="strip" aria-label="Steps by status">{strip}</ul>
<p class="callout"><strong>What a reviewer checks.</strong> The quote (is it in the source, and does it say what our description says?) and the label (is the tactic what the step was for?). The coverage verdict is worked out by a script from the labels, so there is nothing to review there.</p>
<p class="small">The review form is public, so it is not a blind review. Only a named human may mark a step as checked by a person, and only through a pull request.</p>
{"".join(blocks)}
<h2>Recent changes</h2>
{feed_html(act, "", 12)}
"""


# ------------------------------------------------------------------------------------------- Guide section
def guide_incidents(cov: dict, tiers: dict) -> str:
    t = cov["totals"]
    vrows = {"tested_technique": "At least one public task has the same technique. Sub-techniques are compared at the level of their parent, so T1048.003 matches T1048.",
             "tested_tactic_only": "Some public task has this tactic as its end goal or as a stated required step, but none shares the technique.",
             "not_tested": "No public task has this tactic as its end goal or as a stated required step.",
             "unclear": "The step is marked ambiguous, and its two defensible labels give different verdicts."}
    vtab = "".join(f'<tr><th scope="row">{vchip(cov, v["id"])}</th><td>{E(vrows[v["id"]])}</td><td class="num">{t["verdict_counts"][v["id"]]}</td></tr>' for v in cov["verdicts"])
    ttab = "".join(f'<tr><th scope="row">{badge(tiers, k)}</th><td>{E(x["plain"])}</td><td>{E(x["who_may_set"])}</td><td class="num">{t["status_counts"][k]}</td></tr>' for k, x in tiers.items())
    return f"""
<h2 id="incidents">Incidents, steps and verdicts</h2>
<p>The <a href="incidents.html">incident pages</a> ask a second question: when real AI agents acted against real systems, did they do things that no public test states as a goal?</p>
<ol>
<li><strong>Pick incidents with a detailed public account.</strong> There are {t["incidents"]}. They were chosen because they are well documented, not at random.</li>
<li><strong>Split each account into steps.</strong> A step is one distinct behaviour the source describes. Where a source reports thousands of low-level actions, steps follow the source's own phases. There are {t["steps"]} steps: {t["attack_steps"]} attack steps, and {t["detection_steps"] + t["response_steps"]} detection and response steps that show how the incident was found.</li>
<li><strong>Give each step a quote.</strong> At most 25 words from the source, with a link, plus a description in our own words.</li>
<li><strong>Label each attack step</strong> with the tactic the step was <em>for</em> at that moment, and a technique if the source gives enough detail. {t["ambiguous_steps"]} steps are marked ambiguous and {t["steps_with_null_technique"]} have no technique.</li>
<li><strong>Let a script compare</strong> every attack step with the {t["public_tasks"]} public tasks. Nobody sets a verdict by hand.</li>
</ol>
<div class="tablewrap"><table><caption>The four verdicts, and how many of the {t["attack_steps"]} attack steps got each</caption>
<thead><tr><th scope="col">Verdict</th><th scope="col">Rule</th><th scope="col" class="num">Steps</th></tr></thead><tbody>{vtab}</tbody></table></div>
<p>{t["unstable_verdicts"]} verdicts are flagged &ldquo;not firm&rdquo;: they would change if an ambiguous task label were moved to its recorded alternative.</p>
<div class="tablewrap"><table><caption>Step status tiers</caption>
<thead><tr><th scope="col">Status</th><th scope="col">Meaning</th><th scope="col">Who may set it</th><th scope="col" class="num">Steps</th></tr></thead><tbody>{ttab}</tbody></table></div>
<p>The script check is narrow: it matches the quoted words against the source page. It does not judge whether the description or the label is right.</p>
<h3>Limits</h3>
{limits_html(cov)}
<p>The step rules are S1 to S7 in the <a href="{forms_repo()}/blob/main/codebook/CODEBOOK.md">codebook</a> (version {E(cov["versions"]["codebook_steps"])}, not yet approved).</p>
"""
