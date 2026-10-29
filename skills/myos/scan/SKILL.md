---
name: scan
description: Classify an image the user sends (handwritten notes / printed document / homework / a screenshot / a meme), confirm the read, then route it to the right place. Use for any photo/image, or the //scan command.
platforms: [linux]
runner: hermes
status: published
confidence: 0.7
source: taught
version: 1.0.0
escalate_when: you can't read the image confidently, or it fits two types equally — ask the user which it is, don't guess and misfile
---

# scan

The single front door for an image. **Classify → confirm → route.** One image in, the
right destination out — no wandering, no misfiling. Mirrors the bare-image behaviour in
the agent's persona (when the user just drops a photo with no words), and is the `//scan` command.

## Procedure
1. **Read the image** (vision model) and classify it into ONE of:
   - **handwritten notes / printed document / homework / curriculum** → a clean note in the
     **one** Inbox (below).
   - **a type with its own pipeline** (a receipt, a book cover, …) → that pipeline's tool,
     if one is installed. If none is, treat it as a document.
   - **a GIF / meme / reaction** → it's a vibe, not a task. React in kind; don't file it.
2. **State your read and the action, and wait for a quick confirm** ("Looks like lecture
   notes on recursion — transcribe to the Inbox? [y]"). Only act after the user confirms.
   If you can't read it, or two types fit → **ask**, don't guess.
3. **Route** on confirm:
   - notes/doc/homework → OCR/transcribe it, lightly clean errors but **keep the user's wording**,
     then write to the inbox with `write_file`: `<inbox>/<title>.md` where
     `<inbox>` = `python $MYOS_ENGINES/myos_paths.py get inbox`.
4. **Verify** the artifact exists and **report the real path.** Never say "filed" without it.

## Pitfalls
- **Exactly ONE inbox.** ALWAYS resolve it with `python $MYOS_ENGINES/myos_paths.py get inbox` —
  never hardcode, never invent `Vault/Inbox` or any other `Inbox`. Writing a second inbox is the
  exact bug this exists to prevent (and the janitor flags it as CRITICAL).
- **No Dataview / Templater in a filed note** — knowledge notes must read fine as plain
  markdown (a small model writing query blocks it doesn't understand = an unreadable note).
- **Don't rewrite or "improve"** the user's notes — transcribe + clean OCR only, preserve voice.
- **Confirm first.** A wrong guess that acts is worse than a one-line "is this X?".

## Verification
- A new `<inbox>/<title>.md` exists (plain markdown, no Dataview), and the reply quotes its real path.
- A routed type: the downstream tool's own ✅ line, relayed verbatim.

## Cadence
On demand — any image the user sends, or `//scan`.
