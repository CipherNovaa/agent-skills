---
name: escalate-to-architect
description: Queue a hard/ambiguous task for Claude (the architect) instead of guessing — async, offline-safe. Use when a skill's escalate_when fires, or a task needs design, judgment, or system changes.
platforms: [linux]
runner: hermes
status: published
confidence: 0.85
source: taught
version: 1.0.0
escalate_when: this IS the escalation skill
---

# escalate-to-architect

The safety valve that makes local-first viable: Hermes never guesses on hard things — it **queues them for Claude** (the architect). Fully async/offline: write a file now; Claude reads it next session. Background/why: [[NOTES]].

## When to Use
- A skill's `escalate_when` fires.
- An ambiguous sorting / judgment call.
- Multi-step reasoning, design, refactoring, or new-skill authoring.
- Anything that would modify scripts, configs, or system services.
- (No chat trigger — Hermes invokes this internally when it hits a wall.)

## Procedure
1. Open (create if missing): `<claude_memory>/Escalations.md`, where `<claude_memory>` = `python $MYOS_ENGINES/myos_paths.py get claude_memory`.
2. Append:
   ```markdown
   ## YYYY-MM-DD HH:MM — <one-line task>
   - **Context:** <note/file/project; [[links]]>
   - **What I tried:** <or "did not attempt — out of scope">
   - **Why escalated:** <the escalate_when reason>
   - **Status:** OPEN
   ```
3. If a note is blocked, also tag it `#needs-claude`.
4. Tell the user plainly: "Queued for Claude: <task>." Then move on.

## Pitfalls
- **Never attempt the hard task anyway** — the whole point is not guessing. Queue it and stop.
- Always fill Context + Why so Claude can resolve without re-deriving the situation.

## Verification
- The new `## YYYY-MM-DD …` entry is at the tail of `Escalations.md` with `Status: OPEN`.
- The user received the one-line "Queued for Claude" confirmation.

## Cadence
On demand — whenever Hermes hits something outside its lane.
