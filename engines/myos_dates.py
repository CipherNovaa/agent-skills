#!/usr/bin/env python3
"""
myos_dates.py — one deterministic natural-date → ISO parser for the whole capture spine.

Small local models flub date math ("the 21st" → the wrong ISO). So the parsing lives HERE,
in stdlib, not in the model: the `event` / `task` / `capture` paths all resolve their "when"
through `parse_when`, and get the same answer every time, offline.

Understood forms (case-insensitive, a leading "the"/"on"/"by"/"next" is tolerated):
    2026-07-21                 ISO (validated)
    today · tod                today
    tomorrow · tmr · tom       +1 day
    +3 · +3d                   N days out
    friday · next friday       next occurrence of that weekday (a weekday name today → next week)
    21st · the 21st · 21       next occurrence of that day-of-month (this month if still ahead,
                               else next month; rolls the year at December)
    july 21 · jul 21st         month + day (this year if ahead, else next year)
    21 july · 21st of july     day + month

`parse_when(s)` → ISO string, or None for empty; raises ValueError on true garbage.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})   # jan, feb, …

_ORD = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.I)        # "21st" → "21"
_LEAD = re.compile(r"^(?:the|on|by|due|next)\s+", re.I)


def _dom_next(day: int, today: date) -> date:
    """The next calendar date whose day-of-month is `day` (today counts)."""
    if day < 1 or day > 31:
        raise ValueError(f"no such day-of-month: {day}")
    y, m = today.year, today.month
    for _ in range(13):                        # this month, then walk forward
        try:
            cand = date(y, m, day)
        except ValueError:                     # e.g. Feb 30 — skip to next month
            cand = None
        if cand and cand >= today:
            return cand
        m += 1
        if m > 12:
            m, y = 1, y + 1
    raise ValueError(f"could not place day-of-month {day}")


def _md(month: int, day: int, today: date) -> date:
    """month+day → this year if still ahead, else next year."""
    for y in (today.year, today.year + 1):
        try:
            cand = date(y, month, day)
        except ValueError:
            raise ValueError(f"no such date: month {month} day {day}")
        if cand >= today:
            return cand
    return date(today.year + 1, month, day)


def parse_when(s: str | None) -> str | None:
    if not s:
        return None
    raw = s.strip()
    s = raw.lower()
    s = _LEAD.sub("", s).strip()                       # drop a leading the/on/by/next…
    is_next = bool(re.match(r"^next\s+", raw, re.I)) or raw.lower().startswith("next")
    today = date.today()

    # ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s).isoformat()
    # relative words
    if s in ("today", "tod"):
        return today.isoformat()
    if s in ("tomorrow", "tmr", "tom"):
        return (today + timedelta(days=1)).isoformat()
    m = re.fullmatch(r"\+?(\d+)\s*d(?:ays?)?", s) or re.fullmatch(r"\+(\d+)", s)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    m = re.fullmatch(r"in\s+(\d+)\s+days?", s)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    m = re.fullmatch(r"in\s+(\d+)\s+weeks?", s)
    if m:
        return (today + timedelta(weeks=int(m.group(1)))).isoformat()
    # weekday (optionally "next friday")
    if s in _WEEKDAYS:
        delta = (_WEEKDAYS.index(s) - today.weekday()) % 7
        delta = delta or 7                             # same weekday today → next week
        if is_next and delta < 7:
            pass                                        # "next friday" == the coming friday
        return (today + timedelta(days=delta)).isoformat()

    # month + day  ("july 21", "jul 21st")  /  day + month ("21 july", "21st of july")
    s_ord = _ORD.sub(r"\1", s)
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})", s_ord)
    if m and m.group(1) in _MONTHS:
        return _md(_MONTHS[m.group(1)], int(m.group(2)), today).isoformat()
    m = re.fullmatch(r"(\d{1,2})\s+(?:of\s+)?([a-z]+)\.?", s_ord)
    if m and m.group(2) in _MONTHS:
        return _md(_MONTHS[m.group(2)], int(m.group(1)), today).isoformat()

    # bare day-of-month: "21st", "21", "the 21st"
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", s)
    if m:
        return _dom_next(int(m.group(1)), today).isoformat()

    raise ValueError(
        f"unrecognized date: {raw!r} "
        "(try YYYY-MM-DD, today, tomorrow, +Nd, a weekday, 'the 21st', or 'July 21')")


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        try:
            print(f"{arg!r:>22} → {parse_when(arg)}")
        except ValueError as e:
            print(f"{arg!r:>22} → ❌ {e}")
