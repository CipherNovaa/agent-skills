---
name: learn-accelerator
description: "Explain a math problem, word problem, or programming concept in the user's own study style (answer-first, step-by-step, a memory trick, a worked example or gotcha). Use when the user asks to solve, explain, understand or learn a math or programming topic."
platforms: [linux]
runner: hermes
status: published
confidence: 0.8
source: taught
version: 1.0.0
escalate_when: the topic needs a multi-session curriculum or a judgment about what to study next — that is planning, not explaining; queue it with escalate-to-architect
---

# learn-accelerator

A personal "learning accelerator". It explains math problems, word problems and
programming concepts in **the user's** study style, and learns that style over
time. The same engine can sit behind a handwriting-tablet `//learn` command, so
desktop, chat and tablet give consistent answers.

## When to Use
Activate when the user wants to **understand or learn**, not just get a one-line
answer:

- A math problem or expression to solve or evaluate ("solve 4^2 + (15/3)*2 - 7").
- A word problem.
- "Explain / teach me / help me understand / how does X work" for a math or
  programming concept ("what's a pointer in C++", "why does multiplication come
  before addition").
- Anything that looks like studying, homework or concept review.

For a quick factual lookup with no teaching needed, answer directly; this skill
is for explanations that should *stick*.

## Procedure
1. Call the native **`learn`** tool (provided by the learn-accelerator plugin),
   passing the question verbatim as `topic`:
   ```
   learn(topic="<the user's question, verbatim>")
   ```
2. `web` is optional: `"auto"` (default) fact-checks concepts against the local
   SearXNG and skips bare arithmetic; pass `"off"` only for the fastest answer.
3. The tool runs fully local and synchronously and returns the finished
   explanation. It already loads the learning-style profile
   (`MYOS_LEARNING_STYLE`, default `~/.hermes/learning_style.md`) and samples two
   of the user's own well-structured math notes as few-shot examples.
4. **Reply with the tool output verbatim.** Do not summarize it, comment on it, or
   add your own explanation.

## Pitfalls
- If the tool returns an error (e.g. the local model is unreachable), say so
  plainly. Never write an explanation yourself instead — the point is the
  personalised, fact-checked engine, not the chat model's guess.
- When the user states a preference ("more worked examples", "skip the code",
  "shorter"), append one short bullet to the learning-style profile with a file
  tool. The engine reads it on every run, so the style grows with the user.

## Verification
- The reply is the tool's markdown, unchanged: answer first, a numbered
  step-by-step, a "🧠 Memory trick" line, and a worked example or gotcha.

## Cadence
On demand.
