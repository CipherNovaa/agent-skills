#!/usr/bin/env python3
"""
architect_powers.py — "powers" ported from the cloud architect to the local Hermes system.

Abilities the cloud architect has that are genuinely useful for study, implemented
fully locally (a local model via Ollama, no cloud):

  * recall(question)   — grounded QA over the user's OWN Obsidian vault. Keyword-
                         scores every note, feeds the top matches to the LLM,
                         and answers WITH [[citations]] to the notes it used.
                         "Ask your own brain." (the architect's signature: reason over
                         a corpus + cite sources.)
  * quiz(content, n)   — turn note content into active-recall questions with
                         hidden (spoiler) answers. A study accelerator.
  * summarize(content) — condense a note to a TL;DR + key points.

All three return Obsidian-flavoured markdown and never raise — on any failure
they return a short italic error note so the watcher keeps processing.

CLI:
    architect_powers.py recall "what did I decide about the backup schedule"
    architect_powers.py quiz   "<note text>"
    architect_powers.py tldr   "<note text>"
"""
from __future__ import annotations

import re
import sys
import time
import math
import os
import requests
from pathlib import Path

# Single source of truth for vault structure — no hardcoded folder names.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import myos_paths as mp

VAULT      = mp.vault_root()
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/generate"
MODEL      = os.getenv("MYOS_LLM_MODEL", "qwen3:8b")

# Folders that hold real knowledge (skip tag stubs, templates, raw scans and
# Obsidian internals). Built from myos_paths so a vault re-fold can't silently
# break recall — this list once pointed at folders that no longer existed.
# architect_memory (ARCHITECT/) and inventory are included so recall can answer from
# The architect's own memory (a past root cause, a setup decision) and from the
# inventory notes (what hardware the user owns). Override with "recall_dirs".
SEARCH_DIRS = [mp.config()["dirs"][k] for k in
               mp.config().get("recall_dirs",
                               ("myos", "academics", "systems", "source_material",
                                "projects", "inbox", "journal", "architect_memory", "inventory"))
               if k in mp.config()["dirs"]]
# Real knowledge notes are small; anything huge is a session log / transcript
# dump (e.g. the "agent prompt" files) and would pollute recall. Skip them.
MAX_NOTE_BYTES = 40_000
_STOP = {
    "the","a","an","and","or","but","of","to","in","on","for","is","are","was",
    "were","be","with","as","at","by","it","this","that","these","those","my",
    "me","i","do","did","does","what","whats","how","why","when","where","which",
    "about","into","from","you","your","can","could","would","should","note",
    "notes","write","wrote","tell","show","find","did","have","has",
}


def _llm(prompt: str, temperature: float = 0.2, timeout: int = 180) -> str:
    # Retry once on an empty/blank response. When several // commands fire on one
    # note (learn + quiz + summarize all hit Ollama back-to-back), a call can come
    # back empty under load/model-swap — which surfaced as "_(couldn't summarize)_"
    # even though the same prompt works fine moments later.
    for attempt in range(2):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "stream": False,
                      "options": {"temperature": temperature, "think": False},
                      "prompt": prompt},
                timeout=timeout,
            )
            out = r.json().get("response", "").strip()
            out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()
            out = out.replace("<!-- sn:end -->", "")
            if out:
                return out
        except Exception:
            if attempt == 1:
                raise
        time.sleep(1.5)
    return ""


# ── recall: grounded QA over the vault ───────────────────────────────────────

def _iter_notes():
    """Yield (title, relpath, text) for real content notes."""
    for d in SEARCH_DIRS:
        base = VAULT / d
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            try:
                if p.stat().st_size > MAX_NOTE_BYTES:
                    continue                       # session-log / transcript dump
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            if len(txt.strip()) < 20:
                continue
            yield p.stem, str(p.relative_to(VAULT)), txt


def _keywords(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+]+", q.lower())
            if len(w) > 2 and w not in _STOP]


def _excerpt(text: str, kws: list[str], width: int = 500) -> str:
    """Snippet centred on the first keyword in `kws` that occurs. Pass `kws`
    ordered most-important-first (rarest first) so the snippet lands on the
    distinctive term, not whatever common word appears earliest."""
    low = text.lower()
    pos = -1
    for k in kws:
        p = low.find(k)
        if p >= 0:
            pos = p
            break
    if pos < 0:
        return text[:width].strip()
    start = max(0, pos - width // 3)
    return text[start:start + width].strip()


def _lexical_rank(kws: list[str]) -> tuple[list[tuple], dict, int]:
    """Pure TF-IDF-ish lexical ranking over the vault.

    Returns (scored, idf, n_docs): `scored` is [(score, title, txt), …] sorted
    best-first; `idf` weights each keyword by rarity; `n_docs` is corpus size.
    A common word can't drown out a rare one (rarity IDF), term frequency is
    sublinear (1+log tf), and title hits get a 3x boost.
    """
    notes = list(_iter_notes())
    n_docs = len(notes) or 1
    df = {kw: 0 for kw in kws}
    prepared = []
    for title, rel, txt in notes:
        low = txt.lower()
        title_low = title.lower()
        body = {kw: low.count(kw) for kw in kws}
        ttl = {kw: title_low.count(kw) for kw in kws}
        for kw in kws:
            if body[kw] or ttl[kw]:
                df[kw] += 1
        prepared.append((title, txt, body, ttl))

    # Rarity weight: rare keyword → high idf; ubiquitous keyword ("system",
    # "use") → ~0 so it can't drown out the distinctive term. Tiny floor keeps
    # all-common-word queries from collapsing to a zero score.
    idf = {kw: max(math.log((n_docs + 1) / (1 + df[kw])), 0.05) for kw in kws}

    scored = []
    for title, txt, body, ttl in prepared:
        score = 0.0
        for kw in kws:
            tf = body[kw]
            tw = ttl[kw]
            if tf or tw:
                tf_term = (1.0 + math.log(tf)) if tf else 0.0
                score += (tf_term + 3.0 * tw) * idf[kw]
        if score > 0:
            scored.append((score, title, txt))
    scored.sort(key=lambda x: -x[0])
    return scored, idf, n_docs


def _select_notes(question: str, scored: list[tuple], k: int) -> tuple[list[tuple], str]:
    """Pick the top-k (title, txt) notes to feed the LLM.

    Prefers the semantic+lexical HYBRID ranker (mined from Odysseus,
    `myos_semrecall`) — it catches notes that lexical misses on synonyms
    ("typeface" → the Kitty font note). Falls back to pure lexical when the
    embedding model / index / numpy is unavailable, so recall never breaks.
    Returns (top, mode) where mode is "hybrid" or "lexical".
    """
    try:
        import myos_semrecall as sr
        res = sr.rank(question, k=k, mode="hybrid")   # [(score, title, txt), …]
        if res and res[0][0] > 0:
            return [(t, txt) for _, t, txt in res], "hybrid"
    except Exception as e:                            # numpy/Ollama/index missing
        print(f"[recall] semantic unavailable → lexical fallback: {e}",
              file=sys.stderr)
    return [(t, txt) for _, t, txt in scored[:k]], "lexical"


def recall(question: str, k: int = 4) -> str:
    """Answer `question` from the user's own vault, grounded with [[citations]].

    Note selection is a semantic+lexical HYBRID (see `_select_notes`) so synonym
    queries land on the right note; a pure-lexical fallback keeps it working
    offline. The lexical pass still runs to supply rarity weights (for centring
    excerpts on the most distinctive term) and the fallback ranking.
    """
    kws = _keywords(question)
    if not kws:
        return "_(ask a more specific question to search your notes)_"

    scored, idf, n_docs = _lexical_rank(kws)
    top, mode = _select_notes(question, scored, k)
    if not top:
        return (f"_I searched your vault but found nothing about "
                f"**{question}**._")

    # Excerpts should centre on the rarest (most distinctive) matched keyword.
    kws = sorted(kws, key=lambda kw: -idf[kw])

    ctx_parts = []
    for title, txt in top:
        ctx_parts.append(f"### [[{title}]]\n{_excerpt(txt, kws, 600)}")
    context = "\n\n".join(ctx_parts)

    prompt = (
        "You are Hermes, the user's personal assistant. Answer their question USING "
        "ONLY the excerpts from their own notes below. Be concise and direct. "
        "Cite the note(s) you used inline as [[Note Title]]. If the notes don't "
        "actually answer it, say so plainly — do NOT invent facts.\n\n"
        f"Their notes:\n{context}\n\n"
        f"Question: {question}\n\nAnswer (markdown, with [[citations]]):"
    )
    try:
        ans = _llm(prompt) or "_(no answer)_"
    except Exception as e:                        # pragma: no cover — defensive
        return f"_(recall failed: {e})_"
    sources = " · ".join(f"[[{t}]]" for t, _x in top)
    return (f"{ans}\n\n> _Searched {n_docs} notes ({mode}) · "
            f"sources: {sources}_")


# ── quiz: active-recall questions from content ───────────────────────────────

def quiz(content: str, n: int = 5) -> str:
    """Generate active-recall questions with hidden (spoiler) answers."""
    content = (content or "").strip()
    if len(content) < 40:
        return "_(not enough note content to build a quiz)_"
    prompt = (
        f"You are a study coach. From the user's note below, write {n} active-recall "
        "questions that test real understanding (not trivia). For EACH item use "
        "EXACTLY this format so Obsidian hides the answer until clicked (write "
        "the real question and real answer text — do not output any angle "
        "brackets or placeholders):\n\n"
        "**Q1.** What is ...?\n"
        "> [!answer]- Answer\n"
        "> The answer is ...\n\n"
        "Base every question and answer ONLY on the note's content. No preamble, "
        "no closing remarks — output only the questions.\n\n"
        f"Note:\n{content[:3000]}"
    )
    try:
        out = _llm(prompt, temperature=0.4) or "_(couldn't build a quiz)_"
    except Exception as e:                        # pragma: no cover — defensive
        return f"_(quiz failed: {e})_"
    # Defensive: strip any leaked <question>/<answer> placeholder tokens.
    out = re.sub(r"<\/?(?:question|answer)>\s*", "", out, flags=re.IGNORECASE)
    return out.strip()


# ── summarize: TL;DR + key points ────────────────────────────────────────────

def summarize(content: str) -> str:
    content = (content or "").strip()
    if len(content) < 40:
        return "_(not enough note content to summarize)_"
    prompt = (
        "Summarize the user's note below. Output a one-sentence **TL;DR:** line, then "
        "3-6 bullet points of the key information. Use only what's in the note; "
        "do not add commentary or invent anything. No preamble.\n\n"
        f"Note:\n{content[:4000]}"
    )
    try:
        return _llm(prompt) or "_(couldn't summarize)_"
    except Exception as e:                        # pragma: no cover — defensive
        return f"_(summarize failed: {e})_"


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, arg = argv[0], argv[1]
    if cmd == "recall":
        print(recall(arg))
    elif cmd == "quiz":
        print(quiz(arg))
    elif cmd in ("tldr", "summarize"):
        print(summarize(arg))
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
