# PR49/PR59 source-frame geometry boundary

The new development tool reads the existing PR49 registered coordinates and
PR59 isolated conformer without moving either. It independently derives the
same 7XTB SRO pocket anchor from the hash-bound CIF, checks every selected
observed receptor heavy atom against its provenance map, and reports raw
pair distances. **Pair readiness remains false.** This is a geometry diagnostic;
it does not invoke v4 admission, fit data, assign roles, score or minimize.

The source context is `e70eb8e4d66f63c4a928b627a0f3fc0a41653133`. The tool
and its tests were uncommitted during execution. Their final source hashes,
input pins and outputs are in the
[evidence index](../evidence/pr49_pr59_pair_geometry_development_v1.json).
The original inputs and earlier draft output are retained without overwrite.

The source CIF selection is model 1, receptor label asym E; the independent
anchor is label asym F, SRO residue 501, its 13 heavy source atoms 8089–8101.
The anchor center is (84.56507692307693, 110.49638461538461,
82.02238461538461) Å. All 2,124 selected observed receptor heavy atoms map
exactly once with unchanged coordinates, names and elements. Another 2,249
hydrogens and three heavy atoms are explicitly modelled and retain that
provenance; this audit does not validate their physical accuracy.

The original PR49 geometry protocol is itself hash-bound. Its five criteria
are reproduced: minimum all-atom distance 1 Å, minimum heavy-atom distance
2 Å, minimum all/heavy radius-sum ratios 0.60/0.72, and maximum heavy-atom
radius 10 Å around the anchor. Its fixed element-radius table is retained.
Weakened policy copies are rejected after resealing. These five geometry
conditions do not reproduce full chemical/stereo/charge/source admission.

| Input | Atoms / heavy | Minimum all / heavy distance (Å) | Minimum all / heavy radius ratio | Maximum anchor radius (Å) | Geometry-only outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| PR49 registered computational pose | 39 / 25 | 1.5290 / 2.5294 | 0.60652 / 0.74393 | 6.8732 | Pass |
| PR59 isolated centered conformer | 43 / 26 | 134.9153 / 136.7375 | 40.21692 / 40.21692 | 164.8812 | Fail; outside pocket and different frame/origin |
| SRO observed-start positive control | 26 / 13 | 1.5493 / 2.9142 | 0.64556 / 0.94926 | 4.5039 | Pass; separate control |

PR49's geometry pass grants no source role, assay state or v4 eligibility.
This audit deliberately reads the original registered canonical coordinate
artifact, whose coordinates are identical to the later aromatic-annotation
derivative. It does not treat the old missing annotation as chemical admission.
The separate [PR49 component check](pr49_aromatic_annotation_20260930.md)
addresses that representation issue while leaving full source admission false.
PR59's raw conformer is genuinely in an isolated ligand frame; changing a
frame label cannot move its coordinates into the receptor pocket.

The [paper ledger](../evidence/human_5ht6_ki_2024_source_ledger_v1.json) still
has no assigned roles, prepared-state origins or admitted FIT rows. The current
native selector requires at least five eligible point FIT rows from at least
two source components
([implemented gate](../../betelgeuze_product/installed_synthetic_comparison.py#L172)).
The current method contract requires consistent ChEMBL record/assay/document/
target origin and human 5-HT6 Ki identity
([method gate](../../betelgeuze_product/installed_native_v4_protocol_preflight.py#L73),
[prepared-origin gate](../../betelgeuze_product/installed_native_v4_registered_admission.py#L70)).
The two paper rows alone cannot meet these contracts. Source linkage and
independent sanctioned data roles must be resolved without inventing them.

PR59's existing OpenMM projection has 17 constraints and no registered-pose
request or native XML charge-origin descriptor. A legitimate common-frame
initial pose, compatible unconstrained parameter contract and complete
identity/stereo/charge/source binding are still needed. Both neutral graphs
are computational choices: assay protonation/tautomer, batch conditions and
prepared receptor-state equivalence remain unresolved. The modeled receptor
atoms and the SRO-bound receptor do not establish the assayed antagonist state.
A future geometry pass would leave these separate blockers in place.

SRO is solely a positive geometry and mapping control. Its 13 initial heavy
atoms exactly equal the observed CIF atoms, so initial direct RMSD is 0 Å.
The saved installed execution's final heavy coordinates give direct, unaligned
RMSD 0.4767487007932512 Å and maximum displacement 0.845998755950475 Å.
The tool checks retained request/result seals, receptor/ligand bindings and
binary64 coordinate agreement, without replaying the numerical trace. This
observed-pose start is not generated redocking or independent pose recovery;
SRO is not a member of the PR49/PR59 pair and supplies no comparable score or
pose-performance evidence.

Reproduce the read-only audit from this checkout with a fresh output name:

```bash
GEOMETRY_ARCHIVE=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-pr59-source-geometry-20260930-e70eb8e4-bbd597fa
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 tools/analysis/registered_pair_geometry_readiness.py \
  --protocol "$GEOMETRY_ARCHIVE/protocol-final.json" --output /tmp/pr49-pr59-geometry-new.json
```

The output is created exclusively; an existing file is never overwritten.
The archive manifest binds 21 payload files (1,087,272 bytes), including final
source, protocol, output, mutation runner, input pins, and test receipts.
Original large source artifacts are referenced by their retained paths and
hashes. The final pytest run passed 34 cases: 17 geometry boundaries and 17
existing v4 regressions. Ruff and diff checks passed. Seven actual-source
checks also passed under guards that forbid scorer, force, minimizer and
workflow evaluation calls. They include mapping/hash and resealed provenance,
weakened-radius policy, PR59 frame relabel, role promotion and retained SRO
coordinate tampering. Synthetic tests additionally reject source-atom omission.

This geometry audit made zero force, score and placement calls. Its 2.6781 s
arithmetic scope includes input parsing and mapping, ending before final input
rehashing; it excludes startup, tests, upstream preparation, FIT training and
the original saved SRO run. The v4 regression suite is a separate synthetic
execution scope. No new dependency environment or wheel was created here.
All 36 v1.2/v1.3 source files remain byte-identical, and all 523 Python members
of the previously retained v4 wheel still match checkout package source.
The tool lives outside the wheel packages, preserving existing v4 runtime and
receipt identity. No real pair comparison, scientific qualification or product
ranking is claimed.
