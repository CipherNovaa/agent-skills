---
name: my-skill-slug            # kebab-case; MUST equal the folder name
description: One line in "Use when …" style — this is what the skills index shows and what routing matches on. Name the trigger.
platforms: [linux]
runner: either                 # either | hermes | architect  — who can run it (the architect plans, Hermes captures)
status: draft                  # draft | published  — earned autonomy: a skill graduates draft→published once proven
confidence: 0.60               # 0.0–1.0  — how battle-tested it is; nudge up as it proves out
source: taught                 # taught | learned | imported  — taught = the user + the architect authored it
version: 1.0.0                 # semver; bump the minor on a material change, patch on a tweak
escalate_when: <the condition under which Hermes should stop and run escalate-to-architect instead of guessing>
---

# my-skill-slug

One-line statement of what this skill does and its guiding principle. Background/why: [[NOTES]].
(↑ only include the [[NOTES]] pointer if a sibling NOTES.md actually exists.)

## When to Use
Plain-English triggers — when this fires, and the `//command` or `/slash` command if it has one.
Formalizes the `description` + `escalate_when` so the boundary is legible.

## Procedure
1. First concrete step (imperative). Resolve paths via the spine, never hardcode:
   `python $MYOS_ENGINES/myos_paths.py get <key>`.
2. Second step.
3. …

## Pitfalls
- Guardrails + failure-modes to avoid, with recovery. Hard invariants live here too
  (e.g. **read-only**, **never delete**, **preserve the user's wording**).
- When unsure → stop, flag, run `escalate-to-architect`. Misfiring is worse than not acting.

## Verification
- How to CONFIRM it actually worked — not assume. This closes the "no lying 'all fine'" gap.
- Prefer an observable signal: a file now exists / a count > 0 / the output carries an expected marker.

## Cadence
When it runs: on demand, a `//command`, a cron job, weekly, etc. (Optional; round-trips as-is.)

<!--
CONTRACT NOTES (delete in real skills):
- Section names follow Odysseus's skill importer (services/memory/skill_format.py): When to Use /
  Procedure / Pitfalls / Verification. `Steps` is aliased to Procedure; `Cadence` round-trips as body_extra.
- Frontmatter is Hermes-native (name/description/platforms) PLUS the earned-autonomy fields
  (runner/status/confidence/source/version/escalate_when). Each side ignores the other's extra keys.
- Frontmatter MUST be valid YAML: a stray ": " inside a plain value makes Hermes silently drop the
  skill. Quote such values. The janitor checks this.
- Deep design rationale / engine internals go in a sibling NOTES.md, not here — SKILL.md stays runtime-lean.
-->
