# janitor — notes

Design background. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why "manager, not worker"
The author wanted a weekly "janitor" that points at what needs filling/doing but doesn't do the work — the skills do. Generalized: one read-only detector that both the morning check and the weekly review consume, so drift is visible without any skill silently editing the vault. Keeps the trust ladder intact — detection is always safe; fixing stays earned, per-skill.

## Design calls
- **Read-only, always.** A janitor that edits could cascade damage. It only emits a routed punch-list.
- **Graph-first respected.** Bare `[[Concept]]` links to not-yet-created notes are INTENTIONAL (concept nodes in a graph-first vault). So only path-style `[[folder/Note]]` breaks are flagged; otherwise the scan drowns in hundreds of false positives.
- **Expected-skills manifest** (`~/.config/myos/expected_skills.txt`): born from a real event — the `process-inbox` skill directory was deleted mid-session (a cat walked across the keyboard) and nothing noticed until a manual count. The manifest turns "a skill vanished" into a caught, routed finding. `--bless` accepts intentional set changes.
- **Invalid-YAML check.** A SKILL.md whose frontmatter fails to parse doesn't error: Hermes falls back to a naive line parser, `platforms: [linux]` becomes the *string* `"[linux]"`, the platform check fails, and the skill silently disappears from `hermes skills list`. One stray `: ` inside a value is enough. The janitor parses every frontmatter with PyYAML.
- **Feature contracts.** The author deletes how-to callouts after using a feature once or twice and restyles templates constantly — so feature knowledge must not live only in the note. Each template↔code coupling gets a contract (`contracts.json`); a broken one is CRITICAL and auto-escalates. The note is a disposable convenience copy; the contract keeps the knowledge alive and lets the user restyle anything without fear.
- **Rogue folders.** The small model once invented a second `Vault/Inbox` and wrote captures there, silently splitting data. Every operational folder must exist at exactly one canonical path; a same-named duplicate anywhere else is CRITICAL.
- **Memory index size.** Claude's `MEMORY.md` index is loaded whole every session and truncates past ~24 KB with no error — memories past the cut just vanish. The janitor warns at 15 KB and goes CRITICAL at 17 KB, while there's still room to act, and flags when entries fatten past ~400 bytes (detail belongs in the topic file, not the index).
- **Scope excludes** the sandbox, the raw inbox, the skills tree, Claude's memory folder, templates, tag/image stubs, `_Archive`, and anything listed under `janitor_skip` in `paths.json` (e.g. a folder shared with a friend that has its own versioning).

## Engine
`engines/myos_janitor_scan.py` — deterministic, stdlib + `myos_paths` + the template engine (`myos_apply_template` for the template-health check), PyYAML optional. Hermes-runnable, offline. `--brief` for the morning hub, full list for the weekly review.
