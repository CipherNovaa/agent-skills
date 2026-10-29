#!/usr/bin/env python3
"""
myos_semrecall.py — semantic retrieval over the vault (idea mined from Odysseus).

Odysseus does semantic memory via an Ollama embeddings API + a vector store.
This is the myOS-faithful adaptation: embeddings from the LOCAL Ollama, vectors
cached in a small local .npz index — no ChromaDB, no Docker. Offline, portable,
Hermes-runnable. Reuses claude_powers' note-iteration + lexical scoring so the
two rankers stay consistent, and offers a HYBRID (semantic + lexical) rank that
fixes what pure-lexical missed (synonyms like "typeface" -> "font"/"Iosevka").

CLI:
    myos_semrecall.py index                 # (re)build the embedding cache
    myos_semrecall.py "<query>"             # hybrid ranking (default)
    myos_semrecall.py --mode sem  "<query>" # semantic only
    myos_semrecall.py --mode lex  "<query>" # lexical only (baseline)
"""
from __future__ import annotations

import os
import sys
import json
import math
import time
import hashlib
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_powers as cp   # reuse VAULT, _iter_notes, _keywords, _excerpt

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/embeddings"
EMBED_MODEL = os.getenv("MYOS_EMBED_MODEL", "all-minilm")
CACHE_DIR = Path(os.path.expanduser(os.getenv("MYOS_CACHE_DIR", "~/.cache/myos")))
CACHE = CACHE_DIR / "recall_vectors.npz"
MANIFEST = CACHE_DIR / "recall_manifest.json"
MAX_CHARS = 1200   # embed title + head of each note (all-minilm ctx is small)


def _embed(text: str) -> np.ndarray | None:
    # all-minilm's model cap is ~512 tokens and dense markdown is token-heavy, so
    # a fixed char budget still overruns it (Ollama → HTTP 500). Shrink-and-retry
    # embeds as much of each note as actually fits.
    for budget in (MAX_CHARS, 700, 400, 200, 100):
        try:
            r = requests.post(OLLAMA_URL,
                              json={"model": EMBED_MODEL, "prompt": text[:budget]},
                              timeout=30)
            if r.status_code == 200:
                v = r.json().get("embedding")
                if v:
                    a = np.asarray(v, dtype=np.float32)
                    n = np.linalg.norm(a)
                    return a / n if n else a      # L2-normalise → cosine == dot
                return None
            if r.status_code == 500 and "context length" in r.text:
                continue                          # too long → shrink and retry
            return None
        except Exception as e:
            print(f"[embed] failed: {e}", file=sys.stderr)
            return None
    return None


def _note_key(title: str, txt: str) -> str:
    return hashlib.sha1((title + "\n" + txt[:MAX_CHARS]).encode()).hexdigest()


def build_index(verbose: bool = True) -> tuple[list[dict], np.ndarray]:
    """Embed every knowledge note; cache incrementally by content hash."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    old = {}
    if MANIFEST.exists() and CACHE.exists():
        try:
            man = json.loads(MANIFEST.read_text())
            vecs = np.load(CACHE)["v"]
            old = {m["key"]: (m, vecs[i]) for i, m in enumerate(man)}
        except Exception:
            old = {}

    meta, rows, reused, fresh = [], [], 0, 0
    for title, rel, txt in cp._iter_notes():
        key = _note_key(title, txt)
        if key in old:
            m, v = old[key]
            meta.append({"key": key, "title": title, "rel": rel})
            rows.append(v)
            reused += 1
            continue
        v = _embed(f"{title}\n\n{txt[:MAX_CHARS]}")
        if v is None:
            continue
        meta.append({"key": key, "title": title, "rel": rel})
        rows.append(v)
        fresh += 1
        if verbose and fresh % 10 == 0:
            print(f"  embedded {fresh}…", file=sys.stderr)

    mat = np.vstack(rows).astype(np.float32)
    np.savez_compressed(CACHE, v=mat)
    MANIFEST.write_text(json.dumps(meta))
    if verbose:
        print(f"index: {len(meta)} notes ({fresh} new, {reused} cached) → {CACHE}",
              file=sys.stderr)
    return meta, mat


def _load_index() -> tuple[list[dict], np.ndarray]:
    if not (MANIFEST.exists() and CACHE.exists()):
        return build_index()
    return json.loads(MANIFEST.read_text()), np.load(CACHE)["v"]


def _lex_scores(query: str, titles_texts: list[tuple[str, str]]) -> np.ndarray:
    """Reuse claude_powers' TF-IDF-ish idea, returned as a 0-1 normalised vector."""
    kws = cp._keywords(query)
    if not kws:
        return np.zeros(len(titles_texts), dtype=np.float32)
    n = len(titles_texts) or 1
    df = {k: 0 for k in kws}
    per = []
    for title, txt in titles_texts:
        low, tl = txt.lower(), title.lower()
        b = {k: low.count(k) for k in kws}
        t = {k: tl.count(k) for k in kws}
        for k in kws:
            if b[k] or t[k]:
                df[k] += 1
        per.append((b, t))
    idf = {k: max(math.log((n + 1) / (1 + df[k])), 0.05) for k in kws}
    out = np.zeros(len(titles_texts), dtype=np.float32)
    for i, (b, t) in enumerate(per):
        s = 0.0
        for k in kws:
            if b[k] or t[k]:
                # tf term (sublinear) + 3x title boost, mirroring claude_powers.
                # NB: the title term must be OUTSIDE the conditional — a previous
                # precedence slip made the boost apply only when b[k] was 0.
                tf = (1 + math.log(b[k])) if b[k] else 0.0
                s += (tf + 3.0 * t[k]) * idf[k]
        out[i] = s
    m = out.max()
    return out / m if m else out


def rank(query: str, k: int = 4, mode: str = "hybrid"):
    meta, mat = _load_index()
    # need note text for lexical + excerpts; pull fresh (cheap, small vault)
    text_by_rel = {rel: (title, txt) for title, rel, txt in cp._iter_notes()}
    titles_texts = [(m["title"], text_by_rel.get(m["rel"], (m["title"], ""))[1])
                    for m in meta]

    sem = np.zeros(len(meta), dtype=np.float32)
    if mode in ("sem", "hybrid"):
        q = _embed(query)
        if q is not None:
            sem = mat @ q                      # cosine (all normalised)
            sem = (sem - sem.min()) / ((sem.max() - sem.min()) or 1)

    lex = np.zeros(len(meta), dtype=np.float32)
    if mode in ("lex", "hybrid"):
        lex = _lex_scores(query, titles_texts)

    if mode == "sem":
        score = sem
    elif mode == "lex":
        score = lex
    else:
        score = 0.65 * sem + 0.35 * lex        # semantic-led hybrid

    order = np.argsort(-score)[:k]
    return [(float(score[i]), meta[i]["title"], titles_texts[i][1]) for i in order]


def _main(argv):
    mode = "hybrid"
    if argv and argv[0] == "index":
        build_index()
        return 0
    if len(argv) >= 2 and argv[0] == "--mode":
        mode = argv[1]
        argv = argv[2:]
    if not argv:
        print(__doc__)
        return 0
    q = " ".join(argv)
    for score, title, txt in rank(q, mode=mode):
        snip = cp._excerpt(txt, cp._keywords(q) or [""], 160).replace("\n", " ")
        print(f"[{score:.3f}] {title}\n    {snip}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
