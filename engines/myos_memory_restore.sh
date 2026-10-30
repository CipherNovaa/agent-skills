#!/usr/bin/env bash
# myOS :: UNDO the vault-canonical memory setup.
# Replaces each symlink in the architect's flat memory dir with the real file copied
# back from the vault, restoring the original pre-transfer state.
# (Vault/ARCHITECT copies are left in place; delete them by hand if you want them gone.)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${MYOS_PYTHON:-python3}"
MEM="${MYOS_ARCHITECT_MEMORY_DIR:-$("$PY" "$HERE/myos_paths.py" memory)}"
VAULT_ARCHITECT="$("$PY" "$HERE/myos_paths.py" get architect_memory)"
if [[ -z "$MEM" ]]; then
  echo "architect_memory_dir is not configured (paths.json or MYOS_ARCHITECT_MEMORY_DIR) — nothing to do" >&2
  exit 0
fi
mkdir -p "$MEM"

restored=0
for l in "$MEM"/*.md; do
  [[ -L "$l" ]] || continue
  target="$(readlink -f "$l")"
  [[ -e "$target" ]] || { echo "skip (dead link): $(basename "$l")"; continue; }
  rm "$l"; cp "$target" "$l"
  echo "restored real file: $(basename "$l")"; restored=$((restored+1))
done
echo "restored $restored file(s) to flat dir (vault copies untouched)"
