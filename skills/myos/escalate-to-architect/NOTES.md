# escalate-to-architect — notes

Design background. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why
Local-first only works if Hermes has a safe failure mode. Rather than let a small model guess on design/judgment (and corrupt the vault), it writes an async escalation that Claude picks up next session. Claude = architect, Hermes = operator.

Renamed from `escalate-to-claude` → `escalate-to-architect`: the name should point at the **role**, not the tool, so it survives if the architect model ever changes.

## Claude side
On its next session Claude reads `CLAUDE/Escalations.md`, resolves OPEN items, and marks them `Status: DONE (date)`. Recurring escalations of one kind = a signal to write a new skill so Hermes handles it next time — the trust ladder in action: a repeated escalation graduates into an owned, `published` skill.

The janitor writes to the same queue (`--escalate`) when it finds a CRITICAL, feature-breaking regression, so one file is the architect's whole inbox.
