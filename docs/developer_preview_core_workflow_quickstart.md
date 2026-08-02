# Developer Preview Core Workflow Quickstart

This quickstart is the operator-readable path for a new technical user to
exercise the Developer Preview core workflow and create fail-closed receipts.
It does not execute docking by itself, approve paid-pilot wording, upload data,
deploy services, or mutate external state.

## Preconditions

- Start from a clean checkout.
- Confirm that raw customer data stays outside this repository.
- Record only derived, anonymized observation metadata in `.betelgeuze/`.
- Treat every receipt as blocked unless its own status is ready and blocker
  count is zero.
- Record any hidden local state as a hidden local state blocker instead of
  working around it silently.
- Run Windows receipts on Windows. A Windows receipt generated on Linux is
  expected to fail closed with `platform_mismatch`.
- Windows Git Bash and native Windows Python are both accepted for the Windows
  receipt; `MSYS_NT-*` and `MINGW*_NT-*` platform strings are treated as
  Windows evidence, but Linux-generated receipts remain blocked.

## Clean Checkout Bootstrap

Use a fresh clone for Developer Preview receipt generation. Replace
`<repo-url>` with the reviewed repository source and do not copy local
workspace artifacts except the reviewed evidence explicitly required by a gate.

Linux:

```bash
git clone <repo-url> betelgeuze-developer-preview
cd betelgeuze-developer-preview
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Windows Git Bash:

```bash
git clone <repo-url> betelgeuze-developer-preview
cd betelgeuze-developer-preview
py -3 -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Receipt Paths

- `.betelgeuze/developer_preview_clean_checkout_ai_verify.log`
- `.betelgeuze/developer_preview_external_baselines/biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json`
- `.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json`
- `.betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv`
- `.betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md`
- `.betelgeuze/developer_preview_linux_ai_verify.log`
- `.betelgeuze/developer_preview_linux_reproducibility_pytest.xml`
- `.betelgeuze/developer_preview_linux_reproducibility_receipt.json`
- `.betelgeuze/developer_preview_windows_ai_verify.log`
- `.betelgeuze/developer_preview_windows_reproducibility_pytest.xml`
- `.betelgeuze/developer_preview_windows_reproducibility_receipt.json`
- `.betelgeuze/developer_preview_new_user_execution_work_order.json`
- `.betelgeuze/developer_preview_new_user_execution_preflight.json`
- `.betelgeuze/developer_preview_new_user_observation_input_template.json`
- `.betelgeuze/developer_preview_new_user_observation_input.json`
- `.betelgeuze/developer_preview_new_user_observation_checklist.csv`
- `.betelgeuze/developer_preview_new_user_observation_checklist.md`
- `.betelgeuze/developer_preview_new_user_observation_receipt.json`
- `runs/developer_preview_final_gate_audit_current.json`
- `runs/developer_preview_external_operator_work_order_current.json`
- `runs/developer_preview_external_operator_work_order_current.csv`
- `runs/developer_preview_external_operator_work_order_current.md`
- `runs/developer_preview_external_operator_command_pack_current.json`
- `runs/developer_preview_external_operator_command_pack_current.sh`
- `runs/developer_preview_external_operator_command_pack_current.ps1`
- `runs/developer_preview_external_operator_command_pack_current.md`

## Commands

### Operator Command Pack

The final gate builder also emits a target-based command pack. Use it when you
want one generated command surface instead of copying commands from each
section manually.

```bash
python3 tools/product/build_developer_preview_final_gate_audit.py
bash runs/developer_preview_external_operator_command_pack_current.sh <target>
```

```powershell
pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro
```

Available targets are `clean-checkout`, `stage5-recovery`, `linux-repro`,
`windows-repro`, `new-user-draft`, `new-user-final`, and `final-gate`. Run `windows-repro` only
from a Windows checkout or Git Bash session; Linux-generated Windows receipts
remain blocked by design.

The generated command pack fails fast before running target commands when a
required platform or operator environment variable is missing. `clean-checkout`
requires `DEVELOPER_PREVIEW_REPO_URL`, `DEVELOPER_PREVIEW_REVIEWER_ID`, and
`DEVELOPER_PREVIEW_REVIEWED_AT_UTC`.
Set `DEVELOPER_PREVIEW_REF=<branch|tag|sha>` when the clean checkout must be
pinned to a reviewed ref instead of the repository default branch; the command
pack fetches that ref immediately after cloning, checks out `FETCH_HEAD`
detached, and records the requested ref in the source provenance receipt.
`linux-repro` and `windows-repro` include platform guards so a receipt is not
silently generated from the wrong operating system.
The `clean-checkout` target creates a timestamped fresh clone outside the
workspace by default
(`${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-<UTC timestamp>`). If
`DEVELOPER_PREVIEW_WORKDIR` is set, that path must not already exist; an
existing path fails closed to avoid mixing hidden local state into the receipt.
Set `DEVELOPER_PREVIEW_PYTHON=python` before invoking the command pack when a
Windows/Git Bash checkout exposes only `python` and not `python3`. Run
`new-user-draft` before `new-user-final`; the final target checks for
`.betelgeuze/developer_preview_new_user_execution_work_order.json` and
`.betelgeuze/developer_preview_new_user_execution_preflight.json` before it
records observer signoff. `new-user-final` requires `.betelgeuze/developer_preview_new_user_observation_input.json`;
fill that artifact from the draft template with only derived/anonymized observer
metadata before running the final target.
The `stage5-recovery` target is a read-only handoff helper. Run it after a
blocked `clean-checkout` target has emitted the stage5 input-family CSV/MD;
it builds `runs/developer_preview_stage5_restore_packet_current.json`, then
refreshes the final gate audit so the latest restore packet status and primary
restore instruction appear in the audit and command-pack summaries. The target
calls `tools/product/build_developer_preview_stage5_restore_packet.py` and stays
fail-closed while any source CSV is missing. Use the restore packet CSV/MD
`row_blocker`, `restore_queue_ready`, `operator_restore_instruction`, and
`operator_restore_sequence` fields as the source-by-source recovery checklist
before rebuilding the clean-checkout receipt.
The generated PowerShell pack intentionally supports only `windows-repro` and
`final-gate`; use the shell pack for `clean-checkout`, `stage5-recovery`,
`linux-repro`, and new-user observation targets.

### Gate A: Clean Checkout Benchmark Receipt

Run this from a fresh local clone after materializing the reviewed baseline
meta/run-root under `runs/`. The receipt remains blocked when stage5 inputs,
review metadata, or baseline evidence are missing.
The baseline runner writes
`.betelgeuze/developer_preview_external_baselines/developer_preview_clean_checkout_status.txt`;
continue to the receipt builder even when that exit code is non-zero so the
session still produces a fail-closed receipt.
The receipt also requires
`.betelgeuze/developer_preview_clean_checkout_source_provenance.json`, which
records only source URL presence/fingerprint, requested source ref when set,
checked-out ref, HEAD SHA, tracked file count, and clean working-tree status.
When stage5 inputs are missing, use
`.betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv`
and the final gate audit's `Stage5 Source Recovery` section as the operator
work order for the full scores/labels/split/expected-keys input family.
After that fail-closed receipt exists, run
`bash runs/developer_preview_external_operator_command_pack_current.sh stage5-recovery`
to refresh/export the stage5 source recovery handoff and
`runs/developer_preview_stage5_restore_packet_current.json`; each missing row
then carries the exact source path, blocker, and restore instruction needed
before rerunning the clean-checkout target with restored inputs.

```bash
mkdir -p .betelgeuze
: "${DEVELOPER_PREVIEW_REPO_URL:?set DEVELOPER_PREVIEW_REPO_URL}"
python3 - <<'PY'
import hashlib
import json
import os
import subprocess

def run(args):
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    return result.stdout.strip()

repo_url = os.environ.get("DEVELOPER_PREVIEW_REPO_URL", "").strip()
status_text = run(["git", "status", "--porcelain"])
dirty_lines = [line for line in status_text.splitlines() if line.strip()]
payload = {
    "summary": {
        "packet_type": "developer_preview_clean_checkout_source_provenance",
        "schema_version": "developer_preview_clean_checkout_source_provenance_v1",
        "source_repo_url_present": bool(repo_url),
        "source_repo_url_fingerprint": hashlib.sha256(repo_url.encode("utf-8")).hexdigest() if repo_url else "",
        "head_sha": run(["git", "rev-parse", "HEAD"]),
        "tracked_file_count": len(run(["git", "ls-files"]).splitlines()),
        "git_status_porcelain_empty": not dirty_lines,
        "working_tree_clean": not dirty_lines,
        "dirty_path_count": len(dirty_lines),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    },
    "dirty_rows": [{"status_line": line} for line in dirty_lines[:50]],
}
with open(".betelgeuze/developer_preview_clean_checkout_source_provenance.json", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
bash -o pipefail -c './scripts/ai-verify.sh | tee .betelgeuze/developer_preview_clean_checkout_ai_verify.log'
baseline_status=.betelgeuze/developer_preview_external_baselines/developer_preview_clean_checkout_status.txt
mkdir -p "$(dirname "$baseline_status")"
set +e
python3 tools/run_external_validation_baselines.py \
  --spec-json config/external_validation_baselines_v1.json \
  --current-meta-json runs/biorxiv_external_validation_package_current.json \
  --out-root .betelgeuze/developer_preview_external_baselines \
  --label developer_preview_clean_checkout \
  --no-rerun-current \
  --require-tasks
baseline_rc=$?
set -e
printf 'run_external_validation_baselines_exit_code=%s\n' "$baseline_rc" > "$baseline_status"
python3 tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py \
  --ai-verify-log .betelgeuze/developer_preview_clean_checkout_ai_verify.log \
  --baseline-summary-json .betelgeuze/developer_preview_external_baselines/biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json \
  --checkout-provenance-json .betelgeuze/developer_preview_clean_checkout_source_provenance.json \
  --reviewed-receipt-attached \
  --reviewer-id OPERATOR_REVIEWER_ID \
  --reviewed-at-utc 2026-07-05T00:00:00Z \
  --allow-blocked \
  --out-json .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json \
  --out-md .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md \
  --out-stage5-input-family-csv .betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv \
  --out-stage5-input-family-md .betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md
```

### Gate E: Linux Reproducibility Receipt

Run the approved command set on Linux and keep the captured JUnit XML.

```bash
mkdir -p .betelgeuze
bash -o pipefail -c './scripts/ai-verify.sh | tee .betelgeuze/developer_preview_linux_ai_verify.log'
python3 -m pytest -q \
  tests/unit/test_betelgeuze_product_readiness.py \
  tests/unit/test_betelgeuze_product_cli.py \
  tests/unit/test_betelgeuze_cameo_cli.py \
  tests/unit/test_betelgeuze_cleanup_cli.py \
  --junitxml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml
python3 tools/product/build_developer_preview_platform_reproducibility_receipt.py \
  --platform linux \
  --ai-verify-log .betelgeuze/developer_preview_linux_ai_verify.log \
  --pytest-junit-xml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml \
  --allow-blocked \
  --out-json .betelgeuze/developer_preview_linux_reproducibility_receipt.json \
  --out-md .betelgeuze/developer_preview_linux_reproducibility_receipt.md
```

### Gate E: Windows Reproducibility Receipt

Run this from a Windows checkout. The preferred operator surface is the
PowerShell command pack because it keeps the Windows platform guard and receipt
paths in one generated command. Do not copy a Linux receipt into the Windows
slot.

```powershell
pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro
```

If you are using Git Bash on Windows instead of PowerShell, the equivalent
manual command set is:

```bash
mkdir -p .betelgeuze
bash -o pipefail -c './scripts/ai-verify.sh | tee .betelgeuze/developer_preview_windows_ai_verify.log'
python -m pytest -q \
  tests/unit/test_betelgeuze_product_readiness.py \
  tests/unit/test_betelgeuze_product_cli.py \
  tests/unit/test_betelgeuze_cameo_cli.py \
  tests/unit/test_betelgeuze_cleanup_cli.py \
  --junitxml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml
python tools/product/build_developer_preview_platform_reproducibility_receipt.py \
  --platform windows \
  --ai-verify-log .betelgeuze/developer_preview_windows_ai_verify.log \
  --pytest-junit-xml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml \
  --allow-blocked \
  --out-json .betelgeuze/developer_preview_windows_reproducibility_receipt.json \
  --out-md .betelgeuze/developer_preview_windows_reproducibility_receipt.md
```

### Gate F: New-User Observation Receipt

Generate the work order:

```bash
python3 tools/build_product_execution_work_order.py \
  --out-json .betelgeuze/developer_preview_new_user_execution_work_order.json \
  --out-csv .betelgeuze/developer_preview_new_user_execution_work_order.csv \
  --out-md .betelgeuze/developer_preview_new_user_execution_work_order.md
```

Validate the work order without execution:

```bash
python3 tools/build_product_execution_preflight.py \
  --work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json \
  --out-json .betelgeuze/developer_preview_new_user_execution_preflight.json \
  --out-csv .betelgeuze/developer_preview_new_user_execution_preflight.csv \
  --out-md .betelgeuze/developer_preview_new_user_execution_preflight.md
```

Build a fail-closed draft receipt before observer signoff. This command is
expected to produce `blocked_developer_preview_new_user_observation_receipt`
until observer metadata and privacy confirmations are attached, but it still
writes the receipt and observation checklist so the final gate audit can show
the exact remaining fields.

```bash
python3 tools/product/build_developer_preview_new_user_observation_receipt.py \
  --work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json \
  --preflight-json .betelgeuze/developer_preview_new_user_execution_preflight.json \
  --runbook-md docs/developer_preview_core_workflow_quickstart.md \
  --allow-blocked \
  --out-json .betelgeuze/developer_preview_new_user_observation_receipt.json \
  --out-md .betelgeuze/developer_preview_new_user_observation_receipt.md \
  --out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv \
  --out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md \
  --out-observation-input-template-json .betelgeuze/developer_preview_new_user_observation_input_template.json
```

Use `.betelgeuze/developer_preview_new_user_observation_checklist.csv` or
`.betelgeuze/developer_preview_new_user_observation_checklist.md` during the
observed session. The checklist must contain only derived/anonymized operator
metadata, pass/blocker/action status, and privacy confirmations; raw customer
data and private notes stay outside this repository.
Copy `.betelgeuze/developer_preview_new_user_observation_input_template.json`
to `.betelgeuze/developer_preview_new_user_observation_input.json` and fill
only the derived/anonymized observer metadata fields. Leave
`hidden_state_blockers` empty only when the new user did not need undocumented
local paths, credentials, shell aliases, cached files, or other hidden local
state. Do not paste raw customer data or private notes into either JSON file.
The receipt validates the observation input contract before accepting signoff:
`observation_input_contract_ready`, `observation_input_packet_type_valid`,
`observation_input_schema_version_valid`, and `observation_input_policy_ready`
must all be true. Keep `raw_customer_data_allowed` and `stores_private_notes`
false; either value set to true keeps the receipt blocked.

Build the observation receipt after the session:

```bash
python3 tools/product/build_developer_preview_new_user_observation_receipt.py \
  --work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json \
  --preflight-json .betelgeuze/developer_preview_new_user_execution_preflight.json \
  --runbook-md docs/developer_preview_core_workflow_quickstart.md \
  --observation-input-json .betelgeuze/developer_preview_new_user_observation_input.json \
  --allow-blocked \
  --out-json .betelgeuze/developer_preview_new_user_observation_receipt.json \
  --out-md .betelgeuze/developer_preview_new_user_observation_receipt.md \
  --out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv \
  --out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md \
  --out-observation-input-template-json .betelgeuze/developer_preview_new_user_observation_input_template.json
```

For automation that cannot edit JSON, the receipt builder still accepts the
equivalent CLI fields `--observer-signoff`, `--anonymized-notes-only`,
`--raw-customer-data-not-stored-in-repo`, and
`--customer-retained-raw-data`; prefer the JSON input for new-user sessions so
the reviewed metadata is visible as a single artifact.

Rebuild the final gate audit:

```bash
python3 tools/product/build_developer_preview_final_gate_audit.py \
  --out-json runs/developer_preview_final_gate_audit_current.json \
  --out-csv runs/developer_preview_final_gate_audit_current.csv \
  --out-md runs/developer_preview_final_gate_audit_current.md \
  --out-operator-work-order-json runs/developer_preview_external_operator_work_order_current.json \
  --out-operator-work-order-csv runs/developer_preview_external_operator_work_order_current.csv \
  --out-operator-work-order-md runs/developer_preview_external_operator_work_order_current.md \
  --out-operator-command-pack-json runs/developer_preview_external_operator_command_pack_current.json \
  --out-operator-command-pack-sh runs/developer_preview_external_operator_command_pack_current.sh \
  --out-operator-command-pack-ps1 runs/developer_preview_external_operator_command_pack_current.ps1 \
  --out-operator-command-pack-md runs/developer_preview_external_operator_command_pack_current.md
```

The external operator work-order files are generated even when the final gate is
blocked. Use them as the current handoff list for clean-checkout, Windows, and
new-user observation receipts.

## Acceptance

Developer Preview remains blocked until the final gate audit reports every
required receipt as ready. The clean-checkout gate remains blocked until the
benchmark receipt reports:

- `status=developer_preview_clean_checkout_benchmark_receipt_ready`
- `clean_checkout_benchmark_regenerated=True`
- `clean_checkout_provenance_ready=True`
- `clean_checkout_source_repo_url_present=True`
- `clean_checkout_working_tree_clean=True`
- `ai_verify_passed=True`
- `reviewed_receipt_attached=True`
- `stage5_input_family_ready=True`
- `clean_checkout_dirty_path_count=0`
- `stage5_missing_source_artifact_count=0`
- `stage5_incomplete_task_count=0`
- `blocker_count=0`
- `failed_count=0`

The new-user gate remains blocked until the
observation receipt reports:

- `status=developer_preview_new_user_observation_receipt_ready`
- `runbook_ready=True`
- `work_order_ready=True`
- `preflight_ready=True`
- `core_workflow_receipt_path_documented=True`
- `core_workflow_command_set_documented=True`
- `observation_checklist_path_documented=True`
- `developer_preview_exit_receipt_path_documented=True`
- `developer_preview_exit_command_set_documented=True`
- `clean_checkout_bootstrap_documented=True`
- `linux_bootstrap_command_set_documented=True`
- `windows_bootstrap_command_set_documented=True`
- `clean_checkout_receipt_path_documented=True`
- `platform_reproducibility_receipt_paths_documented=True`
- `observer_signoff=True`
- `anonymized_notes_only=True`
- `raw_customer_data_not_stored_in_repo=True`
- `customer_retained_raw_data=True`
- `hidden_state_blocker_count=0`
- `blocker_count=0`

The final audit remains blocked until `.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json`,
`.betelgeuze/developer_preview_linux_reproducibility_receipt.json`,
`.betelgeuze/developer_preview_windows_reproducibility_receipt.json`, and
`.betelgeuze/developer_preview_new_user_observation_receipt.json` all satisfy
their own ready contracts.
