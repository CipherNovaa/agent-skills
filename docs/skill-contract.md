# The skill contract

Every `SKILL.md` follows one shape — start from [`skills/SKILL-TEMPLATE.md`](../skills/SKILL-TEMPLATE.md).
It's Hermes-native frontmatter **plus** an earned-autonomy and section model borrowed from
Odysseus's skill format, so skills are consistent, easy to customise, and import/export
cleanly between the two systems.

## Frontmatter

| field | meaning |
|---|---|
| `name` | kebab slug = folder name |
| `description` | one line, "Use when …" trigger style (the index/routing key; Hermes truncates it in the index, the full body loads when the skill is used) |
| `platforms` | e.g. `[linux]` — gates where it runs |
| `runner` | `either \| hermes \| claude` — Claude plans, Hermes captures |
| `status` | `draft \| published` — **earned autonomy**: graduates draft→published once proven |
| `confidence` | `0.0–1.0` — how battle-tested; nudge up as it proves out |
| `source` | `taught \| learned \| imported` |
| `version` | semver; bump on change |
| `escalate_when` | when Hermes must stop and run `escalate-to-architect` instead of guessing |

The frontmatter **must be valid YAML**. Hermes doesn't error on a bad block: it falls back to a
line parser, `platforms: [linux]` becomes the string `"[linux]"`, the platform check fails, and
the skill silently vanishes. A single `: ` inside an unquoted value is enough. The janitor
parses every frontmatter to catch this.

## Body sections

`## When to Use` · `## Procedure` · `## Pitfalls` · **`## Verification`** · `## Cadence` (optional).

`## Verification` is required wherever a skill *can* self-check. It encodes the "no lying
'all fine'" rule: an observable signal (a file exists, a count > 0, the output carries an
expected marker), never "I ran it, so it worked". Deep design rationale and engine internals go
in a sibling `NOTES.md`, not in `SKILL.md` — the runtime file stays lean because a small local
model reads it on every use.

## How Hermes loads these

- Point `skills.external_dirs` in `~/.hermes/config.yaml` at the folder that contains `myos/`
  (this repo's `skills/`, or a copy inside a synced vault so every device shares one source of
  truth).
- Hermes walks each `external_dirs` path (following symlinks) for `**/SKILL.md`. A skill at
  `myos/<name>/SKILL.md` registers as **category `myos`, name `<name>`**.
- Hermes's skill curator maintains only its own `~/.hermes/skills`, not external dirs, so these
  skills won't be auto-archived or rewritten.
- New skills appear on Hermes's next scan (a fresh session / `hermes skills list`). If the
  running gateway doesn't see one, restart the gateway.

## Adding a skill

1. Copy `skills/SKILL-TEMPLATE.md` to `skills/myos/<name>/SKILL.md` and fill it in.
2. Keep the procedure deterministic; resolve vault paths through the spine
   (`python $MYOS_ENGINES/myos_paths.py get <key>`); prefer a tool that writes the file and
   prints ✅/❌ over prose that asks the model to write it.
3. Bake in the failure mode: **unsure → leave it, flag `#needs-sorting`, escalate.**
4. Start it at `status: draft` with a modest `confidence`. Promote it when it has run clean
   unattended.
5. Run `myos_janitor_scan.py --bless` so the expected-skills manifest includes it.

## Design rule

Deterministic work → scripts (fast, reliable, offline). Judgment work (sorting, review,
planning) → LLM skills. Don't make a 4B model orchestrate what a shell script does in 50 ms.
