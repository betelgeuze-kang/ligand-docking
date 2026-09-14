# Bounded public-assay shadow inference

`run_pre_docking_shadow` keeps the existing JSON sidecar and summary interface,
now with an optional `chunk_size` (default 256, maximum 4096). The real HTVS hook
therefore uses bounded processing without an alternate scheduler or learner.
Model registration, target/endpoint/chemistry admission, original row order,
duplicates, raw CSV cells, null unsupported predictions and non-promotion remain.
Weights and producer/checkpoint hashes are not modified or resealed.

The source is copied once to a private disk snapshot while hashing its exact
bytes. CSV parsing uses that snapshot, bounded records and row/character-limited
batches. Results are spooled on disk, and the existing JSON object is published
by atomic replacement only after full parsing. A changed input, malformed late
record or interrupted publication cannot masquerade as a completed prefix. An
unexpected predictor failure is replayed as unsupported for every original row,
matching the prior whole-input model-failure contract. Alias checks protect the
input and checkpoint. Temporary files are cleaned on normal/error exits.

Memory is independent of row count for this file pipeline, bounded by a chunk
and one record. A record is capped at 1 MiB characters and 256 columns; a batch
at 4 MiB raw cell characters and `chunk_size` rows. These are explicit new
admission limits, not silent row truncation. UTF-8 BOMs, quoted newlines, invalid
widths and measured zero retain their original meaning. Existing CSV field-size
limits remain. Temporary disk usage grows with source and results: this is not
a constant-disk algorithm. Atomic publication can require both an old sidecar
and temporary new output. No hostile source authentication is claimed.

`model.iter_prediction_rows(iterable, chunk_size=...)` yields bounded batches;
`model.predict_rows(sequence, chunk_size=...)` preserves the list API, so its
returned list itself still occupies memory proportional to the requested rows.
Changing matrix batch shape may change last-bit floating-point accumulation;
regressions compare against the original full-batch product and independent
`math.fsum` under fixed 1e-12 absolute/relative tolerance. Metadata and all row
statuses remain exact. No model retraining, candidate filtering, calibrated OOD,
scientific promotion, GPU validation or performance-quality claim is introduced.
