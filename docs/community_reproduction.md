# Community reproduction workflow

This workflow lets an external user report an independently executed CPU or
ROCm/HIP reproduction without turning the submission into an official project
claim.

The current repository license remains controlling.  This document is a
technical submission format, not a software-use license grant.

## Receipt files

- schema: `config/community_reproduction_receipt_v1.schema.json`
- verifier: `tools/verify_community_reproduction_receipt_v1.py`
- GitHub issue template: `.github/ISSUE_TEMPLATE/benchmark-reproduction.yml`

A receipt records:

- exact source commit;
- Engine V2 profile and backend;
- OS, architecture, CPU, GPU, and ROCm identity;
- Python, Rust, compiler, wheel, and extension identity;
- benchmark manifest, case count, 64-candidate denominator, and result hash;
- completed and failed case counts;
- compact metrics;
- submitting GitHub account and independent-run attestation;
- a claim boundary that remains self-reported and non-authoritative.

Do not include private molecular structures, credentials, tokens, raw customer
paths, or proprietary benchmark payloads in a public receipt.

## Minimal example

```json
{
  "schema_id": "betelgeuze.community_reproduction_receipt/1.0.0",
  "repository": "betelgeuze-kang/ligand-docking",
  "source_commit_sha": "1111111111111111111111111111111111111111",
  "profile_id": "engine_v2_native_fixed64_cpu_synthetic_v7",
  "backend": "rust_cpu",
  "hardware": {
    "os": "Ubuntu 24.04",
    "architecture": "x86_64",
    "cpu_model": "Example CPU",
    "gpu_model": null,
    "rocm_version": null
  },
  "software": {
    "python_version": "3.12.4",
    "rustc_version": "rustc ...",
    "compiler_identity": "gcc ...",
    "wheel_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
    "native_extension_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
  },
  "benchmark": {
    "benchmark_id": "synthetic-fixed64-v7",
    "manifest_sha256": "4444444444444444444444444444444444444444444444444444444444444444",
    "case_count": 2,
    "candidate_denominator": 64,
    "result_sha256": "5555555555555555555555555555555555555555555555555555555555555555"
  },
  "results": {
    "completed_case_count": 2,
    "failed_case_count": 0,
    "metrics": {
      "top1_recovery_count": 1,
      "runtime_seconds": 0.125
    }
  },
  "submitter": {
    "github_login": "independent-user",
    "organization": null,
    "attests_independent_run": true
  },
  "claim_boundary": {
    "self_reported": true,
    "project_verified": false,
    "scientific_claim_authorized": false,
    "benchmark_claim_authorized": false,
    "product_claim_authorized": false
  },
  "receipt_sha256": "REPLACE_WITH_CANONICAL_UNSIGNED_DOCUMENT_SHA256"
}
```

`receipt_sha256` is SHA-256 over canonical JSON after removing that field:
ASCII output, sorted keys, no whitespace, no NaN/Infinity.

## Verification

```bash
python tools/verify_community_reproduction_receipt_v1.py \
  reproduction-receipt.json --pretty
```

A successful result means the receipt is structurally complete and self-hash
consistent.  It does not prove that the reported binary, hardware, or result was
observed by the project.

## Submission

Open a **Benchmark reproduction** issue and attach the small JSON receipt or a
stable link to it.  Large raw results should be stored outside GitHub issues;
include their SHA-256 and an access-controlled or public locator as appropriate.

Project maintainers may then perform one of four explicit dispositions:

1. `received_unreviewed`;
2. `structure_verified`;
3. `raw_evidence_reproduced`;
4. `accepted_for_a_specific_claim_review`.

No disposition is implied merely by opening an issue.
