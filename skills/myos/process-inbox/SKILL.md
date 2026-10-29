---
name: process-inbox
description: Triage the whole capture Inbox toward inbox-zero by running file-note over each item. Use for a "clear / process my inbox" pass.
platforms: [linux]
runner: either
status: draft
confidence: 0.50
source: taught
version: 1.1.0
escalate_when: more than a third of items get flagged, or an item needs a real decision
---

# process-inbox

The "empty the inbox" pass. Runs the **file-note** skill over each item. Safe because file-note refuses to guess.

## When to Use
- A "process / clear my inbox" request.
- The weekly maintenance pass (via `weekly-review`).

## Procedure
1. Resolve inbox: `python $MYOS_ENGINES/myos_paths.py get inbox`.
2. List every `.md` in it **except `Quick Capture.md`** (the rolling capture log — leave it). Use `search_files` (pattern `*.md`), not `ls`.
3. For each note, run the **file-note** skill (which also puts each filed note on the
   properties standard via `migrate` — no hand-edited frontmatter).
4. Tally: filed (by destination), flagged `#needs-sorting`, left.
5. Report, e.g.: `Inbox: 11 → 7 filed (3 Systems, 2 Projects, 2 Source Material), 3 flagged, 1 left`.
6. If flagged > ⅓ of items, or any needs judgment → run `escalate-to-architect` with a summary.

## Pitfalls
- **Read-then-move only** — never delete, never rewrite bodies.
- Leave `Quick Capture.md` alone — it's the rolling log, not an item.

## Verification
- The tally balances (filed + flagged + left = starting count); each filed note resolves under its new folder.

## Cadence
Weekly.
