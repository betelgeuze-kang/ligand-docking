# T1331_5AT / current_chain_A Coordinate

- status: `coordinate_materialized`
- mode: `symlink`
- source: `casp17/targets_current/T1331_5AT/objects/chain_A/models/T1331_chain_A.pdb`
- materialized: `casp17/3d_molecular_object_coordinate_materialized_library/T1331_5AT/current_chain_A/coordinates/T1331_chain_A.pdb`
- sha256 match: `true`
- blockers: `-`

## Claim Boundary

CASP17 3D molecular object coordinate materialized library only. It materializes each source coordinate model from the dry-run plan into a protein-name/object folder with sha256 verification. The default symlink mode avoids duplicating raw coordinate bytes. It does not alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.
