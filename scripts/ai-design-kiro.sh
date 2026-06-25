#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: ai-design-kiro.sh [--dry-run] <prompt-file>" >&2
}

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=1
  shift
fi

prompt_file="${1:-}"
if [[ -z "$prompt_file" ]]; then
  usage
  exit 2
fi

expected_model="Opus 4.8"
if [[ -n "${KIRO_EXPECTED_MODEL:-}" && "${KIRO_EXPECTED_MODEL}" != "$expected_model" ]]; then
  echo "BLOCKED: Kiro model is fixed to ${expected_model}; do not substitute ${KIRO_EXPECTED_MODEL}." >&2
  exit 2
fi
model_marker="KIRO_MODEL_CONFIRMED: ${expected_model}"

if [[ ! -f "$prompt_file" ]]; then
  echo "Prompt file not found: $prompt_file" >&2
  exit 2
fi

mkdir -p .betelgeuze
kiro_prompt=".betelgeuze/kiro_design_last_prompt.md"
kiro_output=".betelgeuze/kiro_design_last_output.log"
kiro_status_file=".betelgeuze/kiro_design_last_status.txt"

write_status() {
  local status="$1"
  local reason="$2"
  {
    printf 'status=%s\n' "$status"
    printf 'reason=%s\n' "$reason"
    printf 'expected_model=%s\n' "$expected_model"
    printf 'expected_marker=%s\n' "$model_marker"
    printf 'prompt_file=%s\n' "$prompt_file"
    printf 'wrapped_prompt=%s\n' "$kiro_prompt"
    printf 'output_log=%s\n' "$kiro_output"
    printf 'stdout_contract=first_non_empty_line_must_match_expected_marker\n'
  } > "$kiro_status_file"
}

payload_lines() {
  awk 'NF && $0 !~ /^Reading from stdin via:/' "$kiro_output"
}

{
  cat <<EOF
Required model: Kiro ${expected_model}.

Before giving the design, verify the active Kiro model/session.

If the active Kiro model/session is not ${expected_model}, or if you cannot verify that it is ${expected_model}, stop immediately and report:
BLOCKED: Kiro ${expected_model} is not active.

If and only if the active Kiro model/session is ${expected_model}, your first non-empty stdout line must be exactly:
${model_marker}

You are in design-only mode. Do not edit files, run mutating commands, or decide completion.

EOF
  cat "$prompt_file"
} > "$kiro_prompt"

if [[ "$dry_run" -eq 1 ]]; then
  write_status "dry_run" "wrapped_prompt_prepared"
  echo "Kiro design wrapper dry run ok."
  echo "Prompt saved at: $kiro_prompt"
  echo "Status saved at: $kiro_status_file"
  exit 0
fi

if ! command -v kiro >/dev/null 2>&1; then
  write_status "blocked" "kiro_cli_not_found"
  echo "kiro CLI was not found on PATH. Skip Kiro design planning until installed." >&2
  exit 2
fi

if ! kiro chat --help >/dev/null 2>&1; then
  write_status "blocked" "kiro_chat_unavailable"
  echo "BLOCKED: Kiro CLI is installed, but 'kiro chat' is unavailable." >&2
  echo "Status saved at: $kiro_status_file" >&2
  exit 2
fi

./scripts/ai-dangerous-command-check.sh "kiro chat --mode ask - < prompt-file"

write_status "running" "kiro_chat_started"

set +e
kiro chat --mode ask - < "$kiro_prompt" 2>&1 | tee "$kiro_output"
kiro_status="${PIPESTATUS[0]}"
set -e

if [[ "$kiro_status" -ne 0 ]]; then
  write_status "blocked" "kiro_chat_exit_${kiro_status}"
  exit "$kiro_status"
fi

if ! payload_lines | grep . >/dev/null; then
  write_status "blocked" "no_stdout_design_response"
  echo "BLOCKED: Kiro chat did not return a design response on stdout." >&2
  echo "The prompt may have been opened in the Kiro UI instead of being emitted to this terminal." >&2
  echo "Prompt saved at: $kiro_prompt" >&2
  echo "Output saved at: $kiro_output" >&2
  echo "Status saved at: $kiro_status_file" >&2
  exit 3
fi

if grep -F "BLOCKED: Kiro ${expected_model} is not active." "$kiro_output" >/dev/null; then
  write_status "blocked" "expected_model_not_active"
  echo "BLOCKED: Kiro ${expected_model} is not active." >&2
  echo "Prompt saved at: $kiro_prompt" >&2
  echo "Output saved at: $kiro_output" >&2
  echo "Status saved at: $kiro_status_file" >&2
  exit 4
fi

first_payload_line="$(payload_lines | sed -n '1p')"
if [[ "$first_payload_line" != "$model_marker" ]]; then
  write_status "blocked" "missing_expected_model_marker"
  echo "BLOCKED: Kiro design output did not confirm Opus 4.8." >&2
  echo "Expected first non-empty output line: $model_marker" >&2
  echo "Observed first non-empty output line: ${first_payload_line:-<none>}" >&2
  echo "Prompt saved at: $kiro_prompt" >&2
  echo "Output saved at: $kiro_output" >&2
  echo "Status saved at: $kiro_status_file" >&2
  exit 5
fi

write_status "ok" "expected_model_marker_confirmed"
