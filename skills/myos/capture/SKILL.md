---
name: capture
description: The natural-language front door — the user types a raw thought, you decide if it's a task or a note and file it through the right tool, confirming only when unsure. Use for any freetext capture that isn't already a /command.
platforms: [linux]
runner: hermes
status: draft
confidence: 0.55
source: taught
version: 1.0.0
escalate_when: after one clarifying question you still can't tell what it is or when it is — then drop it raw into the Inbox (never lose it) and say so
---

# capture

The **natural-language capture layer**. The user won't always reach for `/task` or `/note` —
often they just type the thought as it leaves their head: *"remind me to renew the domain
monday"*, *"idea: the janitor should report how long each check took"*. Your job is to catch
it, decide what it is, and file it through the deterministic tool — so **nothing is lost.**

This is the fallback for when a `/command` wasn't used. If the user *did* use `/task` or
`/note`, honour that type directly — don't re-classify.

## The one rule that governs tone
- **Confident → just do it.** File it, then a one-line receipt: *"Done — task for Monday:
  renew the domain."* No permission-seeking.
- **Unsure → one short question, then act.** Ambiguous type or date → ask exactly one crisp
  question. If it's *still* unclear → drop it raw in the Inbox (below) and say so. Never guess a
  date; never lose the thought.

## Classify (top-to-bottom, first match wins)
| It looks like… | Type → tool |
|---|---|
| an **action to do** — "remind me to…", "I need to…", "call/email/buy/fix…", esp. with a deadline | **task** → `myos_task.py add` (see `task` skill) |
| a **thought/idea/note-to-self** with no action — "idea: …", "TIL …", "what if …" | **note** → `capture-to-inbox` (verbatim, one line) |
| longer / needs a real home (a page, not a line) | **note** → the `/note` command or `capture-to-inbox`; `file-note` sorts it later |
| a thing happening at a time you attend ("dentist Tuesday 2pm") | **event** → your calendar tool if one is installed; otherwise a dated **task** |
| **none clear after one question** | **Inbox** → `capture-to-inbox` (raw, flagged) |

Signals: an **imperative verb** ("call", "buy", "email", "finish") or "remind me" → lean
**task**. "idea/note/thought/TIL/what if" or pure musing → **note**.

## Procedure
1. If it came as `/task` / `/note`, skip classification — use that type.
2. Otherwise classify with the table. Pull out the pieces:
   - **task**: terse imperative text, a `--due <when>` if there's a deadline, an `--area`
     if obvious. Pass the user's own date words ("monday", "the 21st") — the tool resolves
     them through `myos_dates`; **never compute an ISO date yourself.** No deadline → just
     add it undated.
   - **note**: the text, verbatim.
3. **Confidence check.** Sure of both *type* and *when*? → file it, one-line receipt. Not sure?
   → one question. Still not sure? → `capture-to-inbox` raw, and say it's parked in the
   Inbox for later.

## Examples
- *"remind me to renew the domain monday"* → **task** with due date →
  `myos_task.py add "Renew the domain" --due monday` → "Noted — task for Monday."
- *"idea: janitor should time each check"* → **note** → `capture-to-inbox` → "Stashed in the Inbox."
- *"squash update thing"* → too vague → ask one question ("a task to do, or just a note?"); no
  clear answer → `capture-to-inbox` raw → "Wasn't sure, so I parked it in the Inbox."

## Pitfalls
- **Never lose it.** If every branch fails, the Inbox is the floor — raw text always lands somewhere.
- **Never guess a date.** Ambiguous when → ask, or add the task undated.
- **Don't over-confirm.** A clear task doesn't need a "shall I?" — the receipt IS the confirmation.
- **Don't re-classify an explicit `/command`.** Trust the verb the user chose.
- Let the tools own the files — you classify and hand off; you don't hand-write notes.

## Verification
- The item exists where its type belongs (Backlog line / Inbox line), created by its tool,
  and your receipt matches what the tool printed (its ✅/❌ line, relayed — not paraphrased).

## Cadence
On demand — the default path for any freetext that isn't already a slash command.
