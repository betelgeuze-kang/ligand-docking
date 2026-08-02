# Developer Preview Final Gate Action Register

Date: 2026-06-29

This register is a planning and operator-action surface only. It does not add
features, regenerate protected evidence, approve solver claims, or promote
AI/GNN/surrogate truth claims. The current repo does not contain materialized
Developer Preview final-gate artifact ids for the six PM-listed blockers, so
each row stays blocked until an operator produces and reviews the named receipt.

## Baseline

| Field | Current value |
| --- | --- |
| Status | blocked_developer_preview_baseline |
| Deliverables | 10/10 reported by PM context, not re-promoted here |
| Final gates | 3/9 reported by PM context, six blockers tracked below |
| Claim posture | frozen; no commercial solver, G1, autonomous AI, GNN, or surrogate-truth promotion |
| Current repo evidence gap | exact gate ids are not materialized in current source/docs/evidence surfaces |

## Action Register

Use the generated command pack for fresh operator runs when possible:
`runs/developer_preview_external_operator_command_pack_current.sh`. Windows
operators can run
`pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro`
for the Windows reproducibility receipt. The `clean-checkout` target records
`.betelgeuze/developer_preview_external_baselines/developer_preview_clean_checkout_status.txt`
and continues to the receipt builder even when baseline regeneration fails, so
the session still emits a fail-closed clean-checkout receipt.
Run Gate A through
`bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout`
with `DEVELOPER_PREVIEW_REPO_URL`, `DEVELOPER_PREVIEW_REVIEWER_ID`, and
`DEVELOPER_PREVIEW_REVIEWED_AT_UTC` set; the generated target calls
`write_clean_checkout_source_provenance` before invoking
`tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py` with
`--checkout-provenance-json .betelgeuze/developer_preview_clean_checkout_source_provenance.json`
and
`--allow-blocked --out-json .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json`.
Set optional `DEVELOPER_PREVIEW_REF=<branch|tag|sha>` when Gate A must verify a
specific reviewed branch, tag, or commit; the generated target fetches that ref
after clone, checks out `FETCH_HEAD` detached, and records
`source_ref_requested`, `source_ref_requested_present`,
`source_checked_out_ref`, and `source_remote_url_redacted` in the provenance
receipt.
The final gate requires the reviewed clean-checkout receipt to report
`clean_checkout_provenance_ready=True`,
`clean_checkout_source_repo_url_present=True`,
`clean_checkout_working_tree_clean=True`, `stage5_input_family_ready=True`,
`clean_checkout_dirty_path_count=0`, `stage5_missing_source_artifact_count=0`,
and `stage5_incomplete_task_count=0`.
The shell command pack normalizes platform detection for Windows Git Bash;
`shell_platform_guard_accepts_git_bash_windows` must remain true.
By default, `clean-checkout` creates a timestamped fresh clone outside the
workspace
(`${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-<UTC timestamp>`). If
`DEVELOPER_PREVIEW_WORKDIR` is set and that path already exists, the command
pack fails closed rather than mixing hidden local state into the receipt.
When `clean-checkout` emits stage5 input-family blockers, run
`bash runs/developer_preview_external_operator_command_pack_current.sh stage5-recovery`
from the receipt checkout to refresh/export the read-only source recovery
handoff and `runs/developer_preview_stage5_restore_packet_current.json` before
restoring the missing scores/labels/split/expected-key CSVs. The target calls
`tools/product/build_developer_preview_stage5_restore_packet.py` and remains
fail-closed when any source CSV is missing.
Use `new-user-draft` to create the work-order, preflight, checklist, blocked
observation receipt, and
`.betelgeuze/developer_preview_new_user_observation_input_template.json`.
Copy that template to
`.betelgeuze/developer_preview_new_user_observation_input.json`, fill only
derived/anonymized observer metadata, and use `new-user-final` only after the
observation is reviewed. Raw customer data and private notes stay outside this
repository.

| Priority | Gate | Owner command | Expected output | Current blocker | Next action |
| --- | --- | --- | --- | --- | --- |
| A | `benchmark_results_clean_checkout_regenerated` | `DEVELOPER_PREVIEW_REPO_URL=<repo-url> DEVELOPER_PREVIEW_REVIEWER_ID=<reviewer-id> DEVELOPER_PREVIEW_REVIEWED_AT_UTC=<utc> bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout` | `ai-verify` passes, baseline summary has non-empty task/score evidence, clean-checkout source provenance records a clean HEAD, and `build_developer_preview_clean_checkout_benchmark_receipt.py` emits a reviewed clean-checkout benchmark receipt plus stage5 input-family recovery CSV/MD or explicit missing-input blockers under `.betelgeuze/` while returning success for fail-closed continuation. | No reviewed clean-checkout benchmark regeneration receipt is recorded for Developer Preview; a plain clone without the reviewed `runs/biorxiv_external_validation_package_current.json` package is insufficient. | Run in a fresh local checkout after materializing the reviewed baseline meta/run-root under `runs/`, keep reviewer metadata set, archive stdout plus `.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json`, `.betelgeuze/developer_preview_clean_checkout_source_provenance.json`, and the stage5 input-family CSV/MD, then decide whether a protected evidence refresh is warranted. |
| B | `silent_import_loss_zero` | `python3 -m pytest -q tests/unit/test_api_product_import.py tests/unit/test_api_cameo_import.py tests/unit/test_api_casp17_import.py tests/unit/test_api_cleanup_import.py tests/unit/test_betelgeuze_product_cli.py tests/unit/test_betelgeuze_cameo_cli.py tests/unit/test_betelgeuze_cleanup_cli.py --junitxml .betelgeuze/developer_preview_import_cli_tests.xml ; python3 scripts/verify_product_capability_matrix.py --out-json .betelgeuze/developer_preview_capability_matrix.json --quiet ; python3 tools/product/build_developer_preview_silent_import_loss_receipt.py --junit-xml .betelgeuze/developer_preview_import_cli_tests.xml --capability-matrix-json .betelgeuze/developer_preview_capability_matrix.json --out-json .betelgeuze/developer_preview_silent_import_loss_receipt.json --out-md .betelgeuze/developer_preview_silent_import_loss_receipt.md` | Import/CLI tests pass, capability matrix reports zero missing or unimportable required Developer Preview surfaces, and the silent-import-loss receipt is materialized for the final gate audit. | Existing repo has import tests, but no Developer Preview-specific silent-import-loss receipt. | Run the command in the same clean checkout as gate A and record any missing optional/API dependency separately from required import loss. |
| C | `selected_medium_models_pass_or_approved_review` | `python3 tools/build_product_pose_sampling_readiness.py --n-starts 8 --out-json .betelgeuze/developer_preview_medium_pose_sampling_readiness.json --out-csv .betelgeuze/developer_preview_medium_pose_sampling_readiness.csv --out-md .betelgeuze/developer_preview_medium_pose_sampling_readiness.md && python3 tools/build_backmapping_scoring_batch_smoke_benchmark.py --frame-count 12 --repeats 2 --out-json .betelgeuze/developer_preview_medium_backmapping_smoke.json --out-md .betelgeuze/developer_preview_medium_backmapping_smoke.md` | Medium-sized deterministic pose/backmapping smoke receipts pass, or an operator-approved review explains each failed medium model. | No selected-medium-model pass/review receipt is materialized. | Freeze the selected medium model list before running; do not substitute cherry-picked passing models after seeing results. |
| D | `large_models_crash_oom_free` | `python3 tools/build_ligand_scaleup_benchmark_summary.py --out-json .betelgeuze/developer_preview_large_model_source_summary.json --out-csv .betelgeuze/developer_preview_large_model_source_summary.csv --out-md .betelgeuze/developer_preview_large_model_source_summary.md ; python3 tools/product/build_developer_preview_large_model_oom_guard_receipt.py --guard-kind ligand-scaleup --source-json .betelgeuze/developer_preview_large_model_source_summary.json --out-json .betelgeuze/developer_preview_large_model_oom_guard.json --out-md .betelgeuze/developer_preview_large_model_oom_guard.md ; python3 tools/build_product_end_to_end_rocm_benchmark.py --out-json .betelgeuze/developer_preview_rocm_large_model_source_summary.json --out-csv .betelgeuze/developer_preview_rocm_large_model_source_summary.csv --out-md .betelgeuze/developer_preview_rocm_large_model_source_summary.md ; python3 tools/product/build_developer_preview_large_model_oom_guard_receipt.py --guard-kind rocm --source-json .betelgeuze/developer_preview_rocm_large_model_source_summary.json --out-json .betelgeuze/developer_preview_rocm_large_model_guard.json --out-md .betelgeuze/developer_preview_rocm_large_model_guard.md` | Large-model guard receipts either show crash/OOM-free status from reviewed local artifacts or fail closed with explicit missing-artifact blockers. | No large-model crash/OOM-free receipt is recorded for the Developer Preview baseline. | Run only on the approved local hardware/profile; keep GPU/HIP as performance/residency evidence, not solver-truth evidence. |
| E | `linux_windows_reproducibility_confirmed` | Linux: `mkdir -p .betelgeuze && bash -o pipefail -c './scripts/ai-verify.sh \| tee .betelgeuze/developer_preview_linux_ai_verify.log' ; python3 -m pytest -q tests/unit/test_betelgeuze_product_readiness.py tests/unit/test_betelgeuze_product_cli.py tests/unit/test_betelgeuze_cameo_cli.py tests/unit/test_betelgeuze_cleanup_cli.py --junitxml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml ; python3 tools/product/build_developer_preview_platform_reproducibility_receipt.py --platform linux --ai-verify-log .betelgeuze/developer_preview_linux_ai_verify.log --pytest-junit-xml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml --allow-blocked --out-json .betelgeuze/developer_preview_linux_reproducibility_receipt.json --out-md .betelgeuze/developer_preview_linux_reproducibility_receipt.md`<br>Windows/Git Bash: `mkdir -p .betelgeuze && bash -o pipefail -c './scripts/ai-verify.sh \| tee .betelgeuze/developer_preview_windows_ai_verify.log' ; python3 -m pytest -q tests/unit/test_betelgeuze_product_readiness.py tests/unit/test_betelgeuze_product_cli.py tests/unit/test_betelgeuze_cameo_cli.py tests/unit/test_betelgeuze_cleanup_cli.py --junitxml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml ; python3 tools/product/build_developer_preview_platform_reproducibility_receipt.py --platform windows --ai-verify-log .betelgeuze/developer_preview_windows_ai_verify.log --pytest-junit-xml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml --allow-blocked --out-json .betelgeuze/developer_preview_windows_reproducibility_receipt.json --out-md .betelgeuze/developer_preview_windows_reproducibility_receipt.md` | Linux receipt passes locally and a matching Windows receipt records the same command set, Python version, dependency inputs, and any expected skips; blocked platform evidence still writes the platform receipt for final-gate audit review. | Linux-only local smoke is available; Windows parity receipt is absent. | Have the owner run the same command set on Windows, attach stdout plus environment details, and keep unresolved platform differences as blockers. |
| F | `new_user_core_workflow_observation_passed` | `python3 tools/build_product_execution_work_order.py --out-json .betelgeuze/developer_preview_new_user_execution_work_order.json --out-csv .betelgeuze/developer_preview_new_user_execution_work_order.csv --out-md .betelgeuze/developer_preview_new_user_execution_work_order.md ; python3 tools/build_product_execution_preflight.py --work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json --out-json .betelgeuze/developer_preview_new_user_execution_preflight.json --out-csv .betelgeuze/developer_preview_new_user_execution_preflight.csv --out-md .betelgeuze/developer_preview_new_user_execution_preflight.md ; python3 tools/product/build_developer_preview_new_user_observation_receipt.py --work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json --preflight-json .betelgeuze/developer_preview_new_user_execution_preflight.json --runbook-md docs/developer_preview_core_workflow_quickstart.md --observation-input-json .betelgeuze/developer_preview_new_user_observation_input.json --allow-blocked --out-json .betelgeuze/developer_preview_new_user_observation_receipt.json --out-md .betelgeuze/developer_preview_new_user_observation_receipt.md --out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv --out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md --out-observation-input-template-json .betelgeuze/developer_preview_new_user_observation_input_template.json` | A new-user observer can follow `docs/developer_preview_core_workflow_quickstart.md` and produce fail-closed work-order/preflight/observation input/checklist/receipt artifacts without hidden local state and with explicit raw-data custody assertions. | No observed new-user workflow receipt is present. | Prepare a scripted observation session, copy the input template to `.betelgeuze/developer_preview_new_user_observation_input.json`, record only derived metadata, and keep raw/private customer data out of the repo. |

## Readiness Delta

| Gate | Delta from blocked baseline |
| --- | --- |
| `benchmark_results_clean_checkout_regenerated` | Receipt builder and action command defined; still blocked pending clean-checkout run plus reviewed receipt attachment. |
| `silent_import_loss_zero` | Required import/CLI check set defined; still blocked pending DP-specific receipt. |
| `selected_medium_models_pass_or_approved_review` | Medium smoke/review path defined; still blocked pending frozen model list and receipt. |
| `large_models_crash_oom_free` | Crash/OOM-free guard path defined; still blocked pending reviewed local hardware/profile output. |
| `linux_windows_reproducibility_confirmed` | Linux/Windows parity command set and platform-specific receipt defaults defined; still blocked pending Windows run. |
| `new_user_core_workflow_observation_passed` | Clean-checkout bootstrap plus observation receipt path defined; still blocked pending observed workflow run. |

## Guardrails

- Do not add product features while these six gates are blocked.
- Do not use GPU/HIP receipts to replace CPU solver closure or G1 evidence.
- Do not interpret missing Developer Preview gate artifacts as pass.
- Do not store private customer raw data, secrets, `.env` content, or approval
  tokens in the receipts.
- Do not promote release-ready, paid-pilot-ready, solver-product-ready,
  autonomous AI, GNN, or surrogate-truth claims from this register.
