"""Validate complete Stage2 manifests before handing candidates to Stage3."""

from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence


def _expected_ids(expected_queue_ids: Sequence[str] | None) -> list[str] | None:
    if expected_queue_ids is None:
        return None
    if isinstance(expected_queue_ids, (str, bytes)) or not isinstance(expected_queue_ids, Sequence):
        raise ValueError("expected Stage2 queue identities must be a sequence of IDs")
    expected = list(expected_queue_ids)
    if (any(not isinstance(value, str) or not value.strip() for value in expected)
            or len(set(expected)) != len(expected)):
        raise ValueError("expected Stage2 queue identities must be unique nonblank strings")
    return expected


def _read_manifest(path: str, expected_queue_ids: Sequence[str] | None = None):
    expected = _expected_ids(expected_queue_ids)
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    columns = reader.fieldnames
    if (not columns or "queue_id" not in columns or len(set(columns)) != len(columns)
            or any(not column.strip() for column in columns)):
        raise ValueError("stage2 manifest requires unique nonblank headers including queue_id")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("stage2 manifest contains an incomplete or extra CSV cell")
    ids = [row["queue_id"] for row in rows]
    if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("stage2 manifest requires unique nonblank queue_id values")
    if expected is not None:
        missing, unexpected = set(expected) - set(ids), set(ids) - set(expected)
        if missing or unexpected:
            raise ValueError(f"stage2 manifest queue coverage mismatch: missing={len(missing)}, unexpected={len(unexpected)}")
    return columns, rows, hashlib.sha256(raw).hexdigest()


def validate_stage2_manifest(path: str, *, expected_queue_ids: Sequence[str]) -> dict[str, Any]:
    """Compare identities without interpreting scores, statuses or failure rows."""
    _, rows, digest = _read_manifest(path, expected_queue_ids)
    return {"manifest_csv": str(path), "row_count": len(rows), "source_sha256": digest,
            "expected_row_count": len(expected_queue_ids), "queue_coverage_validated": True}


def manifest_publication_identity(path: str) -> tuple[int, ...] | None:
    """Observe local file publication; this is not signed run provenance."""
    try:
        stat = Path(path).stat()
    except FileNotFoundError:
        return None
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def merge_stage2_manifests(
    traj_manifest_csv: str,
    skip_manifest_csv: str,
    *,
    out_csv: str,
    expected_traj_queue_ids: Sequence[str] | None = None,
    expected_skip_queue_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Keep every distinct row and original CSV value; reject partial inputs.

    A named input must exist. Optional expected identities bind each manifest
    to its routed partition. Duplicates are ambiguous even if rows look equal.
    """
    output = Path(out_csv)
    expected_traj_queue_ids = _expected_ids(expected_traj_queue_ids)
    expected_skip_queue_ids = _expected_ids(expected_skip_queue_ids)
    columns: list[str] = []
    rows: list[dict[str, str]] = []
    counts, hashes = {}, {}
    for side, path, expected in (("traj", traj_manifest_csv, expected_traj_queue_ids),
                                 ("skip", skip_manifest_csv, expected_skip_queue_ids)):
        if not str(path).strip():
            if expected:
                raise FileNotFoundError(f"missing {side} manifest for expected candidates")
            counts[side], hashes[side] = 0, None
            continue
        source = Path(path)
        if output.resolve() == source.resolve() or (
                output.exists() and source.exists() and output.samefile(source)):
            raise ValueError("stage2 manifest output must be distinct from every input")
        source_columns, source_rows, digest = _read_manifest(path, expected)
        columns.extend(column for column in source_columns if column not in columns)
        rows.extend(source_rows)
        counts[side], hashes[side] = len(source_rows), digest
    if not rows:
        raise ValueError("no Stage2 candidate rows available to merge")
    if len({row["queue_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate queue_id across Stage2 manifest partitions")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=output.parent, prefix=".stage2-merge-", delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"merged_manifest_csv": str(output), "row_count": len(rows),
            "traj_row_count": counts["traj"], "skip_row_count": counts["skip"],
            "traj_manifest_csv": str(traj_manifest_csv), "skip_manifest_csv": str(skip_manifest_csv),
            "traj_manifest_sha256": hashes["traj"], "skip_manifest_sha256": hashes["skip"],
            "merged_manifest_sha256": digest,
            "queue_coverage_validated": expected_traj_queue_ids is not None and expected_skip_queue_ids is not None}
