---
name: interview-me
description: Turn a fuzzy goal into a structured, living plan doc — by interview (the architect) or quick capture (Hermes). Use for a "help me plan / think this through" request or the //plan command. (Named to avoid a builtin `plan` skill.)
platforms: [linux]
runner: either
status: published
confidence: 0.85
source: taught
version: 1.0.0
escalate_when: a Hermes //plan capture needs real back-and-forth or judgment (ambiguous scope, competing options, multi-step design) — capture the goal, then escalate; don't fake an interview locally
---

# interview-me

Turns "I have a bunch of ideas but need structure" into a **living plan document**. Two tiers, split the myOS way — **The architect plans, Hermes captures**. Background/why + the proven interview method: [[NOTES]].

## When to Use
- A "help me plan / think this through / turn these ideas into a plan" request.
- The `//plan <goal>` command.

## Procedure
**Hermes tier — capture (offline, deterministic).** Hermes does *not* run an adaptive interview (a small model can't); it captures and hands off:
1. Run the planner: the `plan` tool (idea-planner plugin), or `python $MYOS_ENGINES/idea_plan.py "<goal>"`. Returns goal → milestones → steps.
2. Save as a stub plan note (frontmatter below, `status: drafting`), with an `## Open questions` list and a top note: *"captured by Hermes — needs the architect to interview & refine."*
3. `escalate-to-architect` with the goal + the stub's path. Done — don't attempt the real planning.

**The architect tier — the interview (the real value).** A structured interview that ends in a plan the user can react to:
1. **Ground first** — run `resume` / read the relevant memory so questions aren't naive.
2. **Interview in small batches** — 1–4 questions at a time, as **options the user reacts to** (reacting beats a blank page). Always allow "Other"/free text. **Recommend, don't survey** — recommended option first, say why.
3. **After every batch: write it down.** Lock decided items, flag open ones as `- [ ]`, update the doc, bump a version line in `## Log`.
4. **Make the user sequence** — if the answer is "all of them," the next question is "which first?"
5. **Surface constraints honestly** (feasibility, portability, what the tools actually do) as you go.
6. **Preserve their voice** — structure the ideas, don't rewrite them.
7. **Close the loop** when it stabilizes: reflect the next action into `Active Threads.md` and, if durable, a project memory + `MEMORY.md` line.

## Artifact format (the plan doc)
- **Location:** system/AI/cross-cutting → `<architect_memory>/Plan — <Topic>.md`; single-project → `projects` (`python $MYOS_ENGINES/myos_paths.py get projects`).
- **Frontmatter:** `title`, `type: plan`, `tags` (`architect` + topic), `updated: YYYY-MM-DD`, `status: drafting|active|paused`.
- **Body:** a `> [!abstract]` "what this is" + version/status line; **Decided** sections; **Open questions** as checkboxes; recommendation **tables** where there's a stack/choice; a dated **`## Log`** at the bottom (one `vX.Y` line per pass). Link related memories with `[[…]]`.

## Pitfalls
- **Plans are documents, not just chat** — if it wasn't written to the doc, it didn't happen.
- **Decisions are the user's** — the architect recommends, never delivers the verdict.
- This skill **writes plans/notes only** — never executes the plan's file-moves or system changes.
- Never block a question batch on a fact you can verify yourself — check the vault/code first.
- **The Hermes planner has no myOS context** → for *internal* goals it can treat myOS terms as external products. Treat the Hermes capture as a rough seed only; the architect corrects it on refine. (See [[NOTES]].)

## Verification
- A plan doc exists at the right location with valid frontmatter and a dated `## Log` entry for this pass.
- Decided items are locked; open ones are `- [ ]` checkboxes — nothing decided was left ambiguous.

## Cadence
On demand. Triggers: a `plan` / `interview-me` request, or `//plan <goal>`.
