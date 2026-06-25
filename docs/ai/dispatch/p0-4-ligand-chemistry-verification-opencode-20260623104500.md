# Worker Slice: P0-4 ligand chemistry verification and repair

Web access: disabled.

## Goal
Verify and repair the current P0-4 ligand chemistry changes without broadening scope. The repository currently has uncommitted changes that add RDKit ChemicalFeatures/tautomer/salt/chirality metadata under `betelgeuze_engine/chemistry`, route those fields through topology validity metadata, and update ONSPS donor/acceptor roles.

## Scope
- Keep changes local and focused to ligand chemistry/topology/ONSPS tests or expectations.
- Do not stage, commit, push, delete, or mutate external state.
- Do not read or print `.env*`.
- Preserve existing P0-2 release CI changes.

## Likely Files
- `betelgeuze_engine/chemistry/ligand_states.py`
- `betelgeuze_engine/topology/ligand.py`
- `betelgeuze_engine/topology/validity.py`
- `betelgeuze_engine/backmapping/onsps.py`
- `tests/unit/test_ligand_chemistry_states.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_run_ligand_backmapping_scoring.py`
- `tests/unit/test_engine_refinement_roadmap.py`

## Tasks
1. Run focused ligand chemistry and topology/ONSPS tests.
2. Fix failures caused by the new typed chemistry-state contract.
3. Ensure RDKit ChemicalFeatures, canonical tautomer metadata, charged atom/salt metadata, unassigned chirality blockers, and ONSPS role evidence are directly asserted.
4. Run ruff on touched Python files.
5. Return a concise summary with changed files, tests run, failures if any, and blockers.

## Verification Commands
- `python3 -m pytest -q tests/unit/test_ligand_chemistry_states.py`
- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py -k "topology_claim_metadata_carries_ligand_product_validity_status or onsps_backmap_evidence_schema_and_fail_closed_geometry or hbond_evidence_uses_onsps_roles_distance_and_angle"`
- `python3 -m pytest -q tests/unit/test_run_ligand_backmapping_scoring.py tests/unit/test_engine_refinement_roadmap.py`
- `python3 -m ruff check betelgeuze_engine/chemistry betelgeuze_engine/topology/ligand.py betelgeuze_engine/topology/validity.py betelgeuze_engine/backmapping/onsps.py tests/unit/test_ligand_chemistry_states.py`
