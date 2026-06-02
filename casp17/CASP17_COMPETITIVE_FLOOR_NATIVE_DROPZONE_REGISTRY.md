# CASP17 Competitive Floor Native Dropzone Registry

- status: `awaiting_native_files`
- dropzones primary/replacement/total: `3/1/4`
- readmes/native present/blocked: `4/0/4`
- coordinate copies/unexpected: `0/0`
- proof eligible/author serialized: `0/0`
- first blocked: `H1319` `native_pdb_missing`
- next action: place the operator-cleared native PDB at the expected native_dropzone_pdb path

## Claim Boundary

Local CASP17 native dropzone registry only. It merges primary and replacement workorder native dropzones, checks README/native-file presence, and flags unexpected coordinate copies. It does not fetch native structures, clear no-leak provenance, compute metrics, serialize CASP author code, or submit to CASP.

## Dropzones

| rank | source | target | replace | readme | native | unexpected | blockers | next action |
| ---: | --- | --- | --- | --- | --- | ---: | --- | --- |
| 1 | primary | `H1319` | `-` | present | missing | 0 | native_pdb_missing | place the operator-cleared native PDB at the expected native_dropzone_pdb path |
| 2 | primary | `H1321` | `-` | present | missing | 0 | native_pdb_missing | place the operator-cleared native PDB at the expected native_dropzone_pdb path |
| 3 | primary | `H2324` | `-` | present | missing | 0 | native_pdb_missing | place the operator-cleared native PDB at the expected native_dropzone_pdb path |
| 4 | replacement | `H1311` | `H1319` | present | missing | 0 | native_pdb_missing | place the operator-cleared native PDB at the expected native_dropzone_pdb path |
