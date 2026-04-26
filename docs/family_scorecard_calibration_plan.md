# Family Scorecard Calibration Plan

## Purpose

This note defines the baseline for any family-specific score improvement or architecture-accuracy claim. It is a prerequisite note, not a scope-expansion note.

Use it when a delivery conversation needs to move from "the stack ran" to "the family score is actually better and stable on held-out data."

## How To Build The Scorecard

Use the scorecard builder on a frozen prediction file and keep the exact packet together with the baseline and held-out family set that produced it.

```bash
python3 tools/build_family_scorecard.py \
  --predictions-csv <path/to/frozen/family_predictions.csv> \
  --family-col family \
  --label-col label \
  --score-col score \
  --top-k 25 \
  --lower-better \
  --baseline-scorecard-json <path/to/baseline/family_scorecard.json> \
  --acceptance-profile-json <path/to/config/family_acceptance_profile.json> \
  --out-json <path/to/output/family_scorecard.json> \
  --out-md <path/to/output/family_scorecard.md> \
  --out-csv <path/to/output/family_scorecard.csv>
```

The raw scorecard command only computes ranking metrics. For scoped delivery, the wrapper or reviewer checklist must also enforce required-family coverage, frozen-packet hashes, and the acceptance profile.
If the scorecard is later bundled, keep the emitted JSON as the source artifact for `--family-scorecard-json` and let the bundle manifest record it under `family_scorecards` with source path, bundle path, checksum, and summary status.

Placeholder scoped-delivery wrapper example:

```bash
python3 tools/build_family_scorecard.py \
  --predictions-csv <path/to/frozen/family_predictions.csv> \
  --family-col family \
  --label-col label \
  --score-col score \
  --top-k 25 \
  --lower-better \
  --required-family gpcr \
  --required-family ion_channel \
  --required-family kinase \
  --baseline-scorecard-json <path/to/baseline/family_scorecard.json> \
  --acceptance-profile-json <path/to/config/family_acceptance_profile.json> \
  --out-json <path/to/output/family_scorecard.json> \
  --out-md <path/to/output/family_scorecard.md> \
  --out-csv <path/to/output/family_scorecard.csv>
```

This placeholder is policy-layer only. If any required family is missing from the frozen packet, the scorecard is blocked before claim wording is drafted.

Placeholder frozen-packet identity example:

```bash
python3 tools/build_family_scorecard.py \
  --predictions-csv <path/to/frozen/family_predictions.csv> \
  --family-col family \
  --label-col label \
  --identity-col target \
  --identity-col ligand_id \
  --score-col score \
  --top-k 25 \
  --lower-better \
  --packet-id gpcr-frozen-20260423 \
  --baseline-scorecard-json <path/to/baseline/family_scorecard.json> \
  --acceptance-profile-json <path/to/config/family_acceptance_profile.json> \
  --out-json <path/to/output/family_scorecard.json> \
  --out-md <path/to/output/family_scorecard.md> \
  --out-csv <path/to/output/family_scorecard.csv>
```

If no `--identity-col` is supplied, the builder stays in family/label-only mode and does not run a separate target/ligand completeness check, identity-columns completeness check, or duplicate explicit-identity check.

## Row Identity Contract

- Use the same ordered `--identity-col` list for the candidate and baseline packets.
- Keep the packet `family` column nonblank, and do not use the reserved family name `overall` for input rows because the scorecard reserves it for aggregate metrics.
- If the baseline scorecard's `summary.identity_columns` is missing or does not exactly match the candidate packet's ordered `identity_columns` list, treat the scorecard as scorecard-level blocked and do not use it for score-uplift, architecture-accuracy, or delivery-ready wording.
- When identity columns are declared, blank target or ligand identity values are a frozen-packet drift risk and the scorecard builder rejects the packet before writing claim evidence.
- When explicit identity columns are used, the canonical row identity is `family`, `label`, plus the ordered identity columns. If two rows collapse to the same canonical row identity, emit a duplicate-row-identity warning, block the scorecard, and deduplicate the packet or rewrite the claim packet before delivery.
- If no `--identity-col` is supplied, the builder stays in family/label-only mode and does not run a separate target/ligand completeness check or a separate duplicate explicit-identity check.
- Record `row_identity_schema_version` with the row-identity metadata. It fixes the meaning of `row_identity_sha256`; candidate and baseline schema-version mismatches are scorecard-level blocked.
- If a baseline scorecard predates `row_identity_schema_version`, treat it as legacy, regenerate it before using it as delivery-ready evidence, and do not rely on the legacy artifact itself for delivery-ready wording.
- If `--packet-id` is present, treat it as a human alias only; the authoritative packet contract is `predictions_csv_sha256`, `row_identity_sha256`, `row_identity_schema_version`, and the ordered `identity_columns` list.

Use `--lower-better` only when smaller numerical values are better for the metric family, such as binding-energy or distance-like scores. Omit it when larger values are better. Do not change the orientation between the candidate and baseline runs for the same claim cycle.

The baseline scorecard must include the same `summary.top_k` and `summary.lower_better` settings as the candidate. Treat a mismatch as blocked for score-uplift language.
If the frozen candidate and baseline packets do not share the same `row_identity_sha256`, restart the claim cycle instead of comparing score deltas across packets.

Minimal acceptance profile shape:

```json
{
  "default": {
    "min_row_count": 20,
    "min_positive_count": 3,
    "min_negative_count": 3,
    "min_score_coverage": 0.95,
    "min_score_unique_ratio": 0.8,
    "max_score_tie_ratio": 0.2,
    "max_score_mode_ratio": 0.3,
    "min_auroc": 0.8,
    "min_average_precision": 0.5,
    "min_delta_average_precision": 0.0
  },
  "families": {
    "gpcr": {
      "min_average_precision": 0.6
    }
  }
}
```

Use `min_delta_*` thresholds only with metrics that are present in both candidate and baseline scorecards. Missing, null, non-finite, or non-numeric baseline metrics are blocking conditions for scorecard-level acceptance.
Missing required families, missing baseline summary metadata, baseline `top_k` / `lower_better` mismatch, and `row_identity_sha256` mismatch are also scorecard-level blocking conditions.

## Frozen Packet Metadata

Record both `predictions_csv_sha256` and `row_identity_sha256` for the frozen packet.

- `predictions_csv_sha256` pins the exact CSV bytes, so it tells you whether the candidate or baseline file itself changed.
- `row_identity_schema_version` fixes the meaning of `row_identity_sha256`. Candidate and baseline schema-version mismatches are scorecard-level blocked.
- `row_identity_sha256` hashes the canonical ordered row-identity payload after dropping score values. The payload includes the row-defining family, label, and configured identity columns, and row order is part of the hash, so any target, ligand, family, label, or order change changes the digest.
- A score-only candidate-vs-baseline comparison is valid only when `row_identity_sha256` matches exactly and the row-identity schema versions match.
- If only `predictions_csv_sha256` changes and `row_identity_sha256` still matches, the comparison may still be a score-only candidate-vs-baseline comparison.
- If the candidate and baseline do not share the same ordered `identity_columns` list, or the baseline scorecard's `summary.identity_columns` is missing or different, the scorecard is blocked at scorecard level and no delivery-ready verdict should be drafted.
- Legacy baselines that do not carry `row_identity_schema_version` should be regenerated before they are used as delivery-ready evidence.
- If `row_identity_sha256` changes, restart the claim cycle instead of comparing score deltas across packets.

## Score Resolution And Tie Diagnostics

The score-resolution diagnostics come from the rounded finite score values:

- `score_unique_ratio` measures how many distinct score values remain after rounding.
- `score_tie_ratio` is `1 - score_unique_ratio`.
- `score_mode_ratio` is the fraction of rows occupied by the most common rounded score.

When `score_unique_ratio` is low or `score_tie_ratio` / `score_mode_ratio` is high, top-k hit rate and average precision become less trustworthy because the ranking is coarse or tie-heavy. In that case, lower the claim language and avoid delivery-ready uplift wording unless an independent gate is stronger than the scorecard.

## Scorecard Flow

1. Freeze the prediction input, the baseline scorecard, and the held-out family packet.
2. Build the scorecard from that frozen packet.
3. Generate any baseline comparison and acceptance profile from the same frozen packet.
4. Treat the result as a family-scorecard decision only; do not turn it into delivery-ready wording by itself.

## Required Baseline

Do not write a score-uplift or architecture-accuracy claim for a family unless all of the following are current for the same frozen input/baseline/held-out family packet:

- held-out family scorecard
- hard-decoy stability
- calibration
- geometry/contact gate

The frozen packet means the exact prediction input, the matched baseline, and the held-out family set used for the comparison. If any one of those artifacts changes, restart the claim cycle instead of mixing packets.

Baseline comparison and acceptance-profile summaries are scorecard-level artifacts only. They can show that the family packet is acceptable for family-scoped evaluation, but they are not delivery-ready verdicts and they do not override the local delivery gates.

If any one of the four required checks is missing or mixed, keep the wording `blocked`, `internal-review`, `staged`, or `review-only`. Do not upgrade it to delivery-ready.

## Family Improvement Axes

- GPCR: orthosteric/contact
  - Treat orthosteric pocket fit, salt-bridge consistency, hydrogen-bond geometry, and contact stability as the improvement axis.
  - Do not turn this into a broad GPCR expansion claim.
- ion_channel: membrane/charge/geometry
  - Treat membrane-aware placement, charge balance, pore or vestibule geometry, and state-aware contacts as the improvement axis.
  - Do not treat the membrane frame as a reason to widen claim scope.
- kinase: hinge/ATP-site
  - Treat hinge anchoring, ATP-pocket geometry, and shape/contact consistency around the active site as the improvement axis.
  - Keep the claim tied to the kinase pocket rules already used in the repo.

## Operating Rule

- The family scorecard is the first baseline for score-improvement discussion.
- The score direction must be explicit. Use `--lower-better` for binding-energy or distance-like scores where smaller values are better, and omit it for higher-is-better rankings.
- Delivery-ready wording for score uplift is only acceptable after the family packet is green on the four required checks above.
- If the scorecard is bundled, delivery-ready wording for that bundle is allowed only when every included scorecard reports `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`; a blocked scorecard may remain in a blocked/internal-review bundle as diagnostics, but it does not authorize delivery-ready wording.
- The absence of a bundled scorecard does not by itself change delivery-ready status here; it only means the scorecard cannot be used as evidence for score-uplift or architecture-accuracy claims.
- Provenance and bundle integrity are necessary, but they are not a substitute for the family scorecard.
- The scorecard, baseline comparison, and acceptance profile are scorecard-level only; they do not authorize broader platform claims or transporter promotion.
- Transporter stays `review-only`, `staged`, or `not yet claim-safe` until direct evidence closure exists.
- Do not use scorecard uplift language to argue for broad platform expansion.

## Where To Use This Note

Use this note together with:

- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_runbook.md`
- `docs/local_delivery_readiness_plan.md`
- `docs/local_delivery_engine_provenance.md`
