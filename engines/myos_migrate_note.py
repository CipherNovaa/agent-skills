#!/usr/bin/env python3
"""
myos_migrate_note.py — bring an existing note onto the myOS frontmatter-properties
standard WITHOUT rewriting the author's words.

The dual of the template engine (`myos_apply_template.py`): that one *instantiates*
a template into a new note; this one *migrates* an already-written note that predates
the properties standard (no YAML `type:`) up to it. It only ever adds/splices a
frontmatter block — the body is preserved byte-for-byte. Idempotent: a note that
already carries `type:` is left untouched.

This is the fix path the janitor routes old-format notes to. Its first real job
was a backlog of near-empty Inventory stubs — it gave each a real `type:`
(+ `category:` from its subfolder) so they became property-bearing notes ready
for a later enrichment pass.

Type is inferred folder-first (conservative): a note's home layer decides its type;
anything unmapped floors to `type: note` (harmless) unless `--strict` (then it's
skipped + listed for escalation instead of guessed).

Pure stdlib → Hermes-runnable, offline, portable.

CLI:
    myos_migrate_note.py <path>              # dry-run: preview the header for one note
    myos_migrate_note.py <path> --apply      # write it
    myos_migrate_note.py --all               # dry-run table over every old-format note
    myos_migrate_note.py --all --apply       # migrate them all
    [--strict]  # unmapped folders → skip + flag (don't floor to `type: note`)
"""
from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import myos_paths as mp
import myos_janitor_scan as janitor   # reuse the exact old-format + literal note sets
import myos_apply_template as eng      # reuse the Templater render engine (R6)

VAULT = mp.vault_root()
_DIRS = mp.config()["dirs"]

# Spine dir key → the `type:` a note living there should carry. Folder-first, since
# these notes are already filed in a layer; the layer is the most reliable signal.
_KEY_TYPE = {
    "projects": "project",
    "journal": "daily",          # only if the filename is a YYYY-MM-DD date
    "academics": "concept",
    "systems": "concept",
    "myos": "concept",
    "source_material": "resource",
    "inventory": "inventory",    # + category: <subfolder>
}
# (prefix rel-path, key, type), most-specific (longest) first so nesting resolves right.
_PREFIXES = sorted(
    ((_DIRS[k], k, t) for k, t in _KEY_TYPE.items() if k in _DIRS),
    key=lambda x: len(x[0]), reverse=True,
)

_DATE_STEM = re.compile(r"^\d{4}-\d{2}-\d{2}")


def infer(rel: str) -> tuple[str | None, dict]:
    """Return (type, extra_fields). type is None only when unmapped under --strict
    handling upstream; here unmapped → ('note', {}) floor."""
    for prefix, key, typ in _PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            tail = rel[len(prefix) + 1:]
            if key == "inventory":
                parts = tail.split("/")
                extra = {"category": parts[0]} if len(parts) > 1 else {}
                return "inventory", extra
            if key == "journal":
                return ("daily", {}) if _DATE_STEM.match(Path(rel).stem) else ("note", {})
            return typ, {}
    return "note", {}   # floor for anything outside the mapped layers


# ── FC-literal repair (R6) ────────────────────────────────────────────────────
# Full Calendar (and any non-Obsidian creator) leaves literal `<% tp.file.title %>` /
# `<% tp.date.now(...) %>` in the notes it makes — Templater only fires inside Obsidian.
# We render exactly the bounded subset the engine supports (expression-only substitution;
# prose is never touched) so those notes stop reading literally. Anything unsupported is
# left intact for the janitor to keep flagging.
_CODE_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.S)


def _repair_literals(text: str, stem: str) -> tuple[str, int]:
    """Render supported literal Templater exprs in `text`. Code spans/fences are
    stashed first so a note that QUOTES `<% tp… %>` as documentation (e.g. the Build
    Log) is never mangled — the same false-positive guard the janitor uses. Returns
    (new_text, n_repaired)."""
    if not eng.unrendered(text):
        return text, 0
    stash: list[str] = []

    def _hide(m: re.Match) -> str:
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"

    protected = _CODE_RE.sub(_hide, text)
    before = len(eng.unrendered(protected))          # count only expressions OUTSIDE code
    rendered = eng.render(protected, title=stem)
    after = len(eng.unrendered(rendered))
    rendered = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], rendered)
    return rendered, before - after


# ── legacy underscore-header cleanup (body-preserving) ────────────────────────
# The pre-properties template left a header block below the frontmatter: rows of
# underscores as dividers, a bare date, a `Status: #tags` line and a `Tags: [[links]]`
# line. Left in place it half-migrates the note and makes Obsidian render tables as
# "PARSING FAILED". We migrate LOSSLESSLY: strip the dividers/date/labels, fold the
# `Status:` hashtags into frontmatter `tags:`, and keep the `Tags:` wikilinks as a
# `**Related:**` line so the graph edges survive.
_UL_DIV    = re.compile(r"^_{8,}\s*$", re.M)
_STATUS_LN = re.compile(r"^Status:\s*(.*)$")
_TAGS_LN   = re.compile(r"^Tags:\s*(.*)$")
_DATE_LN   = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?\s*$")
_HASHTAG   = re.compile(r"#([A-Za-z0-9_/\-]+)")
_TAGS_FLOW = re.compile(r"^tags:\s*\[(.*)\]\s*$")


def _has_legacy_divider(text: str) -> bool:
    _inner, body = _split_fm(text)
    return bool(_UL_DIV.search(body))


def _merge_tags(inner: list[str], extra: list[str]) -> tuple[list[str], bool]:
    """Union `extra` hashtags into a flow-style `tags: [...]` line (order-preserving,
    case-insensitive dedup). Returns (new_inner, folded?). folded=False if there was no
    flow-list tags line to safely edit (→ caller keeps the tags inline instead)."""
    if not extra:
        return inner, True
    out, folded = [], False
    for ln in inner:
        m = _TAGS_FLOW.match(ln)
        if m and not folded:
            have = [t.strip() for t in m.group(1).split(",") if t.strip()]
            seen = {t.lower() for t in have}
            for t in extra:
                if t.lower() not in seen:
                    have.append(t); seen.add(t.lower())
            out.append("tags: [" + ", ".join(have) + "]")
            folded = True
        else:
            out.append(ln)
    return out, folded


def _migrate_legacy_header(text: str) -> tuple[str, int]:
    """Strip the leading legacy underscore-header, folding its Status tags into
    frontmatter and its Tags wikilinks into a `**Related:**` line. Only fires when a
    divider is actually present (so ordinary prose is never touched). Returns
    (new_text, 1|0)."""
    inner, body = _split_fm(text)
    if inner is None:
        return text, 0
    lines = body.split("\n")
    saw_div, status_tags, related, j, end = False, [], None, 0, 0
    while j < len(lines):
        ln = lines[j].rstrip()
        if ln == "":
            j += 1; continue
        if _UL_DIV.match(ln):
            saw_div = True; j += 1; end = j; continue
        m = _STATUS_LN.match(ln)
        if m:
            status_tags += _HASHTAG.findall(m.group(1)); j += 1; end = j; continue
        m = _TAGS_LN.match(ln)
        if m and "[[" in m.group(1):
            related = m.group(1).strip(); j += 1; end = j; continue
        if _DATE_LN.match(ln):
            j += 1; end = j; continue
        break                                   # first line of real content
    if not saw_div:
        return text, 0
    rest = lines[end:]
    while rest and rest[0].strip() == "":
        rest.pop(0)
    new_inner, folded = _merge_tags(inner, status_tags)
    related_bits = related or ""
    if status_tags and not folded:              # couldn't fold → keep tags inline, not as a Status: line
        tagstr = " ".join("#" + t for t in status_tags)
        related_bits = (related_bits + " · " + tagstr) if related_bits else tagstr
    head = ["**Related:** " + related_bits, ""] if related_bits else []
    out = "---\n" + "\n".join(new_inner) + "\n---\n\n" + "\n".join(head + rest)
    if text.endswith("\n") and not out.endswith("\n"):
        out += "\n"
    return out, 1


# ── frontmatter surgery (body-preserving) ─────────────────────────────────────

def _has_type(text: str) -> bool:
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    return bool(re.search(r"^type:\s*\S", text[:end], re.M))


def _split_fm(text: str) -> tuple[list[str] | None, str]:
    """If text opens with a frontmatter block, return (its inner lines, body-after).
    Otherwise (None, whole text)."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end < 0:
        return None, text
    inner = text[4:end] if text.startswith("---\n") else text[3:end]
    inner = inner.splitlines()
    after = text[end + 4:]        # skip the "\n---"
    if after.startswith("\n"):
        after = after[1:]
    return inner, after


def build_note(text: str, rel: str) -> tuple[str, str, dict]:
    """Return (new_text, inferred_type, extra). Body preserved byte-for-byte."""
    typ, extra = infer(rel)
    inner, body = _split_fm(text)

    if inner is None:
        # No frontmatter → prepend a fresh minimal block.
        lines = ["---", f"type: {typ}"]
        lines += [f"{k}: {v}" for k, v in extra.items()]
        lines += ["tags: []", "---"]
        block = "\n".join(lines) + "\n"
        return block + text, typ, extra

    # Existing block missing `type:` → splice the missing house keys in, keep the rest.
    keys_present = {ln.split(":", 1)[0].strip() for ln in inner if ":" in ln}
    additions = [f"type: {typ}"]
    for k, v in extra.items():
        if k not in keys_present:
            additions.append(f"{k}: {v}")
    if "tags" not in keys_present:
        additions.append("tags: []")
    new_inner = additions + inner
    block = "---\n" + "\n".join(new_inner) + "\n---\n"
    return block + body, typ, extra


# ── operations ────────────────────────────────────────────────────────────────

def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(VAULT))


def migrate_one(path: Path, apply: bool, strict: bool) -> tuple[str, str]:
    """Return (status, detail). status ∈ current|migrated|preview|floor-skip|error.
    Two independent, safe fixes: (1) render FC-left literal Templater exprs (R6), and
    (2) splice the missing `type:` frontmatter — either, both, or neither may apply."""
    try:
        rel = _rel(path)
    except ValueError:
        return "error", f"{path} is outside the vault"
    try:
        text = path.read_text(errors="ignore")
    except Exception as e:
        return "error", f"{path}: {e}"

    stem = Path(rel).stem
    work, n_lit = _repair_literals(text, stem)      # (1) literal repair (any note)

    need_fm = not _has_type(work)
    typ, extra = infer(rel)
    unmapped = not any(rel == p or rel.startswith(p + "/") for p, _k, _t in _PREFIXES)
    floor_skip = strict and need_fm and typ == "note" and unmapped  # leave typing for escalation

    tags: list[str] = []
    if n_lit:
        tags.append(f"{n_lit} literal expr")
    work, n_hdr = _migrate_legacy_header(work)      # (3) strip legacy header, keep tags + graph
    if n_hdr:
        tags.append("legacy header cleaned")
    if need_fm and not floor_skip:
        work, typ, extra = build_note(work, rel)    # (2) frontmatter typing (preserves body)
        tags.append("type: " + typ + (f"/{extra['category']}" if extra.get("category") else ""))

    if work == text:                                # nothing to do
        return ("floor-skip", rel) if floor_skip else ("current", rel)

    detail_tags = ", ".join(tags) + (" (type unmapped → escalate)" if floor_skip else "")
    if apply:
        path.write_text(work)
        return "migrated", f"{rel}  →  {detail_tags}"
    # preview: show the new header if frontmatter changed, else the repaired title line.
    if need_fm and not floor_skip:
        header = work[:work.find("\n---", 3) + 4]
    else:
        header = next((l for l in work.splitlines() if l.startswith("#")), "")
    return "preview", f"{rel}  →  {detail_tags}\n{header}"


def run_all(apply: bool, strict: bool) -> int:
    # Reuse the janitor's exact detectors so this fixes precisely what it flags — no
    # drift between detector and fixer: old-format (no `type:`) OR a real literal
    # `<% tp… %>` (janitor's _strip_code guard skips docs that merely quote one).
    targets = []
    for p, rel, txt in janitor._iter_notes():
        if (not _has_type(txt) or janitor._TP_RE.search(janitor._strip_code(txt))
                or _has_legacy_divider(txt)):
            targets.append(p)

    migrated = current = flagged = errors = 0
    rows = []
    for p in sorted(targets):
        status, detail = migrate_one(p, apply, strict)
        if status == "migrated":
            migrated += 1; rows.append(f"  ✅ {detail}")
        elif status == "preview":
            migrated += 1; rows.append(f"  · {detail.splitlines()[0]}")
        elif status == "current":
            current += 1
        elif status == "floor-skip":
            flagged += 1; rows.append(f"  ⚠ would floor to `note` → escalate: {detail}")
        else:
            errors += 1; rows.append(f"  ❌ {detail}")

    verb = "migrated" if apply else "would migrate"
    print(f"🗂  {verb} {migrated}, already-current {current}"
          + (f", flagged {flagged}" if flagged else "")
          + (f", errors {errors}" if errors else ""))
    for r in rows:
        print(r)
    if not apply and migrated:
        print("\n(dry-run — re-run with --apply to write)")
    return 1 if errors else 0


def _main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="a single note to migrate/preview")
    ap.add_argument("--all", action="store_true",
                    help="operate over every old-format note (the janitor's set)")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--strict", action="store_true",
                    help="unmapped folder → skip + flag instead of flooring to `note`")
    a = ap.parse_args(argv)

    if a.all:
        return run_all(a.apply, a.strict)
    if not a.path:
        ap.print_help()
        return 2
    status, detail = migrate_one(Path(a.path), a.apply, a.strict)
    if status == "current":
        print(f"already-current (has type:): {detail}")
    elif status == "migrated":
        print(f"✅ {detail}")
    elif status == "preview":
        print(detail)
        print("\n(dry-run — re-run with --apply to write; body is preserved unchanged)")
    elif status == "floor-skip":
        print(f"⚠ unmapped folder, --strict → left for escalation: {detail}")
    else:
        print(f"❌ {detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
