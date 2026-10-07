# Opt-in parent-distance shape experiment

This research-only profile adds E_shape = lambda/(2M) sum_(i<j) (r_ij-r0_ij)^2 to an explicitly named unchanged base evaluator. All original ligand atoms, including hydrogen, participate with uniform 1/M pair weighting, M=N(N-1)/2. The original supplied parent is the immutable reference. Lambda is restricted to the predeclared values 0, 100, 1000 kcal/mol/Angstrom^2. There is no alignment, receptor-dependent selection, fitted target or crystal replacement.

The penalty permits rigid translation and rotation but resists whole-ligand shape change, including induced-fit torsions. It is reflection-blind and does not enforce chirality or chemical correctness. It is not physical internal energy, not a hard strain constraint and not a guarantee of passing the unpenalized internal-energy gate.

## API and boundaries

`cpu_refinement_shape_v1.cartesian.prepare_reference(system, binding)` validates the complete 2..256 atom source identity and single connected covalent graph, and copies original coordinates, all pair distances, provenance and protocol source identity. `minimize_shape` and `verify_shape` require an explicit reference, strength, and `base_profile` (`fourier` or separately installed `linear_angle`). They preserve the selected base profile's parameter and admission contracts; no parameter conversion occurs. The linear-angle base requires its separate merged package.

Reference/contract documents use canonical finite binary64 values and require trusted expected digests for loading. Run identity binds the reference document/digest, contract digest, lambda, original topology/atom order, base identity, configuration, implementation closure and environment. Resume never resets the reference. Source hashes authenticate local byte identity, not experimental provenance or authorization.

Positive-lambda trials reject separations below 1e-8 Angstrom and any nonfinite intermediate/output. Domain failures consume the combined attempt, with separately retained base and shape work. Lambda zero preserves original base energy/force arrays and decisions without adding zero tensors, dispatching again or applying positive-lambda trial distance checks. Reference admission still applies to every arm.

## Evidence and accounting

A separately versioned observation persists the exact original base observation, separate restraint force vector and penalty, combined force vector and total, and explicit maximum per-atom Euclidean force norms for base and augmented objectives. Internal and cross components remain unpenalized. `internal_energy_gate_passed` uses the original cross-policy maximum internal increase and original unpenalized internal energy. This flag alone does not admit a pose.

The solver uses the augmented objective and forces. Positive-lambda stationarity is reported as `restrained_force_converged`; the result separately records unpenalized stationarity. Force cancellation does not establish base convergence. A four-step budget endpoint remains unconverged.

Existing force-call counters describe combined objective invocations. Added `base_force_calls`, `failed_base_force_calls`, `shape_calls`, `failed_shape_calls` and `augmented_observation_failures` counters distinguish base success from subsequent augmentation failure. A zero-strength arm performs no shape calculation. Graph/base dispatch remains the existing implementation. Shape work is included in the nested force/objective duration. Unfinished durable reservations remain unknown and are never automatically retried; completed shape counters are not a claim about an unknown pending call.

The existing Cartesian state-transition algorithm and execution loop are reused through an optional profile/observation seam. Default schemas and numerical behavior are unchanged; the new profile owns distinct state, observation, journal, checkpoint, binding and result schemas. Read-only replay performs no graph, base, or shape evaluation. Old/new schema reuse, source/reference/lambda drift, mismatched restart vectors and unknown reservations fail closed.

## Validation and execution gate

Synthetic tests cover independent force differences, invariance, reflection blindness, connectivity and atom identity, serialization forgery/mutation, numerical overflow, boundary distances, 2/256 atoms, lambda-zero trajectory parity, failure counts, restart/replay and unchanged default result/journal bytes. Synthetic validity is not scientific validation.

Real-case dispatch remains separately gated on independent review, the merged 180-degree implementation, verified installed source closure and a frozen execution binding. The preregistered pilot uses identical starts, parameters and four accepted-step / 17-attempt maximum budgets across lambda=0/100/1000. Report every arm and its unpenalized/penalty components, forces, geometry, cost and termination without retrospective lambda selection. No default activation, pose-selection admission, affinity claim or scientific promotion is provided.
