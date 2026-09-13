The `prepared_gromacs_coordinate_derivation_v1` input records a supplied local
coordinate derivation while preserving the complete v1/v2/v3 parent. It is
accepted by `load_prepared_gromacs_components`, the existing prepared cross CLI,
and the rigid-pose consumer with request reuse and durable resume.

A tool-generated PDB/SDF/GRO should use this explicit profile when only
coordinates changed. The historical v1/v2/v3 profiles retain their original
published-source assumptions and byte-for-byte behavior; they cannot infer a
file's actual origin. This reader does not run preparation, a solver, or a
method command. It does not admit data for training or certify physical quality.

The request has exactly five fields:

| Field | Required content |
|---|---|
| `schema_version` | `prepared_gromacs_coordinate_derivation_v1` |
| `parent_input` | Complete, inline `prepared_gromacs_components_v1`, v2 or v3 request |
| `derived_coordinates` | Exactly `protein_pdb`, `ligand_sdf`, `ligand_gro` source references |
| `source_declarations` | Original frame, parameter and charge declarations, with a distinct `prepared_state_id` |
| `coordinate_derivation` | The exact method record below |

Each source reference is the existing object with `path` (absolute regular
file), `sha256` (lowercase), and nonblank `source_id`. The existing 16 MiB
per-source capacity applies, including method evidence. Nothing is downloaded.
Parent and method references stay inline so the existing checkpoint mechanism
can bind every transitive source without trusting an unexpanded manifest file.

The method record has exactly these fields:

| Field | Required content |
|---|---|
| `schema_version` | `prepared_coordinate_derivation_record_v1` |
| `parent_input_sha256` | SHA256 of the parent canonical JSON described below |
| `derived_coordinate_sha256` | Hash mapping for all three derived coordinate source keys |
| `prepared_state_id` | The new state declaration, matching the outer request |
| `tool` | Exactly nonblank `name` and `version` |
| `operation` | Nonblank description of the declared operation |
| `settings` | Nonempty object of explicit settings, with finite JSON values |
| `evidence` | Exactly `method`, `execution`, and `model`, each a nonempty file reference |
| `changed_atom_indices` | Exactly `receptor` and `ligand`, each a sorted, unique list of zero-based integer indices |
| `external_solver_called` | Explicit boolean claim about the upstream operation |

The method file can hold the script, the execution file the run record, and the
model file the parameter/model description. Their bytes are hash-checked before
and after loading; the reader does not establish that those files prove an
actual execution. `upstream_tool_execution_verified` remains false even when
`external_solver_called` is declared true. No method text is interpreted as code.

Canonical JSON here means UTF-8 encoding of
`json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)`
with Python's default ASCII escaping. The record hash is computed the same way
and included in each resulting canonical molecular system. Consequently,
changing declared settings changes system identity even if coordinates match.

Both the parent and child pass the existing explicit topology, atom mapping,
charge, mass, geometry and SDF/GRO consistency checks. Only PDB atom XYZ
columns, SDF V2000 atom XYZ columns and GRO atom coordinate tokens can differ.
All remaining bytes—including atom names/order, occupancy, molecule header,
bond/stereo/charge annotations, inert SDF data fields and GRO box—must match.
No topology, hydrogen count, chemical state, isotope, parameter, frame or
registration change is supported. A derivation cannot have a derived parent in
this version. At least one actual canonical atom coordinate must differ.

The reader compares every canonical atom to its parent and rejects inaccurate,
omitted, repeated, Boolean, negative or out-of-range change indices. It reports
changed hydrogens and heavy atoms separately, plus maximum displacement in Å.
Unchanged hydrogen coordinates retain the parent's declared origin; changed
hydrogens receive a local or mixed origin as appropriate. Parent canonical
system hashes are retained in the child provenance. Full parameter lists must
remain exactly equal.

`coordinates_generated=false` and `external_solver_called=false` describe this
ingestion operation. `coordinates_generated_upstream=true` denotes the
observed coordinate change in the supplied child; the separate upstream solver
boolean remains a caller declaration. `coordinate_origin` explicitly identifies
local computational coordinates, not experimental observations. These fields do
not establish minimizer convergence, a correct force field, an acceptable pose,
or scientific/production qualification. Existing claim-policy flags stay false.

The synthetic tests include source-mutation rejection, coordinate-only checks,
legacy parent profiles, actual CPU consumer failures/denominators, and completed
resume with transitive parent/method/output mutation rejection. They execute no
minimization and use no experimental activity values or protected evaluation
data. Original scientific and numerical failures remain separate evidence.
