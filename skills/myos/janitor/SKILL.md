---
name: janitor
description: Read-only vault scan that points at what needs doing — literal templates, unfiled inbox, old-format notes, path-broken links, a rogue duplicate folder, a vanished skill, a broken feature contract — each routed to the skill that fixes it. Use for "what needs tidying?" or as the engine behind the morning check and weekly review.
platforms: [linux]
runner: either
status: draft
confidence: 0.60
source: taught
version: 1.1.0
escalate_when: a finding needs a judgment call (which of two homes, a real rename decision) — route it to escalate-to-architect; don't fix it here
---

# janitor

The vault's **manager, not its worker**. Scans read-only for drift and emits a punch-list, each item tagged with the skill that fixes it. It **never edits notes** — it points; the named skills do the work. A morning health brief consumes `--brief`; the weekly review reads the full list. Background: [[NOTES]].

## When to Use
- "What needs tidying / what's drifting in the vault?"
- As the detector behind a morning health brief (terse) and `weekly-review` (reflective).

## Procedure
1. Run: `python $MYOS_ENGINES/myos_janitor_scan.py` (full punch-list) or `--brief` (one line per issue). Add `--escalate` on a scheduled run to auto-queue CRITICAL feature breakages.
2. Relay the ⚠ / 🚨 lines — each already names its owning skill (🚨 = critical, feature-breaking).
3. Hand each issue to the named skill (do **not** do the work here):
   - un-rendered `<% tp… %>` → `migrate` (it renders the supported subset)
   - unfiled inbox → `process-inbox` / `file-note`
   - no-`type:` notes or a leftover legacy header → `migrate`
   - path-broken `[[links]]` → `escalate-to-architect`
   - rogue duplicate folder (a second "Inbox") → `escalate-to-architect`
   - a missing/expected skill → restore from git, or `escalate-to-architect`
   - invalid SKILL.md YAML → fix the frontmatter (quote any value containing `: `)
   - 🚨 **broken feature contract** (a template edit severed a coupling listed in `contracts.json`) → `escalate-to-architect`; `--escalate` already appended it to `Escalations.md`. Add a contract whenever a new template↔code coupling is introduced.
   - memory index too big / memory duplicated → `escalate-to-architect` / `myos_claude_memory_sync.sh`
4. Never mass-fix. Route what the user OKs; leave the rest on the list.

## Pitfalls
- **Read-only. Never edits notes.** The janitor points; skills act — this prevents a runaway auto-fix across the vault. (Its only writes: seeding the skills manifest, and appending to `Escalations.md` with `--escalate`.)
- **Bare `[[Concept]]` links are NOT flagged** — graph-first concept nodes are intentional; only path-style breaks surface.
- The no-`type:` list is a *backlog*, not an emergency — route a few per pass, don't dump 150 edits at once.
- After INTENTIONALLY adding/removing a skill, run `myos_janitor_scan.py --bless` so the expected-skills manifest matches (else it flags the change).

## Verification
- Output lists each issue with a count + owning skill; the scan makes **zero writes** to notes; `--bless` seeds/updates the expected-skills manifest.

## Cadence
Daily (`--brief --escalate`, scheduled) + weekly (`weekly-review`, full). On demand anytime.
