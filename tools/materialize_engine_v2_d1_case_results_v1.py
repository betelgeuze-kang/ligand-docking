#!/usr/bin/env python3
"""Materialize 32 D1 result documents from explicit candidate coordinates."""

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
    pass


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise MaterializationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise MaterializationError(f"{path} must contain an object")
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def hash_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def hash_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cid(value: Any, name: str) -> str:
    if type(value) is not str or CASE_RE.fullmatch(value) is None:
        raise MaterializationError(f"{name} is not a valid case ID")
    return value


def confined(root: Path, value: Any, name: str) -> Path:
    if type(value) is not str or not value:
        raise MaterializationError(f"{name} must be a non-empty relative path")
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise MaterializationError(f"{name} escaped source root")
    candidate = root / rel
    if candidate.is_symlink():
        raise MaterializationError(f"{name} cannot be a symlink")
    resolved_root, resolved = root.resolve(), candidate.resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise MaterializationError(f"{name} escaped source root")
    if not resolved.is_file():
        raise MaterializationError(f"{name} is not a regular file")
    return resolved


def matrix(value: Any, name: str, count: int | None = None) -> np.ndarray:
    if type(value) is not list or not value or len(value) > 512:
        raise MaterializationError(f"{name} has invalid atom count")
    if count is not None and len(value) != count:
        raise MaterializationError(f"{name} atom count changed")
    output = np.empty((len(value), 3), dtype=np.float64)
    for i, row in enumerate(value):
        if type(row) is not list or len(row) != 3:
            raise MaterializationError(f"{name}[{i}] must be xyz")
        for j, raw in enumerate(row):
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise MaterializationError(f"{name}[{i}] is not numeric")
            number = float(raw)
            if not math.isfinite(number) or abs(number) > 1e6:
                raise MaterializationError(f"{name}[{i}] is out of range")
            output[i, j] = number
    return output


def permutations(value: Any, atoms: int, heavy: int, name: str) -> tuple[tuple[int, ...], ...]:
    if type(value) is not list or not 1 <= len(value) <= 1024:
        raise MaterializationError(f"{name} needs 1..1024 permutations")
    rows = []
    for p, raw in enumerate(value):
        if type(raw) is not list or len(raw) != heavy:
            raise MaterializationError(f"{name}[{p}] length mismatch")
        row = []
        for atom in raw:
            if type(atom) is not int or not 0 <= atom < atoms:
                raise MaterializationError(f"{name}[{p}] atom index")
            row.append(atom)
        if len(set(row)) != len(row):
            raise MaterializationError(f"{name}[{p}] duplicate atom")
        rows.append(tuple(row))
    if len(set(rows)) != len(rows):
        raise MaterializationError(f"{name} duplicate permutation")
    return tuple(sorted(rows))


def aligned_rmsd(candidate: np.ndarray, reference: np.ndarray) -> float:
    p = candidate - candidate.mean(axis=0)
    q = reference - reference.mean(axis=0)
    u, _s, vt = np.linalg.svd(p.T @ q, full_matrices=False)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        u = u.copy()
        u[:, -1] *= -1
        rotation = u @ vt
    return float(np.sqrt(np.square(p @ rotation - q).sum(axis=1).mean()))


def symmetry_rmsd(
    coordinates: np.ndarray,
    reference: np.ndarray,
    perms: tuple[tuple[int, ...], ...],
) -> float:
    return min(aligned_rmsd(coordinates[list(p)], reference) for p in perms)


def fresh_ids(path: Path) -> set[str]:
    doc = load(path)
    if doc.get("schema_id") != FRESH_SCHEMA:
        raise MaterializationError("Fresh registry schema changed")
    values = doc.get("case_ids")
    if type(values) is not list or len(values) != 128:
        raise MaterializationError("Fresh registry must contain 128 IDs")
    ids = [cid(value, "Fresh ID") for value in values]
    if len(set(ids)) != 128:
        raise MaterializationError("Fresh registry contains duplicates")
    return set(ids)


def adapter_manifest(path: Path) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    doc = load(path)
    if doc.get("schema_id") != ADAPTER_MANIFEST or doc.get("profile_id") != PROFILE_ID:
        raise MaterializationError("adapter manifest identity changed")
    rows = doc.get("cases")
    if type(rows) is not list or len(rows) != 32:
        raise MaterializationError("adapter manifest must contain 32 cases")
    output = []
    for i, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"case_id", "source_path"}:
            raise MaterializationError(f"manifest row {i} field set")
        if type(row["source_path"]) is not str or not row["source_path"]:
            raise MaterializationError(f"manifest row {i} source_path")
        output.append((cid(row["case_id"], f"case[{i}]"), row["source_path"]))
    if len({row[0] for row in output}) != 32:
        raise MaterializationError("duplicate D1 case IDs")
    return doc, output


def optional_bool(value: Any, name: str) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise MaterializationError(f"{name} must be boolean or null")


def materialize_case(path: Path, expected: str) -> dict[str, Any]:
    doc = load(path)
    if doc.get("schema_id") != ADAPTER_SOURCE or doc.get("case_id") != expected:
        raise MaterializationError(f"{expected}: source identity changed")
    status = doc.get("preparation_status")
    candidates = doc.get("candidates")
    if status not in {"success", "failure"} or type(candidates) is not list:
        raise MaterializationError(f"{expected}: invalid preparation state")
    source_sha = hash_path(path)
    if status == "failure":
        code = doc.get("preparation_failure_code")
        if type(code) is not str or not code or candidates:
            raise MaterializationError(f"{expected}: invalid preparation failure")
        return {
            "schema_id": D1_RESULT, "case_id": expected,
            "preparation_status": "failure", "preparation_failure_code": code,
            "candidate_denominator": 0, "candidates": [],
            "adapter_source_sha256": source_sha,
            "native_reference_sha256": None, "rmsd_policy_id": RMSD_POLICY,
        }
    if doc.get("preparation_failure_code") is not None:
        raise MaterializationError(f"{expected}: successful source has failure code")
    atoms = doc.get("ligand_atom_count")
    if type(atoms) is not int or not 1 <= atoms <= 512:
        raise MaterializationError(f"{expected}: ligand atom count")
    reference = matrix(doc.get("reference_heavy_atom_coordinates"), f"{expected}.reference")
    perms = permutations(doc.get("symmetry_permutations"), atoms, len(reference), f"{expected}.perms")
    reference_sha = hash_value({
        "case_id": expected, "ligand_atom_count": atoms,
        "reference_heavy_atom_coordinates": reference.tolist(),
        "symmetry_permutations": [list(row) for row in perms],
        "rmsd_policy_id": RMSD_POLICY,
    })
    if len(candidates) != 64:
        raise MaterializationError(f"{expected}: 64 candidate rows required")
    output = []
    for slot, row in enumerate(candidates):
        if type(row) is not dict or row.get("slot_index") != slot:
            raise MaterializationError(f"{expected}: candidate order")
        lane = row.get("lane")
        if type(lane) is not str or not lane or len(lane) > 128:
            raise MaterializationError(f"{expected}: candidate lane")
        if row.get("status") == "typed_failure":
            code = row.get("failure_code")
            if type(code) is not str or not code:
                raise MaterializationError(f"{expected}: typed failure code")
            for key in ("score", "proposal_coordinates", "final_coordinates", "proposal_valid", "pose_valid"):
                if row.get(key) is not None:
                    raise MaterializationError(f"{expected}: failed candidate contains {key}")
            output.append({
                "slot_index": slot, "lane": lane, "status": "typed_failure",
                "failure_code": code, "score": None,
                "proposal_rmsd_angstrom": None, "final_rmsd_angstrom": None,
                "proposal_valid": None, "pose_valid": None,
            })
            continue
        if row.get("status") != "scored" or row.get("failure_code") is not None:
            raise MaterializationError(f"{expected}: invalid scored candidate")
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise MaterializationError(f"{expected}: invalid score")
        proposal = matrix(row.get("proposal_coordinates"), f"{expected}.proposal[{slot}]", atoms)
        final = matrix(row.get("final_coordinates"), f"{expected}.final[{slot}]", atoms)
        output.append({
            "slot_index": slot, "lane": lane, "status": "scored",
            "failure_code": None, "score": float(score),
            "proposal_rmsd_angstrom": symmetry_rmsd(proposal, reference, perms),
            "final_rmsd_angstrom": symmetry_rmsd(final, reference, perms),
            "proposal_valid": optional_bool(row.get("proposal_valid"), "proposal_valid"),
            "pose_valid": optional_bool(row.get("pose_valid"), "pose_valid"),
        })
    return {
        "schema_id": D1_RESULT, "case_id": expected,
        "preparation_status": "success", "preparation_failure_code": None,
        "candidate_denominator": 64, "candidates": output,
        "adapter_source_sha256": source_sha,
        "native_reference_sha256": reference_sha, "rmsd_policy_id": RMSD_POLICY,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n", encoding="ascii")


def materialize(manifest_path: Path, source_root: Path, fresh_path: Path, output_root: Path) -> dict[str, Any]:
    manifest, rows = adapter_manifest(manifest_path)
    overlap = sorted(case for case, _path in rows if case in fresh_ids(fresh_path))
    if overlap:
        raise MaterializationError("D1 overlaps Fresh IDs: " + ",".join(overlap))
    output_root = output_root.resolve()
    if output_root.exists() or output_root.is_symlink():
        raise MaterializationError("output root must be absent")
    temp = output_root.with_name(f".{output_root.name}.tmp-{os.getpid()}")
    temp.mkdir(parents=True, mode=0o700)
    receipts = []
    manifest_rows = []
    try:
        for case, relative in rows:
            source = confined(source_root, relative, f"source_path[{case}]")
            result = materialize_case(source, case)
            name = f"{case}.json"
            write_json(temp / name, result)
            manifest_rows.append({"case_id": case, "result_path": name})
            receipts.append({
                "case_id": case,
                "source_sha256": result["adapter_source_sha256"],
                "result_sha256": hash_path(temp / name),
            })
        write_json(temp / "manifest.json", {
            "schema_id": D1_MANIFEST, "profile_id": PROFILE_ID, "cases": manifest_rows
        })
        receipt = {
            "schema_id": "betelgeuze.engine_v2_d1_materialization_receipt/1.0.0",
            "profile_id": PROFILE_ID,
            "adapter_manifest_sha256": hash_path(manifest_path),
            "adapter_manifest_projection_sha256": hash_value(manifest),
            "fresh_registry_sha256": hash_path(fresh_path),
            "case_count": 32, "candidate_denominator": 64,
            "rmsd_policy_id": RMSD_POLICY, "cases": receipts,
            "authority": {
                "fresh_128_execution_authorized": False,
                "stage0_admission_authorized": False,
                "benchmark_claim_authorized": False,
                "scientific_claim_authorized": False,
                "product_authorized": False,
            },
        }
        receipt["receipt_sha256"] = hash_value(receipt)
        write_json(temp / "materialization_receipt.json", receipt)
        temp.rename(output_root)
        return receipt
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
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
            args.manifest, args.source_root, args.fresh_case_registry, args.output_root
        )
    except MaterializationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({
        "ok": True, "receipt_sha256": receipt["receipt_sha256"],
        "authority_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
