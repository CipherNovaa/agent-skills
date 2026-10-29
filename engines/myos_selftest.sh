#!/usr/bin/env bash
# myOS capability self-test — LIVE checks, not a status guess.
# Each line: ✅/❌ <capability>. Designed for `hermes cron --no-agent --script`
# (stdout delivered verbatim) or on-demand. Exits 0 so the report always sends;
# the ❌ lines are the signal.
#
# Every check actually EXERCISES the thing (writes and removes a file, asks the
# model server, parses the skills) instead of reading a status flag — "no lying
# 'all fine'". Add a line here whenever a new subsystem ships; the original grew
# a check for every bug that once failed silently (an expired calendar token, a
# missing Python dependency in the agent's venv, a vision model that wasn't pulled).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${MYOS_PYTHON:-python3}"
PATHS="$HERE/myos_paths.py"
MEM="$("$PY" "$PATHS" memory 2>/dev/null)"
HERMES="${HERMES_BIN:-$(command -v hermes)}"
ok(){ echo "✅ $1"; }
bad(){ echo "❌ $1"; FAILED=1; }
FAILED=0
echo "🩺 myOS self-test — $(date '+%Y-%m-%d %H:%M')"

# 1. Spine resolves + inbox dir exists
INBOX="$("$PY" "$PATHS" get inbox 2>/dev/null)"
if [ -n "$INBOX" ] && [ -d "$INBOX" ]; then ok "spine + inbox dir ($INBOX)"; else bad "spine/inbox unresolved"; fi

# 2. Inbox is writable (write + remove a temp note)
if [ -d "$INBOX" ]; then
  T="$INBOX/.selftest_$$.md"
  if echo "selftest" > "$T" 2>/dev/null && rm -f "$T" 2>/dev/null; then ok "inbox writable (capture works)"; else bad "inbox NOT writable"; fi
fi

# 3. Template engine renders every template (no literal <% left behind)
if "$PY" "$HERE/myos_apply_template.py" --selftest >/dev/null 2>&1; then ok "template engine renders all templates"
else bad "template engine: a template uses an unsupported expression (myos_apply_template.py --selftest)"; fi

# 4. Claude memory symlinks intact (no broken links)
if [ -n "$MEM" ] && [ -d "$MEM" ]; then
  BROKEN=$(find "$MEM" -maxdepth 1 -name '*.md' -type l ! -exec test -e {} \; -print 2>/dev/null | wc -l)
  if [ "$BROKEN" -eq 0 ]; then ok "memory links intact ($(ls "$MEM"/*.md 2>/dev/null | wc -l) memories)"; else bad "$BROKEN broken memory link(s) — run myos_claude_memory_sync.sh"; fi
fi

# 5. Hermes skills discoverable (the myos category)
if [ -n "$HERMES" ]; then
  SK=$("$HERMES" skills list 2>/dev/null | grep -c '│ myos ')
  if [ "$SK" -ge 1 ]; then ok "Hermes skills loaded ($SK myos skills)"; else bad "myOS skills not discovered by Hermes"; fi
else bad "hermes CLI not found (set HERMES_BIN)"; fi

# 6. Local LLM (ollama) responding
if ollama list >/dev/null 2>&1; then ok "ollama up ($(ollama list 2>/dev/null | tail -n +2 | wc -l) models)"; else bad "ollama not responding"; fi

# 7. Embedding model present (semantic recall; recall still answers lexically without it)
EMB="${MYOS_EMBED_MODEL:-all-minilm}"
if ollama list 2>/dev/null | grep -qi "^$EMB"; then ok "embedding model present ($EMB)"; else bad "no $EMB embedding model — recall falls back to lexical"; fi

# 8. Gateway running
if systemctl --user is-active --quiet hermes-gateway.service; then ok "gateway active"; else bad "gateway not active"; fi

[ "$FAILED" -eq 0 ] && echo "— all systems go —" || echo "— ⚠️ attention needed above —"
exit 0
