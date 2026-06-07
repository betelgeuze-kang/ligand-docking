# T1331_5AT Materialized Coordinates

- objects: `1`
- pass/blocked: `1/0`

| object | coordinate | sha256 match |
| --- | --- | --- |
| `current_chain_A` | `casp17/3d_molecular_object_coordinate_materialized_library/T1331_5AT/current_chain_A/coordinates/T1331_chain_A.pdb` | `true` |

## Claim Boundary

CASP17 3D molecular object coordinate materialized library only. It materializes each source coordinate model from the dry-run plan into a protein-name/object folder with sha256 verification. The default symlink mode avoids duplicating raw coordinate bytes. It does not alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.
