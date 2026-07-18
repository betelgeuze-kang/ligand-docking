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
test -f docs/ai/prompts/internal_subagent_worker_slice.md && ok "internal subagent worker prompt template present" || bad "internal subagent worker prompt template missing"

echo
echo "[execution model]"
ok "Codex direct implementation is active"
ok "Kiro/Opus and Cursor-routed delegation are inactive by policy"

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
