"""Deterministic source manifest for ligand HTVS and PocketMD implementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


IMPLEMENTATION_MANIFEST_SCHEMA_VERSION = "ligand_htvs_implementation_manifest_v1"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_IMPLEMENTATION_SOURCE_GLOBS: tuple[str, ...] = (
    "betelgeuze_engine/**/*.py",
    "betelgeuze_product/**/*.py",
    "betelgeuze_ai_md/**/*.py",
    "api/**/*.py",
    "betelgeuze_engine_v2/**/*.py",
    "core/**/*.py",
    "theory/**/*.py",
    "train/**/*.py",
    "tools/accounting/**/*.py",
    "tools/product/**/*.py",
    "tools/run_ligand*.py",
    "rust_engine/src/**/*.rs",
    "rust_engine_v2/src/**/*.rs",
)
_IMPLEMENTATION_EXPLICIT_SOURCE_PATHS: tuple[str, ...] = (
    "tools/__init__.py",
    "tools/audit_ligand_leakage.py",
    "tools/build_ligand_admet_surface.py",
    "tools/build_ligand_mapping_queue.py",
    "tools/build_bigdata_residual_manifest.py",
    "tools/build_experiment_consistency_metrics.py",
    "tools/calibrate_ligand_mmpbsa_proxy.py",
    "tools/evaluate_ligand_ranking_metrics.py",
    "tools/evaluate_allatom_equivalence_gate.py",
    "tools/generate_ligand_trajectory_engine.py",
    "tools/build_hard_mining_target_weights.py",
    "tools/build_kinetics_equivalence_metrics.py",
    "tools/build_thermodynamics_equivalence_metrics.py",
    "tools/native_target_registry.py",
    "tools/pdb_loader.py",
    "tools/run_active_learning_cycle.py",
    "tools/run_allatom_claim_readiness.py",
    "tools/run_bigdata_curriculum_training.py",
    "tools/run_claim_metric_correction_loop.py",
    "tools/update_closeout_latest.py",
    "tools/validate_ligand_eval_integrity.py",
    "train_router.py",
)
_IMPLEMENTATION_OPTIONAL_SOURCE_PATHS: tuple[str, ...] = (
    "config/ligand_engine_production.json",
)


def _reviewed_implementation_source_paths(root: Path) -> tuple[str, ...]:
    paths = set(_IMPLEMENTATION_EXPLICIT_SOURCE_PATHS)
    paths.update(
        relative_path
        for relative_path in _IMPLEMENTATION_OPTIONAL_SOURCE_PATHS
        if (root / relative_path).is_file()
    )
    for pattern in _IMPLEMENTATION_SOURCE_GLOBS:
        for source in root.glob(pattern):
            if source.is_file() and "__pycache__" not in source.parts:
                paths.add(source.relative_to(root).as_posix())
    return tuple(sorted(paths))


# This reviewed closure deliberately covers the canonical runners plus their
# first-party engine, contract, physics, topology, interaction, residual,
# backmapping, stage-router, materialization, and subprocess source surfaces.
# It is resolved once per process so a deployed process and every artifact it
# emits use one stable source inventory.
HTVS_IMPLEMENTATION_SOURCE_PATHS: tuple[str, ...] = (
    _reviewed_implementation_source_paths(_REPO_ROOT)
)
_MANIFEST_FIELDS = frozenset(
    {"schema_version", "algorithm", "files", "manifest_sha256"}
)
_FILE_FIELDS = frozenset({"path", "sha256"})


class ImplementationProvenanceError(ValueError):
    """Raised when implementation provenance is absent or inconsistent."""


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unsigned_manifest(files: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": IMPLEMENTATION_MANIFEST_SCHEMA_VERSION,
        "algorithm": "sha256",
        "files": files,
    }


def build_implementation_source_manifest(
    root: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    files: list[dict[str, str]] = []
    for relative_path in HTVS_IMPLEMENTATION_SOURCE_PATHS:
        source = repo_root / relative_path
        if not source.is_file():
            raise ImplementationProvenanceError(
                f"implementation source missing: {relative_path}"
            )
        files.append({"path": relative_path, "sha256": _sha256_file(source)})
    unsigned = _unsigned_manifest(files)
    return {
        **unsigned,
        "manifest_sha256": hashlib.sha256(
            _canonical_json(unsigned).encode("utf-8")
        ).hexdigest(),
    }


def validate_implementation_source_manifest(
    payload: Mapping[str, Any],
    *,
    root: str | Path | None = None,
    require_current: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ImplementationProvenanceError("implementation manifest must be an object")
    keys = frozenset(str(key) for key in payload)
    if keys != _MANIFEST_FIELDS:
        raise ImplementationProvenanceError("implementation manifest fields mismatch")
    if payload.get("schema_version") != IMPLEMENTATION_MANIFEST_SCHEMA_VERSION:
        raise ImplementationProvenanceError("implementation manifest schema mismatch")
    if payload.get("algorithm") != "sha256":
        raise ImplementationProvenanceError("implementation manifest algorithm mismatch")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != len(
        HTVS_IMPLEMENTATION_SOURCE_PATHS
    ):
        raise ImplementationProvenanceError("implementation manifest file coverage mismatch")
    files: list[dict[str, str]] = []
    for expected_path, raw in zip(HTVS_IMPLEMENTATION_SOURCE_PATHS, raw_files):
        if not isinstance(raw, Mapping) or frozenset(str(key) for key in raw) != _FILE_FIELDS:
            raise ImplementationProvenanceError("implementation manifest file entry mismatch")
        path = str(raw.get("path") or "")
        digest = str(raw.get("sha256") or "").lower()
        if path != expected_path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ImplementationProvenanceError("implementation manifest path mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ImplementationProvenanceError("implementation source sha256 is invalid")
        files.append({"path": path, "sha256": digest})
    manifest_sha256 = str(payload.get("manifest_sha256") or "").lower()
    expected = hashlib.sha256(
        _canonical_json(_unsigned_manifest(files)).encode("utf-8")
    ).hexdigest()
    if manifest_sha256 != expected:
        raise ImplementationProvenanceError("implementation manifest_sha256 mismatch")
    validated = {**_unsigned_manifest(files), "manifest_sha256": expected}
    if require_current:
        current = build_implementation_source_manifest(root)
        if validated != current:
            raise ImplementationProvenanceError(
                "implementation manifest does not match current source tree"
            )
    return validated


__all__ = [
    "IMPLEMENTATION_MANIFEST_SCHEMA_VERSION",
    "HTVS_IMPLEMENTATION_SOURCE_PATHS",
    "ImplementationProvenanceError",
    "build_implementation_source_manifest",
    "validate_implementation_source_manifest",
]
