#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="${AI_VERIFY_MODE:-smoke}"

cd "$PROJECT_ROOT"

print_packet_summary() {
  local packet_path="$1"
  python3 - "$packet_path" <<'PY'
import json
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
summary = packet.get("summary", {})
status = summary.get("status", "unknown")
blockers = summary.get("blocked_checks") or summary.get("blocked_check_ids") or []
print(f"status={status}; blockers={','.join(str(item) for item in blockers) or 'none'}")
PY
}

run_packet_check() {
  local label="$1"
  local script="$2"
  local packet_path=".betelgeuze/ai_verify_${label}.json"
  mkdir -p .betelgeuze
  if python3 "$script" --out-json "$packet_path" --quiet; then
    printf '  OK   %s ' "$label"
    print_packet_summary "$packet_path"
    rm -f "$packet_path"
    return 0
  fi
  printf '  FAIL %s ' "$label"
  print_packet_summary "$packet_path"
  rm -f "$packet_path"
  return 1
}

echo "==> orchestration shell syntax"
bash -n \
  scripts/ai-dangerous-command-check.sh \
  scripts/ai-worker-cursor.sh \
  scripts/ai-worker-opencode.sh \
  scripts/ai-preflight.sh \
  scripts/ai-verify.sh

echo "==> json"
python3 -m json.tool opencode.json >/dev/null

echo "==> required orchestration files"
test -f AGENTS.md
test -f docs/ai/ORCHESTRATION.md
test -f docs/ai/tasks/TASK-TEMPLATE.md
test -f docs/ai/reviews/code_review.md
test -f docs/ai/prompts/codex_pursue_goal_start.md
test -f docs/ai/prompts/cursor_worker_slice.md
test -f docs/ai/prompts/opencode_worker_slice.md
test -x scripts/ai-worker-cursor.sh
test -x scripts/ai-worker-opencode.sh

echo "==> python syntax smoke"
python3 -m py_compile \
  scripts/verify_quality_gate.py \
  scripts/check_independent_product_readiness.py \
  scripts/verify_product_capability_matrix.py

if [[ "$MODE" == "product" || "$MODE" == "full" ]]; then
  echo "==> product quality smoke"
  run_packet_check "quality_gate" scripts/verify_quality_gate.py
  run_packet_check "independent_product_readiness" scripts/check_independent_product_readiness.py
  run_packet_check "product_capability_matrix" scripts/verify_product_capability_matrix.py
fi

if [[ "$MODE" == "full" ]]; then
  echo "==> full pytest"
  python3 -m pytest -q
fi

echo "verify ok (${MODE})"
