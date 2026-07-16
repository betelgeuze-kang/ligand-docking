# PR #66 bounded extraction matrix

Status: active extraction record; six bounded children merged

Observed at: 2026-07-15

- First-child extraction base: `origin/main@13af55c8f9251bc465d144b90d263efa5f5d01ea`
- Current reviewed `main`: `7dc025ed5a1f6f53e33d09bd457e9d6afa825808`
- Donor PR head: `83e4eb221377b03069b3d8546e7057f475b6be8d`
- Donor PR base: `fbf1a419b7926333b7e33f43bd751a9566b2b1d6`
- Common ancestor: `29aa6de8b15ed33a72519e4a7e06acf01e1ac356`
- Divergence measured at the extraction base: 192 commits on main, 12 commits
  on the donor side
- Divergence remeasured at current `main`: 249 commits on main, 12 commits on
  the donor side; common ancestor remains `29aa6de8b15ed33a72519e4a7e06acf01e1ac356`

This document records source ownership, dependency order, and bounded child-PR
decisions for PR #66. It is not scientific evidence. No donor commit is
approved for cherry-pick or bulk merge.

The donor base itself contains five commits and differs from the common
ancestor by 100 files, 11,119 insertions, and 688 deletions. Each retained
contract must therefore be reconstructed on current `main` from reviewed
source files and focused tests, without inheriting the donor base.
Because `origin/main` can advance after this snapshot, each child must be
updated and the dependency facts remeasured immediately before merge.

## Claim boundary

Source-level tests establish only the behavior of the named bounded contract.
Unless separate reviewed evidence changes them, all child PRs keep:

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`
- GPU parity, commercial readiness, and public benchmark validation
  unestablished

Parsing syntax does not establish dictionary conformance, molecular identity,
topology, assembly state, missingness interpretation, preparation readiness,
parameterability, physics support, runtime eligibility, or simulation
readiness. No child may modify a promotion flag to satisfy a test.

## Donor commit matrix

| Donor commit | Donor scope and size | Extraction buckets | Current-main dependency state | Decision and order |
|---|---|---|---|---|
| `d07dc5e8` | Mixed Engine v2 foundation; 247 files, +132,386/-104 | CIF syntax; shared topology/observation; exact PDB, SDF V2000, and SMILES parsing/writing; base mmCIF identity/missingness/assembly; C1-C4 alkane; harmonic diagnostics/minimization | Current main has bounded CIF syntax, identity/polymer-sequence, zero-occupancy, altloc, nonpoly identity, and component declaration children, but not the donor's general writer/topology/forcefield layers | Never cherry-pick. #73/#89/#90/#91/#94/#95 reconstruct accepted subsets; audit every remaining family independently against current canonical APIs |
| `18414be9` | Ordered opaque PDB `CONECT` preservation; 25 files, +4,118/-18 | `pdb_conect_declaration.py`, one corpus manifest, 15 PDB fixtures, and two focused tests | Missing `missingness.py`, `pdb_mmcif.py`, `pdb_writer.py`, `topology.py`, and three serialization APIs used by the donor | Defer until a current-main PDB parser/writer substrate exists. Preserve direction and duplicate declarations only; never infer bond order, covalence, or coordination |
| `be7fec2b` | Selected mmCIF zero-occupancy declarations; 18 files, +8,494/-21 | Atom-level and residue-level zero-occupancy envelopes, one corpus, six fixtures, and three tests | Bounded source-declaration subset merged in #90 without donor topology/writer/preparation | Extracted subset complete; broader donor semantics remain discarded unless separately justified |
| `1e32ead3` | Explicit mmCIF alternate-location selection; 14 files, +4,489/-5 | One altloc envelope, one corpus, six fixtures, and two tests | Bounded source-declaration subset merged in #91 without selection chemistry or preparation authority | Extracted subset complete; no chemical-correctness or preparation claim |
| `ad9c3780` | Strict nonpoly component and covalent `struct_conn` topology envelopes; 28 files, +11,918/-339 | Two topology contracts, two corpora, eight fixtures, six tests, and preparation/profile bridges | #94 provides identity and #95 provides selected atom/optional bond source declarations; no topology materialization or preparation bridge was accepted | Next extract selected `_struct_conn` identity relationships only; topology interpretation and preparation remain separate decisions |
| `e5842399` | Polymer component topology and polymer/nonpoly composition; 32 files, +11,798/-119 | Two new topology contracts and corpora plus changes to the preceding nonpoly contracts | Depends on the `ad9c3780` nonpoly contracts, polymer sequence, observation, serialization, topology, and preparation bridges | Defer until nonpoly topology is accepted; split polymer topology from mixed composition and re-run all predecessor tests |
| `83e4eb22` | Peptide preparation and SPICE evidence gates; 60 files, +31,841/-39 | Standard-L-peptide topology/completion/preparation family; separate SPICE C1-C4 quantum-reference, source-review, population, target, and observability family | Peptide work depends on preceding polymer topology. SPICE records are structurally separable but still need provenance and scientific review before any validation claim | Split into at least peptide and SPICE child families. Peptide follows polymer topology; SPICE evidence remains non-promoting and cannot authorize fitting, execution, or validation |

## Dependency order

```text
bounded CIF syntax [merged in #73]
  -> bounded identity/polymer-sequence projection [merged in #89]
     -> zero occupancy and altloc declarations [merged in #90/#91]
     -> nonpoly identity [merged in #94]
        -> selected component atom/bond declarations [merged in #95]
        -> selected struct_conn identity declarations [next]
        -> nonpoly topology interpretation [not authorized]
        -> polymer topology and mixed composition
           -> peptide completion and preparation

current-main canonical topology/serialization reconciliation
  -> exact SDF V2000 and SMILES parser children
  -> PDB parser/writer child
     -> ordered opaque PDB CONECT declaration child

reviewed alkane parameter/evaluation contracts
  -> harmonic diagnostics/minimization
  -> separately reviewed SPICE evidence and fitting inputs
```

## First child: bounded CIF syntax

Branch: `codex/v2-mmcif-syntax-contract`

PR #73 was restacked directly onto the first-child extraction base and merged
as `6ae6d1140c52402a3d375d74b4c34d3a3b7e9ddb` on 2026-07-15.

The first child starts from only two files added by
`d07dc5e84eba1df92316b455e2e9077bbdea9ef7`. Their donor blobs remained
unchanged through the PR head; the bounded current-main adaptations listed
below intentionally change the child copies:

| Path | Donor blob | Owned behavior |
|---|---|---|
| `betelgeuze_engine_v2/molecular/mmcif_syntax.py` | `82cd80d685fd3e36c8fb59600c14778fdbc80427` | Bounded token, scalar, loop, category-order, and stable syntax-error behavior for one supported CIF data block |
| `tests/unit/test_engine_v2_mmcif_syntax.py` | `8ec99a71f2f7524e6811d9345549741649222e9b` | Quote, comment, multiline, loop, resource-limit, and fail-closed error coverage |

The source has no direct third-party or internal Engine v2 imports. The test
uses the existing `pytest` development dependency and no fixture files.

Current-main adaptations are intentionally narrow:

- Describe the implementation as a supported, bounded, single-data-block CIF
  lexical/structural subset rather than a complete CIF or semantic mmCIF
  parser.
- Count `CRLF` as one physical line separator, report source lines correctly
  for CR-only input, and cover both behaviors with regression tests.
- Add the focused test to the current hosted Python 3.10-3.12 canonical
  workflow and exercise one direct parse after installing the built wheel.

Explicitly excluded from this child:

- donor `molecular/__init__.py` exports
- capabilities or promotion-state changes
- corpus manifests and coordinate fixtures
- donor architecture, commercial-roadmap, or migration documents
- donor `.github/workflows/ci-engine-v2-cpu.yml`
- PDB, SDF, SMILES, semantic mmCIF, alkane, harmonic, peptide, or SPICE code

## First-child verification

| Surface | Required evidence |
|---|---|
| Focused contract | `python -m pytest -q tests/unit/test_engine_v2_mmcif_syntax.py` |
| Canonical regression | Existing `ci-engine-v2-main` focused suite, including H2 docking semantics, H5 reference physics, H6 packaging guards, and H7 external-baseline contracts |
| Architecture and syntax | `compileall`, `tools/check_engine_v2_architecture.py`, workflow YAML parse, and `git diff --check` |
| Packaging | Build the isolated Engine v2 wheel, install it without the source checkout, import `parse_cif_block`, and parse one bounded data block |
| Remote | Hosted Python 3.10, 3.11, and 3.12 canonical matrix |

No later bucket is authorized by completion of the first child. Every later
child requires a fresh current-main dependency and claim-boundary review.

Actual first-child evidence:

- focused bounded CIF syntax contract: `37 passed`
- current canonical Engine v2 suite including H5/H6/H7: `167 passed`
- workflow trust-boundary regressions: `11 passed`
- final hosted Python 3.10, 3.11, and 3.12 checks: passed
- Ruff, architecture guard, compileall, workflow YAML parsing, wheel install and
  outside-checkout parse, and diff check: passed

## Bounded child ledger

| PR | Merge SHA | Accepted scope |
|---|---|---|
| #73 | `6ae6d114` | single-block CIF lexical/structural subset |
| #89 | `eeed0433` | entry/entity/asym/polymer-sequence identity projection |
| #90 | `57f61a64` | zero-occupancy source declarations |
| #91 | `41f78162` | alternate-location source declarations |
| #94 | `7dc4e5de` | nonpoly entity/component/asym/instance identity carrier |
| #95 | `e570cd70` | selected component atom and optional bond source declarations |

## Remaining extraction decisions

PR #66 remains draft/open and is not a merge candidate. The next child must be
chosen only after re-auditing its dependencies against current `main@7dc025ed`.
The current order remains:

1. selected `_struct_conn` identity relationships without bond-order chemistry,
   coordinate materialization, or topology authority;
2. separately review whether any nonpoly topology interpretation is retained;
3. polymer topology before mixed composition and peptide preparation;
4. peptide completion/preparation only after those topology contracts;
5. PDB/SDF/SMILES, alkane physics, and SPICE evidence as separately owned
   families with focused workflows.

No donor commit is approved for cherry-pick. Donor #66 may be closed as
superseded only after each retained family has a linked current-main child or
an explicit discard record.
