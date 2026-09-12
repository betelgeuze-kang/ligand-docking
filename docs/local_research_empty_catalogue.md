# Empty catalogue execution boundary

This is a focused follow-up to #521 on the live prepared development branch. It
changes no physics formula, model weight, registration, ranking, native V2 source,
GPU qualification, or scientific/customer execution authority.

## Correct observed state

An intact CSV with no data rows (empty, header-only, or a UTF-8 BOM with no data)
now publishes `status: not_evaluated` and `reason: no_csv_data_rows`. Requested,
evaluated and unsupported row counts are all the observed value zero. Its exact
input hash and empty sidecar are preserved. Model-load failures keep their original
reason instead of being hidden by the no-row diagnosis. Unreadable, changed or
malformed input retains unknown counts, not an invented zero.

A nonempty catalogue whose rows are all unsupported still retains every row and
its rejection reason. Enumeration may complete, but that is not successful
inference or successful overall research work. Disabling optional shadow inference
remains an explicit valid operation; an enabled but empty catalogue is different.

## Independent physics and resumption

The local workflow still computes valid independent physical requests. If the
enabled catalogue is empty, its overall result is `partial_or_failed` (exit 2),
not success. The HTML and summary contain only the fixed no-row diagnostic, never
arbitrary producer exception text. A later resume restores committed physical
rows without recomputing them, rechecks the catalogue, and stays partial.

Both the writer and read-only verifier reject a `completed` shadow summary with
zero requested rows. Old reports claiming such completion are not silently
reinterpreted or repaired; the verifier rejects the inconsistent claim. Valid
prior reports retain their existing compatibility rules. Existing source-bound
journals need their original implementation/environment or a fresh run; this
change provides no migration or force-reseal path.

## Validation

Owning tests: `tests/unit/test_empty_shadow_catalogue.py`, plus the existing
local research workflow, delivery, resume, rigid-pose, selector and native-boundary
selections. Fresh synthetic fixtures cover empty/header/BOM inputs, independent
physics, resume, read-only verification, missing models, source mutation,
nonempty unsupported input, invalid producer summaries and diagnostic privacy.
The existing hosted CPU workflow includes the new module without removing tests.
These are implementation regressions, not molecular accuracy or AMD/MD results.
