#!/usr/bin/env python3
"""Materialize 32 D1 result documents from explicit candidate coordinates.

The adapter computes aligned, symmetry-aware heavy-atom RMSD without reading or
executing Fresh-128. It retains all 64 candidate rows for prepared cases and
preserves typed failures. No Stage 0, benchmark, scientific, product, customer,
or performance authority is granted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
from typing import Any

import numpy as np

PROFILE_ID = "engine_v2_d1_repeatable_development_v1"
ADAPTER_MANIFEST = "betelgeuze.engine_v2_d1_adapter_manifest/1.0.0"
ADAPTER_SOURCE = "betelgeuze.engine_v2_d1_adapter_source/1.0.0"
FRESH_SCHEMA = "betelgeuze.engine_v2_fresh_case_registry/1.0.0"
D1_MANIFEST = "betelgeuze.engine_v2_d1_manifest/1.0.0"
D1_RESULT = "betelgeuze.engine_v2_d1_case_result/1.0.0"
RMSD_POLICY = "aligned_symmetry_aware_heavy_atom_kabsch_v1"
CASE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class MaterializationError(ValueError):
    """D1 adapter input is malformed, overlaps Fresh IDs, or is incomplete."""


def _object_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise MaterializationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_no_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise MaterializationError(f"{path} must contain an object")
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise MaterializationError("value is not canonical JSON") from exc


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_id(value: Any, name: str) -> str:
    if type(value) is not str or CASE_RE.fullmatch(value) is None:
        raise MaterializationError(f"{name} is not a valid case ID")
    return value


def _confined(root: Path, value: Any, name: str) -> Path:
    if type(value) is not str or not value:
        raise MaterializationError(f"{name} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise MaterializationError(f"{name} escaped source root")
    candidate = root / relative
    if candidate.is_symlink():
        raise MaterializationError(f"{name} cannot be a symlink")
    resolved_root, resolved = root.resolve(), candidate.resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise MaterializationError(f"{name} escaped source root")
    if not resolved.is_file():
        raise MaterializationError(f"{name} is not a regular file")
    return resolved


def _matrix(value: Any, name: str, count: int | None = None) -> np.ndarray:
    if type(value) is not list or not value or len(value) > 512:
        raise MaterializationError(f"{name} has invalid atom count")
    if count is not None and len(value) != count:
        raise MaterializationError(f"{name} atom count changed")
    output = np.empty((len(value), 3), dtype=np.float64)
    for index, row in enumerate(value):
        if type(row) is not list or len(row) != 3:
            raise MaterializationError(f"{name}[{index}] must be xyz")
        for axis, raw in enumerate(row):
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise MaterializationError(f"{name}[{index}] is not numeric")
            number = float(raw)
            if not math.isfinite(number) or abs(number) > 1_000_000.0:
                raise MaterializationError(f"{name}[{index}] is out of range")
            output[index, axis] = number
    return output


def _permutations(
    value: Any,
    atom_count: int,
    heavy_count: int,
    name: str,
) -> tuple[tuple[int, ...], ...]:
    if type(value) is not list or not 1 <= len(value) <= 1024:
        raise MaterializationError(f"{name} needs 1..1024 permutations")
    rows: list[tuple[int, ...]] = []
    for permutation_index, raw in enumerate(value):
        if type(raw) is not list or len(raw) != heavy_count:
            raise MaterializationError(f"{name}[{permutation_index}] length mismatch")
        row: list[int] = []
        for atom_index in raw:
            if type(atom_index) is not int or not 0 <= atom_index < atom_count:
                raise MaterializationError(f"{name}[{permutation_index}] atom index")
            row.append(atom_index)
        if len(set(row)) != len(row):
            raise MaterializationError(f"{name}[{permutation_index}] duplicate atom")
        rows.append(tuple(row))
    if len(set(rows)) != len(rows):
        raise MaterializationError(f"{name} duplicate permutation")
    return tuple(sorted(rows))


def aligned_rmsd(candidate: np.ndarray, reference: np.ndarray) -> float:
    """Return Kabsch-aligned RMSD for corresponding coordinate rows."""
    p = candidate - candidate.mean(axis=0)
    q = reference - reference.mean(axis=0)
    u, _singular, vt = np.linalg.svd(p.T @ q, full_matrices=False)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0.0:
        u = u.copy()
        u[:, -1] *= -1.0
        rotation = u @ vt
    return float(np.sqrt(np.square(p @ rotation - q).sum(axis=1).mean()))


def symmetry_rmsd(
    coordinates: np.ndarray,
    reference: np.ndarray,
    permutations: tuple[tuple[int, ...], ...],
) -> float:
    return min(
        aligned_rmsd(coordinates[list(permutation)], reference)
        for permutation in permutations
    )


def _fresh_ids(path: Path) -> set[str]:
    document = _load(path)
    if document.get("schema_id") != FRESH_SCHEMA:
        raise MaterializationError("Fresh registry schema changed")
    values = document.get("case_ids")
    if type(values) is not list or len(values) != 128:
        raise MaterializationError("Fresh registry must contain 128 IDs")
    identifiers = [_case_id(value, "Fresh ID") for value in values]
    if len(set(identifiers)) != 128:
        raise MaterializationError("Fresh registry contains duplicates")
    return set(identifiers)


def _adapter_manifest(path: Path) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    document = _load(path)
    if (
        document.get("schema_id") != ADAPTER_MANIFEST
        or document.get("profile_id") != PROFILE_ID
    ):
        raise MaterializationError("adapter manifest identity changed")
    rows = document.get("cases")
    if type(rows) is not list or len(rows) != 32:
        raise MaterializationError("adapter manifest must contain 32 cases")
    output: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"case_id", "source_path"}:
            raise MaterializationError(f"manifest row {index} field set")
        if type(row["source_path"]) is not str or not row["source_path"]:
            raise MaterializationError(f"manifest row {index} source_path")
        output.append(
            (_case_id(row["case_id"], f"case[{index}]"), row["source_path"])
        )
    if len({row[0] for row in output}) != 32:
        raise MaterializationError("duplicate D1 case IDs")
    return document, output


def _optional_bool(value: Any, name: str) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise MaterializationError(f"{name} must be boolean or null")


def _materialize_case(path: Path, expected_case_id: str) -> dict[str, Any]:
    document = _load(path)
    if (
        document.get("schema_id") != ADAPTER_SOURCE
        or document.get("case_id") != expected_case_id
    ):
        raise MaterializationError(f"{expected_case_id}: source identity changed")
    status = document.get("preparation_status")
    candidates = document.get("candidates")
    if status not in {"success", "failure"} or type(candidates) is not list:
        raise MaterializationError(f"{expected_case_id}: invalid preparation state")
    source_sha256 = _hash_path(path)
    if status == "failure":
        failure_code = document.get("preparation_failure_code")
        if type(failure_code) is not str or not failure_code or candidates:
            raise MaterializationError(
                f"{expected_case_id}: invalid preparation failure"
            )
        return {
            "schema_id": D1_RESULT,
            "case_id": expected_case_id,
            "preparation_status": "failure",
            "preparation_failure_code": failure_code,
            "candidate_denominator": 0,
            "candidates": [],
            "adapter_source_sha256": source_sha256,
            "native_reference_sha256": None,
            "rmsd_policy_id": RMSD_POLICY,
        }
    if document.get("preparation_failure_code") is not None:
        raise MaterializationError(
            f"{expected_case_id}: successful source has failure code"
        )
    atom_count = document.get("ligand_atom_count")
    if type(atom_count) is not int or not 1 <= atom_count <= 512:
        raise MaterializationError(f"{expected_case_id}: ligand atom count")
    reference = _matrix(
        document.get("reference_heavy_atom_coordinates"),
        f"{expected_case_id}.reference",
    )
    permutations = _permutations(
        document.get("symmetry_permutations"),
        atom_count,
        len(reference),
        f"{expected_case_id}.permutations",
    )
    reference_sha256 = _hash_value(
        {
            "case_id": expected_case_id,
            "ligand_atom_count": atom_count,
            "reference_heavy_atom_coordinates": reference.tolist(),
            "symmetry_permutations": [list(row) for row in permutations],
            "rmsd_policy_id": RMSD_POLICY,
        }
    )
    if len(candidates) != 64:
        raise MaterializationError(
            f"{expected_case_id}: 64 candidate rows required"
        )
    output: list[dict[str, Any]] = []
    for slot, row in enumerate(candidates):
        if type(row) is not dict or row.get("slot_index") != slot:
            raise MaterializationError(f"{expected_case_id}: candidate order")
        lane = row.get("lane")
        if type(lane) is not str or not lane or len(lane) > 128:
            raise MaterializationError(f"{expected_case_id}: candidate lane")
        if row.get("status") == "typed_failure":
            failure_code = row.get("failure_code")
            if type(failure_code) is not str or not failure_code:
                raise MaterializationError(
                    f"{expected_case_id}: typed failure code"
                )
            for key in (
                "score",
                "proposal_coordinates",
                "final_coordinates",
                "proposal_valid",
                "pose_valid",
            ):
                if row.get(key) is not None:
                    raise MaterializationError(
                        f"{expected_case_id}: failed candidate contains {key}"
                    )
            output.append(
                {
                    "slot_index": slot,
                    "lane": lane,
                    "status": "typed_failure",
                    "failure_code": failure_code,
                    "score": None,
                    "proposal_rmsd_angstrom": None,
                    "final_rmsd_angstrom": None,
                    "proposal_valid": None,
                    "pose_valid": None,
                }
            )
            continue
        if row.get("status") != "scored" or row.get("failure_code") is not None:
            raise MaterializationError(
                f"{expected_case_id}: invalid scored candidate"
            )
        score = row.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise MaterializationError(f"{expected_case_id}: invalid score")
        proposal = _matrix(
            row.get("proposal_coordinates"),
            f"{expected_case_id}.proposal[{slot}]",
            atom_count,
        )
        final = _matrix(
            row.get("final_coordinates"),
            f"{expected_case_id}.final[{slot}]",
            atom_count,
        )
        output.append(
            {
                "slot_index": slot,
                "lane": lane,
                "status": "scored",
                "failure_code": None,
                "score": float(score),
                "proposal_rmsd_angstrom": symmetry_rmsd(
                    proposal, reference, permutations
                ),
                "final_rmsd_angstrom": symmetry_rmsd(
                    final, reference, permutations
                ),
                "proposal_valid": _optional_bool(
                    row.get("proposal_valid"), "proposal_valid"
                ),
                "pose_valid": _optional_bool(row.get("pose_valid"), "pose_valid"),
            }
        )
    return {
        "schema_id": D1_RESULT,
        "case_id": expected_case_id,
        "preparation_status": "success",
        "preparation_failure_code": None,
        "candidate_denominator": 64,
        "candidates": output,
        "adapter_source_sha256": source_sha256,
        "native_reference_sha256": reference_sha256,
        "rmsd_policy_id": RMSD_POLICY,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def materialize(
    manifest_path: Path,
    source_root: Path,
    fresh_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    manifest, rows = _adapter_manifest(manifest_path)
    overlap = sorted(case for case, _path in rows if case in _fresh_ids(fresh_path))
    if overlap:
        raise MaterializationError("D1 overlaps Fresh IDs: " + ",".join(overlap))
    output_root = output_root.resolve()
    if output_root.exists() or output_root.is_symlink():
        raise MaterializationError("output root must be absent")
    temporary = output_root.with_name(f".{output_root.name}.tmp-{os.getpid()}")
    temporary.mkdir(parents=True, mode=0o700)
    receipts: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []
    try:
        for case, relative in rows:
            source = _confined(source_root, relative, f"source_path[{case}]")
            result = _materialize_case(source, case)
            name = f"{case}.json"
            _write_json(temporary / name, result)
            manifest_rows.append({"case_id": case, "result_path": name})
            receipts.append(
                {
                    "case_id": case,
                    "source_sha256": result["adapter_source_sha256"],
                    "result_sha256": _hash_path(temporary / name),
                }
            )
        _write_json(
            temporary / "manifest.json",
            {
                "schema_id": D1_MANIFEST,
                "profile_id": PROFILE_ID,
                "cases": manifest_rows,
            },
        )
        receipt: dict[str, Any] = {
            "schema_id": "betelgeuze.engine_v2_d1_materialization_receipt/1.0.0",
            "profile_id": PROFILE_ID,
            "adapter_manifest_sha256": _hash_path(manifest_path),
            "adapter_manifest_projection_sha256": _hash_value(manifest),
            "fresh_registry_sha256": _hash_path(fresh_path),
            "case_count": 32,
            "candidate_denominator": 64,
            "rmsd_policy_id": RMSD_POLICY,
            "cases": receipts,
            "authority": {
                "fresh_128_execution_authorized": False,
                "stage0_admission_authorized": False,
                "benchmark_claim_authorized": False,
                "scientific_claim_authorized": False,
                "product_authorized": False,
            },
        }
        receipt["receipt_sha256"] = _hash_value(receipt)
        _write_json(temporary / "materialization_receipt.json", receipt)
        temporary.rename(output_root)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--fresh-case-registry", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = materialize(
            args.manifest,
            args.source_root,
            args.fresh_case_registry,
            args.output_root,
        )
    except MaterializationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "receipt_sha256": receipt["receipt_sha256"],
                "authority_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
