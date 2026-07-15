# API Validated Runner Profiles

This directory is intentionally fail-closed.

The API only executes docking/MD work when all conditions are true:

- `API_VALIDATED_RUNNER_ENABLED=1`
- the worker is running on a separately audited namespace-capable host runtime
- a current `validated_runner_namespace_runtime_receipt_v1` receipt is verified
- the request includes `runner_profile_id`
- `{runner_profile_id}.json` exists in this directory
- the profile JSON has `"enabled": true`
- `runner_script` is allowlisted by `api/validated_runner.py`
- `production_readiness` is present and includes:
  - `approved_by`
  - `approved_at_utc`
  - `claim_scope`
  - `evidence_artifact`
  - `runner_script_sha256`
- `evidence_artifact` is a JSON object where these checks are true:
  - `input_contract_reviewed`
  - `output_contract_reviewed`
  - `claim_boundary_reviewed`
  - `gate_policy_reviewed`
  - `fake_result_emission_forbidden`
  - non-empty `gate_policy_artifact`
- the runner exits with status `0`
- the configured `result_file_template` exists after execution

Requests cannot provide arbitrary command-line arguments. The profile controls
the executable and arguments; request data is written to `{request_json_path}` for
the runner to read.

Keep example profiles disabled until an operator reviews the exact input/output
contract and claim scope.

The standard Docker/Compose and Kubernetes manifests intentionally force
`API_VALIDATED_RUNNER_ENABLED=0`. Do not add `privileged`, `SYS_ADMIN`, or
unconfined seccomp/AppArmor settings to bypass that boundary. The current
container runtime is not qualified for the private user/PID/mount namespace
contract; customer execution remains disabled.

On a separately audited host, the runtime gate requires both of these operator
settings before `API_VALIDATED_RUNNER_ENABLED=1` can execute anything:

- `API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH`: absolute path to the separate
  runtime qualification JSON receipt
- `API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256`: lowercase SHA-256 of that
  exact file, pinned independently from the receipt and product smoke artifacts

The verifier rejects any symlink in the receipt path, non-regular or multiply
linked files, group- or other-writable receipt files, receipts larger than 32
KiB, duplicate/unknown schema fields, incomplete containment claims, digest
mismatches, future receipts, expired receipts, and windows longer than 24 hours.
Do not copy the digest pin into the receipt being verified; keep it in the
operator-controlled service environment. Standard Kubernetes pods
additionally use an explicit `API_VALIDATED_RUNNER_ENABLED=0` container
environment entry so a later `envFrom` Secret cannot override the fail-closed
value.

Run the profile gate before enabling production profiles:

```bash
python tools/product/validate_api_runner_profiles.py --profiles-dir config/api_validated_runner_profiles
```

Build an operator enablement work order and evidence templates for disabled
profiles:

```bash
python tools/product/build_api_runner_profile_enablement_work_order.py \
  --profiles-dir config/api_validated_runner_profiles \
  --write-evidence-templates
```

The generated evidence templates deliberately default every review field to
`false`. They are not approval artifacts until an operator fills and reviews
them.
