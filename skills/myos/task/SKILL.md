---
name: task
description: Turn "remind me to / I need to / add a task" into a real backlog task (deterministic, dashboard-ready). Use for a new to-do, or the //task command.
platforms: [linux]
runner: hermes
status: draft
confidence: 0.5
source: taught
version: 1.0.0
escalate_when: the task text is unclear, the input is several tasks at once, or a date is ambiguous — split/confirm rather than guess
---

# task

Turns "remind me to email the registrar about enrolment by Friday" into a real, correctly-formatted line on the task board (`<tasks>/Backlog.md`) via `myos_task.py`. The tool owns the Obsidian-Tasks emoji syntax (priority + dates), so the task carries over until checked and shows on any Tasks/Dataview dashboard. The deterministic add path for the backlog — the model classifies, the tool writes.

## When to Use
- "Add a task / to-do", "remind me to…", "I need to…".
- The `//task <text + when + how-important>` command.

## Procedure
1. Pull the **task text** (imperative, terse), and if present the **priority** and a **date**.
   - Priority words → flag: *must / critical / important* → `--priority must`; *should* → `should`; *could / maybe / bonus* → `could`; *today's highlight / #1* → `highlight`. If unstated, omit (normal).
   - A deadline → `--due <when>`; "start / work on it on X" → `--scheduled <when>`. Pass the user's words — `YYYY-MM-DD`, `today`, `tomorrow`, `+Nd`, a weekday, `the 21st`, `July 21` — the tool resolves them through `myos_dates` (never compute ISO dates yourself).
   - An area if obvious → `--area math|programming|systems|life` (default unsorted).
2. If the input bundles **several tasks**, add each with its own call. If the text is vague ("do the thing") or a date is ambiguous ("sometime soon") → **stop and confirm** (don't guess a date).
3. Add it:
   ```
   python $MYOS_ENGINES/myos_task.py add "<text>" [--priority …] [--due <when>] [--scheduled <when>] [--recurring "<rule>"] [--area …]
   ```
4. Relay the tool's `✅ added → …` line verbatim (it shows the formatted card).

## Pitfalls
- **One task per call** — split a bundled input; don't cram several into one line.
- **Never guess a date** — ambiguous when → ask, or add it undated (still carries over).
- Don't hand-edit the backlog markdown — let `myos_task.py` own the emoji syntax.
- Marking done: `myos_task.py done "<match>"` (checks the first matching open task + stamps ✅) — but only when the user says it's done.

## Verification
- The tool printed `✅ added → <lane>: - [ ] …` with the correct priority emoji + `📅`/`⏳` date, and `myos_task.py list` shows it.

## Cadence
On demand. Triggers: an "add a task / remind me" request, or `//task`.
