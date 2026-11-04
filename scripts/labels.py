"""Label tiers, the bot guard, and helpers shared by the Phase 3 scripts.

Status tiers (low to high trust):
  draft_needs_human_review -> ai_cross_checked -> reviewed -> adjudicated
`reviewed` and `adjudicated` may only be set by a named human. Anything that looks like a bot,
script or AI is refused.
"""
from __future__ import annotations

import re
from datetime import date

import common as c

TIERS = ["draft_needs_human_review", "ai_cross_checked", "reviewed", "adjudicated"]
UNLABELLED = "unlabelled"
HUMAN_ONLY = {"reviewed", "adjudicated"}
BOT_MAY_SET = {"draft_needs_human_review", "ai_cross_checked"}
HUMAN_REVIEWERS = {"Adrita Rahman Tory"}  # add contributors here by pull request
BOT_PATTERN = re.compile(r"(claude|bot|script|\bai\b|gpt|llm|assistant|auto|agent)", re.I)


class StatusError(ValueError):
    pass


def looks_like_bot(who: str | None) -> bool:
    return not who or not who.strip() or bool(BOT_PATTERN.search(who))


def check_status_change(new_status: str, who: str | None) -> None:
    """Raise StatusError unless `who` may set `new_status`."""
    if new_status not in TIERS:
        raise StatusError(f"unknown status {new_status!r}")
    if new_status in HUMAN_ONLY:
        if looks_like_bot(who) or who not in HUMAN_REVIEWERS:
            raise StatusError(f"{who!r} may not set {new_status!r}: only a listed human may")


def set_status(task: dict, new_status: str, who: str, change: str, reason: str,
               today: str | None = None) -> None:
    check_status_change(new_status, who)
    old = task.get("label_status")
    task["label_status"] = new_status
    task.setdefault("history", []).append(dict(
        date=today or date.today().isoformat(), who=who, change=f"status {old} -> {new_status}: {change}",
        reason=reason))


def tactic_ids(fw: dict) -> dict:
    return {t["name"]: t["id"] for t in fw["attack"]["tactics"]}


def load_tasks(public_only: bool = False) -> dict:
    """{(environment, id): (path, task)}. public_only=True drops tasks that are hidden by config/publish.yml."""
    out = {}
    for f in (c.public_task_files() if public_only else sorted(c.TASKS_DIR.rglob("*.yml"))):
        t = c.load_yaml(f)
        out[(t["environment"], t["id"])] = (f, t)
    return out


def make_label(primary, technique, steps, confidence, rationale, atlas=None, alternative=None) -> dict:
    lab = dict(attack=dict(primary_tactic=primary, technique=technique, required_step_tactics=list(steps or [])))
    if atlas:
        lab["atlas"] = dict(technique=atlas)
    lab["confidence"] = confidence
    lab["alternative"] = alternative
    lab["rationale"] = rationale
    return lab
