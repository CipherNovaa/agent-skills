#!/usr/bin/env python3
"""
myos_task.py — the deterministic add/close path for the myOS task backlog.

The single master list is `1 Active/Tasks/Backlog.md` (spine key `tasks`). Tasks are
plain Obsidian-Tasks-plugin checkboxes carrying emoji metadata, so the Tasks/Dataview
queries and the daily/Home dashboards render them (and a calendar bridge can push any
📅/⏳-dated one to a phone). This script is the offline, no-LLM bridge so the AI (or a
`//task` command) can turn "email the registrar Friday" into a real, correctly-formatted
backlog line without hand-editing markdown.

Priority → emoji (Obsidian Tasks): must=⏫ high · should=🔼 medium · could=🔽 low ·
highlight=🔺 highest. Dates accept ISO, today/tomorrow, +Nd, or a weekday name (next
occurrence). Pure stdlib → Hermes-runnable, portable.

CLI:
    myos_task.py add "<text>" [--priority must|should|could|highlight]
                 [--due <when>] [--scheduled <when>] [--recurring "<rule>"]
                 [--area math|programming|systems|life|unsorted]
    myos_task.py list [--all]                 # open tasks (‑‑all: include done)
    myos_task.py done "<text match>"          # check off the first matching open task
"""
from __future__ import annotations

import re
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import myos_paths as mp
import myos_dates

BACKLOG_NAME = "Backlog.md"
_PRIORITY = {"must": "⏫", "should": "🔼", "could": "🔽", "highlight": "🔺"}
# The Backlog is a Kanban board (list/vertical view): lanes = STATUS (📥 Inbox, 🎯 This
# Week, 🔨 Doing, 🚧 Blocked, ✅ Done), and TOPIC rides as a colored tag on the card.
# New tasks land in Inbox; `area` → topic tag (colored on the board via tag-colors).
_INBOX_KEYWORD = "inbox"
_AREA_TAG = {
    "math": "#math",
    "programming": "#cpp",
    "cpp": "#cpp",
    "systems": "#systems",
    "projects": "#systems",
    "life": "#life",
    "health": "#life",
}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _tasks_dir() -> Path:
    return mp.vault_root() / mp.config()["dirs"]["tasks"]


def _parse_when(s: str | None) -> str | None:
    """Tolerant natural date → ISO YYYY-MM-DD (shared parser, so events/tasks/capture
    resolve dates identically). Also accepts 'the 21st', 'July 21', etc. See myos_dates."""
    return myos_dates.parse_when(s)


def _format_line(text: str, priority: str | None, due: str | None,
                 scheduled: str | None, recurring: str | None,
                 tag: str | None = None) -> str:
    text = re.sub(r"\s{2,}", " ", text.strip())
    parts = [f"- [ ] {text}"]
    if tag:                                                # topic tag before signifiers
        parts.append(tag)
    if priority and priority in _PRIORITY:
        parts.append(_PRIORITY[priority])
    if recurring:
        parts.append(f"🔁 {recurring.strip()}")
    if scheduled:
        parts.append(f"⏳ {scheduled}")
    if due:
        parts.append(f"📅 {due}")
    return " ".join(parts)


def _find_heading(lines: list[str], keyword: str) -> int | None:
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and keyword in ln.lower():
            return i
    return None


def add(text: str, priority: str | None, due_raw: str | None, sched_raw: str | None,
        recurring: str | None, area: str) -> tuple[int, str]:
    path = _tasks_dir() / BACKLOG_NAME
    if not path.exists():
        return 2, f"❌ backlog not found: {path} (create 1 Active/Tasks/Backlog.md first)"
    try:
        due = _parse_when(due_raw)
        scheduled = _parse_when(sched_raw)
    except ValueError as e:
        return 2, f"❌ {e}"
    if priority and priority not in _PRIORITY:
        return 2, f"❌ unknown priority {priority!r} (must|should|could|highlight)"

    tag = _AREA_TAG.get((area or "").lower())              # topic → colored board tag (None → untagged)
    line = _format_line(text, priority, due, scheduled, recurring, tag)
    lines = path.read_text().splitlines()

    # Kanban board: drop the card into the 📥 Inbox lane (newest first, under the heading).
    idx = _find_heading(lines, _INBOX_KEYWORD)
    if idx is None:                                        # no Inbox lane → use the first lane
        idx = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if idx is None:                                        # not a lane board → create Inbox before settings
        cut = next((i for i, ln in enumerate(lines) if ln.startswith("%% kanban:settings")), len(lines))
        lines[cut:cut] = ["## 📥 Inbox", "", line, ""]
        idx = cut
    else:
        lines.insert(idx + 1, line)
    path.write_text("\n".join(lines) + "\n")

    where = lines[idx].lstrip("# ").strip()
    return 0, f"✅ added → {where}: {line}"


def _iter_tasks(lines: list[str], done: bool | None = None):
    """Yield (idx, line) for task lines. done=False → open only, True → done only, None → both."""
    for i, ln in enumerate(lines):
        m = re.match(r"\s*- \[( |x|X)\] ", ln)
        if not m:
            continue
        is_done = m.group(1).lower() == "x"
        if done is None or is_done == done:
            yield i, ln


def list_tasks(include_done: bool) -> tuple[int, str]:
    path = _tasks_dir() / BACKLOG_NAME
    if not path.exists():
        return 2, f"❌ backlog not found: {path}"
    lines = path.read_text().splitlines()
    heading = ""
    out = []
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            heading = ln.lstrip("# ").strip()
        m = re.match(r"\s*- \[( |x|X)\] (.*)", ln)
        if not m:
            continue
        is_done = m.group(1).lower() == "x"
        body = m.group(2).strip()
        if not body:
            continue                                       # skip the empty seed placeholders
        if is_done and not include_done:
            continue
        mark = "✔" if is_done else "☐"
        out.append(f"  {mark} [{heading}] {body}")
    if not out:
        return 0, "(no tasks)"
    return 0, "\n".join(out)


def done(match: str) -> tuple[int, str]:
    path = _tasks_dir() / BACKLOG_NAME
    if not path.exists():
        return 2, f"❌ backlog not found: {path}"
    lines = path.read_text().splitlines()
    needle = match.strip().lower()
    for i, ln in _iter_tasks(lines, done=False):
        body = re.match(r"(\s*- \[) \] (.*)", ln)
        if body and needle in body.group(2).lower() and body.group(2).strip():
            done_stamp = f" ✅ {date.today().isoformat()}"
            lines[i] = f"{body.group(1)}x] {body.group(2)}{done_stamp}"
            path.write_text("\n".join(lines) + "\n")
            return 0, f"✅ done: {body.group(2).strip()}"
    return 1, f"⚠ no open task matching {match!r}"


def _main(argv) -> int:
    ap = argparse.ArgumentParser(description="myOS task backlog add/close")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add")
    a.add_argument("text")
    a.add_argument("--priority", choices=list(_PRIORITY))
    a.add_argument("--due")
    a.add_argument("--scheduled")
    a.add_argument("--recurring")
    a.add_argument("--area", default="unsorted")

    l = sub.add_parser("list")
    l.add_argument("--all", action="store_true", help="include done tasks")

    d = sub.add_parser("done")
    d.add_argument("match")

    args = ap.parse_args(argv)
    if args.cmd == "add":
        code, msg = add(args.text, args.priority, args.due, args.scheduled,
                        args.recurring, args.area)
    elif args.cmd == "list":
        code, msg = list_tasks(args.all)
    elif args.cmd == "done":
        code, msg = done(args.match)
    else:
        ap.print_help()
        return 2
    print(msg)
    return code


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
