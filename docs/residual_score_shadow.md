# Versioned residual score shadow inference

The canonical BioDiscovery backmapping consumer can now load the same tabular
`ResidualScoreMLP` architecture and feature encoding used by
`tools/train_residual_production_score_model.py`. The shared implementation is
`betelgeuze_engine/product/residual_score_contract.py`; strict CPU inference is
`betelgeuze_engine/product/residual_score_shadow.py`.

The backmapping CLI accepts `--residual-score-shadow-checkpoint` and
`--residual-score-shadow-checkpoint-sha256`. Both default empty. With a valid
checkpoint it appends `residual_model_shadow_*` diagnostics after all ranking
and replicate metrics, and records requested/evaluated/rejected counts and
reasons in `residual_score_model_shadow` metadata. Existing scores, AuxMLP,
ranking and selection authority do not change.

The loader requires exact checkpoint bytes, the versioned shared source and
architecture, state keys/shapes, feature order/families, saved normalization,
constant-feature and unseen-missingness policies, and an explicit original
score-column identity. It rejects missing/mismatched schema, state, nonfinite
values, unknown families or absent required observations. It does not substitute
another score column, random weights or measured zero for a missing input.
CPU allocation, float32 evaluation and disabled inference autocast keep the
result independent of caller default-device/default-dtype/autocast context.

`binder_logit` is uncalibrated. `corrected_score` is the existing diagnostic
composite score plus a learned score residual, not an affinity or physical
energy. Force and uncertainty outputs are null. An energy-head output is exposed
only when the checkpoint declares that head trained; physical validation remains
false. Production/checkpoint promotion and customer flags stay disabled.

## Checkpoint migration and evidence

The old residual checkpoint has no serving contract and must be regenerated
with the updated trainer; it cannot be passed through the legacy AuxMLP loader.
The trainer/cache fingerprint includes the shared contract source, so a changed
schema/source cannot reuse a stale checkpoint. This is a new shadow schema,
not a migration of existing production ranking scores.

A new synthetic known-weight control reproduced the old Aux bridge returning
0.52985 where the residual model's known logit was 2.0. An independent positive
control showed the Aux bridge still read its own checkpoint correctly. The old
Aux path is retained; the residual model receives its matching loader.

The final exact-source CPU suite passed 458 tests (392 existing and 66 new),
with no failure or skip. It includes a synthetic trainer-to-saved-loader
roundtrip, an independently specified ReLU oracle, raw input/cached fingerprint
regressions, and actual canonical `run_pipeline` interception. The latter uses
literal synthetic row results instead of running molecular calculations and
checks unchanged original ranking/CSV fields plus the new shadow diagnostics.
Default-device, default-dtype and CPU autocast defects were each reproduced and
fixed. These are software checks and agent source reviews, not external human
review, experimental training, calibrated uncertainty or physical validation.

The public assay cheap-selector model described in
`docs/public_assay_development.md` is a different model/endpoint. Its IC50 data
must not be relabeled as score residuals or fed into this loader.
