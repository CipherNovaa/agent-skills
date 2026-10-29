---
name: capture-to-inbox
description: Append a timestamped thought to the capture inbox, verbatim. Use for a fast "get it out of my head" note, mirroring a desktop capture hotkey.
platforms: [linux]
runner: either
status: published
confidence: 0.85
source: taught
version: 1.0.0
escalate_when: input is multi-paragraph or needs filing into a specific note (use process-inbox / file-note)
---

# capture-to-inbox

Fast "get it out of my head" path. Mirrors a desktop capture hotkey.

## When to Use
- A quick single-line thought to stash without breaking flow.
- The hotkey-capture equivalent in chat.

## Procedure
1. Take the raw text as a single line. **Do not rewrite or improve it** — preserve the user's voice.
2. Resolve the inbox dir (don't hardcode): `python $MYOS_ENGINES/myos_paths.py get inbox`. Target file: `<inbox>/Quick Capture.md`.
3. With a file tool (`read_file`/`write_file`/`patch`, not `cat`), append one line: `- HH:MM — <text>` (24h local).
4. If the file is missing, create it with a `# Quick Capture` heading first.
5. Confirm: the timestamp + captured text. Nothing else.

## Pitfalls
- **Don't rewrite** the thought — verbatim only.
- **Don't trigger sync or export** — capture stays instant.
- Multi-paragraph or needs-filing → that's `process-inbox`/`file-note`, not this.

## Verification
- The new `- HH:MM — <text>` line is present at the tail of `<inbox>/Quick Capture.md`.

## Cadence
On demand — instant capture.
