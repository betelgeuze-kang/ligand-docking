# Source-preserving linear-equilibrium harmonic angles, opt-in v1

This research-only Python API preserves GROMACS funct-1 source energy
`E = 0.5 * k * (theta - pi)^2`, with the original angle constant in
kcal/mol/radian². A source constant in kJ/mol/radian² is divided by 4.184.
It does not replace that energy with a finite Fourier/cosine potential,
apply a Cartesian restraint, project the coordinates, or claim validation.

## Explicit model and ownership

`betelgeuze_product.cpu_refinement_linear_angle_v1.parameters` exposes:

- `LinearHarmonicAngleParameter(i, j, k, equilibrium_radians, force_constant_kcal_per_mol_radian2)`:
  exact `math.pi` equilibrium, distinct bounded atom indices, positive finite constant
- `LinearAngleParameters(base_parameters, linear_angles)`: a nonempty tuple of
  these rows and an unchanged `FourierParameters` model containing all remaining
  ordinary angles and original signed proper/ordered improper/pair terms
- New canonical schema `cpu_prepared_linear_harmonic_parameters/1.0.0`.
  Fingerprints include both the base model and every source linear angle

Complete combined graph-implied angle coverage is checked before numerical
work. Missing/extra/duplicate/overlapping rows are rejected; the angle-incomplete
base is not an admissible standalone legacy model. Ordinary harmonic rows retain
`0 < theta0 < pi`; the legacy serializers and evaluators reject the new type.
The public Cartesian profile also requires the new model and environment types.

`evaluation.LinearAngleInternalEvaluator` and `LinearAngleFixedEvaluator` use
new internal/fixed evaluator identities. `LinearAngleEnvironment` reuses the
unchanged, explicitly declared Fourier cross physics but binds its
`ligand_base_parameters_sha256` field to the **whole new model** fingerprint.
A base-only hash is rejected. Source admission still owns molecular source
selection, mapping and completeness; this numerical API does not establish it.

`cartesian.minimize_cartesian` and `verify_cartesian` are separate opt-in wrappers
around the existing shared CPU SD/L-BFGS executor. Supply an explicit new input
binding (`cpu_prepared_linear_harmonic_cartesian_input/1.0.0`), original coordinate
hash, candidate ID and prepared protocol hash. Existing bounded limits remain
17 objective attempts, 4 accepted steps, 3 backtracks and 2 restart checks.
The owning binding/result schemas and evaluator identity are distinct from
Fourier v1. All shared and new implementation files are source-bound. The one
private arithmetic extraction changes the Fourier module source hash, so old
source-bound runs cannot be silently resumed or resealed after upgrading.
No new default route, CLI campaign loader, projected solver or constraint
experiment is enabled by this package.

## Endpoint mathematics and numerical domain

For normalized nonzero bond vectors u,v, use q = |u+v|². Near the antiparallel
equilibrium, E/k = 2 asin(sqrt(q)/2)² has the regular expansion
`q/2 + q²/24 + q³/180 + q⁴/1120 + q⁵/6300 + ...`.
At q <= 1e-4, the five-term series has an absolute energy/k remainder below
4e-29 (well below binary64 rounding); outside it, evaluate
`0.5 * atan2(|u cross v|, -u dot v)^2`.
Branches are selected before the regular norm calculation to avoid a dormant
singular derivative contaminating exact-endpoint higher derivatives.

At theta=theta0=pi the energy and Cartesian gradient are zero, with a finite
bending curvature. No arbitrary angular direction is chosen. This is the
removable limit of the source harmonic energy, not a zero-force dead zone.

Still unsupported: bond norm <=1e-12 Å, nonfinite coordinates/norms,
parallel vectors at the incompatible theta=0 endpoint (sine <=8 binary64 eps),
ordinary interior-equilibrium collinearity, and undefined torsion/improper
planes. Angle support does not make a collinear dihedral defined. The profile
is CPU binary64, nonperiodic and bounded to the existing single-model domain.
Higher-order derivatives are tested at the primitive endpoint only; this is
not a general force-field Hessian qualification.

## Evidence and gates

Owning synthetic tests cover analytic energy/forces, arbitrarily small bends,
exact endpoint/curvature, mixed batches, symmetry, schema separation, complete
coverage, invalid geometries, fixed environment identity, both Cartesian
algorithms, restart/verification and implementation drift. CI includes an
isolated installed-wheel smoke outside the checkout. Independent high-precision
comparisons must precede real-molecule runs; successful synthetic tests and
parameter construction are not scientific qualification of a molecular pilot.

References: [GROMACS harmonic and linear angle definitions](https://manual.gromacs.org/documentation/2022/reference-manual/functions/bonded-interactions.html).
The separately documented Cartesian Linear Angle potential is a different model.
