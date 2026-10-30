#!/usr/bin/env python3
"""
myos_janitor_scan.py — the myOS "janitor": a READ-ONLY drift detector.

It never edits anything. It scans the vault for things that need doing and emits
a punch-list, each item routed to the skill that should fix it (Hermes owns some;
others → escalate-to-architect). A morning health brief consumes `--brief`; the
weekly review consumes the full list.

Checks:
  * skills health   — every <skills_dir>/<skill> has a parseable SKILL.md,
                      and the set matches an expected manifest (catches a skill
                      that silently vanished — e.g. a cat on the keyboard).
  * skill frontmatter — every SKILL.md frontmatter is valid YAML (invalid YAML makes
                      Hermes silently drop the skill via its fallback parser)      → fix SKILL.md.
  * literal <%       — real notes still holding un-rendered Templater `<% %>`
                      (created outside Obsidian) → re-render (person / engine).
  * old-format notes — notes with no YAML frontmatter `type:` (pre-properties)  → migrate.
  * unfiled inbox    — capture items awaiting sorting                           → file-note.
  * broken links     — [[wikilinks]] whose target note doesn't exist            → escalate-to-architect.
  * rogue folders    — an operational folder (inbox, tasks…) duplicated at a wrong
                      path, e.g. a model-invented second "Inbox"               → escalate-to-architect.
  * template health  — a template using an expression the engine can't render   → fix template / engine.
  * feature contracts — a template/code coupling listed in contracts.json no longer
                      holds (a freely-edited template severed a feature)      → escalate-to-architect.
  * memory index     — ARCHITECT/MEMORY.md is loaded whole each session and TRUNCATES
                      past a read limit SILENTLY (lost memories, no error)      → compact the index.
  * memory symlinks  — each memory must be one vault file + a symlink; a real
                      file on both sides = two copies that drift               → run the reconciler.

CLI:
    myos_janitor_scan.py                 # full punch-list
    myos_janitor_scan.py --brief         # one-line-per-issue summary (for a morning brief)
    myos_janitor_scan.py --bless         # accept current skill set as the expected manifest
    myos_janitor_scan.py --escalate      # also queue CRITICAL findings for the architect

Config:
    MYOS_EXPECTED_SKILLS   expected-skills manifest (default ~/.config/myos/expected_skills.txt)
    MYOS_CONTRACTS         feature-contract list    (default ~/.config/myos/contracts.json,
                           see config/contracts.example.json)
"""
from __future__ import annotations

import os
import re
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import myos_paths as mp
import myos_apply_template as eng

VAULT = mp.vault_root()
SKILLS_DIR = mp.skills_dir()
TEMPLATES_DIR = VAULT / mp.config()["dirs"]["templates"]
MANIFEST = Path(os.path.expanduser(
    os.environ.get("MYOS_EXPECTED_SKILLS", "~/.config/myos/expected_skills.txt")))
CONTRACTS = Path(os.path.expanduser(
    os.environ.get("MYOS_CONTRACTS", "~/.config/myos/contracts.json")))
ARCHITECT_DIR = mp.d("architect_memory")


def _rel_or_none(p: Path) -> str | None:
    try:
        return str(p.resolve().relative_to(VAULT.resolve()))
    except (ValueError, OSError):
        return None

# Dirs to skip when scanning real user notes (not myOS-managed knowledge; noise).
_SKIP_PARTS = {".obsidian", ".git", ".stversions", ".trash", "_Archive",
               "Templates", "node_modules", "Tags", "Images", "_backup"}
_DIRS = mp.config()["dirs"]
_SKIP_REL_PREFIXES = tuple(p for p in (
    _rel_or_none(SKILLS_DIR),   # skills aren't user notes
    _DIRS.get("architect_memory"), # The architect's memory/planning — own format (nested metadata:)
    _DIRS.get("sandbox"),       # scratch/experiments by definition
    _DIRS.get("inbox"),         # raw captures — typed when filed, not before
) if p) + tuple(mp.config().get("janitor_skip", []))   # e.g. a shared folder with its own versioning


def _iter_notes():
    """Yield (path, rel, text) for real user notes (excludes templates/skills/internals)."""
    for p in VAULT.rglob("*.md"):
        parts = set(p.relative_to(VAULT).parts)
        if parts & _SKIP_PARTS:
            continue
        rel = str(p.relative_to(VAULT))
        if any(rel.startswith(pre) for pre in _SKIP_REL_PREFIXES):
            continue
        try:
            yield p, rel, p.read_text(errors="ignore")
        except Exception:
            continue


class Finding:
    __slots__ = ("ok", "label", "count", "owner", "examples", "critical")

    def __init__(self, ok, label, count=0, owner="", examples=None, critical=False):
        self.ok, self.label, self.count = ok, label, count
        self.owner, self.examples = owner, examples or []
        # critical = a feature-breaking regression → auto-escalates to the architect
        # queue (templates get edited a lot; the automation must not fail silently).
        self.critical = critical


# ── checks ────────────────────────────────────────────────────────────────────

def check_skills() -> Finding:
    if not SKILLS_DIR.is_dir():
        return Finding(False, f"skills dir missing ({SKILLS_DIR})", count=1,
                       owner="fix skills_dir in paths.json", critical=True)
    dirs = sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
    broken = [d for d in dirs if not (SKILLS_DIR / d / "SKILL.md").exists()]
    on_disk = set(dirs) - set(broken)
    if not MANIFEST.exists():
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text("\n".join(sorted(on_disk)) + "\n")
        return Finding(True, f"skills manifest seeded ({len(on_disk)} skills)")
    expected = {l.strip() for l in MANIFEST.read_text().splitlines() if l.strip()}
    missing = sorted(expected - on_disk)
    problems = []
    if missing:
        problems.append(f"MISSING: {', '.join(missing)}")
    if broken:
        problems.append(f"no SKILL.md: {', '.join(broken)}")
    if problems:
        return Finding(False, "expected skills — " + "; ".join(problems),
                       count=len(missing) + len(broken),
                       owner="restore from git / escalate-to-architect",
                       examples=missing + broken)
    extra = sorted(on_disk - expected)
    note = f" (+{len(extra)} new, run --bless: {', '.join(extra)})" if extra else ""
    return Finding(True, f"skills present ({len(on_disk)} match manifest){note}")


def _strip_code(txt: str) -> str:
    """Remove fenced code blocks and inline code spans so documentation that
    QUOTES a link or a Templater expr as an example (```…```, `[[x]]`, `<% tp %>`)
    isn't mistaken for a live link / un-rendered template. Code spans aren't
    rendered as links in Obsidian anyway, so a link inside code is correctly
    not 'live' — this is a semantics fix, not just noise suppression."""
    txt = re.sub(r"```.*?```", " ", txt, flags=re.S)
    txt = re.sub(r"~~~.*?~~~", " ", txt, flags=re.S)
    txt = re.sub(r"`[^`\n]*`", " ", txt)
    return txt


_TP_RE = re.compile(r"<%[-=]?\s*tp\.")   # real Templater call, not prose mentioning "<%"


def check_literal_templater() -> Finding:
    hits = [rel for _p, rel, txt in _iter_notes() if _TP_RE.search(_strip_code(txt))]
    return Finding(not hits, "notes with un-rendered <% tp… %> (literal template)",
                   count=len(hits), owner="person / apply-template engine",
                   examples=hits[:6])


def check_old_format() -> Finding:
    old = []
    for _p, rel, txt in _iter_notes():
        fm = txt.startswith("---") and txt.find("\n---", 3) > 0
        has_type = fm and re.search(r"^type:\s*\S", txt[:txt.find("\n---", 3)], re.M)
        if not has_type:
            old.append(rel)
    return Finding(not old, "notes with no frontmatter `type:` (pre-properties format)",
                   count=len(old), owner="migrate (--all)", examples=old[:6])


# The pre-properties template's header block: a row of underscores used as a divider,
# and inline "Status: #tag" / body-level "Tags: [[...]]" lines. When one of these is left
# in the BODY of a note that already has frontmatter, the note is half-migrated (a "dual
# header") — and the stale block also makes Obsidian render tables/callouts as
# "PARSING FAILED". Reliable, low-false-positive signal: 8+ underscores on their own line.
_LEGACY_DIV    = re.compile(r"^_{8,}\s*$", re.M)
_LEGACY_STATUS = re.compile(r"^Status:\s*#", re.M)
_LEGACY_TAGS   = re.compile(r"^Tags:\s*\[\[", re.M)


def check_legacy_header() -> Finding:
    bad = []
    for _p, rel, txt in _iter_notes():
        body = txt
        if txt.startswith("---"):                     # skip past frontmatter; only scan the body
            end = txt.find("\n---", 3)
            if end > 0:
                body = txt[end + 4:]
        if _LEGACY_DIV.search(body) or _LEGACY_STATUS.search(body) or _LEGACY_TAGS.search(body):
            bad.append(rel)
    return Finding(not bad, "notes with leftover legacy underscore-header (half-migrated dual header → tables render 'PARSING FAILED')",
                   count=len(bad), owner="migrate-note / strip old header", examples=bad[:8])


def check_inbox() -> Finding:
    inbox = VAULT / mp.config()["dirs"]["inbox"]
    if not inbox.exists():
        return Finding(True, "inbox empty/absent")
    items = [p.name for p in inbox.glob("*.md") if p.name != "Quick Capture.md"]
    return Finding(not items, "unfiled inbox items", count=len(items),
                   owner="process-inbox / file-note", examples=items[:6])


def check_broken_links() -> Finding:
    notes = list(_iter_notes())
    # Obsidian resolves a PATH-style link ([[folder/Note]]) by path suffix, so we
    # check against every path in the WHOLE vault (wider than _iter_notes: a
    # link INTO an excluded dir like [[ARCHITECT/START HERE]] is not broken; a link
    # whose target only survives in _Archive under a different path still is).
    # Include NON-.md files: a path-style embed of an attachment
    # ([[Images/scans/foo.png]]) is a real target, not a broken note link.
    all_files = [str(p.relative_to(VAULT)) for p in VAULT.rglob("*") if p.is_file()]
    _ATTACH = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
               ".pdf", ".mp4", ".webm", ".mp3", ".excalidraw"}

    def _resolves(raw: str) -> bool:
        # an attachment link keeps its extension; a note link gets .md appended
        tgt = raw if Path(raw).suffix.lower() in _ATTACH else raw + ".md"
        return any(r == tgt or r.endswith("/" + tgt) for r in all_files)

    link_re = re.compile(r"\[\[([^\]|#^]+)")
    broken = []
    for _p, rel, txt in notes:
        for m in link_re.finditer(_strip_code(txt)):
            raw = m.group(1).strip().rstrip("\\").strip()
            # Graph-first: bare [[Concept]] links to not-yet-created notes are
            # INTENTIONAL (concept nodes), not bugs. Only PATH-style links
            # ([[folder/Note]]) signal a real move/rename break worth flagging.
            if "/" not in raw or raw.startswith(("http", "#")):
                continue
            if not _resolves(raw):
                broken.append(f"{Path(rel).stem} → [[{raw}]]")
    # de-dup, keep order
    seen, uniq = set(), []
    for b in broken:
        if b not in seen:
            seen.add(b); uniq.append(b)
    return Finding(not uniq, "broken [[wikilinks]] (target note missing)",
                   count=len(uniq), owner="escalate-to-architect", examples=uniq[:6])


def check_skill_frontmatter() -> Finding:
    """Every SKILL.md frontmatter must be valid YAML. If it isn't, Hermes' loader
    falls back to a naive line parser that mis-types fields (e.g. `platforms: [linux]`
    becomes the string "[linux]"), the platform check fails, and the skill is
    **silently dropped** — it just vanishes from `hermes skills list` with no error.
    A single stray `: ` (colon-space) in a plain scalar is enough to trigger it."""
    try:
        import yaml
    except Exception:
        return Finding(True, "SKILL.md YAML check skipped (no pyyaml on this interpreter)")
    bad = []
    if not SKILLS_DIR.is_dir():
        return Finding(True, "SKILL.md YAML check skipped (no skills dir)")
    for d in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        sk = d / "SKILL.md"
        if not sk.exists():
            continue
        try:
            parts = sk.read_text().split("---", 2)
            yaml.safe_load(parts[1] if len(parts) >= 3 else "")
        except Exception:
            bad.append(d.name)
    return Finding(not bad, "SKILL.md files with invalid YAML frontmatter (Hermes silently drops these)",
                   count=len(bad), owner="fix SKILL.md frontmatter", examples=bad)


def check_template_health() -> Finding:
    bad = []
    for tpl in sorted(TEMPLATES_DIR.glob("*.md")):
        if eng.unrendered(eng.render(tpl.read_text(), "Selftest Note")):
            bad.append(tpl.name)
    return Finding(not bad, "templates the engine can't fully render",
                   count=len(bad), owner="fix template / extend engine", examples=bad)


def check_feature_contracts() -> Finding:
    """Verify the couplings between FREELY-EDITED templates/notes and the myOS
    automation still hold. Users restyle templates constantly and delete how-to
    callouts once they know a feature; a stray edit can silently sever a feature
    (a daily note losing the link a script relies on, a dashboard losing the
    marker that makes it render). Each broken contract is CRITICAL → auto-escalates
    so it reaches the architect, not just a punch-list.

    Contracts live in a JSON list (MYOS_CONTRACTS), one entry per coupling:
        {"file": "Templates/Daily.md",            # vault-relative, or ~/absolute
         "all_of": ["### Checklist"],             # every marker must be present
         "any_of": ["[[", "%20-%20BD"],           # at least one must be present
         "why": "habit streaks read this heading"}
    A missing file is itself a broken contract. Add an entry whenever a new
    template↔code coupling is introduced — the note is a disposable convenience
    copy; the contract is what keeps the knowledge alive."""
    import json
    if not CONTRACTS.exists():
        return Finding(True, "feature contracts (none configured)")
    try:
        contracts = json.loads(CONTRACTS.read_text())
    except Exception as e:
        return Finding(False, f"feature contracts file unreadable ({e})", count=1,
                       owner="fix contracts.json", examples=[str(CONTRACTS)])
    broken = []
    for c in contracts:
        raw = c.get("file", "")
        path = Path(os.path.expanduser(raw))
        if not path.is_absolute():
            path = VAULT / raw
        why = c.get("why", "")
        if not path.exists():
            broken.append(f"{raw}: missing" + (f" ({why})" if why else ""))
            continue
        txt = path.read_text(errors="ignore")
        lost = [m for m in c.get("all_of", []) if m not in txt]
        any_of = c.get("any_of", [])
        if any_of and not any(m in txt for m in any_of):
            lost.append("one of " + " / ".join(any_of))
        if lost:
            broken.append(f"{raw}: lost {', '.join(lost)}" + (f" ({why})" if why else ""))
    return Finding(not broken, "myOS feature contracts a template edit has broken",
                   count=len(broken), owner="escalate-to-architect",
                   examples=broken, critical=True)


_INBOX_SKIP = {".obsidian", ".git", ".stversions", ".trash", "_Archive",
               "node_modules", "_backup"}


# myOS operational folders that must exist at exactly ONE canonical path each. The
# small model has invented siblings (`Vault/Inbox`; `Active/Calendar` missing the `1 `)
# that silently split data or break the calendar sync — every such duplicate is CRITICAL.
_MANAGED_KEYS = mp.config().get("managed_dirs", ["inbox", "tasks", "journal", "projects"])


def check_rogue_myos_folders() -> Finding:
    """North-Star invariant: each myOS operational folder lives at ONE canonical path.
    Any other vault folder with the same basename (a model-invented duplicate) is CRITICAL."""
    canon = {}
    for k in _MANAGED_KEYS:
        try:
            p = mp.d(k).resolve()
            canon[p.name.lower()] = p
        except Exception:
            continue
    rogue = []
    for p in VAULT.rglob("*"):
        if not p.is_dir():
            continue
        cp = canon.get(p.name.lower())
        if cp is None or set(p.relative_to(VAULT).parts) & _INBOX_SKIP:
            continue
        rel = str(p.relative_to(VAULT))
        # Skip non-vault-note trees that legitimately mirror layer names (the architect's memory
        # `ARCHITECT/Projects`, an export mirror, a shared folder, the skills tree).
        if any(rel.startswith(pre) for pre in _SKIP_REL_PREFIXES):
            continue
        if p.resolve() != cp:
            rogue.append(f"{rel} (should be {cp.relative_to(VAULT)})")
    return Finding(not rogue,
                   "rogue myOS folder — an operational folder duplicated at a wrong path",
                   count=len(rogue), owner="escalate-to-architect",
                   examples=rogue, critical=True)


def check_memory_index_size() -> Finding:
    """The architect's memory index (ARCHITECT/MEMORY.md) is loaded whole every session and
    TRUNCATES past a read limit — silently. Everything past the cut is simply
    invisible to the architect, with no error at read time, so memories can go missing
    without anyone noticing. Growth has two sources: new memories (fine) and
    existing one-line entries fattening as projects advance (not fine — that
    detail belongs in the topic file). Flag it early so the index gets compacted
    on purpose instead of by accident."""
    idx = ARCHITECT_DIR / "MEMORY.md"
    if not idx.is_file():
        return Finding(False, "Architect memory index missing (ARCHITECT/MEMORY.md)",
                       count=1, owner="escalate-to-architect", critical=True)
    size = idx.stat().st_size
    entries = len([ln for ln in idx.read_text(errors="ignore").splitlines()
                   if ln.startswith("- [")])
    per = size // max(1, entries)
    problems = []
    # 24.4KB is the hard read limit; warn with room to act, escalate near it.
    if size >= 17_000:
        problems.append(f"index is {size/1024:.1f}KB / 24.4KB limit ({entries} entries, "
                        f"{per}B each) — COMPACT NOW, entries are about to vanish")
    elif size >= 15_000:
        problems.append(f"index is {size/1024:.1f}KB ({entries} entries, {per}B each) — "
                        "compact soon: shorten fat entries, detail lives in the topic file")
    if per > 400 and size >= 12_000:
        problems.append(f"entries average {per}B — index lines are absorbing project "
                        "detail again (target ~230B, one line per memory)")
    return Finding(not problems, f"Architect memory index size ({size/1024:.1f}KB, {entries} entries)",
                   count=len(problems), owner="escalate-to-architect",
                   examples=problems, critical=size >= 17_000)


def check_memory_symlinks() -> Finding:
    """Every memory should exist ONCE: a real file in the vault, symlinked into
    the architect's recall dir. A real file on BOTH sides means two copies that drift
    apart silently — the reconciler refuses to guess which one wins, so it just
    warns forever and the sync becomes a manual step someone will forget."""
    mem = mp.architect_memory_dir()
    if mem is None or not mem.is_dir():
        return Finding(True, "Architect memory symlinks (no recall dir)")
    problems = []
    for f in sorted(mem.glob("*.md")):
        if f.is_symlink():
            continue
        cand = [ARCHITECT_DIR / f.name] + [ARCHITECT_DIR / c / f.name
                for c in ("User", "Feedback", "Projects", "Reference")]
        twin = next((c for c in cand if c.is_file()), None)
        if twin is None:
            continue                       # unfiled; the reconciler will file it
        same = twin.read_bytes() == f.read_bytes()
        problems.append(f"{f.name}: real file on BOTH sides"
                        + ("" if same else " AND THEY DIFFER") + f" (vault: {twin.name})")
    return Finding(not problems, "Architect memory symlinks (one copy per memory)",
                   count=len(problems), owner="myos_memory_sync.sh",
                   examples=problems,
                   critical=any("DIFFER" in p for p in problems))


CHECKS = [check_skills, check_skill_frontmatter, check_literal_templater,
          check_old_format, check_legacy_header, check_inbox, check_rogue_myos_folders,
          check_broken_links, check_template_health, check_feature_contracts,
          check_memory_index_size, check_memory_symlinks]


def run() -> list[Finding]:
    return [c() for c in CHECKS]


ESCALATIONS = ARCHITECT_DIR / "Escalations.md"


def escalate(findings: list[Finding]) -> int:
    """Append CRITICAL failing findings to the architect Escalations queue so a
    feature-breaking regression reaches the architect async (not just a morning punch-list).
    Idempotent: the exact broken-contract text already present in the file (OPEN or
    resolved) is not re-appended."""
    from datetime import datetime
    crit = [(f, ex) for f in findings if not f.ok and f.critical for ex in (f.examples or [f.label])]
    if not crit:
        return 0
    # A missing queue file must not silently swallow a CRITICAL breakage — create it.
    if not ESCALATIONS.exists():
        ESCALATIONS.write_text("# Escalations\n")
    text = ESCALATIONS.read_text()
    new_blocks, added = [], 0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    for f, ex in crit:
        if ex in text:                       # already queued (open or resolved) → skip
            continue
        new_blocks.append(
            f"\n## {ts} — Janitor CRITICAL: {ex}\n"
            f"- **Context:** myOS janitor auto-escalation (template-edit fragility).\n"
            f"- **What I tried:** detected by the janitor's scheduled scan\n"
            f"- **Why escalated:** {ex}\n"
            f"- **Status:** OPEN\n")
        added += 1
    if added:
        ESCALATIONS.write_text(text.rstrip("\n") + "\n" + "".join(new_blocks))
    return added


def _main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true", help="issues only, one line each")
    ap.add_argument("--bless", action="store_true", help="accept current skills as expected")
    ap.add_argument("--escalate", action="store_true",
                    help="append CRITICAL feature-contract breakages to the Escalations queue")
    a = ap.parse_args(argv)

    if a.bless:
        on_disk = sorted(d.name for d in SKILLS_DIR.iterdir()
                         if d.is_dir() and (d / "SKILL.md").exists())
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text("\n".join(on_disk) + "\n")
        print(f"blessed {len(on_disk)} skills → {MANIFEST}")
        return 0

    findings = run()
    issues = [f for f in findings if not f.ok]
    escalated = escalate(findings) if a.escalate else 0
    if a.brief:
        if not issues:
            print("🧹 janitor: all clear")
        else:
            for f in issues:
                mark = "🚨 " if f.critical else "⚠ "
                print(mark + f.label
                      + (f" ({f.count})" if f.count else "")
                      + (f" → {f.owner}" if f.owner else ""))
        if escalated:
            print(f"   ↳ {escalated} feature-breakage(s) escalated to the architect queue")
        return 0

    print("🧹 myOS janitor scan\n")
    for f in findings:
        if f.ok:
            print(f"✅ {f.label}")
        else:
            print(f"⚠ {f.label}"
                  + (f" ({f.count})" if f.count else "")
                  + (f"  → {f.owner}" if f.owner else ""))
            for ex in f.examples:
                print(f"     · {ex}")
    print(f"\n— {len(issues)} issue(s) to route —" if issues else "\n— all clear —")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
