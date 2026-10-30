# escalate-to-architect — notes

Design background. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why
Local-first only works if Hermes has a safe failure mode. Rather than let a small model guess on design/judgment (and corrupt the vault), it writes an async escalation that the architect picks up next session. The architect = architect, Hermes = operator.

Renamed to `escalate-to-architect` from a name that pointed at the tool: the name should point at the **role**, not the tool, so it survives if the architect model ever changes.

## The architect side
On its next session the architect reads `ARCHITECT/Escalations.md`, resolves OPEN items, and marks them `Status: DONE (date)`. Recurring escalations of one kind = a signal to write a new skill so Hermes handles it next time — the trust ladder in action: a repeated escalation graduates into an owned, `published` skill.

The janitor writes to the same queue (`--escalate`) when it finds a CRITICAL, feature-breaking regression, so one file is the architect's whole inbox.
