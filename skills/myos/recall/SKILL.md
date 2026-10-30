---
name: recall
description: Answers a question using only the user's own Obsidian vault notes, grounded with [[citations]], and says so plainly when the answer isn't there. Use for "where did I note X" / "what did I decide about Y", or the //recall command.
platforms: [linux]
runner: either
status: published
confidence: 0.90
source: taught
version: 1.1.0
escalate_when: recall returns "found nothing" on something the user is sure exists (a retrieval gap) — escalate to check scope/indexing; don't guess
---

# recall

Ask-the-vault: answer from the user's own notes only, with `[[citations]]`; never invent. Read-only, offline. Wraps `engines/architect_powers.py recall` — the same engine a handwriting-tablet `//recall` command can call, so every device gives the same answer. Background + engine internals: [[NOTES]].

## When to Use
- A recall / ask-vault request: "where did I note X", "what did I decide about Y".
- The `//recall <question>` command.

## Procedure
1. Take the question (natural language is fine).
2. Run: `python $MYOS_ENGINES/architect_powers.py recall "<question>"`
3. Relay the answer verbatim, including its `> _… sources: [[…]]_` line — the citations let the user jump to the source.
4. On "found nothing": say so; offer broader keywords or note it may not be in the vault yet. Never fabricate.

## Pitfalls
- **Never invent** — answer from the vault or admit it can't. A confident wrong answer is worse than "not in your notes".
- **Always cite** — every claim ties to a `[[note]]`.
- **Read-only** — never writes or moves notes.
- Repeated "found nothing" on something that *does* exist = retrieval gap → run `escalate-to-architect`.
- Deeper (the architect, not Hermes): for cross-note questions, `rg -i` the vault and read more notes — still cite, still vault-only.

## Verification
- The output ends with a `> _Searched N notes (hybrid|lexical) · sources: [[…]]_` line — if that's missing, the engine failed, don't relay a bare answer.
- Every factual claim in the answer carries a `[[citation]]`.

## Cadence
On demand. Triggers: a recall / ask-vault request, or `//recall <q>`.
