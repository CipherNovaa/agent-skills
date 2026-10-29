# interview-me — notes

Design background. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why
The author thinks by reacting, not from a blank page. A structured interview that hands over **options to react to** converts a fuzzy pile of ideas into an ordered, written plan — and writing each batch down means nothing evaporates (output over tuning). This skill built the author's own AI-and-skills plan over two passes; the Claude-tier method in SKILL.md is what actually worked there.

## Two tiers — Claude plans, Hermes captures
The split is the myOS routing rule. A small local model can't run an adaptive interview, so Hermes only *captures* (deterministic `idea_plan.py` seed) and escalates; the real back-and-forth is Claude's.

## Known limitation (logged)
`idea_plan.py` has **no myOS grounding** — for internal goals it can hallucinate external products (e.g. "sign up for myOS", web links). So the Hermes capture is a rough seed only; Claude corrects it on refine. Future fix: feed the planner some myOS context so the seed isn't misleading.
