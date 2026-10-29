---
name: resume
description: Cold-start orientation — reconstruct exactly where work stands, on any device, losing no thread. Use at the start of a session or after a laptop↔desktop switch.
platforms: [linux]
runner: either
status: published
confidence: 0.85
source: taught
version: 1.0.0
escalate_when: the RESUME anchor is missing or contradicts the build log (state is ambiguous) — surface it, don't guess the next action
---

# resume

The first thing to run at the **start of a session** or after a **device switch**. Turns "where was I?" into a 20-second answer. Read-only — it *orients*; it does not change vault state. Background/why: [[NOTES]].

## When to Use
- Start of every session.
- After a device switch (laptop ↔ desktop).

## Source of truth (read in this order)
All under `<claude_memory>` = `python $MYOS_ENGINES/myos_paths.py get claude_memory`, except the build log:
1. **`Active Threads.md`** — the **▶ RESUME callout** is the single source of truth for *where we are + next step*.
2. **`MEMORY.md`** — the memory index (terse). Pull the one project memory the RESUME block names.
3. **`<myos>/myOS Build Log.md`** (`myos_paths.py get myos`) — the **last entry** is the current frontier (cross-check against RESUME).
4. **`Escalations.md`** — any `Status: OPEN` items Hermes queued.

## Procedure
1. **Device / sync check first** (the cross-device guard):
   - `git -C "<vault>" log -1 --format='%cd  %s'` → last backup.
   - `git -C "<vault>" status -s` → uncommitted local changes (count).
   - `systemctl --user is-active syncthing` → if `active`, files auto-sync (anchors are current); else warn this device may be stale.
   - If `Active Threads.md` `updated:` is older than other recently-edited memory files → flag a possibly stale anchor.
2. **Read the anchors** (order above). Quote, don't paraphrase, the RESUME block.
3. **Triage the threads** into 🟢 Active · 🟡 Deferred · 📌 Pinned/Paused · ⚠️ Watch · 🔺 OPEN escalations. For each 🟢: `name — one-line state — next action`.
4. **Emit the resume brief** (tight): Where we are (1–2 lines) · ▶ Next action (single step) · Threads (triaged; parked/dead collapsed to a count) · Escalations (count + one-liners, or "none") · Device/sync (last backup · N uncommitted · syncthing?).
5. **Then stop and ask** whether to start the next action. Do **not** auto-execute it.

## Pitfalls
- **Read-only.** Never edits Active Threads, the build log, or memory. (Updating those at the *end* of work is a separate discipline.)
- **The RESUME callout wins.** If it's missing or contradicts the build log's last entry → don't guess: say so, show both, and `escalate-to-architect` (or hand to the user).
- **Don't re-derive** what's already written — surface the anchors, don't reconstruct from code/git.
- **Hermes-lite (offline):** Hermes presents anchors + triage + device/sync line verbatim. It must **not** attempt a judgment/multi-step next action — that's Claude's; leave it for the user or escalate.

## Verification
- The brief names a single ▶ Next action taken from the RESUME callout (not invented).
- The device/sync line is present (last backup · uncommitted count · syncthing state) so drift is visible at a glance.

## Cadence
Start of every session and every device switch.
