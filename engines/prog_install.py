#!/usr/bin/env python3
"""
prog_install.py — Hermes "program installer" engine.

Scans the system's real package sources for a program, ranks the candidates,
shows the user exactly what would be installed, and installs it — safely.

Safety model (the whole point: "we do not want it to break anything"):
  * search/plan are READ-ONLY — they only query package databases.
  * The only thing this engine runs WITHOUT asking a human is a per-user
    Flatpak install (`flatpak install --user`): no sudo, user-scoped, and
    trivially reversible (`flatpak uninstall --user`).
  * pacman / AUR installs need root (no passwordless sudo on this box) and do a
    full sync that can break a half-updated system. So for those, the engine
    does NOT elevate — it returns the exact, vetted command for the user to run
    themselves, together with a plan of what it pulls in.
  * Every external command is run via a list argv (never shell=True) and only
    after the package NAME is validated against a strict whitelist regex, so a
    crafted "name" can't smuggle in shell metacharacters.

Sources scanned:
  * official  — Arch repos via `pacman -Ss`     (most trusted / most compatible)
  * flatpak   — Flathub via `flatpak search`     (sandboxed, user-installable)
  * aur       — AUR via `paru -Ssa`              (community; ranked by votes)

rofi: GUI packages ship their own .desktop file (pacman → /usr/share/...,
flatpak → ~/.local/share/flatpak/exports/...), both already on rofi's
`-show drun` path, so they appear automatically. For a launcher-less CLI/binary
the user wants in rofi anyway, `ensure_rofi_entry()` synthesises a .desktop.

Usage (CLI):
    prog_install.py search "obsidian"
    prog_install.py plan obsidian --source official
    prog_install.py install org.gimp.GIMP --source flatpak
    prog_install.py install obsidian --source official   # prints command to run

Importable:
    import prog_install
    md = prog_install.search_md("obsidian")
"""

from __future__ import annotations

import re
import sys
import shutil
import argparse
import subprocess
from dataclasses import dataclass, field

# ── Config ────────────────────────────────────────────────────────────────────

SEARCH_TIMEOUT = 30      # seconds per source search (AUR can be slow)
PLAN_TIMEOUT   = 30
INSTALL_TIMEOUT = 1800   # flatpak downloads can be large
PER_SOURCE_MAX = 6       # cap candidates shown per source

# A package/app name we are willing to hand to a package manager. Covers Arch
# package names and Flatpak application IDs (dotted). Deliberately strict —
# anything else is rejected before it reaches a subprocess.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@-]*$")

VALID_SOURCES = ("official", "aur", "flatpak")
FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _valid_name(name: str) -> bool:
    return bool(name) and len(name) <= 128 and bool(NAME_RE.match(name))


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run argv with no shell, capturing output. Never raises on non-zero."""
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, check=False
    )


# ── Candidate model ───────────────────────────────────────────────────────────

@dataclass
class Candidate:
    name: str                 # package name / flatpak app id
    source: str               # official | aur | flatpak
    version: str = ""
    desc: str = ""
    votes: int = 0            # AUR popularity (0 for others)
    installed: bool = False
    repo: str = ""            # e.g. extra/community for official, remote for flatpak

    def rank_key(self, query: str) -> tuple:
        q = query.lower()
        exact = self.name.lower() == q
        starts = self.name.lower().startswith(q)
        # Trust order: official > flatpak > aur (official is most likely to be
        # compatible and not break the system).
        src_rank = {"official": 0, "flatpak": 1, "aur": 2}.get(self.source, 3)
        # Sort: exact-name first, then name-prefix, then source trust, then
        # AUR votes (desc), then name.
        return (not exact, not starts, src_rank, -self.votes, self.name.lower())


# ── Installed-state helpers ───────────────────────────────────────────────────

def _installed_pacman() -> set[str]:
    if not _have("pacman"):
        return set()
    r = _run(["pacman", "-Qq"], PLAN_TIMEOUT)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def _installed_flatpak() -> set[str]:
    if not _have("flatpak"):
        return set()
    r = _run(["flatpak", "list", "--columns=application"], PLAN_TIMEOUT)
    return set(r.stdout.split()) if r.returncode == 0 else set()


# ── Source searches (read-only) ───────────────────────────────────────────────

def _search_official(query: str, installed: set[str]) -> list[Candidate]:
    """Parse `pacman -Ss <query>`: 'repo/name ver [extra]\\n    desc'."""
    if not _have("pacman"):
        return []
    r = _run(["pacman", "-Ss", query], SEARCH_TIMEOUT)
    out: list[Candidate] = []
    lines = r.stdout.splitlines()
    i = 0
    while i < len(lines):
        head = lines[i]
        m = re.match(r"^(\S+?)/(\S+)\s+(\S+)", head)
        if m:
            repo, name, ver = m.group(1), m.group(2), m.group(3)
            desc = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                desc = lines[i + 1].strip()
                i += 1
            out.append(Candidate(name=name, source="official", version=ver,
                                  desc=desc, repo=repo,
                                  installed=name in installed))
        i += 1
    return out


def _search_aur(query: str, installed: set[str]) -> list[Candidate]:
    """Parse `paru -Ssa <query>`: 'aur/name ver [+votes ~pop]\\n    desc'."""
    helper = "paru" if _have("paru") else ("yay" if _have("yay") else None)
    if not helper:
        return []
    r = _run([helper, "-Ssa", query], SEARCH_TIMEOUT)
    out: list[Candidate] = []
    lines = r.stdout.splitlines()
    i = 0
    while i < len(lines):
        head = lines[i]
        m = re.match(r"^aur/(\S+)\s+(\S+)(?:.*?\[\+(\d+)\s)?", head)
        if m:
            name, ver = m.group(1), m.group(2)
            votes = int(m.group(3)) if m.group(3) else 0
            desc = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                desc = lines[i + 1].strip()
                i += 1
            out.append(Candidate(name=name, source="aur", version=ver,
                                  desc=desc, votes=votes, repo="aur",
                                  installed=name in installed))
        i += 1
    return out


def _search_flatpak(query: str, installed: set[str]) -> list[Candidate]:
    """Parse `flatpak search <query>`: Name\\tDesc\\tAppID\\tVer\\tBranch\\tRemote."""
    if not _have("flatpak"):
        return []
    r = _run(["flatpak", "search", "--columns=name,description,application,version,remotes",
              query], SEARCH_TIMEOUT)
    if r.returncode != 0 or "No matches found" in (r.stdout + r.stderr):
        return []
    out: list[Candidate] = []
    for line in r.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) < 3:
            continue
        name, desc, appid = cols[0], cols[1], cols[2]
        ver = cols[3] if len(cols) > 3 else ""
        remote = cols[4] if len(cols) > 4 else "flathub"
        out.append(Candidate(name=appid, source="flatpak", version=ver,
                              desc=f"{name} — {desc}".strip(" —"),
                              repo=remote, installed=appid in installed))
    return out


def search(query: str) -> list[Candidate]:
    """Scan all sources, rank, and return a capped, de-duplicated candidate list."""
    query = query.strip()
    if not query:
        return []
    inst_pac = _installed_pacman()
    inst_flat = _installed_flatpak()

    results: list[Candidate] = []
    results += _search_official(query, inst_pac)[:PER_SOURCE_MAX * 2]
    results += _search_flatpak(query, inst_flat)[:PER_SOURCE_MAX * 2]
    results += _search_aur(query, inst_pac)[:PER_SOURCE_MAX * 2]

    results.sort(key=lambda c: c.rank_key(query))

    # Keep at most PER_SOURCE_MAX per source, preserving rank order.
    seen: dict[str, int] = {}
    capped: list[Candidate] = []
    for c in results:
        n = seen.get(c.source, 0)
        if n < PER_SOURCE_MAX:
            capped.append(c)
            seen[c.source] = n + 1
    return capped


# ── Markdown presentation ─────────────────────────────────────────────────────

_SRC_LABEL = {"official": "🟢 official", "flatpak": "🔵 flatpak", "aur": "🟡 AUR"}


def search_md(query: str) -> str:
    cands = search(query)
    if not cands:
        return (f"No packages found for **{query}** in the official repos, "
                f"Flathub, or the AUR. Try a different name/keyword.")
    lines = [f"Found **{len(cands)}** option(s) for **{query}** — pick one to install:\n"]
    for i, c in enumerate(cands, 1):
        tags = [_SRC_LABEL.get(c.source, c.source)]
        if c.installed:
            tags.append("✅ already installed")
        if c.votes:
            tags.append(f"👍 {c.votes}")
        meta = " · ".join(tags)
        desc = (c.desc[:140] + "…") if len(c.desc) > 140 else c.desc
        lines.append(f"{i}. **{c.name}** `{c.version}`  ({meta})\n   {desc}")
    lines.append(
        "\nReply with the number (or name) you want. Official/AUR installs need "
        "your password, so I'll hand you the exact command; Flatpaks I can "
        "install for you directly."
    )
    return "\n".join(lines)


# ── Plan (read-only "exactly what will be installed") ─────────────────────────

def plan_md(name: str, source: str) -> str:
    if source not in VALID_SOURCES:
        return f"Error: unknown source '{source}'."
    if not _valid_name(name):
        return f"Error: '{name}' is not a valid package name."
    if source == "official":
        r = _run(["pacman", "-Si", name], PLAN_TIMEOUT)
        if r.returncode != 0:
            return f"Couldn't find **{name}** in the official repos."
        info = {}
        for ln in r.stdout.splitlines():
            if ":" in ln and not ln.startswith(" "):
                k, _, v = ln.partition(":")
                info[k.strip()] = v.strip()
        return (f"**{name}** (official `{info.get('Repository','')}`)\n"
                f"- Version: {info.get('Version','?')}\n"
                f"- Download size: {info.get('Download Size','?')}\n"
                f"- Installed size: {info.get('Installed Size','?')}\n"
                f"- Depends on: {info.get('Depends On','none')[:200]}\n")
    if source == "flatpak":
        return (f"**{name}** (Flathub) — I'll install it per-user "
                f"(`flatpak install --user`); no system changes, no password, "
                f"and removable with one command.")
    # aur
    helper = "paru" if _have("paru") else "yay"
    r = _run([helper, "-Si", name], PLAN_TIMEOUT)
    if r.returncode != 0:
        return f"Couldn't find **{name}** in the AUR."
    desc = ""
    for ln in r.stdout.splitlines():
        if ln.startswith("Description"):
            desc = ln.partition(":")[2].strip()
            break
    return (f"**{name}** (AUR) — {desc}\n"
            f"AUR packages build from source and need your password, so I'll give "
            f"you the command to run rather than installing it silently.")


# ── Install ────────────────────────────────────────────────────────────────────

def _ensure_flathub_user() -> None:
    _run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
          FLATHUB_REPO], PLAN_TIMEOUT)


def install(name: str, source: str) -> str:
    """Install (flatpak) or return the exact command to run (official/aur)."""
    if source not in VALID_SOURCES:
        return f"Error: unknown source '{source}' (expected official/aur/flatpak)."
    if not _valid_name(name):
        return (f"Error: refusing to act on '{name}' — not a valid package name. "
                f"(Safety check: names must be plain package identifiers.)")

    if source == "flatpak":
        if not _have("flatpak"):
            return "Error: flatpak is not installed on this system."
        _ensure_flathub_user()
        r = _run(["flatpak", "install", "--user", "-y", "flathub", name],
                 INSTALL_TIMEOUT)
        if r.returncode == 0:
            return (f"✅ Installed **{name}** (Flatpak, per-user). It should now "
                    f"appear in rofi. To remove it later: "
                    f"`flatpak uninstall --user {name}`.")
        err = (r.stderr or r.stdout).strip()[-400:]
        return f"⚠️ Flatpak install of **{name}** failed:\n```\n{err}\n```"

    # official / AUR: do NOT elevate. Hand back the vetted command + plan.
    if source == "official":
        cmd = f"sudo pacman -S --needed {name}"
    else:
        helper = "paru" if _have("paru") else "yay"
        cmd = f"{helper} -S {name}"
    plan = plan_md(name, source)
    return (
        f"{plan}\n\n"
        f"This needs your password, so I won't run it unattended. Run it yourself "
        f"(it'll show the full package list and ask Y/n before changing anything):\n\n"
        f"```\n{cmd}\n```\n"
        f"Once installed it'll show up in rofi automatically. Tell me if you want "
        f"me to walk through it or check what it pulls in first."
    )


# ── rofi launcher synthesis (for launcher-less CLI/binaries) ──────────────────

def ensure_rofi_entry(name: str, exec_cmd: str, display: str = "") -> str:
    if not _valid_name(name):
        return f"Error: '{name}' is not a valid entry name."
    from pathlib import Path
    appdir = Path.home() / ".local/share/applications"
    appdir.mkdir(parents=True, exist_ok=True)
    target = appdir / f"{name}.desktop"
    if target.exists():
        return f"rofi entry for **{name}** already exists ({target})."
    target.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={display or name}\n"
        f"Exec={exec_cmd}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
    return f"✅ Added rofi launcher for **{name}** → {target}"


# ── CLI ────────────────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Hermes program installer engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("search"); ps.add_argument("query", nargs="+")
    pp = sub.add_parser("plan")
    pp.add_argument("name"); pp.add_argument("--source", required=True, choices=VALID_SOURCES)
    pi = sub.add_parser("install")
    pi.add_argument("name"); pi.add_argument("--source", required=True, choices=VALID_SOURCES)

    args = p.parse_args(argv)
    if args.cmd == "search":
        print(search_md(" ".join(args.query)))
    elif args.cmd == "plan":
        print(plan_md(args.name, args.source))
    elif args.cmd == "install":
        print(install(args.name, args.source))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
