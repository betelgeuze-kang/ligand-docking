# Engine V2 public redocking 300-case contract

## Scope

This is a frozen, offline evaluation contract plus a local execution tool. The
library contract does not download structures or publish results. The tool
requires operator-supplied copies of the hash-verified public archive, the
published 308-case identifier document, and an exact GNINA binary.

The source is the public PoseBusters paper data:

- paper: `https://doi.org/10.1039/D3SC04185A`
- data record: `https://zenodo.org/records/8278563`
- source license: `CC-BY-4.0`
- paper-data archive SHA-256:
  `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`
- published 308-case identifier document SHA-256:
  `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`

The journal reports a 308-case subset after excluding crystal-contact cases
from the original 428-case archive. The Engine V2 contract uses exactly 300 of
those 308 cases to remain within the stated 100–300-case evaluation envelope.
Selection is performed before results by sorting
`SHA256("betelgeuze-engine-v2-posebusters-300-v1:" + case_id)` and retaining the
lowest 300 keys. The final case list is stored in source and protected by its
own SHA-256.

## Comparable-input and output policy

Every engine must provide exactly one ordered row for every frozen case:

- `engine_v2`
- `vina`
- `gnina`

Each successful row contains exactly five score-ranked poses, each with:

- symmetry-aware heavy-atom RMSD in the fixed receptor frame;
- geometric validity;
- chemical validity;
- exact pose-artifact SHA-256.

Each failed row retains a failure code and runtime. Missing poses turn the
entire engine/case row into a failure, so Top-3 or Top-5 cannot silently use a
smaller candidate budget.

The engines share the frozen receptor, starting conformer, crystal-ligand
pocket source, case seed, one enforced CPU, and five retained output poses.
Their exact pocket geometry is not equal: Engine V2 uses a sphere derived from
the crystal ligand, while Vina and GNINA use the corresponding ligand-derived
axis-aligned autobox. Their internal search effort is also not equal: Engine V2
uses five proposals, while the external engines use their own
`exhaustiveness=1` search. The report therefore records
`same_ranked_pose_count: true` and `same_pocket_source: true`, but keeps
`same_pocket_geometry`, `same_search_effort_budget`, and
`search_effort_comparable` false. Paired recovery deltas are descriptive under
these explicit settings, not equal-region or equal-compute performance claims.

Runtime covers each engine invocation through ranked-pose serialization and
stops before the shared PoseBusters evaluator. Torch intra-op and inter-op
threads are both fixed to one for Engine V2, and both external modes receive
`--cpu 1`. The external timeout is part of the policy, engine identity, and
per-case cache receipt; changing it invalidates cached external rows. Runtime
deltas remain descriptive because the search regions and algorithms differ.

## Required outputs

The scorecard emits deterministic percentile-bootstrap confidence intervals
for:

- symmetry-aware Top-1, Top-3, and Top-5 RMSD success at 2 Å;
- Top-1, Top-3, and Top-5 joint RMSD plus geometric/chemical validity success;
- top-pose geometric and chemical validity;
- full-case failure rate;
- median runtime;
- heavy-atom size subgroups: 1–20, 21–40, and 41+;
- rotor subgroups: 0, 1–4, and 5+;
- paired Engine V2 deltas against Vina and GNINA for recovery, valid recovery,
  failure rate, and runtime.

Heavy-atom count and rotor subgroups are frozen from each source-bound ligand
artifact using RDKit 2022.09.5 and strict
`Lipinski.NumRotatableBonds`. The 300 profile rows and each ligand-artifact
SHA-256 are protected by a separate aggregate SHA-256. Engine V2 admission and
its chemistry-aware rotor policy remain separate execution outcomes; an
unsupported macrocycle must become a failure row rather than being removed from
the denominator.

The report binds exact engine version, full Engine V2 Python source-closure or
external binary SHA-256, command, CPU/timeout policy, cohort fingerprint, policy
fingerprint, all 900 engine/case rows, profiles, and metric rows. Evaluator or
artifact-I/O failures abort the run instead of being counted as engine
failures.

## Local execution

The evaluator is frozen to RDKit 2022.09.5 and PoseBusters 0.3.1. Install the
older RDKit distribution first and install PoseBusters without dependency
resolution so pip does not replace it with a newer `rdkit` distribution:

```bash
python -m pip install numpy==1.26.4 pandas==2.3.3 PyYAML==6.0.3 \
  rdkit-pypi==2022.9.5
python -m pip install --no-deps posebusters==0.3.1
```

Run against operator-supplied source artifacts and a local GNINA executable:

```bash
python tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --gnina /path/to/gnina \
  --output-root .betelgeuze/public-redocking-300
```

`--limit` creates only a non-claimable partial summary. A complete run creates
all 900 rows and `public-redocking-report.json`. Per-case receipts make a run
resumable while rejecting changed input bytes, commands, implementation hashes,
or source identities.

## Current boundary

No raw structure, prepared input, external-engine output, Engine V2 output, or
benchmark result is committed by this change. A constructed report records
`benchmark_executed: true` because all 900 failure-complete rows exist, while it
continues to state:

```text
scientifically_validated: false
benchmark_validated: false
product_qualified: false
claim_safe: false
```

Actual execution is local under the frozen policy. The runner verifies and
materializes the archive itself, retains per-case command/input/result receipts,
and supports resumable partial runs. A completed report still requires
scientific review before any claim.
