#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

pass=0
warn=0
fail=0

ok() { echo "  OK   $*"; pass=$((pass + 1)); }
note() { echo "  WARN $*"; warn=$((warn + 1)); }
bad() { echo "  FAIL $*"; fail=$((fail + 1)); }

echo "=== Codex goal-mode orchestration preflight ==="

test -f AGENTS.md && ok "AGENTS.md present" || bad "AGENTS.md missing"
test -f docs/ai/ORCHESTRATION.md && ok "orchestration guide present" || bad "orchestration guide missing"
test -f docs/ai/prompts/codex_pursue_goal_start.md && ok "Codex start prompt present" || bad "Codex start prompt missing"
test -f docs/ai/prompts/kiro_design_slice.md && ok "Kiro design prompt template present" || bad "Kiro design prompt template missing"
test -f docs/ai/prompts/cursor_worker_slice.md && ok "Cursor worker prompt template present" || bad "Cursor worker prompt template missing"
test -f docs/ai/prompts/opencode_worker_slice.md && ok "OpenCode-named worker prompt template present" || bad "OpenCode-named worker prompt template missing"
test -f docs/ai/prompts/internal_subagent_worker_slice.md && ok "internal subagent worker prompt template present" || bad "internal subagent worker prompt template missing"
test -f opencode.json && ok "opencode.json present" || bad "opencode.json missing"

echo
echo "[worker tools]"
if command -v kiro >/dev/null 2>&1; then
  ok "Kiro design command available; Opus 4.8 required by wrapper"
else
  note "Kiro command not found; skip Kiro design planning until installed"
fi

if command -v cursor-agent >/dev/null 2>&1 || command -v cursor >/dev/null 2>&1 || [ -x "${HOME}/.local/bin/cursor" ]; then
  ok "Cursor worker command available; default model composer-2.5"
else
  note "Cursor worker command not found; skip Cursor delegation until installed"
fi

if command -v cursor-agent >/dev/null 2>&1 || command -v cursor >/dev/null 2>&1 || [ -x "${HOME}/.local/bin/cursor" ]; then
  ok "OpenCode-named wrapper routes to Cursor Composer 2.5"
else
  note "OpenCode-named wrapper needs Cursor; skip routed OpenCode assignments until Cursor is installed"
fi

echo
echo "[verify]"
if ./scripts/ai-verify.sh >/dev/null 2>&1; then
  ok "ai-verify.sh passed"
else
  bad "ai-verify.sh failed"
fi

echo
echo "=== Summary: ${pass} ok, ${warn} warn, ${fail} fail ==="
if [ "$fail" -gt 0 ]; then
  exit 1
fi
