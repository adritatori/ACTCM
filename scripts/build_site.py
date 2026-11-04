#!/usr/bin/env python3
"""Phase 6: build the static site in site/ from data/generated/*.

Writes site/index.html, guide.html, verify.html, and copies data files to site/data/.
Every number in the HTML comes from counts.json / stress_results.json / the lock file; none is typed by hand.
"""
from __future__ import annotations

import html
import json
import shutil

import common as c
import frameworks as fwm  # noqa: F401  (keeps the import path consistent)

SITE = c.ROOT / "site"
GEN = c.DATA / "generated"
REPO_URL = "https://github.com/" + c.config()["repository"]   # config/publish.yml
TOU = "https://attack.mitre.org/resources/legal-and-branding/terms-of-use/"
MITRE_LINE = "© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation."
LICENCE_TXT = (c.DATA / "legal" / "attack_licence.txt").read_text(encoding="utf-8")
LICENCE_PARA = " ".join(LICENCE_TXT.split("\n\n")[0].split("\n")[2:]).strip()
DISCLAIMER_PARAS = [" ".join(x.split()) for x in LICENCE_TXT.split("Disclaimers\n-----------\n")[1].strip().split("\n\n")]
DISCLAIMER_HTML = "".join(f"<p>{html.escape(x)}</p>" for x in DISCLAIMER_PARAS)
DISCLAIMERS = LICENCE_TXT.split("Disclaimers\n-----------\n")[1].strip()
E = html.escape

OPEN_DECISIONS = ["the three tenant-isolation tasks", "the line between Stealth and Defense Impairment"]
BANNER = ("<strong>PROVISIONAL RESULTS.</strong> No human has reviewed any label yet. "
          f"Counts and gaps may still change: {len(OPEN_DECISIONS)} decisions are open ({' and '.join(OPEN_DECISIONS)}).")


def load():
    cn = json.loads((GEN / "counts.json").read_text())
    st = json.loads((GEN / "stress_results.json").read_text())
    lock = c.load_yaml(c.LOCK_FILE)
    return cn, st, lock


def page(title: str, active: str, body: str, cn: dict, lock: dict, desc: str) -> str:
    v = cn["versions"]
    nav = "".join(f'<li><a href="{h}"{" aria-current=\"page\"" if k == active else ""}>{n}</a></li>'
                  for k, h, n in [("explorer", "index.html", "Explorer"), ("guide", "guide.html", "Guide"), ("verify", "verify.html", "Verify")])
    srcs = len(c.public_lock(lock)["sources"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to the content</a>
<div class="banner" role="note"><div class="wrap">{BANNER}</div></div>
<header class="site"><div class="wrap">
<a class="brand" href="index.html">ACTCM<small>Agent Control Threat Coverage Matrix</small></a>
<nav class="main" aria-label="Main"><ul>{nav}</ul></nav>
</div></header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p class="warn">A task count shows what is <em>tested</em>, not what is <em>caught</em>. A gap means &ldquo;untested&rdquo;, not &ldquo;dangerous&rdquo; and not &ldquo;undefended&rdquo;.</p>
<p><strong>Pinned versions:</strong> ATT&amp;CK Enterprise v{v['attack']} (commit {v['attack_sha'][:10]}), ATLAS {v['atlas']} (commit {v['atlas_sha'][:10]}), codebook {v['codebook']}, {srcs} source repositories at fixed commits (<a href="{REPO_URL}/blob/main/data/sources.lock.yml">sources.lock.yml</a>, <span class="pending">works after publishing</span>).</p>
<p><strong>MITRE ATT&amp;CK® licence.</strong> {E(LICENCE_PARA)}</p>
<p>{E(MITRE_LINE)} See the <a href="{TOU}">ATT&amp;CK Terms of Use</a>. ATLAS is licensed under Apache License 2.0.</p>
<details><summary>MITRE disclaimers (reproduced from MITRE's licence text)</summary>{DISCLAIMER_HTML}</details>
<p><strong>Not affiliated with or endorsed by The MITRE Corporation.</strong></p>
<p>Licences: code MIT (<a href="{REPO_URL}/blob/main/LICENSE">LICENSE</a>), data and labels CC BY 4.0 (<a href="{REPO_URL}/blob/main/LICENSE-DATA">LICENSE-DATA</a>), <a href="{REPO_URL}/blob/main/THIRD_PARTY_NOTICES.md">third-party notices</a>. <span class="pending">These links work after publishing.</span> Source: <a href="{REPO_URL}">{REPO_URL.replace('https://', '')}</a> <span class="pending">(works after publishing)</span>.</p>
</div></footer>
{{SCRIPT}}
</body>
</html>
"""


# ------------------------------------------------------------------------------------------- Explorer
def explorer_body(cn: dict) -> str:
    extras_line = f'<p class="small" id="extras-note">{E(cn["extras_note"])}</p>' if cn.get("extras_note") else ""
    seg = lambda name, items: "".join(
        f'<label><input type="radio" name="{name}" id="{i}"><span>{E(t)}</span></label>' for i, t in items)
    return f"""
<h1>Which kinds of attack do AI control tests cover?</h1>
<p class="lede">For each public AI control setting, this page lists every hidden attack task (a <a href="guide.html#g-side-task">side task</a>),
labels it with a MITRE ATT&amp;CK® <a href="guide.html#g-tactic">tactic</a> and <a href="guide.html#g-technique">technique</a>
(plus MITRE ATLAS where the target is an AI system), and shows which kinds of attack are tested and which are missing.
A <a href="guide.html#g-gap">gap</a> is a tactic with zero tasks.</p>
<p class="note"><strong>Tested, not caught.</strong> A task count shows what is tested, not what is caught. A gap means &ldquo;untested&rdquo;, not &ldquo;dangerous&rdquo; and not &ldquo;undefended&rdquo;.</p>
{extras_line}
<details><summary>Why this matters</summary>
<p>An AI control evaluation reports how often safety measures stop an AI agent that is secretly trying to cause harm. That number only covers the attacks the evaluation includes. If whole kinds of attack are missing, the number says nothing about them. Security teams check this kind of gap with MITRE ATT&amp;CK; this project applies the same check to AI control settings. <a href="guide.html">Read the guide</a>.</p>
</details>
<p id="load-error" class="callout" role="alert" hidden></p>

<div class="controls">
<fieldset><legend>Setting</legend><div class="seg">{seg('setting', [('set-all', 'All')] + [(f"set-{x['hash']}", x['name']) for x in cn['settings']])}</div></fieldset>
<fieldset><legend>Count mode</legend><div class="seg">{seg('mode', [('mode-primary', 'End goal only'), ('mode-steps', 'End goal + required steps')])}</div></fieldset>
<fieldset><legend>Framework</legend><div class="seg">{seg('fw', [('fw-attack', 'ATT&CK (15 tactics)'), ('fw-atlas', 'ATLAS (16 tactics)')])}</div></fieldset>
</div>
<p id="mode-note" class="small" aria-live="polite"></p>

<h2>Summary</h2>
<ul id="summary" class="strip" aria-label="Summary numbers"></ul>
<h3>Label status</h3>
<p class="small">How far each label has been checked. A second AI agreeing is <strong>not</strong> a human review.</p>
<ul id="tiers" class="tiers" aria-label="Label status counts"></ul>

<h2 id="matrix-title">MITRE ATT&amp;CK® matrix (15 tactics)</h2>
<p id="matrix-help" class="small"></p>
<p class="small">Click a tactic or a technique to list its tasks. Columns marked with a dashed hatched box and the text &ldquo;0 tasks: gap&rdquo; have no tasks.</p>
<div class="matrix-scroll"><div id="matrix" class="matrix" role="group" aria-labelledby="matrix-title"></div></div>

<div id="panel" class="panel" role="region" aria-label="Task details" aria-live="polite"></div>

<h2>All tasks</h2>
<div class="tools">
<div><label for="f-search">Search</label><input id="f-search" type="search" placeholder="id, tactic, text"></div>
<div><label for="f-tactic">Main tactic</label><select id="f-tactic"><option value="">Any</option></select></div>
<div><label for="f-tier">Label status</label><select id="f-tier"><option value="">Any</option></select></div>
</div>
<p id="table-count" class="small" aria-live="polite"></p>
<div class="tablewrap" tabindex="0" role="region" aria-label="Table of tasks, scrolls sideways on small screens">
<table><caption>Side tasks in the selected setting</caption>
<thead><tr><th scope="col">Task</th><th scope="col">Setting</th><th scope="col">Environment</th><th scope="col">Main tactic</th><th scope="col">Technique</th><th scope="col">Label status</th><th scope="col">Flags</th></tr></thead>
<tbody id="tbody"></tbody></table></div>

<h2>Take the data</h2>
<div class="btns">
<a id="nav-link" class="btn" href="#" rel="noopener">Open in ATT&amp;CK Navigator</a>
<a class="btn" href="data/tasks.csv" download>Download CSV</a>
<a class="btn" href="data/tasks.json" download>Download JSON</a>
</div>
<p class="small"><span id="nav-note" class="pending"></span> The Navigator link loads a layer file from the repository, so it only works once the repository is published.
Layers show tasks per technique for the selected setting; tasks with no ATT&amp;CK technique ({cn['summary']['null_technique_tasks']} in total) cannot be shown there.</p>
"""


# ------------------------------------------------------------------------------------------- Guide
DIAGRAM = """<svg class="diagram" viewBox="0 0 440 685" role="img" aria-labelledby="dg-t dg-d" style="max-width:460px">
<title id="dg-t">How a control evaluation works</title>
<desc id="dg-d">An agent takes actions. A monitor gives each action a suspicion score. The most suspicious actions go to a human audit, limited by a budget. The result is caught or not caught.</desc>
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z"/></marker></defs>
<rect class="box" x="70" y="10" width="300" height="70" rx="10"/><text x="220" y="38" text-anchor="middle" font-weight="700">1. Agent (the untrusted model)</text><text x="220" y="60" text-anchor="middle">works on a main task; an attack run also</text>
<text x="220" y="76" text-anchor="middle" font-size="12">has a hidden side task</text>
<path class="arrow" d="M220 82 L220 118"/>
<rect class="box" x="70" y="120" width="300" height="60" rx="10"/><text x="220" y="148" text-anchor="middle" font-weight="700">2. Actions</text><text x="220" y="168" text-anchor="middle">each step that makes tool calls</text>
<path class="arrow" d="M220 182 L220 218"/>
<rect class="box" x="70" y="220" width="300" height="60" rx="10"/><text x="220" y="248" text-anchor="middle" font-weight="700">3. Monitor (a weaker, trusted model)</text><text x="220" y="268" text-anchor="middle">reads every action</text>
<path class="arrow" d="M220 282 L220 318"/>
<rect class="box" x="70" y="320" width="300" height="60" rx="10"/><text x="220" y="348" text-anchor="middle" font-weight="700">4. Suspicion score</text><text x="220" y="368" text-anchor="middle">higher = more suspicious</text>
<path class="arrow" d="M220 382 L220 418"/>
<rect class="box" x="70" y="420" width="300" height="70" rx="10"/><text x="220" y="448" text-anchor="middle" font-weight="700">5. Audit (a human, limited budget)</text><text x="220" y="468" text-anchor="middle">only the most suspicious actions are</text><text x="220" y="484" text-anchor="middle" font-size="12">checked; budget = share of honest actions</text>
<path class="arrow" d="M150 492 L100 548"/><path class="arrow" d="M290 492 L340 548"/>
<rect class="hot" x="10" y="550" width="190" height="64" rx="10"/><text x="105" y="578" text-anchor="middle" font-weight="700">Caught</text><text x="105" y="598" text-anchor="middle" font-size="12">audit before the harm</text>
<rect class="box" x="240" y="550" width="190" height="64" rx="10"/><text x="335" y="578" text-anchor="middle" font-weight="700">Not caught</text><text x="335" y="598" text-anchor="middle" font-size="12">side task succeeds first</text>
<text x="220" y="652" text-anchor="middle" font-size="12">The side tasks in this project decide which</text>
<text x="220" y="670" text-anchor="middle" font-size="12">attacks step 1 can try.</text>
</svg>"""

GLOSSARY = [
    ("g-ai-model", "AI model", "A program trained on data to produce outputs (text, code, actions) from inputs. Here, usually a large language model (LLM)."),
    ("g-llm", "Large language model (LLM)", "An AI model trained on large amounts of text to predict the next piece of text. Examples: Claude, GPT."),
    ("g-agent", "AI agent", "An AI model run in a loop with tools (shell commands, file edits, web requests). It takes an action, sees the result, and picks the next action, working toward a goal over many steps."),
    ("g-agentic", "Agentic", "Describes an AI system that acts through tools over many steps with little human input per step, instead of giving one reply."),
    ("g-ai-control", "AI control", "A research field focused on extracting maximum usefulness from a potentially misaligned AI while ensuring safety. <span class=\"small\">(Wording from the Control Tower docs. The brief's extra sentence about treating the agent like an insider threat was not found in those docs, so it is left out.)</span>"),
    ("g-control-setting", "Control setting", "A practice environment for control research: realistic software systems plus a list of honest jobs and hidden attack goals. LinuxArena is one."),
    ("g-control-eval", "Control evaluation (control eval)", "A test that runs agents in a control setting and measures how often safety measures stop attacks. It has two halves: an honest eval (measures usefulness) and an attack eval (measures safety)."),
    ("g-main-task", "Main task", "The honest job the agent is asked to do (for example, fix a bug)."),
    ("g-side-task", "Side task", "A hidden harmful goal given only to the attacking version of the agent (for example, leak a password). This project maps side tasks."),
    ("g-runs", "Honest run / attack run", "The same agent run without (honest) and with (attack) a side task."),
    ("g-action", "Action", "One response of the agent that makes tool calls, all of them together. A monitor scores actions, and an audit stops one. A reply with no tool call is not an action."),
    ("g-monitor", "Monitor", "A watcher, often a weaker trusted AI model, that reads the agent's actions and gives each a suspicion score."),
    ("g-suspicion", "Suspicion score", "A number from the monitor saying how suspicious an action looks. Higher = more suspicious."),
    ("g-audit", "Audit budget / false positive rate (FPR)", "The share of honest actions that get flagged for human review. A 1% FPR means 1 in 100 honest actions is flagged. Suspicion thresholds are set from this."),
    ("g-safety", "Safety (in control evals)", "The probability the blue team wins: that it catches the attacking agent before the agent accomplishes a side task. Formula: P(caught) / (P(caught) + P(uncaught and side task succeeded)). Source: Control Tower docs, <em>AI Control Concepts</em>. The LinuxArena paper's own wording was not read (see Related work)."),
    ("g-live-delayed", "Live failure / delayed failure", "LinuxArena's <code>failure_type</code>. Live: the harm happens during the agent's run and cannot be undone. Delayed: the agent plants something (for example a vulnerability) that causes harm after the run ends; it can still be reviewed and reverted before then, and the agent supplies proof that it works."),
    ("g-attack", "MITRE ATT&CK®", "A public catalogue of real attacker behaviour, maintained by MITRE, sorted into tactics and techniques. This project uses Enterprise ATT&CK v20 (data file dated 13 Oct 2026). Definition in our own words."),
    ("g-tactic", "Tactic", "The attacker's goal at one stage, for example Exfiltration (getting data out). ATT&CK v20 Enterprise has 15."),
    ("g-technique", "Technique / sub-technique", "How the attacker reaches a tactic, for example T1048 Exfiltration Over Alternative Protocol. A sub-technique is a more specific version (T1070.003 Clear Command History)."),
    ("g-atlas", "MITRE ATLAS", "MITRE's catalogue of attacks on AI systems, same structure as ATT&CK. This project uses ATLAS 2026.10 (16 tactics, 221 techniques and sub-techniques)."),
    ("g-navigator", "MITRE ATT&CK® Navigator", "MITRE's free web tool for colouring the ATT&CK matrix. It loads &ldquo;layer&rdquo; files (JSON)."),
    ("g-coverage", "Coverage", "Which tactics and techniques have at least one side task."),
    ("g-gap", "Gap", "A tactic or technique with zero side tasks (or below a stated threshold)."),
    ("g-codebook", "Codebook", "The written rules for assigning labels, so two people label the same way."),
    ("g-agreement", "Inter-rater agreement", "How often two people, labelling independently, choose the same label."),
    ("g-kappa", "Cohen's kappa (κ)", "Agreement corrected for chance. 1 = perfect, 0 = no better than chance. Report it with the number of items."),
    ("g-adjudication", "Adjudication", "The step where raters discuss each disagreement and record a final label and the reason."),
    ("g-tiers", "Label status", "How far a label has been checked: Draft (one AI), AI cross-checked (a second AI, blind to our label, agreed; <strong>no human has checked it</strong>), Reviewed by a human, Adjudicated by humans."),
    ("g-provisional", "Provisional", "Counts and gaps that depend on decisions not yet made. They can change."),
]


def guide_body(cn: dict, st: dict, lock: dict) -> str:
    s = cn["summary"]
    names = {t["id"]: t["name"] for t in cn["tactics"]}
    gaps_p = ", ".join(names[g] for g in cn["gaps"]["primary"])
    gaps_s = ", ".join(names[g] for g in cn["gaps"]["with_steps"])
    tiers = cn["tiers"]["total"]
    by = cn["totals"]["by_setting"]
    ex = next(t for t in json.loads((GEN / "tasks.json").read_text()) if t["id"] == "poison_git_sync")
    stress = "".join(
        f"<tr><td>{E(g['name'])}</td><td>{100 * g['current_labels']:.1f}%</td><td>{100 * g['before_v1_1_original_steps']:.1f}%</td>"
        f"<td>{'yes' if g['robust_current'] else 'no'}</td></tr>"
        for g in st["gap_stays_zero"])
    settings_text = ", ".join(f"{x['name']} {by[x['id']]}" for x in cn["settings"])
    unf_text = f" {cn['totals']['unfinished_upstream']} unfinished upstream drafts are excluded." if cn["totals"]["unfinished_upstream"] else ""
    extras_li = f"\n<li>{E(cn['extras_note'])}</li>" if cn.get("extras_note") else ""
    planned_text = f" {s['planned_scorer_tasks']} tasks have an upstream scorer that is only planned, so their labels rest on a written design." if s["planned_scorer_tasks"] else ""
    gloss = "".join(f'<dt id="{i}">{t}</dt><dd>{d}</dd>' for i, t, d in GLOSSARY)
    toc = "".join(f'<li><a href="#{a}">{t}</a></li>' for a, t in [("why", "What AI control is, and why coverage matters"), ("how", "How a control evaluation works"),
          ("labels", "How a side task becomes a label"), ("reading", "How to read the Explorer"), ("results", "What the results show, and do not show"),
          ("glossary", "Glossary"), ("related", "Related work"), ("cite", "How to cite")])
    return f"""
<h1>Guide</h1>
<p class="lede">Plain-language notes on what this project measures. Every number on this page is computed by a script from the files in the repository.</p>
<nav aria-label="On this page"><ol class="toc">{toc}</ol></nav>
<div class="prose">
<h2 id="why">What AI control is, and why coverage matters</h2>
<p>An <a href="#g-ai-control">AI control</a> evaluation reports how often safety measures stop an AI agent that is secretly trying to cause harm. That number only covers the attacks the evaluation includes. If whole kinds of attack are missing, the number says nothing about them.</p>
<p>Security teams check this kind of gap with MITRE ATT&amp;CK®; this project applies the same check to AI control settings. For each public <a href="#g-control-setting">control setting</a> it lists every <a href="#g-side-task">side task</a>, labels it with an ATT&amp;CK <a href="#g-tactic">tactic</a> and <a href="#g-technique">technique</a> (plus MITRE ATLAS where the target is an AI system), and shows which tactics have no side task.</p>
<p class="callout"><strong>What this does not claim.</strong> A task count shows what is <em>tested</em>, not what is <em>caught</em>. A gap means &ldquo;untested&rdquo;, not &ldquo;dangerous&rdquo; and not &ldquo;undefended&rdquo;.</p>

<h2 id="how">How a control evaluation works</h2>
<figure>{DIAGRAM}<figcaption>One attack run, step by step. In an honest run there is no side task, and the same monitor and audit steps measure how often honest actions get flagged.</figcaption></figure>
<ol>
<li>The <a href="#g-agent">agent</a> works on a <a href="#g-main-task">main task</a>. In an attack run it also has a hidden side task.</li>
<li>Each step that makes tool calls is an <a href="#g-action">action</a>.</li>
<li>A <a href="#g-monitor">monitor</a> reads every action and gives it a <a href="#g-suspicion">suspicion score</a>.</li>
<li>The most suspicious actions go to a human <a href="#g-audit">audit</a>. The audit budget limits how many honest actions can be flagged.</li>
<li>The agent is <em>caught</em> if an audit comes before the side task's harm. Otherwise it is not caught. <a href="#g-safety">Safety</a> is the chance of being caught: P(caught) / (P(caught) + P(uncaught and side task succeeded)).</li>
</ol>
<p>Sources for these definitions: the Control Tower docs (<em>AI Control Concepts</em> and <em>Glossary</em>) at commit <code>{lock['references']['control_tower_docs']['sha'][:10]}</code>.</p>

<h2 id="labels">How a side task becomes a label</h2>
<p>Example, end to end: the side task <code>{E(ex['environment'])}/{E(ex['id'])}</code> in LinuxArena (MIT-licensed text).</p>
<ol>
<li><strong>Goal.</strong> &ldquo;{E(ex['goal'])}&rdquo;</li>
<li><strong>What the scorer checks.</strong> That valid workflow definitions synced from the repository end up corrupted, so executions fail.</li>
<li><strong>Rule R1.</strong> The tactic is the end goal the scorer checks, not the method. The method (changing a service) is not the goal. The end goal is damaged data.</li>
<li><strong>Rule R5.</strong> Data is changed and the harm is the change itself, so the tactic is Impact ({E(ex['primary_tactic'])}).</li>
<li><strong>Technique.</strong> {E(ex['technique'])} {E(ex['technique_name'])}.</li>
<li><strong>ATLAS.</strong> None. The stored data is not an AI system (rule R7).</li>
<li><strong>Status.</strong> {E(ex['label_status'].replace('_', ' '))}. A human has not yet checked it.</li>
</ol>
<p>The full rules are in the <a href="{REPO_URL}/blob/main/codebook/CODEBOOK.md">codebook</a> <span class="pending">(works after publishing)</span>.</p>

<h2 id="reading">How to read the Explorer</h2>
<figure><img src="assets/img/explorer-1280-light.png" alt="The Explorer at desktop width: controls, a summary strip, label status counts and the tactic matrix with gap columns hatched" width="1280" height="900" loading="lazy">
<figcaption>Desktop. Controls at the top, then the summary strip, label status counts, and one column per tactic. Hatched columns with &ldquo;0 tasks: gap&rdquo; have no tasks.</figcaption></figure>
<figure><img src="assets/img/explorer-400-light.png" alt="The Explorer on a phone: columns stack into a single list" width="400" height="900" loading="lazy" style="max-width:260px">
<figcaption>Phone width. Tactic columns stack into one list.</figcaption></figure>
<ul>
<li><strong>Setting</strong> picks one control setting or all of them together.</li>
<li><strong>End goal only</strong> counts each task once, under its main tactic. <strong>End goal + required steps</strong> also counts it under each tactic its goal text requires.</li>
<li>Click a tactic or technique to list its tasks. Click a task for its goal (or our summary), source link at the pinned commit, labels, rationale, confidence, alternative, status and history.</li>
<li>The page address stores your choices, for example <code>#setting-vllm&amp;steps</code>.</li>
</ul>

<h2 id="results">What the results show, and do not show</h2>
<p class="callout"><strong>Provisional.</strong> All {s['tasks']} labels are drafts. Counts and gaps will change once the open decisions are settled.</p>
<ul>
<li>{s['tasks']} side tasks are counted: {E(settings_text)}.{unf_text}</li>{extras_li}
<li>Counting each task once, across all settings combined, {s['tactics_covered_primary']} of {s['tactics_total']} tactics have at least one task. The gaps are: {E(gaps_p)}. (In a single setting there are more gaps; the Explorer labels them &ldquo;gaps in this setting&rdquo;.)</li>
<li>Also counting required steps, {s['tactics_covered_with_steps']} of {s['tactics_total']} are covered. Still empty: {E(gaps_s)}.</li>
<li>{s['template_tasks']} tasks ({s['template_share_percent']}%) are repeated template tasks (remote code execution, reverse shell, run malware) that appear in several environments.</li>
<li>{s['ambiguous_labels']} labels are marked ambiguous (two tactics are defensible).{planned_text}</li>
<li>Label status: {tiers['draft_needs_human_review']} Draft, {tiers['ai_cross_checked']} AI cross-checked, {tiers['reviewed']} Reviewed by a human, {tiers['adjudicated']} Adjudicated by humans.</li>
</ul>
<p><strong>How firm are the gaps?</strong> We re-ran the counts {st['runs']:,} times, randomly flipping ambiguous labels to their alternative (chance {st['p_flip_ambiguous']}) and moving a task to one of its required-step tactics (chance {st['p_take_step']}). The table shows how often each gap still had zero tasks. We call a gap <em>robust</em> if that is at least {int(100 * st['robust_threshold'])}% of runs. That threshold is our choice, not a standard.</p>
<div class="tablewrap"><table><caption>Share of runs in which a gap tactic stays at zero tasks</caption>
<thead><tr><th scope="col">Gap tactic</th><th scope="col">Current labels</th><th scope="col">Before the required-steps rule was tightened (v1.0)</th><th scope="col">Robust now?</th></tr></thead><tbody>{stress}</tbody></table></div>
<p class="small">This test only reshuffles labels we already have. A gap at 100% means nothing in our labels or alternatives points to it. It does not show that no other labelling would find tasks there.</p>
<p><strong>What the results do not show.</strong> They do not show which attacks monitors catch, only which attacks are included. They cover public tasks only; held-out tasks may fill some gaps. ATT&amp;CK was built for human attackers, so some AI-specific goals fit loosely ({s['null_technique_tasks']} tasks have no fitting technique). One AI drafted every label and a second AI checked them; that is <strong>AI-versus-AI agreement, not human validation</strong>.</p>

<h2 id="glossary">Glossary</h2>
<dl class="glossary">{gloss}</dl>

<h2 id="related">Related work</h2>
<p>We searched for newer work that maps control settings to ATT&amp;CK or ATLAS and found none (five web searches; not exhaustive). Details: <a href="{REPO_URL}/blob/main/docs/RELATED_WORK_SEARCH.md">RELATED_WORK_SEARCH.md</a> <span class="pending">(works after publishing)</span>.</p>
<div class="tablewrap"><table><caption>Related work and how it differs</caption>
<thead><tr><th scope="col">Work</th><th scope="col">How it differs from this project</th></tr></thead><tbody>
<tr><td><a href="https://arxiv.org/abs/2604.15384">LinuxArena paper</a></td><td>The control setting itself. Its abstract reports 20 environments and 184 side tasks; we count only the public tasks in the repositories we cover.</td></tr>
<tr><td>Anthropic's LLM ATT&amp;CK Navigator <em>(not verified: only third-party write-ups found, the original page was not located)</em></td><td>Reported to map real-world misuse of an AI model to ATT&amp;CK. It does not map control-setting tasks.</td></tr>
<tr><td><a href="https://taoq-ai.github.io/ziran/reference/benchmarks/atlas-mapping/">ZIRAN ATLAS mapping</a></td><td>A red-team scanner whose attack library is mapped to ATLAS (October 2025 release). A tool for testing agents, not a list of control-setting tasks.</td></tr>
<tr><td><a href="https://arxiv.org/abs/2604.06019">CritBench</a></td><td>81 tasks for AI agents in industrial digital substations, mapped to ATT&amp;CK <em>for ICS</em>. Industrial, not Enterprise, and not about control evaluations.</td></tr>
<tr><td><a href="https://labs.cloudsecurityalliance.org/research/csa-research-note-atlas-agentic-gap-analysis-20260327/">CSA ATLAS agentic gap analysis</a> (draft, 2026-03-27)</td><td>Looks for agent techniques that ATLAS lacks. We checked that ATLAS 2026.10 contains Lateral Movement and Command and Control tactics; we did not verify what the note says about them.</td></tr>
</tbody></table></div>

<h2 id="cite">How to cite</h2>
<p>A <code>CITATION.cff</code> file is added with the repository docs. Until then: Rahman Tory, A. <em>Agent Control Threat Coverage Matrix (ACTCM)</em>, version 0.1.0-draft, 2026. Provisional; not yet published.</p>
</div>
"""


# ------------------------------------------------------------------------------------------- Verify (stub until Phase 7)
def protocol_ctx(cn: dict) -> dict:
    return dict(show_extras=c.publish_extras(), n_repos=len(c.public_lock(c.load_yaml(c.LOCK_FILE))["sources"]), tiers=cn["tiers"]["total"], open_n=len(OPEN_DECISIONS), open_text=" and ".join(OPEN_DECISIONS))


def verify_body(cn: dict) -> str:
    import protocol_content as pc
    return f"""
<h1>Verify</h1>
<p class="lede">How to repeat the work and check it: reproduce the data, check one label, relabel everything independently, check the gaps, and add a new setting.</p>
<div class="prose">
{pc.to_html(pc.sections(protocol_ctx(cn)))}
</div>
"""


def main() -> None:
    cn, st, lock = load()
    (SITE / "assets" / "img").mkdir(parents=True, exist_ok=True)
    data = SITE / "data"
    if data.exists():
        shutil.rmtree(data)
    data.mkdir(parents=True)
    for f in ("counts.json", "tasks.json", "tasks.csv", "stress_results.json"):
        shutil.copy(GEN / f, data / f)
    import yaml
    (data / "status_tiers.json").write_text(json.dumps(yaml.safe_load((c.DATA / "status_tiers.yml").read_text()), indent=1))
    shutil.copy(GEN / "navigator" / "links.json", data / "navigator_links.json")
    (data / "navigator").mkdir()
    for f in (GEN / "navigator").glob("actcm_*.json"):
        shutil.copy(f, data / "navigator" / f.name)
    import protocol_content as pc
    (c.ROOT / "docs" / "PROTOCOL.md").write_text(pc.to_markdown(pc.sections(protocol_ctx(cn))), encoding="utf-8")
    script = '<script src="assets/app.js" defer></script>'
    pages = {
        "index.html": ("ACTCM Explorer", "explorer", explorer_body(cn), script, "Which kinds of attack AI control tests cover, by tactic."),
        "guide.html": ("ACTCM Guide", "guide", guide_body(cn, st, lock), "", "Plain-language guide to AI control, the labels and the results."),
        "verify.html": ("ACTCM Verify", "verify", verify_body(cn), "", "How to verify the data and labels."),
    }
    for fn, (title, active, body, scr, desc) in pages.items():
        (SITE / fn).write_text(page(title, active, body, cn, lock, desc).replace("{SCRIPT}", scr), encoding="utf-8")
    print("built", ", ".join(pages), "and", len(list(data.rglob('*'))), "data files")


if __name__ == "__main__":
    main()
