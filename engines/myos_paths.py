#!/usr/bin/env python3
"""
myos_paths.py — the SINGLE source of truth for the myOS vault structure.

Every myOS script imports this instead of hardcoding folder names like
"Academics" or "0 Capture/Inbox". A re-organisation then becomes a one-line
edit in the JSON config (or the DEFAULTS below) instead of silently breaking
exports, sync or dashboards — which is exactly what used to happen.

Resilience by design:
  - DEFAULTS below ALWAYS work, even if the JSON override is missing/corrupt.
  - The config file (if present) shallow-overrides them.
  - A few environment variables override both (handy for tests and CI).
  So there is no single point of failure: a missing config can't brick a script.

Where things are looked up:
  MYOS_CONFIG              path of the JSON config   (default ~/.config/myos/paths.json)
  MYOS_VAULT               the vault root            (default: config "vault", else ~/Documents/Obsidian Vault)
  MYOS_CLAUDE_MEMORY_DIR   Claude Code's memory dir for the project whose memory
                           is mirrored into the vault (default: config "claude_memory_dir")
  MYOS_SKILLS_DIR          where the skills live     (default: config "skills_dir",
                           else <vault>/HERMES/Skills/myos)

CLI (so shell scripts can use it too):
    python myos_paths.py                # selftest: print every path + exists?
    python myos_paths.py get inbox      # print one absolute path
    python myos_paths.py vault          # print the vault root
    python myos_paths.py skills         # print the skills dir
    python myos_paths.py memory         # print Claude's memory dir ('' if unset)
    python myos_paths.py layout         # print current layout name
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("MYOS_CONFIG",
                                  str(Path.home() / ".config" / "myos" / "paths.json"))).expanduser()

# ── DEFAULTS ────────────────────────────────────────────────────────────────
# The fallback that keeps every script working if the JSON is missing/corrupt.
# A layout change is edited in the config first, then mirrored here.
DEFAULTS = {
    "schema_version": 1,
    "layout": "layers-v1",
    "vault": str(Path.home() / "Documents" / "Obsidian Vault"),
    # Claude Code keeps per-project memory under ~/.claude/projects/<slug>/memory.
    # Point this at the one you want mirrored into the vault ("" = feature off).
    "claude_memory_dir": "",
    # Where the SKILL.md tree lives. "" = <vault>/HERMES/Skills/myos.
    "skills_dir": "",
    "dirs": {
        "inbox": "0 Capture/Inbox",
        "sandbox": "0 Capture/Sandbox",
        "projects": "1 Active/Projects",
        "journal": "1 Active/Journal",
        "tasks": "1 Active/Tasks",
        "inventory": "1 Active/Inventory",
        "academics": "2 Knowledge/Academics",
        "systems": "2 Knowledge/Systems",
        "source_material": "2 Knowledge/Source Material",
        "myos": "3 myOS",
        "tags": "Tags",
        "templates": "Templates",
        "images": "Images",
        "archive": "_Archive",
        "claude_memory": "CLAUDE",
    },
    # Paths never treated as live knowledge.
    "exclude_globs": ["**/_Archive/**", "**/Archive/**", "**/.trash/**"],
}


def _deep_copy(obj):
    return json.loads(json.dumps(obj))


def _load() -> dict:
    cfg = _deep_copy(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            override = json.loads(CONFIG_FILE.read_text())
            for k, v in override.items():
                if k.startswith("_"):
                    continue                      # comments like "_README"
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    except Exception as e:  # never let bad config brick a caller
        print(f"[myos_paths] WARNING: ignoring bad {CONFIG_FILE}: {e}", file=sys.stderr)
    # Environment wins over the file.
    for env, key in (("MYOS_VAULT", "vault"),
                     ("MYOS_CLAUDE_MEMORY_DIR", "claude_memory_dir"),
                     ("MYOS_SKILLS_DIR", "skills_dir")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


_CFG = _load()


# ── Public API ──────────────────────────────────────────────────────────────
def config() -> dict:
    return _CFG


def layout() -> str:
    return _CFG.get("layout", "unknown")


def vault_root() -> Path:
    return Path(_CFG["vault"]).expanduser()


def d(key: str) -> Path:
    """Absolute path for a logical dir key. Raises KeyError on unknown key."""
    rel = _CFG["dirs"].get(key)
    if rel is None:
        raise KeyError(
            f"[myos_paths] unknown dir key {key!r}; known: {sorted(_CFG['dirs'])}"
        )
    return vault_root() / rel


def skills_dir() -> Path:
    raw = _CFG.get("skills_dir") or ""
    return Path(raw).expanduser() if raw else vault_root() / "HERMES" / "Skills" / "myos"


def claude_memory_dir() -> Path | None:
    """Claude Code's flat memory dir that mirrors <vault>/CLAUDE, or None if unset."""
    raw = _CFG.get("claude_memory_dir") or ""
    return Path(raw).expanduser() if raw else None


def exclude_globs() -> list[str]:
    return list(_CFG.get("exclude_globs", []))


# Convenience accessors (readability at call sites)
def inbox() -> Path: return d("inbox")
def sandbox() -> Path: return d("sandbox")
def journal() -> Path: return d("journal")
def projects() -> Path: return d("projects")
def myos() -> Path: return d("myos")
def tags() -> Path: return d("tags")
def templates() -> Path: return d("templates")
def images() -> Path: return d("images")
def archive() -> Path: return d("archive")


# ── CLI / selftest ──────────────────────────────────────────────────────────
def _selftest() -> int:
    vr = vault_root()
    print(f"layout : {layout()}")
    print(f"vault  : {vr}  exists={vr.exists()}")
    print(f"config : {CONFIG_FILE}  exists={CONFIG_FILE.exists()}")
    print(f"skills : {skills_dir()}  exists={skills_dir().exists()}")
    mem = claude_memory_dir()
    print(f"memory : {mem or '(unset)'}" + (f"  exists={mem.exists()}" if mem else ""))
    print("dirs:")
    missing = []
    for k in _CFG["dirs"]:
        p = d(k)
        ok = p.exists()
        if not ok:
            missing.append(k)
        print(f"  {k:16} {'ok ' if ok else 'MISS'}  {p}")
    print()
    print(f"missing dirs : {missing or 'none'}")
    # Non-zero exit if the vault itself or the inbox is missing (the silent-breakage signal).
    return 1 if (not vr.exists() or "inbox" in missing) else 0


def main(argv: list[str]) -> int:
    if not argv:
        return _selftest()
    cmd = argv[0]
    if cmd == "get" and len(argv) > 1:
        print(d(argv[1]))
        return 0
    if cmd == "layout":
        print(layout())
        return 0
    if cmd == "vault":
        print(vault_root())
        return 0
    if cmd == "skills":
        print(skills_dir())
        return 0
    if cmd == "memory":
        print(claude_memory_dir() or "")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
