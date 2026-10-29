---
name: weekly-review
description: Weekly reflection brief + inbox triage + drift report. Use for the weekly maintenance pass — surfaces wins, open loops, open escalations, and next week's one focus.
platforms: [linux]
runner: either
status: draft
confidence: 0.65
source: taught
version: 1.4.0
escalate_when: process-inbox flags many items, the janitor reports a CRITICAL finding, or a real planning decision is needed
---

# weekly-review

The weekly maintenance + reflection pass. Keeps entropy down and surfaces the week. Derived numbers come from tools; the user writes only the reflection prose.

## When to Use
- The weekly review (maintenance + reflection), usually at the end of the week.

## Procedure
1. Run the **process-inbox** skill (triage the week's captures).
2. Run the **janitor** full scan (`python $MYOS_ENGINES/myos_janitor_scan.py`) and keep its punch-list for the review.
3. Skim this week's dailies: `python $MYOS_ENGINES/myos_paths.py get journal` → the last 7 `YYYY-MM-DD.md` (`read_file`).
4. Find (or create) **this week's** review note, named by ISO week:
   `WK=$(date +%G-W%V)` (e.g. `2026-W27`), path `<journal>/$WK.md`.
   - If it **exists** → enrich it **in place** (don't create a second note).
   - If not → create it from the user's REAL template (engine-rendered, so no literal `<% %>`):
     `python $MYOS_ENGINES/myos_apply_template.py "Weekly Review" "$WK" --dir journal`
5. Pull the facts, don't invent them:
   - tasks done this week: `python $MYOS_ENGINES/myos_task.py list --all` (done lines carry a `✅ YYYY-MM-DD` stamp);
   - open escalations: the `Status: OPEN` entries in `<claude_memory>/Escalations.md`;
   - the janitor punch-list from step 2.
6. Fill the prose from the skim — **what actually moved / a win / biggest blocker**, a short
   **drift** section (the janitor items worth routing this week), and **next week — pick 3**
   (make #1 the single focus). Terse, in the user's voice, no padding.
7. Report the inbox result + the one focus.

## Pitfalls
- **Reflection, not perfectionism** — a 5-line review beats a polished one that never gets written.
- **One note per week** — reuse the `$WK` note; don't spawn a parallel "Weekly Review <date>".
- Use the template — a hand-built review note has no `type: review` frontmatter and drifts from the format the user reads.
- Numbers are DERIVED — paste them from the tools, don't retype or round them by hand.

## Verification
- `<journal>/<GGGG-[W]WW>.md` exists with `type: review` frontmatter, the facts + focus filled,
  no unrendered `<%`, and the inbox was triaged (process-inbox's tally balances).

## Cadence
Weekly.
