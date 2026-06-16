#!/usr/bin/env bash
set -euo pipefail

prompt_file="${1:?usage: ai-worker-cursor.sh <prompt-file>}"

if [[ ! -f "$prompt_file" ]]; then
  echo "Prompt file not found: $prompt_file" >&2
  exit 2
fi

CURSOR_AGENT_MODEL="${CURSOR_AGENT_MODEL:-auto}"
CURSOR_AGENT_SANDBOX="${CURSOR_AGENT_SANDBOX:-enabled}"

if ! command -v cursor-agent >/dev/null 2>&1 && [ -x "${HOME}/.local/bin/cursor-agent" ]; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if command -v cursor-agent >/dev/null 2>&1; then
  CURSOR_AGENT_CMD=(cursor-agent)
elif command -v cursor >/dev/null 2>&1; then
  CURSOR_AGENT_CMD=(cursor agent)
elif [ -x "${HOME}/.local/bin/cursor" ]; then
  CURSOR_AGENT_CMD=("${HOME}/.local/bin/cursor" agent)
else
  echo "Neither cursor-agent nor cursor was found on PATH." >&2
  exit 2
fi

./scripts/ai-dangerous-command-check.sh "${CURSOR_AGENT_CMD[*]} --model ${CURSOR_AGENT_MODEL} < prompt-file"

"${CURSOR_AGENT_CMD[@]}" \
  --print \
  --force \
  --trust \
  --sandbox "$CURSOR_AGENT_SANDBOX" \
  --model "$CURSOR_AGENT_MODEL" < "$prompt_file"
