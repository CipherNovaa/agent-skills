#!/usr/bin/env bash
# myOS :: Claude memory reconciler (self-healing, structural — NOT content sync)
#
# Canonical brain lives in the vault:  Vault/CLAUDE/<Category>/<name>.md
# Claude's flat memory dir holds symlinks pointing at those real files.
#
# This heals the STRUCTURE in both directions (one real copy of content, always):
#   1. Any REAL file that appears in the flat memory dir (e.g. Claude wrote a new
#      memory the normal way) -> moved into the right vault category + symlinked back.
#   2. Any vault memory file missing its flat symlink -> symlink (re)created
#      (covers memories that arrived via Syncthing from another device).
#   3. Broken symlinks in the flat dir -> pruned.
#
# Safe to run anytime; idempotent. Wire to a systemd-user timer or a morning report.
# Paths come from myos_paths.py (claude_memory_dir + the claude_memory vault dir).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${MYOS_PYTHON:-python3}"
MEM="${MYOS_CLAUDE_MEMORY_DIR:-$("$PY" "$HERE/myos_paths.py" memory)}"
VAULT_CLAUDE="$("$PY" "$HERE/myos_paths.py" get claude_memory)"
if [[ -z "$MEM" ]]; then
  echo "claude_memory_dir is not configured (paths.json or MYOS_CLAUDE_MEMORY_DIR) — nothing to do" >&2
  exit 0
fi
mkdir -p "$MEM"

mkdir -p "$VAULT_CLAUDE/User" "$VAULT_CLAUDE/Feedback" "$VAULT_CLAUDE/Projects" "$VAULT_CLAUDE/Reference" "$VAULT_CLAUDE/Skills"

category_for() {
  case "$1" in
    MEMORY.md)   echo "." ;;
    user_*)      echo "User" ;;
    feedback_*)  echo "Feedback" ;;
    project_*)   echo "Projects" ;;
    reference_*) echo "Reference" ;;
    *)           echo "" ;;   # unknown -> leave alone, report
  esac
}

healed=0

# 1 + uncategorized report: real files sitting in the flat dir
shopt -s nullglob
for f in "$MEM"/*.md; do
  [[ -L "$f" ]] && continue            # already a symlink, fine
  base="$(basename "$f")"
  cat="$(category_for "$base")"
  if [[ -z "$cat" ]]; then
    echo "WARN uncategorized memory (left in place): $base" >&2
    continue
  fi
  if [[ "$cat" == "." ]]; then dest="$VAULT_CLAUDE/$base"; else dest="$VAULT_CLAUDE/$cat/$base"; fi
  if [[ -e "$dest" ]]; then
    echo "WARN both real flat file AND vault file exist for $base — NOT overwriting; resolve by hand" >&2
    continue
  fi
  mv "$f" "$dest"; ln -s "$dest" "$f"
  echo "filed new memory: $base -> ${dest#$VAULT_CLAUDE/}"; healed=$((healed+1))
done

# 2: vault MEMORY files missing their flat symlink.
# Only true memories get linked into Claude's recall dir — NOT the index/contract/
# skills docs. A true memory = MEMORY.md or a categorized prefix file living under
# User/ Feedback/ Projects/ Reference/.
while IFS= read -r -d '' vf; do
  base="$(basename "$vf")"
  cat="$(category_for "$base")"
  [[ -z "$cat" ]] && continue            # README.md, Memory Index.md, etc -> never linked
  link="$MEM/$base"
  if [[ ! -e "$link" && ! -L "$link" ]]; then
    ln -s "$vf" "$link"; echo "relinked from vault: $base"; healed=$((healed+1))
  fi
done < <(find "$VAULT_CLAUDE/User" "$VAULT_CLAUDE/Feedback" "$VAULT_CLAUDE/Projects" "$VAULT_CLAUDE/Reference" "$VAULT_CLAUDE/MEMORY.md" -maxdepth 1 -name '*.md' -type f -print0 2>/dev/null)

# 3: prune broken symlinks
for l in "$MEM"/*.md; do
  if [[ -L "$l" && ! -e "$l" ]]; then
    rm "$l"; echo "pruned broken link: $(basename "$l")"; healed=$((healed+1))
  fi
done

echo "memory reconciler: $healed change(s)"
