#!/usr/bin/env python3
"""
sys_update.py — Hermes "system updater" engine.

The whole point (the author's words): "just the standard update command but tell me
everything that will be updated so I can commit like y/n ... an updater that
helps prevent breakage."

So this engine is, above all, a SAFE PREVIEW:

  * check() / check_md() are 100% READ-ONLY. They never touch the live pacman
    sync database. Official updates come from `checkupdates` (which syncs into a
    throwaway temp DB — the canonical way to see pending updates without the
    dangerous `pacman -Sy` partial-sync that breaks Arch systems), AUR updates
    from `paru -Qua` (a query), and Flatpak from `flatpak remote-ls --updates`.

  * Before any update it FLAGS risky packages (kernel, nvidia, mesa, glibc,
    systemd, grub, …) and says whether a reboot will be needed — that's the
    "prevent breakage" part.

  * apply():
      - Flatpak updates run directly (`flatpak update --user -y`): user-scoped,
        no password, no system risk.
      - Official + AUR updates need root, and this box has no passwordless sudo.
        We deliberately do NOT elevate. We hand back the exact, vetted command
        (`paru -Syu`, the correct all-in-one transaction that never leaves a
        partial upgrade) for the user to run in a terminal, where it shows the full
        package list and asks Y/n itself. Same safety model as prog_install.py.

Usage (CLI):
    sys_update.py check                 # list everything pending (read-only)
    sys_update.py check --full          # don't truncate the list
    sys_update.py apply                 # run flatpak updates; print pacman/AUR cmd
    sys_update.py apply --flatpak-only  # only the Flatpak updates

Importable:
    import sys_update
    md = sys_update.check_md()
"""

from __future__ import annotations

import sys
import shutil
import argparse
import subprocess
from dataclasses import dataclass

# ── Config ────────────────────────────────────────────────────────────────────

CHECK_TIMEOUT   = 120     # checkupdates can download a fresh temp DB
AUR_TIMEOUT     = 120     # paru hits the AUR RPC for every installed AUR pkg
FLATPAK_TIMEOUT = 120
UPDATE_TIMEOUT  = 3600    # a full flatpak update can be large

# How many packages to show in the per-source list before truncating (the
# summary stays readable on Discord/Supernote; `full=True` shows everything).
LIST_CAP = 60

# Substrings that mark a package as "watch out, this can break boot/graphics or
# needs a reboot". Matched case-insensitively against the package name.
RISKY = {
    "kernel/boot": ("linux", "linux-cachyos", "linux-zen", "linux-lts",
                    "linux-headers", "mkinitcpio", "grub", "systemd-boot",
                    "limine", "dracut"),
    "graphics":    ("nvidia", "nvidia-utils", "mesa", "vulkan", "xorg-server",
                    "xf86-video", "lib32-nvidia", "lib32-mesa"),
    "core":        ("glibc", "systemd", "gcc", "gcc-libs", "pacman",
                    "archlinux-keyring", "dbus", "openssl"),
}
# Updating any of these implies a reboot is the safe move.
REBOOT_HINT = ("linux", "linux-cachyos", "linux-zen", "linux-lts", "nvidia",
               "systemd", "glibc", "mesa")


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run argv with no shell, capturing output. Never raises on non-zero."""
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, check=False
    )


# ── Update model ──────────────────────────────────────────────────────────────

@dataclass
class Upd:
    name: str
    old: str
    new: str
    source: str        # official | aur | flatpak


# ── Read-only checks ──────────────────────────────────────────────────────────

def _check_official() -> list[Upd]:
    """`checkupdates`: 'name old -> new' lines, against a throwaway temp DB."""
    if not _have("checkupdates"):
        return []
    r = _run(["checkupdates"], CHECK_TIMEOUT)
    # checkupdates exits 2 when there are simply no updates — not an error.
    out: list[Upd] = []
    for ln in r.stdout.splitlines():
        parts = ln.split()
        if len(parts) >= 4 and parts[2] == "->":
            out.append(Upd(parts[0], parts[1], parts[3], "official"))
    return out


def _check_aur() -> list[Upd]:
    """`paru -Qua` (query AUR for updates to installed AUR pkgs) — read-only."""
    helper = "paru" if _have("paru") else ("yay" if _have("yay") else None)
    if not helper:
        return []
    r = _run([helper, "-Qua"], AUR_TIMEOUT)
    out: list[Upd] = []
    for ln in r.stdout.splitlines():
        parts = ln.split()
        if len(parts) >= 4 and parts[2] == "->":
            out.append(Upd(parts[0], parts[1], parts[3], "aur"))
    return out


def _check_flatpak() -> list[Upd]:
    """`flatpak remote-ls --updates`: tab columns name/app-id/version/branch…"""
    if not _have("flatpak"):
        return []
    r = _run(["flatpak", "remote-ls", "--updates",
              "--columns=application,version"], FLATPAK_TIMEOUT)
    if r.returncode != 0:
        return []
    out: list[Upd] = []
    for ln in r.stdout.splitlines():
        cols = ln.split("\t")
        appid = cols[0].strip()
        ver = cols[1].strip() if len(cols) > 1 else ""
        if appid:
            out.append(Upd(appid, "", ver, "flatpak"))
    return out


def check() -> dict[str, list[Upd]]:
    """Read-only: gather pending updates from all three sources."""
    return {
        "official": _check_official(),
        "aur":      _check_aur(),
        "flatpak":  _check_flatpak(),
    }


# ── Risk analysis ─────────────────────────────────────────────────────────────

def _risk_flags(upds: list[Upd]) -> dict[str, list[str]]:
    """Group risky package names by category, for the 'prevent breakage' note."""
    hits: dict[str, list[str]] = {}
    names = [u.name.lower() for u in upds]
    for cat, needles in RISKY.items():
        found = sorted({u.name for u, nl in zip(upds, names)
                        if any(nl == n or nl.startswith(n + "-") or nl == n
                               for n in needles)})
        if found:
            hits[cat] = found
    return hits


def _needs_reboot(upds: list[Upd]) -> bool:
    names = [u.name.lower() for u in upds]
    return any(nl == n or nl.startswith(n + "-")
               for nl in names for n in REBOOT_HINT)


# ── Markdown presentation ─────────────────────────────────────────────────────

def _fmt_list(upds: list[Upd], full: bool) -> list[str]:
    lines = []
    shown = upds if full else upds[:LIST_CAP]
    for u in shown:
        if u.old:
            lines.append(f"- `{u.name}`  {u.old} → {u.new}")
        else:
            lines.append(f"- `{u.name}`  → {u.new}")
    if not full and len(upds) > LIST_CAP:
        lines.append(f"- _…and {len(upds) - LIST_CAP} more "
                     f"(ask for the full list)_")
    return lines


def check_md(full: bool = False) -> str:
    data = check()
    official, aur, flatpak = data["official"], data["aur"], data["flatpak"]
    total = len(official) + len(aur) + len(flatpak)
    if total == 0:
        return "✅ **System is up to date** — nothing pending in the repos, AUR, or Flatpak."

    repo_pkgs = official + aur          # everything that goes through paru -Syu
    parts = [f"🔄 **{total} update(s) available** "
             f"— official: {len(official)}, AUR: {len(aur)}, "
             f"Flatpak: {len(flatpak)}\n"]

    # Risk / breakage note first — this is the "prevent breakage" payload.
    flags = _risk_flags(repo_pkgs)
    if flags:
        parts.append("> ⚠️ **Heads-up — sensitive packages in this update:**")
        labels = {"kernel/boot": "Kernel/boot", "graphics": "Graphics",
                  "core": "Core system"}
        for cat, found in flags.items():
            parts.append(f"> - **{labels.get(cat, cat)}:** "
                         f"{', '.join('`'+n+'`' for n in found)}")
        if _needs_reboot(repo_pkgs):
            parts.append("> - 🔁 A **reboot** is recommended after this update.")
        parts.append("")

    if official:
        parts.append(f"\n**🟢 Official ({len(official)})**")
        parts += _fmt_list(official, full)
    if aur:
        parts.append(f"\n**🟡 AUR ({len(aur)})**")
        parts += _fmt_list(aur, full)
    if flatpak:
        parts.append(f"\n**🔵 Flatpak ({len(flatpak)})**")
        parts += _fmt_list(flatpak, full)

    # The commit / y-n instruction.
    parts.append("")
    if repo_pkgs:
        helper = "paru" if _have("paru") else "yay"
        parts.append(
            f"To apply the **official + AUR** updates, run this in a terminal "
            f"(it needs your password and will show the full list + ask Y/n "
            f"before changing anything — never a partial upgrade):\n\n"
            f"```\n{helper} -Syu\n```"
        )
    if flatpak:
        parts.append(
            f"\nThe **Flatpak** updates I can apply for you directly (per-user, "
            f"no password) — just say the word."
        )
    return "\n".join(parts)


# ── Apply ─────────────────────────────────────────────────────────────────────

def apply(flatpak_only: bool = False) -> str:
    """Run Flatpak updates directly; return the vetted command for repo/AUR."""
    data = check()
    official, aur, flatpak = data["official"], data["aur"], data["flatpak"]
    repo_pkgs = official + aur
    out: list[str] = []

    # Flatpak: safe to run unattended (user-scoped, no password).
    if flatpak:
        if not _have("flatpak"):
            out.append("⚠️ Flatpak updates pending but flatpak isn't installed.")
        else:
            r = _run(["flatpak", "update", "--user", "-y"], UPDATE_TIMEOUT)
            if r.returncode == 0:
                out.append(f"✅ Applied **{len(flatpak)}** Flatpak update(s).")
            else:
                err = (r.stderr or r.stdout).strip()[-400:]
                out.append(f"⚠️ Flatpak update failed:\n```\n{err}\n```")
    elif not flatpak_only and not repo_pkgs:
        return "✅ Already up to date — nothing to apply."

    if flatpak_only:
        return "\n".join(out) if out else "No Flatpak updates pending."

    # Official + AUR: hand back the command (no passwordless sudo on this box).
    if repo_pkgs:
        helper = "paru" if _have("paru") else "yay"
        flags = _risk_flags(repo_pkgs)
        warn = ""
        if flags and _needs_reboot(repo_pkgs):
            warn = ("\n⚠️ This pulls in kernel/driver/core packages — "
                    "**reboot afterwards.**")
        out.append(
            f"\nThe **{len(repo_pkgs)}** official + AUR update(s) need your "
            f"password, so I won't run them unattended (and an unattended "
            f"system upgrade is exactly how things break). Run this in a "
            f"terminal — it shows the full list and asks Y/n first:\n\n"
            f"```\n{helper} -Syu\n```{warn}"
        )
    return "\n".join(out)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Hermes system updater engine")
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("check"); pc.add_argument("--full", action="store_true")
    pa = sub.add_parser("apply"); pa.add_argument("--flatpak-only", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "check":
        print(check_md(full=args.full))
    elif args.cmd == "apply":
        print(apply(flatpak_only=args.flatpak_only))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
