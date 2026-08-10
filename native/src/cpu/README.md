# CPU evaluator contract

The CPU evaluator is the first production implementation of
`betelgeuze.reference_physics/1.0.0`. It owns no external solver code and uses
only scalar binary64 C++ operations.

Evaluation order is frozen: input-order bonds, angles and torsions, followed by
lexicographic nonbonded pairs `i < j`. Forces are closed-form negative energy
gradients, accumulated serially into temporary SoA buffers and committed only
after the entire call succeeds. Numerical finite differences are tests, never
an execution path.

The implementation shares these semantic boundaries with the Rust oracle:

- canonical angstrom, radian, elementary-charge and kcal/mol units;
- Lorentz-Berthelot Lennard-Jones mixing;
- screened Coulomb and one quintic switch for both nonbonded components;
- explicit exclusions and pair scales without topology inference;
- orthorhombic `d - L*floor(d/L + 0.5)` minimum images;
- cutoff strictly below half every periodic box length;
- angle cosine clamp to `[-1+1e-12, 1-1e-12]`;
- deterministic errors for singular or non-finite force geometries.

Strict builds disable fast math and floating-point contraction. Repeated calls
to one binary are required to be bitwise identical. Because C++ and Rust
standard-library transcendental functions are not specified bit-for-bit across
all platforms, cross-language parity uses tight absolute/relative tolerances,
while algebraic frozen fixtures use exact IEEE-754 words.
