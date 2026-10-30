# resume — notes

Design background. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why
`resume` fixes the three ways a thread gets lost: **(a)** where work left off, **(b)** cross-device drift (laptop ↔ desktop), **(c)** too many threads (which are active vs parked vs dead). It turns "where was I?" into a 20-second answer instead of re-reading the whole vault.

It **orients only** — updating the anchors at the *end* of work is a separate discipline, deliberately kept out of this skill so `resume` stays safe and read-only.

## Split of labour
The architect plans, Hermes captures. Hermes can present the anchors + triage + device/sync line offline, but the *next action* on a 🟢 thread is often judgment/multi-step — that's the architect's call, so the skill stops and asks rather than auto-executing.

Because the architect's memory lives in the vault (see `myos_memory_sync.sh`), both agents read the same anchors: whichever one starts the session sees the same state.
