# Saved cross-force arithmetic diagnosis

`tools/product/diagnose_prepared_cross_numerics.py` supplements the historical
scalar checker without changing it or its fixed absolute tolerances. It finds
the actual maximum-error force component, retains tied components, and records
each contributing receptor/ligand pair. A large force elsewhere is not used as
a substitute for locating the discrepancy.

For that component, independent Decimal evaluations at 80 and 120 significant
digits start from the exact reported binary64 coordinates, parameters, and
binary64 Coulomb constant. The tool records per-pair arithmetic error, ordinary
versus compensated scalar accumulation, and distance to the nearest representable
binary64 total. Two high-precision finite differences check the dominant pair's
analytic force. These are mathematical checks of the declared cross-only model,
not an external molecular simulation or preparation validation.

Run the module with `--report saved-report.json --output new-diagnostic.json`.
The optional `--with-engine-pairs` invokes the existing V2 kernel on independent
one-pair projections of the saved canonical systems. These projections are an
engine diagnostic, not an independent oracle. Their sum's difference from the
original result includes full-tile shape and reduction effects; it is not
attributed to accumulation alone. The default script needs only Python's standard
library. Engine-pair mode requires the repository and its CPU dependencies.

When even the nearest binary64 value is farther than the original `1e-8` force
tolerance from the stable high-precision total, the report marks that component
`unsupported_at_diagnosed_component`. This is evidence against achieving that
absolute accuracy with that output representation. Otherwise the field is
`not_determined_for_other_components`: checking one component does not qualify
the entire system. Two binary64 implementations can agree with one another
while both differ from the high-precision model by more than the tolerance.

The observed PFKFB3 development failures `lig_20`, `lig_41`, and `lig_42` have
maximum discrepancies at receptor 2931/x, ligand 31/y, and ligand 45/z respectively.
Their nearest binary64 representation errors at those components are approximately
`1.329e-8`, `1.004e-7`, and `1.594e-8`. The dominant pair in all three includes the
previously observed receptor hydrogen 2931, with cross distances about 0.504,
0.549 and 0.475 angstrom. Pair arithmetic and reduction both contribute at these
scales. No evidence from this diagnosis establishes the scientific correctness
of those very short contacts or authorizes removing or moving those atoms.

All 40 historical reports were retained: the original 37 passes and three failures
remain unchanged. Every input was processed under the same diagnostic rule; the
three original failures are the ones with a demonstrated binary64 representation
floor above the tolerance at their diagnosed component. Remaining preparation
questions require source-verified derived states with new identities. Original
sources, parameters, force outputs and checker tolerances are not modified.

The synthetic regressions test closed forms, independent finite differences,
actual error localization, an unachievable binary64 accuracy floor, agreement
between float implementations despite that floor, malformed and failed rows,
canonical one-pair engine calls, and immutable output publication.
