# Community license owner decision record v1

No license is changed by this document. The existing repository `LICENSE`
remains controlling until the owner records and applies an explicit decision
after a third-party audit.

## Candidate models

- MPL-2.0 native engine core plus Apache-2.0 benchmark and verifier tools;
- Apache-2.0 core;
- AGPL-3.0 plus a separate commercial license;
- an interim source-available community evaluation license;
- remain proprietary.

## Required audit

1. Inventory first-party and third-party source, datasets, model weights,
   binaries, templates, and generated artifacts.
2. Decide whether hosted service use must trigger source-sharing.
3. Decide whether proprietary embedding is an intended revenue source.
4. Define engine, benchmark, enterprise-service, UI, and model-weight
   boundaries.
5. Review patents and pending applications.
6. Choose CLA, DCO, assignment, or no external code acceptance.
7. Add package-level license files, SPDX metadata, and
   `THIRD_PARTY_NOTICES`.
8. Confirm that the chosen terms permit the intended independent build,
   benchmark, modification, patch submission, and publication of complete
   result and failure rows.

## Owner decision fields

```text
decision:
effective_date:
covered_directories_and_packages:
excluded_commercial_components:
contributor_terms:
model_weight_terms:
third_party_audit_reference:
legal_review_reference:
owner_signature:
```

Until all fields are completed and the license change is separately reviewed,
community reproduction tooling is only a technical receipt format and does not
grant a right to run or modify the proprietary software.
