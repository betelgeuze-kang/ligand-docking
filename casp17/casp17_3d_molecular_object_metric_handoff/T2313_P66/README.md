# P66 Metric Handoff

- protein key: `T2313_P66`
- target: `T2313`
- objects ready/blocked/total: `2/0/2`
- metric requirements: `15`
- metric names: `DockQ|GDT_HA|GDT_TS|ICS|IPS|MolProbity|RMSD|TM-score|lDDT`

## Objects

| object | family | status | metrics | handoff |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `monomer_domain` | `ready_review_only` | `GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity` | `casp17/casp17_3d_molecular_object_metric_handoff/T2313_P66/current_chain_A/METRIC_HANDOFF.md` |
| `massivefold_model1_candidate` | `protein_complex` | `ready_review_only` | `GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity|DockQ|ICS|IPS` | `casp17/casp17_3d_molecular_object_metric_handoff/T2313_P66/massivefold_model1_candidate/METRIC_HANDOFF.md` |

## Claim Boundary

CASP17 3D molecular object metric handoff only. It maps organized 3D object folders to win-tier metric requirements for review. It does not copy model coordinates, compute native accuracy, serialize a CASP author code, claim strict-blind competitive proof, or submit to CASP.
