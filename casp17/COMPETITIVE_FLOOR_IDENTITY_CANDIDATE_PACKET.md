# CASP17 Competitive-Floor Identity Candidate Packet

- generated: `2026-05-28T02:16:33+09:00`
- identity_candidate_status: `awaiting_candidate_sources`
- apply_mode: `dry_run`
- intake rows ready/awaiting: `0/15`
- source candidates ready/blocked/total: `0/55/55`
- operator preflight/import: `blocked`/`blocked`
- applied intake rows: `0`
- first open: `priority_001_REQUIRED_MONOMER_001` `awaiting_candidate_source`
- next action: fix blocked local candidate rows until a cleared non-current historical target is ready

## Intake Candidate Rows

| priority | dropzone | scope | status | proposed benchmark | proposed target | source | blockers | next action |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `priority_001_REQUIRED_MONOMER_001` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 2 | `priority_002_REQUIRED_MONOMER_002` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 3 | `priority_003_REQUIRED_MONOMER_003` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 4 | `priority_004_REQUIRED_MONOMER_004` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 5 | `priority_005_REQUIRED_MONOMER_005` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 6 | `priority_006_REQUIRED_MONOMER_006` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 7 | `priority_007_REQUIRED_MONOMER_007` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 8 | `priority_008_REQUIRED_MONOMER_008` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 9 | `priority_009_REQUIRED_MONOMER_009` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 10 | `priority_010_REQUIRED_MONOMER_010` | `monomer` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:35` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 11 | `priority_011_REQUIRED_COMPLEX_001` | `complex` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:20` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 12 | `priority_012_REQUIRED_COMPLEX_002` | `complex` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:20` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 13 | `priority_013_REQUIRED_COMPLEX_003` | `complex` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:20` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 14 | `priority_014_REQUIRED_COMPLEX_004` | `complex` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:20` | fix blocked local candidate rows until a cleared non-current historical target is ready |
| 15 | `priority_015_REQUIRED_COMPLEX_005` | `complex` | `awaiting_candidate_source` | `-` | `-` | `-` | `blocked_source_candidates:20` | fix blocked local candidate rows until a cleared non-current historical target is ready |

## Claim Boundary

Local competitive-floor identity candidate packet only. It inspects local historical benchmark/operator manifests and proposes intake values only when a source row already has a non-placeholder historical target identity and no-leak/operator clearance. It does not choose targets, clear provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP. It writes intake CSV values only when --apply is explicitly provided.
