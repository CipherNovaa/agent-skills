#!/usr/bin/env python3
"""
myos_apply_template.py — instantiate an Obsidian/Templater template into a
finished note, OUTSIDE Obsidian.

The vault's templates (Templates/*.md) use Templater `<% %>` expressions that only
render inside Obsidian. Any note Hermes/Claude creates from them shows the raw
`<% tp.file.title %>` / `<% tp.date.now("YYYY-MM-DD") %>` literally. This engine
renders the small, bounded subset the templates actually use so a note created
offline looks exactly like one Obsidian made.

Supported Templater subset (everything the author's vault used as of 2026-07-01):
  <% tp.file.title %>          → the note title (target filename stem)
  <% tp.file.cursor() %>       → stripped (it's only a caret position)
  <% tp.date.now("<fmt>") %>   → now, formatted with moment.js tokens

Moment tokens handled by _moment_format(): YYYY YY · MMMM MMM MM M · DD D ·
dddd ddd · HH H · mm · ss · GGGG (ISO week-year) · WW W (ISO week) · and
[literal] escapes. Longest-token-first so MMMM never mis-parses as MM+M.

Pure stdlib → Hermes-runnable, offline, portable.

CLI:
    myos_apply_template.py <TemplateName> "<Note Title>" [--dir <key|path>]
                           [--stdout] [--force]
    myos_apply_template.py --selftest        # render every template, assert no <% left
    myos_apply_template.py --render "<text>" --title "<t>"   # render arbitrary text
"""
from __future__ import annotations

import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import myos_paths as mp

# `<% ... %>` (Templater). We only render tp.* calls; anything unknown is left
# intact so --selftest / the janitor can flag it rather than silently blanking.
_EXPR_RE = re.compile(r"<%[-=]?\s*(.*?)\s*-?%>", re.DOTALL)

# Full weekday / month names — avoid locale surprises from strftime %A/%B.
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

# Moment tokens, longest first so greedy matching is correct.
_MOMENT_TOKENS = [
    "YYYY", "GGGG", "MMMM", "dddd", "YY", "MM", "MMM", "DD", "ddd", "HH",
    "mm", "ss", "WW", "GG", "M", "D", "H", "W", "d",
]
_MOMENT_RE = re.compile("|".join(sorted(_MOMENT_TOKENS, key=len, reverse=True)))


def _moment_format(dt: datetime, fmt: str) -> str:
    """Render a moment.js format string for `dt`. Honors [literal] escapes."""
    out = []
    i = 0
    iso_year, iso_week, iso_wday = dt.isocalendar()
    while i < len(fmt):
        ch = fmt[i]
        if ch == "[":                       # literal block: [W] → W
            end = fmt.find("]", i)
            if end < 0:
                out.append(fmt[i + 1:])
                break
            out.append(fmt[i + 1:end])
            i = end + 1
            continue
        m = _MOMENT_RE.match(fmt, i)
        if not m:
            out.append(ch)
            i += 1
            continue
        tok = m.group(0)
        out.append(_moment_token(dt, tok, iso_year, iso_week))
        i = m.end()
    return "".join(out)


def _moment_token(dt: datetime, tok: str, iso_year: int, iso_week: int) -> str:
    return {
        "YYYY": f"{dt.year:04d}",
        "YY": f"{dt.year % 100:02d}",
        "GGGG": f"{iso_year:04d}",
        "GG": f"{iso_year % 100:02d}",
        "MMMM": _MONTHS[dt.month],
        "MMM": _MONTHS[dt.month][:3],
        "MM": f"{dt.month:02d}",
        "M": str(dt.month),
        "DD": f"{dt.day:02d}",
        "D": str(dt.day),
        "dddd": _WEEKDAYS[dt.weekday()],
        "ddd": _WEEKDAYS[dt.weekday()][:3],
        "d": str((dt.weekday() + 1) % 7),   # moment: 0=Sun
        "HH": f"{dt.hour:02d}",
        "H": str(dt.hour),
        "mm": f"{dt.minute:02d}",
        "ss": f"{dt.second:02d}",
        "WW": f"{iso_week:02d}",
        "W": str(iso_week),
    }[tok]


def _render_expr(code: str, title: str, dt: datetime) -> str | None:
    """Render one Templater expression's inner code. Return None if unsupported
    (so the caller leaves it intact for the janitor to flag)."""
    code = code.strip()
    if code == "tp.file.title":
        return title
    if code in ("tp.file.cursor()", "tp.file.cursor(0)"):
        return ""
    m = re.fullmatch(r'tp\.date\.now\(\s*"([^"]*)"\s*\)', code)
    if m:
        return _moment_format(dt, m.group(1))
    m = re.fullmatch(r"tp\.date\.now\(\s*'([^']*)'\s*\)", code)
    if m:
        return _moment_format(dt, m.group(1))
    if code == "tp.date.now()":
        return _moment_format(dt, "YYYY-MM-DD")
    return None


def render(text: str, title: str, dt: datetime | None = None) -> str:
    """Render all supported `<% %>` expressions in `text`. Unsupported ones are
    left verbatim (never silently blanked)."""
    dt = dt or datetime.now()

    def repl(m: re.Match) -> str:
        val = _render_expr(m.group(1), title, dt)
        return m.group(0) if val is None else val

    return _EXPR_RE.sub(repl, text)


def unrendered(text: str) -> list[str]:
    """Return any `<% %>` expressions still present (unsupported / not rendered)."""
    return [m.group(0) for m in _EXPR_RE.finditer(text)]


# ── template + path resolution ────────────────────────────────────────────────

def _templates_dir() -> Path:
    return mp.vault_root() / mp.config()["dirs"]["templates"]


def template_path(name: str) -> Path:
    """Accept 'Person', 'Person.md', or an absolute path."""
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    stem = name[:-3] if name.endswith(".md") else name
    return _templates_dir() / f"{stem}.md"


def _resolve_dir(dir_arg: str | None) -> Path:
    if not dir_arg:
        return mp.vault_root() / mp.config()["dirs"]["inbox"]
    # a spine key?
    if dir_arg in mp.config()["dirs"]:
        return mp.vault_root() / mp.config()["dirs"][dir_arg]
    p = Path(dir_arg).expanduser()
    return p if p.is_absolute() else mp.vault_root() / dir_arg


def instantiate(template: str, title: str, dir_arg: str | None,
                to_stdout: bool, force: bool,
                dt: datetime | None = None) -> tuple[int, str]:
    tpl = template_path(template)
    if not tpl.exists():
        return 2, f"template not found: {tpl}"
    rendered = render(tpl.read_text(), title, dt)
    left = unrendered(rendered)
    warn = f"  ⚠ {len(left)} unsupported expr left: {left}" if left else ""
    if to_stdout:
        return 0, rendered + (("\n" + warn) if warn else "")
    dest_dir = _resolve_dir(dir_arg)
    dest = dest_dir / f"{title}.md"
    if dest.exists() and not force:
        return 3, f"refuse to overwrite (use --force): {dest}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered)
    return 0, f"wrote {dest}{warn}"


# ── selftest: every template must fully render ────────────────────────────────

def selftest() -> int:
    tdir = _templates_dir()
    if not tdir.exists():
        print(f"❌ templates dir missing: {tdir}")
        return 1
    bad = 0
    for tpl in sorted(tdir.glob("*.md")):
        rendered = render(tpl.read_text(), title="Selftest Note")
        left = unrendered(rendered)
        if left:
            bad += 1
            print(f"❌ {tpl.name}: unsupported → {left}")
        else:
            print(f"✅ {tpl.name}")
    print("— all templates render —" if not bad else f"— ⚠️ {bad} need engine support —")
    return 1 if bad else 0


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("template", nargs="?")
    ap.add_argument("title", nargs="?")
    ap.add_argument("--dir", dest="dir")
    ap.add_argument("--date", dest="date",
                    help="YYYY-MM-DD to render tp.date.now as (default: today). "
                         "Lets the calendar create a correctly-dated back/forward daily.")
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--render", dest="render_text")
    ap.add_argument("--title", dest="title_opt")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if a.render_text is not None:
        print(render(a.render_text, a.title_opt or a.title or "Untitled"))
        return 0
    if not a.template or not a.title:
        ap.print_help()
        return 2
    dt = None
    if a.date:
        try:
            dt = datetime.strptime(a.date, "%Y-%m-%d")
        except ValueError:
            print(f"bad --date (want YYYY-MM-DD): {a.date}")
            return 2
    code, msg = instantiate(a.template, a.title, a.dir, a.stdout, a.force, dt)
    print(msg)
    return code


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
