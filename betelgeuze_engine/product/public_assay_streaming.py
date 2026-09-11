"""Bounded-memory shadow CSV execution; model admission remains in its owner.

A private disk snapshot binds the bytes parsed. Predictions are spooled on disk,
then published atomically as the existing JSON sidecar. Memory is bounded by
one capped CSV record and one capped batch, not by the number of requested rows.
No training, ranking, candidate filtering or customer authorization is added.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile

DEFAULT_CHUNK_SIZE = 256
MAX_CHUNK_SIZE = 4096
MAX_RECORD_CHARS = 1024 * 1024
MAX_COLUMNS = 256
MAX_BATCH_CHARS = 4 * 1024 * 1024
COPY_BYTES = 64 * 1024


def validate_chunk_size(value):
    if type(value) is not int or not 1 <= value <= MAX_CHUNK_SIZE:
        raise ValueError("chunk_size must be an integer in 1..4096")
    return value


def iter_prediction_rows(model, rows, *, chunk_size=DEFAULT_CHUNK_SIZE):
    """Iterable interface; list-returning compatibility API still owns its list."""
    validate_chunk_size(chunk_size)
    batch, offset = [], 0
    for row in rows:
        batch.append(row)
        if len(batch) == chunk_size:
            for prediction in model._predict_batch(batch):
                yield {**prediction, "row_index": offset + prediction["row_index"]}
            offset += len(batch)
            batch = []
    if batch:
        for prediction in model._predict_batch(batch):
            yield {**prediction, "row_index": offset + prediction["row_index"]}


class _RecordLines:
    def __init__(self, stream):
        self.stream = stream
        self.used = 0

    def __iter__(self):
        return self

    def __next__(self):
        line = self.stream.readline(MAX_RECORD_CHARS + 1 - self.used)
        if not line:
            raise StopIteration
        self.used += len(line)
        if self.used > MAX_RECORD_CHARS:
            raise ValueError("csv_record_exceeds_character_limit")
        return line


def _records(snapshot):
    snapshot.seek(0)
    text = io.TextIOWrapper(snapshot, encoding="utf-8-sig", newline="")
    lines = _RecordLines(text)
    reader = csv.reader(lines, strict=True)
    try:
        while True:
            lines.used = 0
            try:
                record = next(reader)
            except StopIteration:
                return
            if len(record) > MAX_COLUMNS:
                raise ValueError("csv_record_exceeds_column_limit")
            yield record
    finally:
        text.detach()  # the caller owns and may replay the snapshot


def _copy_source(path, destination=None):
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("csv_source_must_be_regular_file")
        while True:
            block = source.read(COPY_BYTES)
            if not block:
                break
            digest.update(block)
            if destination is not None:
                destination.write(block)
        after = os.fstat(source.fileno())
        current = os.stat(path)
        def identity(value):
            return (value.st_dev, value.st_ino, value.st_size,
                    value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(after) or identity(after) != identity(current):
            raise ValueError("csv_source_changed_during_read")
    return digest.hexdigest()


def _check_destination(destination, protected):
    for path in protected:
        source = Path(path)
        if (destination.resolve() == source.resolve()
                or (destination.exists() and source.exists()
                    and os.path.samefile(destination, source))):
            raise ValueError("sidecar_aliases_input_or_checkpoint")


class _PredictionFailure(Exception):
    pass


def _spool_rows(snapshot, spool, model, schema, binding, load_error, chunk_size):
    from . import public_assay_selector_shadow as owner

    records = _records(snapshot)
    try:
        header = next(records, [])
        schema_ok = model is not None and (len(header) == len(set(header))
            and model.required_input_columns.issubset(header))
        requested = evaluated = 0
        batch, chars = [], 0

        def flush(batch):
            entries, indices, admitted = [], [], []
            for index, cells in batch:
                row = dict(zip(header, cells))
                entry = owner._row_result(index, row, schema, binding.get("prediction_quantity"))
                entry["reason"] = load_error or "invalid_csv_schema_or_row_width"
                entry["input_cells"] = cells
                entries.append(entry)
                if schema_ok and len(cells) == len(header):
                    indices.append(len(entries) - 1)
                    admitted.append(row)
            if admitted:
                try:
                    predictions = model.predict_rows(admitted, chunk_size=chunk_size)
                    if len(predictions) != len(admitted):
                        raise ValueError("prediction_row_count_mismatch")
                except Exception as exc:
                    raise _PredictionFailure(f"model_unavailable:{type(exc).__name__}:{exc}") from exc
                for position, prediction in zip(indices, predictions):
                    previous = entries[position]
                    entries[position] = {**prediction, "row_index": previous["row_index"],
                                         "input_cells": previous["input_cells"]}
            for entry in entries:
                spool.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), allow_nan=False))
                spool.write("\n")
            return sum(entry["status"] == "evaluated" for entry in entries)

        for cells in records:
            size = sum(map(len, cells))
            if batch and (len(batch) >= chunk_size or chars + size > MAX_BATCH_CHARS):
                evaluated += flush(batch)
                batch, chars = [], 0
            batch.append((requested, cells))
            chars += size
            requested += 1
        if batch:
            evaluated += flush(batch)
        return header, requested, evaluated
    finally:
        records.close()


def run_pre_docking_shadow(*, ligand_csv, ligand_sdf, docking_request_json,
                           resume_stage3_only, checkpoint, checkpoint_sha256,
                           output_json, chunk_size=DEFAULT_CHUNK_SIZE):
    from . import public_assay_selector_shadow as owner

    result = {**owner._contract(), "status": "not_evaluated", "reason": None,
              "input_scope": "original_csv_before_mapping_filters_truncation_and_replicas",
              "requested_rows": None, "evaluated_rows": 0, "unsupported_rows": None,
              "input_path": ligand_csv, "input_sha256": None,
              "streaming_policy": "disk_snapshot_bounded_batches_atomic_sidecar_v1",
              "streaming_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        schema, binding = owner._registration(checkpoint_sha256)
    except owner.SelectorContractError:
        schema, binding = None, {}
    protected = [p for p in (ligand_csv, ligand_sdf, docking_request_json, checkpoint) if p]
    destination, temporary = Path(output_json), None
    # Disk-backed temporary files never retain all requested rows in RAM.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as spool:
        try:
            validate_chunk_size(chunk_size)
            if resume_stage3_only:
                result["reason"] = "resume_has_no_pre_docking_input_evaluation"
            elif docking_request_json and Path(docking_request_json).exists():
                result.update(reason="unsupported_input_type:docking_request_json",
                              input_path=docking_request_json,
                              input_scope="unmodified_docking_request_not_enumerated")
            elif not ligand_csv:
                result.update(reason="unsupported_input_type:sdf_or_unspecified", input_path=ligand_sdf,
                              input_scope="unmodified_non_csv_input_not_enumerated")
            else:
                with tempfile.TemporaryFile(mode="w+b") as snapshot:
                    result["input_sha256"] = _copy_source(ligand_csv, snapshot)
                    model, load_error = None, None
                    try:
                        model = owner.load_public_assay_selector(checkpoint, expected_sha256=checkpoint_sha256)
                        result.update(owner._contract(model.metadata["checkpoint_schema_version"], binding))
                        result["model"] = model.metadata
                    except Exception as exc:
                        load_error = f"model_unavailable:{type(exc).__name__}:{exc}"
                    try:
                        header, requested, evaluated = _spool_rows(
                            snapshot, spool, model, schema, binding, load_error, chunk_size)
                    except _PredictionFailure as exc:
                        # Preserve the former all-rows model-failure semantics,
                        # even when an unexpected failure occurs in a late batch.
                        load_error = str(exc)
                        spool.seek(0)
                        spool.truncate()
                        header, requested, evaluated = _spool_rows(
                            snapshot, spool, None, schema, binding, load_error, chunk_size)
                    if _copy_source(ligand_csv) != result["input_sha256"]:
                        raise ValueError("csv_source_changed_during_prediction")
                    result.update(status="completed", reason=load_error, input_header=header,
                                  requested_rows=requested, evaluated_rows=evaluated,
                                  unsupported_rows=requested - evaluated)
        except Exception as exc:
            # A malformed/truncated late record never produces a successful prefix.
            spool.seek(0)
            spool.truncate()
            result.update(status="not_evaluated", requested_rows=None, evaluated_rows=0,
                          unsupported_rows=None, reason=f"input_unavailable:{type(exc).__name__}:{exc}")
        try:
            _check_destination(destination, protected)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                             prefix=destination.name + ".", delete=False) as output:
                temporary = Path(output.name)
                output.write('{"rows":[')
                spool.seek(0)
                first = True
                for line in spool:
                    if not first:
                        output.write(",")
                    first = False
                    output.write(line.rstrip("\n"))
                output.write("]")
                for key in sorted(result):
                    output.write("," + json.dumps(key) + ":")
                    json.dump(result[key], output, sort_keys=True, allow_nan=False)
                output.write("}\n")
                output.flush()
                os.fsync(output.fileno())
            _check_destination(destination, protected)
            os.replace(temporary, destination)
            result.update(sidecar_status="written", sidecar_json=str(destination))
        except Exception as exc:
            result.update(sidecar_status="failed", sidecar_error=f"{type(exc).__name__}:{exc}")
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return {key: value for key, value in result.items() if key != "input_header"}
