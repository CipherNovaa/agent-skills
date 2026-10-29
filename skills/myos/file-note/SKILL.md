---
name: file-note
description: Sort one note into the correct myOS layer folder, conservatively. Use to file a single note; it leaves + flags anything ambiguous rather than misfiling.
platforms: [linux]
runner: either
status: published
confidence: 0.75
source: taught
version: 1.1.0
escalate_when: content fits two layers equally, has no clear home, or confidence < 80% — then leave it, flag, escalate
---

# file-note

The atomic vault-sorting primitive. **Conservative: misfiling is worse than not filing.** When unsure, leave it and flag it.

## When to Use
- A single note needs sorting into the right layer folder.
- Called per-item by `process-inbox`.

## Decision table (top-to-bottom, first match wins)
| The note is… | Folder key (resolve via spine) |
|---|---|
| a raw, unprocessed thought | `inbox` (leave) |
| messy scratch / experiment | `sandbox` |
| about an active project | `projects` |
| a dated daily (`YYYY-MM-DD`) | `journal` |
| math / programming / coursework | `academics` (+ subject subfolder) |
| how a system/tool works | `systems` |
| an external source (book/article/video) | `source_material` |
| about the myOS system itself | `myos` |
| retired / superseded | `archive` |
| **none clear, or two fit equally** | **leave + escalate** |

Resolve real paths: `python $MYOS_ENGINES/myos_paths.py get <key>`.

## Procedure
1. Read the note (`read_file`).
2. Pick a row. If none clearly wins or confidence < 80% → **stop**: add `#needs-sorting`, run `escalate-to-architect`, done. Do **not** move it.
3. **Do not rewrite the body** — preserve the user's wording.
4. Move the file to the chosen folder (file tool / `terminal mv`). By-name `[[wikilinks]]` survive the move.
5. **Now** put it on the properties standard **deterministically** — don't hand-edit frontmatter:
   `python $MYOS_ENGINES/myos_migrate_note.py --apply "<new path>"`. Run it *after* the move so the
   `type:` is inferred from the destination folder (idempotent; body untouched). See `migrate`.
6. Report: `filed "<title>" → <folder>` or `flagged "<title>" #needs-sorting`.

## Pitfalls
- **Never delete.** "Remove" = move to the `archive` folder.
- Knowledge-layer notes must read fine without plugins (no Dataview/Templater in them).
- When unsure, **leave + flag** — an unfiled note beats a misfiled one.

## Verification
- Filed: the note now resolves under the chosen folder (`python $MYOS_ENGINES/myos_paths.py get <key>`) and nowhere else.
- Flagged: the note carries `#needs-sorting` and an escalation was queued.

## Cadence
On demand, or per-item under `process-inbox`.
