# recall — notes

Design background for the `recall` skill. Not on the runtime path; read when working *on* the skill, not *with* it.

## Why
Retrieval — not storage — was the author's bottleneck: notes went in, but finding them again was slow. `recall` is the direct fix, and the one "win" Hermes can fully own offline. It uses the same engine as the tablet `//recall`, so phone ↔ desktop give the same answer.

## How the engine works
`engines/architect_powers.py` → `recall()`:
- **Hybrid ranking:** note selection is semantic + lexical. `myos_semrecall.rank()` embeds the query with a local Ollama embedding model (`all-minilm` by default), scores it against an incremental index of every note (cached by content hash in `~/.cache/myos/recall_vectors.npz`), and blends cosine similarity 0.65 / lexical 0.35 — so synonym queries land ("typeface" finds the font-config note). **Lexical fallback:** if numpy/Ollama/index is unavailable it logs `semantic unavailable → lexical fallback`, tags the sources line `(lexical)`, and still answers — recall never breaks.
- **Lexical layer = TF-IDF:** per-keyword rarity weight `log((N+1)/(1+df))` floored at 0.05, sublinear tf `1+log(tf)`, 3× title boost; the excerpt centres on the rarest matched term. (An earlier raw-count ranking let a common word like "system" swamp the distinctive one.)
- **Embedding budget:** all-minilm caps at ~512 tokens and dense markdown overruns any fixed character budget, so `_embed()` shrinks and retries (1200 → 700 → 400 → 200 → 100 chars) on Ollama's context-length error instead of dropping the note.
- Feeds the top ~4 note excerpts to a local model, which answers using **only** those excerpts and cites `[[Note Title]]`. Honesty is enforced at this layer (the ranker always returns *something*, so the prompt must allow "your notes don't say").
- **Scope** (from the spine, re-fold-safe, override with `recall_dirs` in `paths.json`): `myos · academics · systems · source_material · projects · inbox · journal · architect_memory · inventory`. Skips templates, tags, raw scans, Obsidian internals, and any file > 40 KB (session logs and transcripts pollute results).

## Maintenance
- After adding notes to a scoped dir (or changing the scope), rebuild the embedding index: `python engines/myos_semrecall.py index` (incremental — only changed notes are re-embedded).

## Known gaps
- Terse inventory notes (a keyboard's note that never says "keyboard") can't be tied to possession queries by a small embedding model. Richer item notes fix it.
