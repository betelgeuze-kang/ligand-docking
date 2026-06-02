# T2313_P66 Materialized Coordinates

- objects: `2`
- pass/blocked: `2/0`

| object | coordinate | sha256 match |
| --- | --- | --- |
| `current_chain_A` | `casp17/3d_molecular_object_coordinate_materialized_library/T2313_P66/current_chain_A/coordinates/T2313_chain_A.pdb` | `true` |
| `massivefold_model1_candidate` | `casp17/3d_molecular_object_coordinate_materialized_library/T2313_P66/massivefold_model1_candidate/coordinates/model.cif` | `true` |

## Claim Boundary

CASP17 3D molecular object coordinate materialized library only. It materializes each source coordinate model from the dry-run plan into a protein-name/object folder with sha256 verification. The default symlink mode avoids duplicating raw coordinate bytes. It does not alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.
