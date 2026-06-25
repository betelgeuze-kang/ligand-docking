#!/usr/bin/env bash
set -euo pipefail

prompt_file="${1:?usage: ai-worker-opencode.sh <prompt-file>}"

if [[ ! -f "$prompt_file" ]]; then
  echo "Prompt file not found: $prompt_file" >&2
  exit 2
fi

OPENCODE_ROUTED_CURSOR_MODEL="${OPENCODE_ROUTED_CURSOR_MODEL:-composer-2.5}"

echo "OpenCode worker assignment is routed to Cursor model ${OPENCODE_ROUTED_CURSOR_MODEL}." >&2
./scripts/ai-dangerous-command-check.sh "CURSOR_AGENT_MODEL=${OPENCODE_ROUTED_CURSOR_MODEL} ./scripts/ai-worker-cursor.sh <prompt-file>"
CURSOR_AGENT_MODEL="$OPENCODE_ROUTED_CURSOR_MODEL" ./scripts/ai-worker-cursor.sh "$prompt_file"
