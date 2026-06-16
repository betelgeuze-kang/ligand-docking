#!/usr/bin/env bash
set -euo pipefail

prompt_file="${1:?usage: ai-worker-opencode.sh <prompt-file>}"

if [[ ! -f "$prompt_file" ]]; then
  echo "Prompt file not found: $prompt_file" >&2
  exit 2
fi

OPENCODE_MODEL="${OPENCODE_MODEL:-opencode-go/minimax-m3}"

if ! command -v opencode >/dev/null 2>&1; then
  if [ -x "${HOME}/.local/bin/opencode" ]; then
    export PATH="${HOME}/.local/bin:${PATH}"
  elif command -v npm >/dev/null 2>&1; then
    npm_prefix="$(npm prefix -g 2>/dev/null || true)"
    if [ -n "$npm_prefix" ] && [ -x "${npm_prefix}/bin/opencode" ]; then
      export PATH="${npm_prefix}/bin:${PATH}"
    fi
  fi
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode CLI was not found on PATH. Install with: npm install -g opencode-ai" >&2
  exit 2
fi

./scripts/ai-dangerous-command-check.sh "opencode run --model ${OPENCODE_MODEL} --dir . --file <prompt-file>"

opencode run \
  --model "$OPENCODE_MODEL" \
  --dir . \
  --file "$prompt_file" \
  --title "codex-goal-worker" \
  "Read the attached prompt file and execute its instructions. Do not echo the full prompt body. Explore locally, implement, run focused checks when safe, and return at most 80 lines with changed files, check status, failed test names, key diff summary, and blockers. Do not print full logs or full diffs."
