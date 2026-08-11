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
require bit-identical rows.

`hip_safe` and `hip_fast` instantiate the frozen device formula as separately
compiled providers with separate symbols and persistent receptor/ligand device
state; neither lane calls or relabels the other. Each fixed64 kernel uses one
serial thread per candidate. `hip_safe` is available only in an exact ROCm
6.0.2 build with an explicitly qualified architecture and a compatible runtime
device. `hip_fast` uses the explicit native HIP build and remains on strict
math flags until safe parity is qualified; performance math must be enabled by
a later, separately reviewed profile.

The device suite compares every typed failure/count exactly, uses a frozen
binary64 tolerance for score terms, and requires bit-identical same-device
repeats. No backend fallback, performance claim, execution authority, or
product authority is created here.
