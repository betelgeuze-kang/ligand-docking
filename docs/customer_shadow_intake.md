# Customer Shadow Intake

This intake lane records privacy-preserving customer shadow evidence without taking custody of private customer raw data.

## Status Gate

- Minimum evidence before the status gate can be ready: 3 reviewed `customer_shadow` rows.
- Mock rows may be used for tests and dry runs, but `mock_fixture` and `redacted_mock_fixture` rows do not count toward the minimum.
- The status gate never promotes commercial readiness claims. It only reports whether the intake schema and reviewed metadata rows are complete.

## Required Intake Values

Use `config/customer_shadow_evidence_intake_template.csv` as the header template. Each real row must keep:

- `row_kind`: `customer_shadow`
- `raw_data_custody`: `customer_retained`
- `customer_retained_raw_data`: `true`
- `redistribution_allowed`: `false`
- `raw_data_stored_in_repo`: `false`
- `derived_metadata_fields`: includes `case_domain`, `input_size_class`, `runner_profile`, `result_metric_summary`, and `artifact_fingerprint`
- `anonymized_result_summary`: derived summary only, with no emails or private identifiers
- `reviewer_signoff_status`: `approved`
- `reviewer_id`, timezone-aware ISO `reviewed_at_utc` such as `2026-06-29T00:00:00Z`, and a 64-character hex `source_artifact_fingerprint`

Do not add customer names, emails, patient IDs, subject IDs, raw data paths, raw data URIs, private payloads, private raw data, PII, author codes, or similar private columns.

The PM priority queue treats schema-only status as blocked. The customer shadow item is ready only when the status gate reports three real reviewed `customer_shadow` rows; even then, paid-pilot wording remains locked until the release gates agree.

## Local Check

Write outputs under `.betelgeuze/` while collecting evidence:

```bash
python3 tools/build_customer_shadow_evidence_status.py \
  --intake-csv config/customer_shadow_evidence_intake_template.csv \
  --out-json .betelgeuze/customer_shadow_evidence_status_current.json \
  --out-csv .betelgeuze/customer_shadow_evidence_status_current.csv \
  --out-md .betelgeuze/customer_shadow_evidence_status_current.md
```

The default template is expected to block until three real reviewed customer-shadow metadata rows are available.
