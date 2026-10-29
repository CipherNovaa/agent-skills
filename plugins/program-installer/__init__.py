"""
program-installer plugin — exposes the user's program installer as two native
Hermes tools: ``search_programs`` and ``install_program``.

The engine lives in ``engines/prog_install.py`` (also usable as a CLI). These
handlers run it in-process and return finished markdown, so the agent never has
to shell out to a long-running command.

Safety: ``search_programs`` is read-only. ``install_program`` only ever runs a
per-user Flatpak install autonomously (no sudo, reversible); for official/AUR
packages it returns the exact command for the user to run rather than elevating.
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
    import prog_install  # noqa: WPS433 (deliberate lazy import)
    return prog_install


SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "search_programs",
    "description": (
        "Search for a program/app to install across the official Arch repos, "
        "Flathub, and the AUR. Returns a ranked, numbered list of candidates "
        "(name, version, source, whether already installed). Use this FIRST "
        "whenever the user wants to install/find a program but hasn't named an exact "
        "package, so they can pick which one and which version.\n"
        "IMPORTANT: the tool output is the FINAL user-facing list. Reply with it "
        "VERBATIM — do not summarize, reword, renumber, shorten, or pick for them, "
        "and do NOT invent packages that aren't in the list. In particular never "
        "change which sources need a password: the tool states that "
        "official/AUR installs need the user's password and Flatpaks do not — keep "
        "that exactly. Just present the list and ask which one they want."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What the user wants to install (program name or keywords).",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

INSTALL_SCHEMA: Dict[str, Any] = {
    "name": "install_program",
    "description": (
        "Install a specific package that the user chose from search_programs. You "
        "MUST pass the exact package name/app-id and its source. Flatpaks are "
        "installed directly (per-user, no password). For 'official' or 'aur' "
        "packages this does NOT run anything — it returns the exact command for "
        "the user to run themselves (they need a password). Only call this after the user "
        "has clearly chosen a specific option; never guess the package or source."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact package name (official/AUR) or Flatpak app id.",
            },
            "source": {
                "type": "string",
                "enum": ["official", "aur", "flatpak"],
                "description": "Which source the chosen package came from.",
            },
        },
        "required": ["name", "source"],
        "additionalProperties": False,
    },
}


def handle_search(args: Dict[str, Any], **_kw) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "Error: no search query provided."
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("program-installer: engine import failed")
        return f"Error: the installer engine could not be loaded: {e}"
    try:
        return engine.search_md(query)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("program-installer: search failed")
        return f"Error searching for programs: {e}"


def handle_install(args: Dict[str, Any], **_kw) -> str:
    name = (args.get("name") or "").strip()
    source = (args.get("source") or "").strip().lower()
    if not name or not source:
        return "Error: both 'name' and 'source' are required to install."
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("program-installer: engine import failed")
        return f"Error: the installer engine could not be loaded: {e}"
    try:
        return engine.install(name, source)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("program-installer: install failed")
        return f"Error installing {name}: {e}"


def register(ctx) -> None:
    """Called once by the plugin loader when the plugin is enabled."""
    ctx.register_tool(
        name="search_programs",
        toolset="installer",
        schema=SEARCH_SCHEMA,
        handler=handle_search,
        emoji="🔎",
    )
    ctx.register_tool(
        name="install_program",
        toolset="installer",
        schema=INSTALL_SCHEMA,
        handler=handle_install,
        emoji="📦",
    )
    logger.info("program-installer: registered 'search_programs' + 'install_program' "
                "(toolset=installer)")
