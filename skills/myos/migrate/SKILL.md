---
name: migrate
description: Bring an old-format note (no frontmatter `type:`) onto the myOS properties standard without rewriting the body. Use to fix a pre-properties note, or the note the janitor routes here.
platforms: [linux]
runner: hermes
status: draft
confidence: 0.6
source: taught
version: 1.0.0
escalate_when: the note's folder is outside the mapped layers AND its content clearly wants a real type (the tool would floor it to a bare `note` type) — surface it instead of guessing
---

# migrate

The dual of the template engine: `apply-template` *instantiates* a new note; **migrate** brings an
*already-written* note that predates the properties standard (no YAML `type:`) up to it. It only ever
adds/splices a frontmatter block — **the user's words are preserved byte-for-byte**. Idempotent: a note
that already has `type:` is left untouched. This is the fix path the **janitor** routes old-format
notes to.

## When to Use
- The janitor flags "notes with no frontmatter `type:`" → run this to clear them.
- `file-note` calls it to guarantee a filed note lands on the standard (see that skill's step 3).
- Any single pre-properties note you want typed.

## How type is decided (folder-first, conservative)
The note's home layer decides its `type:` — the layer is the most reliable signal:

| Folder (spine key) | `type:` |
|---|---|
| `projects` | project |
| `journal` + `YYYY-MM-DD` filename | daily |
| `academics` / `systems` / `myos` | concept |
| `source_material` | resource |
| `inventory` | inventory (+ `category:` from the subfolder) |
| anything unmapped | `note` (floor) — or with `--strict`, skipped + flagged |

## Procedure
1. **One note:** `python $MYOS_ENGINES/myos_migrate_note.py "<path>"` → previews the header it would add
   (dry-run). Confirm the inferred `type:` looks right, then re-run with `--apply` to write.
2. **The whole backlog:** `python $MYOS_ENGINES/myos_migrate_note.py --all` → dry-run table over every
   old-format note (exactly the janitor's set). Then `--all --apply` to migrate them all.
3. **When unsure it should guess:** add `--strict` — unmapped folders are then left + listed for
   escalation instead of floored to `type: note`.
4. Report: `migrated N, already-current M` (+ any flagged/errors).

## Pitfalls
- **Body is never rewritten** — the tool prepends/splices frontmatter only. If you ever need to
  change wording, that's a different job (don't do it here).
- **Idempotent** — safe to re-run; a note with `type:` is skipped. Don't hand-add a second block.
- Existing inline `#tags` in the body keep working (body untouched); the block seeds `tags: []`.
- Floored `type: note` on a note that clearly wants a real type → that's the escalation case.

## Verification
- `myos_migrate_note.py "<note>"` twice → 2nd run says `already-current`.
- The migrated note opens with a `---` block carrying a correct `type:`, and its body is unchanged
  (`git diff` shows only added frontmatter lines, zero deletions).
- After `--all --apply`, `$MYOS_ENGINES/myos_janitor_scan.py --brief` no longer lists the "no frontmatter `type:`"
  line.

## Cadence
On demand, or whenever the janitor surfaces old-format notes.
