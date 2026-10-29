"""
system-updater plugin — exposes the user's system updater as two native Hermes
tools: ``check_updates`` and ``apply_updates``.

The engine lives in ``engines/sys_update.py`` (also usable as a CLI). These
handlers run it in-process and return finished markdown, so the agent never has
to shell out.

Safety: ``check_updates`` is 100% read-only (it never touches the live pacman
sync DB — official updates come from ``checkupdates``' throwaway temp DB). It
flags risky packages (kernel/nvidia/glibc/systemd) and whether a reboot is
needed. ``apply_updates`` only ever runs Flatpak updates autonomously (per-user,
no password); for official/AUR it returns the exact ``paru -Syu`` command for
the user to run themselves, because an unattended system upgrade is how things break.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# The engine lives in engines/; make it importable.
_SCRIPTS_DIR = os.environ.get("MYOS_ENGINES", str(Path(__file__).resolve().parents[2] / "engines"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_engine():
    """Import the shared engine lazily so a bad import can't break plugin load."""
    import sys_update  # noqa: WPS433 (deliberate lazy import)
    return sys_update


CHECK_SCHEMA: Dict[str, Any] = {
    "name": "check_updates",
    "description": (
        "Check what system updates are pending for the user (official Arch repos, "
        "AUR, and Flatpak) and show them so they can decide whether to apply. This "
        "is READ-ONLY and safe — it never changes the system. It lists package "
        "version changes and flags risky packages (kernel, nvidia, glibc, "
        "systemd) and whether a reboot will be needed. Use this whenever the user "
        "asks to update, check for updates, or 'what needs updating'.\n"
        "IMPORTANT: the tool output is the FINAL user-facing message. Reply with "
        "it VERBATIM — do not summarize, reword, renumber, or drop the risk "
        "warnings or the exact command. By default the list is truncated; pass "
        "full=true only if the user explicitly asks to see every package."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "full": {
                "type": "boolean",
                "description": "Show every pending package instead of a capped list.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

APPLY_SCHEMA: Dict[str, Any] = {
    "name": "apply_updates",
    "description": (
        "Apply pending updates after the user has confirmed they want them. Flatpak "
        "updates are applied directly (per-user, no password). For official/AUR "
        "updates this does NOT run anything — it returns the exact `paru -Syu` "
        "command for the user to run themselves (they need the user's password, and an "
        "unattended full upgrade is exactly what breaks Arch systems). Only call "
        "this after the user has clearly said yes to updating. Pass flatpak_only=true "
        "if they only want the Flatpak updates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "flatpak_only": {
                "type": "boolean",
                "description": "Only apply the Flatpak updates (skip the repo/AUR command).",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


def handle_check(args: Dict[str, Any], **_kw) -> str:
    full = bool(args.get("full"))
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("system-updater: engine import failed")
        return f"Error: the updater engine could not be loaded: {e}"
    try:
        return engine.check_md(full=full)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("system-updater: check failed")
        return f"Error checking for updates: {e}"


def handle_apply(args: Dict[str, Any], **_kw) -> str:
    flatpak_only = bool(args.get("flatpak_only"))
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("system-updater: engine import failed")
        return f"Error: the updater engine could not be loaded: {e}"
    try:
        return engine.apply(flatpak_only=flatpak_only)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("system-updater: apply failed")
        return f"Error applying updates: {e}"


def register(ctx) -> None:
    """Called once by the plugin loader when the plugin is enabled."""
    ctx.register_tool(
        name="check_updates",
        toolset="updater",
        schema=CHECK_SCHEMA,
        handler=handle_check,
        emoji="🔄",
    )
    ctx.register_tool(
        name="apply_updates",
        toolset="updater",
        schema=APPLY_SCHEMA,
        handler=handle_apply,
        emoji="⬆️",
    )
    logger.info("system-updater: registered 'check_updates' + 'apply_updates' "
                "(toolset=updater)")
