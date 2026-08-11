# Native docking kernel boundary

ABI 1.5 introduces a persistent Engine V2 ScorerV1 handle shared by the
qualification C++ lane and the product Rust CPU lane. Its frozen batch contract
is candidate-major float64 SoA with exactly 64 slots. Inactive upstream rows are
not deleted; they return `UPSTREAM_NOT_ADMITTED`, so denominator and failure
accounting remain intact.

The term order is:

1. typed van der Waals
2. electrostatics
3. directional hydrogen bond
4. hydrophobic contact
5. desolvation proxy
6. torsion energy
7. ligand strain
8. weak pocket prior

Context creation deep-copies the receptor, ligand reference geometry, typed
atom parameters, donors, exclusions, rotors, configuration, and four evidence
identity digests. A batch writes no scientific output until all descriptor and
backend checks succeed. Candidate-local geometry/capacity failures are rows,
not batch aborts.

`cpp_cpu_reference` independently reimplements the frozen formula for
qualification only. `rust_cpu` calls the canonical Rust ScorerV1 core through a
private versioned provider. Synthetic parity requires equal status, failure,
pair/contact counts, and tight binary64 term/total agreement; repeated runs
require bit-identical rows. `hip_safe` and `hip_fast` currently fail closed at
this new scorer boundary until their real kernels and parity suites land. No
backend fallback and no execution or product authority are created here.
