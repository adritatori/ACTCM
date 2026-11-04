"""Shared helpers: paths, YAML I/O, and read-only git access pinned to a SHA."""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOCK_FILE = DATA / "sources.lock.yml"
TASKS_DIR = DATA / "tasks"
CACHE = ROOT / ".cache" / "sources"
CONFIG_FILE = ROOT / "config" / "publish.yml"
HIDDEN_SETTING = "linuxarena-extras"       # hidden unless publish_extras is true
GITHUB = "https://github.com"


class _Dumper(yaml.SafeDumper):
    pass


def _str_repr(dumper: yaml.Dumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_repr)


def dump_yaml(obj, path: Path | None = None) -> str:
    text = yaml.dump(obj, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def config() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {"publish_extras": False}


def publish_extras() -> bool:
    """False (the safe default) hides the LinuxArena-extras tasks from every public output."""
    return bool(config().get("publish_extras", False))


def is_public_setting(setting: str) -> bool:
    return setting != HIDDEN_SETTING or publish_extras()


def visible_settings() -> list[str]:
    return [s for s in ["linuxarena", "linuxarena-extras", "refactor_arena", "vllm"] if is_public_setting(s)]


def public_task_files() -> list:
    """Task files that may appear in public outputs. Label tooling uses every file under data/tasks instead."""
    out = []
    for f in sorted(TASKS_DIR.rglob("*.yml")):
        rel = f.relative_to(TASKS_DIR).parts
        if is_public_setting(rel[0]):
            out.append(f)
    return out


def public_lock(lock: dict) -> dict:
    """The lock file as the public build sees it: hidden sources and manifests removed."""
    out = dict(lock)
    out["sources"] = [s for s in lock["sources"] if is_public_setting(s["setting"])]
    out["manifests"] = [m for m in lock["manifests"] if is_public_setting(m["setting"])]
    return out


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def resolve_tag(repo: str, tag: str) -> str:
    """Return the commit SHA a tag points to (peeled, for annotated tags)."""
    out = git("ls-remote", f"{GITHUB}/{repo}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    refs = {}
    for line in out.splitlines():
        sha, ref = line.split()
        refs[ref] = sha
    peeled = refs.get(f"refs/tags/{tag}^{{}}")
    direct = refs.get(f"refs/tags/{tag}")
    sha = peeled or direct
    if not sha:
        raise RuntimeError(f"tag {tag} not found in {repo}")
    return sha


def fetch_at(repo: str, sha: str, name: str) -> Path:
    """Shallow-fetch exactly `sha` into the cache. Fails if the fetched commit differs."""
    d = CACHE / name
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".git").exists():
        git("init", "-q", cwd=d)
    remotes = git("remote", cwd=d).split()
    if "origin" not in remotes:
        git("remote", "add", "origin", f"{GITHUB}/{repo}", cwd=d)
    have = git("cat-file", "-t", sha, cwd=d, check=False).strip()
    if have != "commit":
        git("fetch", "-q", "--depth", "1", "origin", sha, cwd=d)
    got = git("rev-parse", "FETCH_HEAD", cwd=d).strip() if have != "commit" else sha
    if got != sha:
        raise RuntimeError(f"{repo}: wanted {sha}, got {got}")
    return d


# All reads below go through the object database at an explicit SHA, never the working tree.
def show(d: Path, sha: str, path: str) -> str | None:
    res = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=d, capture_output=True)
    return res.stdout.decode("utf-8") if res.returncode == 0 else None


def exists(d: Path, sha: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}:{path}"], cwd=d, capture_output=True).returncode == 0


def ls_tree(d: Path, sha: str, path: str = "", dirs_only: bool = False) -> list[str]:
    spec = f"{sha}:{path}" if path else sha
    out = git("ls-tree", *(["-d"] if dirs_only else []), "--name-only", spec, cwd=d, check=False)
    return sorted(out.splitlines())
