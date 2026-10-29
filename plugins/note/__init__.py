"""
note plugin — exposes a top-level ``/note`` slash command (Q3).

A quick capture note is the "nothing lost" floor (Q7): whatever the user types after
``/note`` gets filed into their **canonical** inbox (``0 Capture/Inbox`` — resolved
from the `myos_paths` spine, NOT hard-coded, so it can never resurrect the old
rogue ``Vault/Inbox`` the janitor now guards against) with proper myOS
``type: note`` frontmatter (the current properties standard — not the legacy
underscore header the old `save-note` tool still emits). Deterministic, no model.

NOTE: the older `save_note` *tool* (used by the agent's NL path) writes the legacy
format to the deprecated path and should be migrated separately — that's why this
slash command uses its own writer rather than reusing it.
"""
from __future__ import annotations

import re
import sys
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SCRIPTS = os.environ.get("MYOS_ENGINES", str(Path(__file__).resolve().parents[2] / "engines"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def _inbox_dir() -> Path:
    """Canonical capture inbox from the myOS single-source-of-truth paths spine."""
    import myos_paths as mp
    return mp.vault_root() / mp.config()["dirs"]["inbox"]


def _title_from(text: str) -> str:
    """A short, filesystem-safe title from the first line of the note."""
    first = (text.strip().splitlines() or [""])[0].strip()
    first = re.sub(r"[\\/:*?\"<>|#\[\]]", "", first).strip()
    if len(first) > 60:
        first = first[:57].rstrip() + "…"
    return first or f"Note {datetime.now():%Y-%m-%d %H%M}"


def _unique(dest: Path) -> Path:
    """Never overwrite an existing note — add ' 2', ' 3', … if needed."""
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    n = 2
    while (parent / f"{stem} {n}{suffix}").exists():
        n += 1
    return parent / f"{stem} {n}{suffix}"


def handle_note_slash(raw_args: str = "", **_kw) -> str:
    """``/note <text>`` → frontmatter note in 0 Capture/Inbox. Deterministic."""
    body = (raw_args or "").strip()
    if not body:
        return "Usage: `/note <whatever you want to remember>`"
    try:
        title = _title_from(body)
        inbox = _inbox_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        dest = _unique(inbox / f"{title}.md")
        now = datetime.now()
        fm = (
            "---\n"
            "type: note\n"
            f"created: {now:%Y-%m-%d %H:%M}\n"
            "tags:\n  - capture\n"
            "---\n"
        )
        dest.write_text(f"{fm}# {title}\n\n{body}\n", encoding="utf-8")
        rel = dest.relative_to(mp_root())
        logger.info("note: wrote %s", dest)
        return f"✅ Noted → {rel}"
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("note slash: failed")
        return f"❌ Couldn't save that note: {e}"


def mp_root() -> Path:
    import myos_paths as mp
    return mp.vault_root()


def register(ctx) -> None:
    ctx.register_command(
        name="note",
        handler=handle_note_slash,
        description="Save a quick note to your inbox",
        args_hint="<whatever you want to remember>",
    )
    logger.info("note: registered '/note' slash command")
