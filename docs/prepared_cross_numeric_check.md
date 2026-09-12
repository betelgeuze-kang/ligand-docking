# Saved prepared report numerical check

Run from a source checkout with Python 3.10 or newer. The checker uses only the standard library and does not import the engine:

```sh
python3 -I -S -B tools/product/verify_prepared_cross_numerics.py \
  --report saved-report.json --output new-numeric-check.json
```

The output must be a new file. Exit 0 means all requested rows passed the arithmetic comparison; exit 2 means at least one row failed or was not compared. Malformed top-level inputs raise an error. Input and checker SHA-256 digests identify the comparison. The input is read without modification.

Supported inputs are saved prepared cross report v1/v2 and prepared rigid pose report v1. The checker independently enumerates every receptor–ligand pair from the embedded float64 coordinates and explicit charge, sigma and epsilon parameters. It recomputes the declared nonperiodic switched Lennard-Jones and screened Coulomb model, energies, forces and pair membership. It does not use the reported pair list to select the calculation.

Absolute tolerances are fixed at 1e-8 kcal/mol for energy and 1e-8 kcal/mol/angstrom for force. They retain the original PFK40 audit criterion. No relative tolerance or command-line relaxation is available. Failed and skipped calculation rows remain in the denominator. Unsupported models, malformed parameters and capacity limits cannot receive a passing result. Limits are 256 MiB per input, 32 report rows, 16384 atoms per component and two million cross pairs per row.

This is a scalar arithmetic check on the reported inputs. It does not authenticate the original source, establish suitable protonation or force-field parameters, repair contacts, validate physical accuracy, or admit data for training. A calculation can complete while this comparison fails; a comparison can pass while the structure remains unsuitable for research. All scientific and training approval flags remain false.

The local development audit replayed all 40 original PFK40 reports: 37 passed and lig_20, lig_41 and lig_42 failed. Every result and maximum energy/force error matched the preserved earlier scalar reference. These are development observations, not a new held-out benchmark. Large force scales in the three failures do not justify silently relaxing the criterion.

CI uses synthetic closed-form, finite-difference and engine-generated fixtures, malformed inputs, tampered results, failed-row preservation and a site-packages-disabled CLI invocation. Actual research reports remain separately hash-bound evidence outside the source tree.
