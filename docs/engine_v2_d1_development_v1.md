# Engine V2 D1 repeatable development lane v1

This lane exists to let sampling and ranking work iterate on one fixed 32-case
development cohort without consuming or exposing the protected Fresh-128
holdout.

It is deliberately **repeatable development**, not a one-shot qualification.
Results may inform later development changes.  No output from this lane can
admit Stage 0 or authorize a public, scientific, product, customer, or GPU
performance claim.

## Files

- profile: `config/engine_v2_d1_development_profile_v1.json`
- analyzer: `tools/run_engine_v2_d1_development_v1.py`
- persisted-report verifier: `tools/verify_engine_v2_d1_development_v1.py`
- tests: `tests/unit/test_engine_v2_d1_development_v1.py`

## Required cohort

The manifest must contain exactly 32 unique case IDs in a stable order.
Separately, the caller must supply the complete protected 128-case ID registry.
Any overlap fails before case-result processing.

Manifest shape:

```json
{
  "schema_id": "betelgeuze.engine_v2_d1_manifest/1.0.0",
  "profile_id": "engine_v2_d1_repeatable_development_v1",
  "cases": [
    {"case_id": "CASE_001", "result_path": "CASE_001.json"}
  ]
}
```

The example shows one row only; an executable manifest requires exactly 32.
Every result path must be a relative, non-symlinked regular file under the
explicit result root.

Fresh registry shape:

```json
{
  "schema_id": "betelgeuze.engine_v2_fresh_case_registry/1.0.0",
  "case_ids": ["FRESH_CASE_001"]
}
```

An executable registry requires exactly 128 unique IDs.

## Case-result contract

A prepared case retains exactly 64 ordered candidate rows.  A preparation
failure retains no candidate rows and requires a typed preparation failure.

A scored candidate contains:

```json
{
  "slot_index": 0,
  "lane": "uniform",
  "status": "scored",
  "failure_code": null,
  "score": -1.25,
  "proposal_rmsd_angstrom": 3.4,
  "final_rmsd_angstrom": 2.8,
  "proposal_valid": true,
  "pose_valid": false
}
```

A typed candidate failure contains no score, RMSD, or validity value:

```json
{
  "slot_index": 1,
  "lane": "single_anchor",
  "status": "typed_failure",
  "failure_code": "source_missing",
  "score": null,
  "proposal_rmsd_angstrom": null,
  "final_rmsd_angstrom": null,
  "proposal_valid": null,
  "pose_valid": null
}
```

## Metrics

The analyzer derives:

- preparation success and typed preparation failures;
- proposal-oracle recovery at an exact 2.0 Å threshold;
- valid proposal-oracle recovery;
- stable score-then-slot Top-1 and Top-5 recovery;
- invalid or unavailable Top-1 validity;
- scoring regret, defined as Top-1 RMSD minus best scored-candidate RMSD;
- lane-level candidate, failure, native-like, valid, Top-1, and Top-5 evidence;
- typed candidate-failure distribution;
- optional new and lost recovery case IDs relative to an ordered baseline
  manifest over the same cohort.

The score direction is fixed to lower-is-better.  No user-supplied rank is
accepted.

## Usage

```bash
python tools/run_engine_v2_d1_development_v1.py \
  --manifest /absolute/d1/manifest.json \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --result-root /absolute/d1/results \
  --output /absolute/d1/reports/run-001.json
```

Optional baseline comparison:

```bash
python tools/run_engine_v2_d1_development_v1.py \
  --manifest /absolute/d1/current-manifest.json \
  --result-root /absolute/d1/current-results \
  --baseline-manifest /absolute/d1/baseline-manifest.json \
  --baseline-result-root /absolute/d1/baseline-results \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --output /absolute/d1/reports/current-vs-baseline.json
```

Persisted verification does not rerun docking:

```bash
python tools/verify_engine_v2_d1_development_v1.py \
  --report /absolute/d1/reports/run-001.json --pretty
```

Output paths are absent-only.  Repeatable development uses a new output path for
each run rather than replacing prior evidence.

## Promotion boundary

D1 may be used to choose and tune sampling or ranking changes.  It must never be
presented as blind evidence.  A later Fresh-128 execution remains separately
frozen, exactly-once, non-overlapping, and authority-controlled.
