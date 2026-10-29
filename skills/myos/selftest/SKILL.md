---
name: selftest
description: Live capability check of myOS — actually exercises each tool instead of guessing status. Use to answer "is everything working?" honestly.
platforms: [linux]
runner: either
status: published
confidence: 0.80
source: taught
version: 1.1.0
escalate_when: any check reports ❌ that you can't trivially fix
---

# selftest

Runs the real myOS capability checks — actually exercises each tool rather than assuming it works (the "no more lying 'all fine'" rule).

## When to Use
- An "is everything working / run a health check" request.
- After changing scripts, paths, or skills.

## Procedure
1. Run: `bash $MYOS_ENGINES/myos_selftest.sh`.
2. Relay its output verbatim (the ✅/❌ lines).
3. For any ❌, take the obvious fix if one is named (e.g. broken memory links → `bash $MYOS_ENGINES/myos_claude_memory_sync.sh`); otherwise run `escalate-to-architect`.

## What it checks
spine + inbox resolves · inbox writable (writes and removes a file) · every template renders · Claude memory links intact · Hermes myOS skills loaded · ollama up · embedding model present · gateway active.

## Pitfalls
- **Relay verbatim** — never summarize a ❌ into an "all good". That's the exact failure mode this skill exists to kill.
- **Don't schedule a second report** — if a morning brief already folds these checks in (green-collapsed to one line unless something fails), run this skill on demand only.

## Verification
- The ✅/❌ block was reproduced as-is; every ❌ has either an applied fix or a queued escalation.

## Cadence
On demand, and folded into a scheduled morning brief.
