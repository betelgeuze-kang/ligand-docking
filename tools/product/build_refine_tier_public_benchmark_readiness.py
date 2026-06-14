#!/usr/bin/env python3
"""Fail-closed readiness gate for curated refine-tier public benchmarks."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import tarfile
from pathlib import Path
from typing import Any

import numpy as np

from core.score_calibration import calibration_quality_gate, fit_linear_calibration
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_CSV = "config/refine_tier_public_benchmark_intake_current.csv"
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_readiness_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_readiness_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_readiness_current.md"
DEFAULT_OUT_WORK_ORDER_CSV = "runs/refine_tier_public_benchmark_work_order_current.csv"
DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV = "runs/refine_tier_public_benchmark_science_input_gap_current.csv"
DEFAULT_OUT_RECEPTOR_COORDINATE_INTAKE_CSV = (
    "runs/refine_tier_public_benchmark_receptor_coordinate_intake_current.csv"
)
DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV = (
    "runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv"
)
DEFAULT_OUT_METRIC_EVIDENCE_CSV = "runs/refine_tier_public_benchmark_metric_evidence_current.csv"
DEFAULT_WORK_ORDER_SEED_CSV = "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv"
DEFAULT_WORK_ORDER_AFFINITY_TSV = "data/public_benchmarks/pdbbind_casf_pose_affinity/pdb_to_affinity.txt.original"
DEFAULT_WORK_ORDER_DATASET_DIR = "data/public_benchmarks/pdbbind_casf_pose_affinity"
REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN = "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
DEFAULT_WORK_ORDER_APPLY_COMMAND = "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py"
DEFAULT_WORK_ORDER_APPLY_WRITE_INTAKE_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py "
    f"--write-intake --approval-token {REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN}"
)

REQUIRED_COLUMNS = [
    "benchmark_id",
    "target_id",
    "benchmark_family",
    "split",
    "provenance_kind",
    "provenance_id",
    "license_ok",
    "external_engine_calls",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "deltaG_experimental_kcal_mol",
]
ALLOWED_PROVENANCE_KINDS = {"pdbbind", "casf", "bm5", "public_pdb", "operator_curated_public"}
ALLOWED_SPLITS = {"fit", "holdout", "test"}
CLAIM_BOUNDARY = (
    "Refine-tier public benchmark readiness only; verifies operator-curated public pose/free-energy rows, "
    "provenance, licensing flags, and no external engine calls. It does not download data, run docking/MD, "
    "contact providers, or open an OpenMM/Schrödinger-grade claim."
)

WORK_ORDER_COLUMNS = [
    "work_order_id",
    "target_input_csv",
    "template_row_index",
    "benchmark_id",
    "target_id",
    "benchmark_family",
    "split",
    "provenance_kind",
    "provenance_id",
    "license_ok",
    "external_engine_calls",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "deltaG_experimental_kcal_mol",
    "operator_action",
    "acceptance_rule",
    "external_state_mutated",
]
WORK_ORDER_OPERATOR_FIELDS = [
    "benchmark_id",
    "target_id",
    "provenance_id",
    "license_ok",
    "pose_rmsd_A",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "deltaG_experimental_kcal_mol",
]
SCIENCE_INPUT_GAP_COLUMNS = [
    "work_order_id",
    "target_id",
    "pose_id",
    "ligand_pose_artifact",
    "ligand_pose_artifact_present",
    "receptor_coordinate_artifact",
    "receptor_coordinate_artifact_present",
    "interaction_metric_source_present",
    "internal_deltaG_source_present",
    "pending_dockq",
    "pending_lddt_pli",
    "pending_internal_deltaG",
    "next_required_science_input",
]
RECEPTOR_COORDINATE_INTAKE_COLUMNS = [
    "work_order_id",
    "target_id",
    "pose_id",
    "current_receptor_coordinate_artifact",
    "receptor_coordinate_artifact_present",
    "accepted_offline_coordinate_patterns",
    "expected_archive_member_examples",
    "suggested_public_coordinate_urls",
    "suggested_local_coordinate_paths",
    "operator_coordinate_source_review_required",
    "next_operator_action",
]
RECEPTOR_COORDINATE_VALIDATION_COLUMNS = [
    "work_order_id",
    "target_id",
    "pose_id",
    "receptor_coordinate_artifact",
    "receptor_coordinate_artifact_present",
    "receptor_coordinate_artifact_sha256",
    "coordinate_source_kind",
    "coordinate_parse_status",
    "coordinate_atom_record_count",
    "coordinate_pdb_atom_record_count",
    "coordinate_pdb_hetatm_record_count",
    "coordinate_mol2_atom_record_count",
    "coordinate_macromolecule_atom_record_count",
    "coordinate_distinct_residue_count",
    "coordinate_protein_like_atom_record_count",
    "coordinate_protein_like_residue_count",
    "coordinate_model_record_count",
    "coordinate_validation_status",
    "blockers",
    "next_required_science_input",
]
METRIC_EVIDENCE_COLUMNS = [
    "work_order_id",
    "target_id",
    "pose_id",
    "dockq",
    "lddt_pli",
    "deltaG_mm_gbsa_kcal_mol",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "expected_dockq_source_artifact",
    "expected_lddt_pli_source_artifact",
    "expected_internal_deltaG_source_artifact",
    "required_metric_input_artifacts",
    "required_metric_input_artifact_sha256s",
    "missing_required_metric_input_artifacts",
    "required_metric_source_payload_fields",
    "dockq_source_artifact_present",
    "lddt_pli_source_artifact_present",
    "internal_deltaG_source_artifact_present",
    "dockq_source_payload_valid",
    "lddt_pli_source_payload_valid",
    "internal_deltaG_source_payload_valid",
    "dockq_source_payload_blockers",
    "lddt_pli_source_payload_blockers",
    "internal_deltaG_source_payload_blockers",
    "metric_evidence_status",
    "blockers",
    "next_required_science_input",
    "metric_evidence_next_operator_action",
]
REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS = (
    "metric_name",
    "target_id",
    "pose_id",
    "value",
    "method",
    "input_artifacts",
    "input_artifact_sha256s",
    "operator_id",
    "reviewed_at_utc",
    "license_ok",
    "external_engine_calls",
)
PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
GAS_CONSTANT_KCAL_PER_MOL_K = 0.00198720425864083
DEFAULT_DELTA_G_TEMPERATURE_K = 298.15
PAFFINITY_TO_DG_KCAL_PER_MOL = -GAS_CONSTANT_KCAL_PER_MOL_K * DEFAULT_DELTA_G_TEMPERATURE_K * math.log(10.0)
RECEPTOR_COORDINATE_SUFFIXES = (".pdb", ".ent", ".pdbqt", ".mol2", ".mae", ".maegz", ".cif", ".mmcif")
TARGET_COMPLEX_COORDINATE_SUFFIXES = (".pdb", ".ent", ".cif", ".mmcif")
RECEPTOR_COORDINATE_NAME_HINTS = ("protein", "receptor", "pocket", "complex")
MIN_RECEPTOR_COORDINATE_ATOM_RECORDS = 20
MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS = 20
MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES = 5
MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES = 5
PROTEIN_LIKE_RESIDUE_NAMES = {
    "ALA",
    "ARG",
    "ASN",
    "ASP",
    "CYS",
    "GLN",
    "GLU",
    "GLY",
    "HIS",
    "ILE",
    "LEU",
    "LYS",
    "MET",
    "PHE",
    "PRO",
    "SER",
    "THR",
    "TRP",
    "TYR",
    "VAL",
    "ASH",
    "CYX",
    "GLH",
    "HID",
    "HIE",
    "HIP",
    "LYN",
    "MSE",
    "SEC",
    "PYL",
}
SEED_RECEPTOR_COLUMN_NAMES = {
    "protein_path",
    "protein_artifact",
    "receptor_path",
    "receptor_artifact",
    "pocket_path",
    "complex_structure_path",
}
SEED_INTERACTION_METRIC_COLUMN_NAMES = {"dockq", "lddt_pli", "pli_lddt", "interaction_lddt"}
SEED_INTERNAL_DG_COLUMN_NAMES = {
    "deltaG_mm_gbsa_kcal_mol",
    "delta_g_mm_gbsa_kcal_mol",
    "internal_refine_deltaG_kcal_mol",
    "internal_deltaG_kcal_mol",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _is_iso_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _zero_external_engine_calls(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    return _text(value) in {"0", "0.0", "false", "False"}


def _nonempty_input_artifacts(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value) and all(bool(_text(item)) and not _has_placeholder(item) for item in value)
    return bool(_text(value)) and not _has_placeholder(value)


def _input_artifact_entries(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _local_input_artifact_present(reference: str) -> bool:
    reference = _text(reference)
    if not reference or _has_placeholder(reference):
        return False
    if "::" in reference:
        archive_name, member_name = reference.split("::", 1)
        archive = _resolve(archive_name)
        if not archive.is_file() or not member_name:
            return False
        try:
            with tarfile.open(archive, "r:*") as handle:
                member = handle.getmember(member_name)
        except (KeyError, OSError, tarfile.TarError):
            return False
        return member.isfile()
    return _resolve(reference).is_file()


def _local_input_artifacts_present(value: Any) -> bool:
    entries = _input_artifact_entries(value)
    return bool(entries) and all(_local_input_artifact_present(entry) for entry in entries)


def _input_artifact_sha256(reference: str) -> str:
    reference = _text(reference)
    if not reference or _has_placeholder(reference):
        return ""
    if "::" in reference:
        archive_name, member_name = reference.split("::", 1)
        archive = _resolve(archive_name)
        if not archive.is_file() or not member_name:
            return ""
        try:
            with tarfile.open(archive, "r:*") as handle:
                member_file = handle.extractfile(member_name)
                if member_file is None:
                    return ""
                with member_file:
                    return hashlib.sha256(member_file.read()).hexdigest()
        except (KeyError, OSError, tarfile.TarError):
            return ""
    path = _resolve(reference)
    if not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _payload_input_artifact_hashes_valid(input_artifacts: Any, payload_hashes: Any) -> bool:
    entries = _input_artifact_entries(input_artifacts)
    if not entries:
        return False
    actual_hashes = [_input_artifact_sha256(entry) for entry in entries]
    if not all(actual_hashes):
        return False
    if isinstance(payload_hashes, dict):
        return all(
            _text(payload_hashes.get(entry)) == actual
            for entry, actual in zip(entries, actual_hashes, strict=True)
        )
    if isinstance(payload_hashes, list):
        expected_hashes = [_text(item) for item in payload_hashes]
        return expected_hashes == actual_hashes
    return len(entries) == 1 and _text(payload_hashes) == actual_hashes[0]


def _split_archive_reference(reference: str) -> tuple[Path | None, str] | None:
    reference = _text(reference)
    if "::" not in reference:
        return None
    archive_text, member_name = reference.split("::", 1)
    if not archive_text or not member_name:
        return None
    return _resolve(archive_text).resolve(strict=False), member_name


def _input_artifact_reference_matches(left: str, right: str) -> bool:
    left = _text(left)
    right = _text(right)
    if not left or not right:
        return False
    if left == right:
        return True
    left_archive = _split_archive_reference(left)
    right_archive = _split_archive_reference(right)
    if left_archive or right_archive:
        return bool(left_archive and right_archive and left_archive == right_archive)
    return _resolve(left).resolve(strict=False) == _resolve(right).resolve(strict=False)


def _payload_includes_required_input_artifacts(input_artifacts: Any, required_input_artifacts: list[str]) -> bool:
    required = [_text(item) for item in required_input_artifacts if _text(item)]
    if not required:
        return True
    entries = _input_artifact_entries(input_artifacts)
    return all(
        any(_input_artifact_reference_matches(entry, expected) for entry in entries)
        for expected in required
    )


def _payload_field_missing(payload: dict[str, Any], field: str) -> bool:
    if field not in payload:
        return True
    value = payload.get(field)
    if value is None:
        return True
    if isinstance(value, (bool, int, float)):
        return False
    return _has_placeholder(value)


def _stable_id(value: Any) -> str:
    text = _text(value).upper()
    return "".join(char if char.isalnum() else "_" for char in text).strip("_")


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6g}"


def _has_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or any(text.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _lower_columns(columns: list[str]) -> set[str]:
    return {str(column).strip().lower() for column in columns}


def _column_count(columns: list[str], accepted_names: set[str]) -> int:
    lowered = _lower_columns(columns)
    return len(lowered & accepted_names)


def _looks_like_receptor_coordinate(name: str) -> bool:
    lower_name = str(name).lower()
    basename = Path(lower_name).name
    return any(basename.endswith(suffix) for suffix in RECEPTOR_COORDINATE_SUFFIXES) and any(
        hint in basename for hint in RECEPTOR_COORDINATE_NAME_HINTS
    )


def _matches_target_receptor_coordinate(name: str, target: str) -> bool:
    lower_name = str(name).lower()
    basename = Path(lower_name).name
    if not target or target not in lower_name:
        return False
    if _looks_like_receptor_coordinate(basename):
        return True
    return any(basename == f"{target}{suffix}" for suffix in TARGET_COMPLEX_COORDINATE_SUFFIXES)


def _looks_like_ligand_pose_archive_member(name: str) -> bool:
    parts = Path(str(name)).parts
    return len(parts) >= 2 and parts[0] == "data_5_sdf"


def _local_metric_input_availability(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    local_receptor_coordinate_file_count = 0
    tar_archive_count = 0
    tar_receptor_coordinate_member_count = 0
    tar_ligand_pose_member_count = 0
    tar_ligand_only_archive_count = 0
    tar_read_error_count = 0
    if path.is_dir():
        for candidate in path.rglob("*"):
            if candidate.is_file() and _looks_like_receptor_coordinate(candidate.name):
                local_receptor_coordinate_file_count += 1
        for archive in path.glob("*.tar*"):
            if not archive.is_file():
                continue
            tar_archive_count += 1
            try:
                with tarfile.open(archive, "r:*") as handle:
                    members = [member for member in handle.getmembers() if member.isfile()]
                    archive_receptor_count = sum(
                        1 for member in members if _looks_like_receptor_coordinate(member.name)
                    )
                    archive_ligand_count = sum(
                        1 for member in members if _looks_like_ligand_pose_archive_member(member.name)
                    )
                    tar_receptor_coordinate_member_count += archive_receptor_count
                    tar_ligand_pose_member_count += archive_ligand_count
                    if archive_ligand_count and not archive_receptor_count:
                        tar_ligand_only_archive_count += 1
            except (tarfile.TarError, OSError):
                tar_read_error_count += 1
    return {
        "work_order_dataset_artifact": str(path_like),
        "work_order_dataset_artifact_present": path.is_dir(),
        "work_order_local_receptor_coordinate_file_count": local_receptor_coordinate_file_count,
        "work_order_tar_archive_count": tar_archive_count,
        "work_order_tar_ligand_pose_member_count": tar_ligand_pose_member_count,
        "work_order_tar_receptor_coordinate_member_count": tar_receptor_coordinate_member_count,
        "work_order_tar_ligand_only_archive_count": tar_ligand_only_archive_count,
        "work_order_tar_read_error_count": tar_read_error_count,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _pose_id_from_work_order_row(row: dict[str, Any]) -> str:
    provenance_id = _text(row.get("provenance_id"))
    if ":" in provenance_id:
        return provenance_id.rsplit(":", 1)[-1]
    return ""


def _matching_ligand_pose_artifact(dataset_dir: str | Path, pose_id: str) -> str:
    pose_id = _text(pose_id)
    if not pose_id:
        return ""
    dataset = _resolve(dataset_dir)
    direct_candidates = [
        dataset / "data_5_sdf" / pose_id,
        dataset / "data_5_sdf" / f"{pose_id}.sdf",
        dataset / "data_5_sdf" / f"{pose_id}.mol2",
        dataset / pose_id,
        dataset / f"{pose_id}.sdf",
        dataset / f"{pose_id}.mol2",
    ]
    for candidate in direct_candidates:
        if candidate.exists() and candidate.is_file():
            return _display_path(candidate)
    if dataset.is_dir():
        for candidate in dataset.rglob(pose_id):
            if candidate.is_file():
                return _display_path(candidate)
    return ""


def _matching_receptor_coordinate_artifact(dataset_dir: str | Path, target_id: str) -> str:
    target = _text(target_id).lower()
    if not target:
        return ""
    dataset = _resolve(dataset_dir)
    candidate_dirs = [
        dataset,
        dataset / target,
        dataset / "CASF-2016_scoring" / target,
        dataset / "CASF-2016_docking" / target,
        dataset / "PDBbind_v2016_refined" / target,
    ]
    suffixes = (".pdb", ".ent", ".pdbqt", ".mol2", ".mae", ".maegz", ".cif", ".mmcif")
    stems = (
        target,
        f"{target}_protein",
        f"{target}_receptor",
        f"{target}_pocket",
        f"{target}_complex",
    )
    for directory in candidate_dirs:
        for stem in stems:
            for suffix in suffixes:
                candidate = directory / f"{stem}{suffix}"
                if candidate.exists() and candidate.is_file():
                    return _display_path(candidate)
    if dataset.is_dir():
        for candidate in dataset.rglob("*"):
            if not candidate.is_file():
                continue
            relative_name = candidate.relative_to(dataset).as_posix()
            lower_name = relative_name.lower()
            if target not in lower_name:
                continue
            if lower_name.endswith(suffixes) and _matches_target_receptor_coordinate(relative_name, target):
                return _display_path(candidate)
        for archive in sorted(dataset.glob("*.tar*")):
            if not archive.is_file():
                continue
            try:
                with tarfile.open(archive, "r:*") as handle:
                    for member in handle.getmembers():
                        if member.isfile() and _matches_target_receptor_coordinate(member.name, target):
                            return f"{_display_path(archive)}::{member.name}"
            except (tarfile.TarError, OSError):
                continue
    return ""


def _build_science_input_gap_rows(
    work_order_rows: list[dict[str, Any]],
    *,
    dataset_dir: str | Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in work_order_rows:
        target_id = _text(row.get("target_id"))
        pose_id = _pose_id_from_work_order_row(row)
        ligand_artifact = _matching_ligand_pose_artifact(dataset_dir, pose_id)
        receptor_artifact = _matching_receptor_coordinate_artifact(dataset_dir, target_id)
        pending_dockq = _has_placeholder(row.get("dockq"))
        pending_lddt_pli = _has_placeholder(row.get("lddt_pli"))
        pending_internal_delta_g = _has_placeholder(row.get("deltaG_mm_gbsa_kcal_mol"))
        dockq_source_validation = _metric_source_payload_validation(
            row.get("dockq_source_artifact"),
            expected_metric_name="dockq",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=row.get("dockq"),
        )
        lddt_source_validation = _metric_source_payload_validation(
            row.get("lddt_pli_source_artifact"),
            expected_metric_name="lddt_pli",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=row.get("lddt_pli"),
        )
        internal_delta_g_source_validation = _metric_source_payload_validation(
            row.get("internal_deltaG_source_artifact"),
            expected_metric_name="internal_deltaG",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=row.get("deltaG_mm_gbsa_kcal_mol"),
        )
        dockq_source_present = bool(dockq_source_validation["payload_valid"])
        lddt_source_present = bool(lddt_source_validation["payload_valid"])
        internal_delta_g_source_present = bool(internal_delta_g_source_validation["payload_valid"])
        next_inputs: list[str] = []
        if not ligand_artifact:
            next_inputs.append("local_ligand_pose_artifact")
        if not receptor_artifact:
            next_inputs.append("native_receptor_or_complex_coordinate")
        if pending_dockq or pending_lddt_pli:
            next_inputs.append("DockQ_and_lDDT_PLI_metric_values")
        if not (dockq_source_present and lddt_source_present):
            next_inputs.append("DockQ_and_lDDT_PLI_metric_source_artifacts")
        if pending_internal_delta_g:
            next_inputs.append("internal_refine_deltaG_value")
        if not internal_delta_g_source_present:
            next_inputs.append("internal_refine_deltaG_source_artifact")
        rows.append(
            {
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": target_id,
                "pose_id": pose_id,
                "ligand_pose_artifact": ligand_artifact,
                "ligand_pose_artifact_present": bool(ligand_artifact),
                "receptor_coordinate_artifact": receptor_artifact,
                "receptor_coordinate_artifact_present": bool(receptor_artifact),
                "interaction_metric_source_present": bool(
                    not (pending_dockq or pending_lddt_pli)
                    and dockq_source_present
                    and lddt_source_present
                ),
                "internal_deltaG_source_present": bool(
                    not pending_internal_delta_g and internal_delta_g_source_present
                ),
                "pending_dockq": pending_dockq,
                "pending_lddt_pli": pending_lddt_pli,
                "pending_internal_deltaG": pending_internal_delta_g,
                "next_required_science_input": ";".join(next_inputs) if next_inputs else "none",
            }
        )
    return rows


def _science_input_gap_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    local_ligand_count = sum(1 for row in rows if row["ligand_pose_artifact_present"])
    receptor_ready_count = sum(1 for row in rows if row["receptor_coordinate_artifact_present"])
    interaction_ready_count = sum(1 for row in rows if row["interaction_metric_source_present"])
    internal_delta_g_ready_count = sum(1 for row in rows if row["internal_deltaG_source_present"])
    blocked_count = sum(1 for row in rows if row["next_required_science_input"] != "none")
    return {
        "work_order_science_input_gap_row_count": len(rows),
        "work_order_science_input_gap_blocked_row_count": blocked_count,
        "work_order_local_ligand_pose_artifact_count": local_ligand_count,
        "work_order_missing_ligand_pose_artifact_count": len(rows) - local_ligand_count,
        "work_order_receptor_coordinate_ready_row_count": receptor_ready_count,
        "work_order_missing_receptor_coordinate_row_count": len(rows) - receptor_ready_count,
        "work_order_ligand_pose_only_row_count": sum(
            1
            for row in rows
            if row["ligand_pose_artifact_present"] and not row["receptor_coordinate_artifact_present"]
        ),
        "work_order_interaction_metric_source_ready_row_count": interaction_ready_count,
        "work_order_missing_interaction_metric_source_row_count": len(rows) - interaction_ready_count,
        "work_order_internal_deltaG_source_ready_row_count": internal_delta_g_ready_count,
        "work_order_missing_internal_deltaG_source_row_count": len(rows) - internal_delta_g_ready_count,
    }


def _accepted_receptor_coordinate_patterns(target_id: str) -> str:
    target = _text(target_id).lower()
    if not target:
        return ""
    suffix_patterns = [
        f"{target}_protein.pdb",
        f"{target}_protein.cif",
        f"{target}_receptor.pdb",
        f"{target}_receptor.cif",
        f"{target}_complex.pdb",
        f"{target}_complex.cif",
        f"{target}.pdb",
        f"{target}.cif",
    ]
    return ";".join(suffix_patterns)


def _expected_receptor_archive_member_examples(target_id: str) -> str:
    target = _text(target_id).lower()
    if not target:
        return ""
    return ";".join(
        [
            f"pdbbind/{target}/{target}_protein.pdb",
            f"pdbbind/{target}/{target}_receptor.cif",
            f"casf/{target}/{target}_complex.pdb",
        ]
    )


def _suggested_public_coordinate_urls(target_id: str) -> str:
    target = _text(target_id).strip()
    if not target or len(target) != 4 or not target.isalnum():
        return ""
    pdb_id = target.upper()
    return ";".join(
        [
            f"https://files.rcsb.org/download/{pdb_id}.cif",
            f"https://files.rcsb.org/download/{pdb_id}.pdb",
        ]
    )


def _suggested_local_coordinate_paths(target_id: str, dataset_dir: str | Path) -> str:
    target = _text(target_id).lower()
    if not target:
        return ""
    dataset = _resolve(dataset_dir)
    candidates = [
        dataset / f"{target}_protein.pdb",
        dataset / target / f"{target}_protein.pdb",
        dataset / target / f"{target}_receptor.cif",
        dataset / "CASF-2016_scoring" / target / f"{target}_complex.pdb",
        dataset / "PDBbind_v2016_refined" / target / f"{target}_protein.pdb",
    ]
    return ";".join(_display_path(candidate) for candidate in candidates)


def _operator_coordinate_source_review_required(target_id: str) -> str:
    if not _text(target_id):
        return ""
    return (
        "confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target"
    )


def _build_receptor_coordinate_intake_rows(
    science_input_gap_rows: list[dict[str, Any]],
    *,
    dataset_dir: str | Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in science_input_gap_rows:
        target_id = _text(row.get("target_id"))
        present = bool(row.get("receptor_coordinate_artifact_present"))
        rows.append(
            {
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": target_id,
                "pose_id": _text(row.get("pose_id")),
                "current_receptor_coordinate_artifact": _text(row.get("receptor_coordinate_artifact")),
                "receptor_coordinate_artifact_present": present,
                "accepted_offline_coordinate_patterns": _accepted_receptor_coordinate_patterns(target_id),
                "expected_archive_member_examples": _expected_receptor_archive_member_examples(target_id),
                "suggested_public_coordinate_urls": _suggested_public_coordinate_urls(target_id),
                "suggested_local_coordinate_paths": _suggested_local_coordinate_paths(target_id, dataset_dir),
                "operator_coordinate_source_review_required": _operator_coordinate_source_review_required(
                    target_id
                ),
                "next_operator_action": (
                    "none"
                    if present
                    else "place_reviewed_public_receptor_or_complex_coordinate_in_dataset_dir_or_tar_archive"
                ),
            }
        )
    return rows


def _receptor_coordinate_intake_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matched = sum(1 for row in rows if row["receptor_coordinate_artifact_present"])
    suggested_public_url = sum(1 for row in rows if _text(row.get("suggested_public_coordinate_urls")))
    suggested_local_path = sum(1 for row in rows if _text(row.get("suggested_local_coordinate_paths")))
    operator_review_required = sum(
        1 for row in rows if _text(row.get("operator_coordinate_source_review_required"))
    )
    return {
        "work_order_receptor_coordinate_intake_row_count": len(rows),
        "work_order_receptor_coordinate_intake_matched_row_count": matched,
        "work_order_receptor_coordinate_intake_missing_row_count": len(rows) - matched,
        "work_order_receptor_coordinate_intake_suggested_public_url_row_count": suggested_public_url,
        "work_order_receptor_coordinate_intake_suggested_local_path_row_count": suggested_local_path,
        "work_order_receptor_coordinate_intake_operator_review_required_row_count": (
            operator_review_required
        ),
    }


def _read_coordinate_artifact_text(artifact: str) -> tuple[str, str, str]:
    artifact = _text(artifact)
    if not artifact:
        return "", "missing", "missing"
    if "::" in artifact:
        archive_text, member_name = artifact.split("::", 1)
        archive_path = _resolve(archive_text)
        try:
            with tarfile.open(archive_path, "r:*") as handle:
                extracted = handle.extractfile(member_name)
                if extracted is None:
                    return "", "tar_member", "member_not_found"
                return extracted.read().decode("utf-8", errors="replace"), "tar_member", "read"
        except (tarfile.TarError, OSError, UnicodeDecodeError):
            return "", "tar_member", "read_error"
    path = _resolve(artifact)
    try:
        return path.read_text(encoding="utf-8", errors="replace"), "local_file", "read"
    except OSError:
        return "", "local_file", "read_error"


def _coordinate_record_counts(text: str) -> dict[str, int]:
    pdb_atom_count = 0
    pdb_hetatm_count = 0
    mol2_atom_count = 0
    model_count = 0
    residue_keys: set[str] = set()
    protein_like_residue_keys: set[str] = set()
    protein_like_atom_count = 0
    in_mol2_atom_section = False

    def pdb_residue_parts(raw_line: str, stripped_line: str) -> tuple[str, str]:
        if len(raw_line) >= 27:
            resname = raw_line[17:20].strip()
            chain = raw_line[21:22].strip()
            resseq = raw_line[22:26].strip()
            icode = raw_line[26:27].strip()
            if resname or chain or resseq or icode:
                return f"pdb:{chain}:{resseq}:{icode}:{resname}", resname.upper()
        parts = stripped_line.split()
        if len(parts) >= 6:
            return "pdb:" + ":".join(parts[3:6]), parts[3].upper()
        return "", ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        upper = line.upper()
        if upper.startswith("MODEL"):
            model_count += 1
        if upper.startswith("ATOM"):
            pdb_atom_count += 1
            residue_key, residue_name = pdb_residue_parts(raw_line, line)
            if residue_key:
                residue_keys.add(residue_key)
                if residue_name in PROTEIN_LIKE_RESIDUE_NAMES:
                    protein_like_atom_count += 1
                    protein_like_residue_keys.add(residue_key)
            continue
        if upper.startswith("HETATM"):
            pdb_hetatm_count += 1
            continue
        if upper.startswith("@<TRIPOS>ATOM"):
            in_mol2_atom_section = True
            continue
        if upper.startswith("@<TRIPOS>"):
            in_mol2_atom_section = False
            continue
        if in_mol2_atom_section and line:
            mol2_atom_count += 1
            parts = line.split()
            if len(parts) >= 8:
                residue_key = f"mol2:{parts[6]}:{parts[7]}"
                residue_name = parts[7].upper()
                residue_keys.add(residue_key)
                if residue_name in PROTEIN_LIKE_RESIDUE_NAMES:
                    protein_like_atom_count += 1
                    protein_like_residue_keys.add(residue_key)
    atom_count = pdb_atom_count + pdb_hetatm_count + mol2_atom_count
    macromolecule_atom_count = max(pdb_atom_count, mol2_atom_count)
    return {
        "coordinate_atom_record_count": atom_count,
        "coordinate_pdb_atom_record_count": pdb_atom_count,
        "coordinate_pdb_hetatm_record_count": pdb_hetatm_count,
        "coordinate_mol2_atom_record_count": mol2_atom_count,
        "coordinate_macromolecule_atom_record_count": macromolecule_atom_count,
        "coordinate_distinct_residue_count": len(residue_keys),
        "coordinate_protein_like_atom_record_count": protein_like_atom_count,
        "coordinate_protein_like_residue_count": len(protein_like_residue_keys),
        "coordinate_model_record_count": model_count,
    }


def _build_receptor_coordinate_validation_rows(science_input_gap_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in science_input_gap_rows:
        artifact = _text(row.get("receptor_coordinate_artifact"))
        present = bool(row.get("receptor_coordinate_artifact_present"))
        text, source_kind, read_status = _read_coordinate_artifact_text(artifact)
        counts = _coordinate_record_counts(text) if read_status == "read" else {
            "coordinate_atom_record_count": 0,
            "coordinate_pdb_atom_record_count": 0,
            "coordinate_pdb_hetatm_record_count": 0,
            "coordinate_mol2_atom_record_count": 0,
            "coordinate_macromolecule_atom_record_count": 0,
            "coordinate_distinct_residue_count": 0,
            "coordinate_protein_like_atom_record_count": 0,
            "coordinate_protein_like_residue_count": 0,
            "coordinate_model_record_count": 0,
        }
        blockers: list[str] = []
        if not present:
            blockers.append("receptor_coordinate_missing")
            parse_status = "missing"
        elif read_status != "read":
            blockers.append(f"receptor_coordinate_{read_status}")
            parse_status = read_status
        elif counts["coordinate_atom_record_count"] < MIN_RECEPTOR_COORDINATE_ATOM_RECORDS:
            blockers.append("receptor_coordinate_atom_record_count_below_min")
            parse_status = "parsed_coordinate_records"
        elif (
            counts["coordinate_macromolecule_atom_record_count"]
            < MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS
            or counts["coordinate_distinct_residue_count"] < MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES
        ):
            blockers.append("receptor_coordinate_macromolecule_record_count_below_min")
            parse_status = "parsed_coordinate_records"
        elif counts["coordinate_protein_like_residue_count"] < MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES:
            blockers.append("receptor_coordinate_protein_like_residue_count_below_min")
            parse_status = "parsed_coordinate_records"
        else:
            parse_status = "parsed_coordinate_records"
        validation_status = "pass" if not blockers else "blocked"
        rows.append(
            {
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
                "pose_id": _text(row.get("pose_id")),
                "receptor_coordinate_artifact": artifact,
                "receptor_coordinate_artifact_present": present,
                "receptor_coordinate_artifact_sha256": _input_artifact_sha256(artifact) if present else "",
                "coordinate_source_kind": source_kind,
                "coordinate_parse_status": parse_status,
                **counts,
                "coordinate_validation_status": validation_status,
                "blockers": ";".join(blockers),
                "next_required_science_input": "none" if validation_status == "pass" else "validated_native_receptor_or_complex_coordinate",
            }
        )
    return rows


def _receptor_coordinate_validation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for row in rows if row["coordinate_validation_status"] == "pass")
    missing = sum(1 for row in rows if "receptor_coordinate_missing" in _text(row.get("blockers")).split(";"))
    read_error = sum(1 for row in rows if _text(row.get("coordinate_parse_status")) in {"read_error", "member_not_found"})
    below_min = sum(
        1
        for row in rows
        if "receptor_coordinate_atom_record_count_below_min" in _text(row.get("blockers")).split(";")
    )
    below_macromolecule = sum(
        1
        for row in rows
        if "receptor_coordinate_macromolecule_record_count_below_min" in _text(row.get("blockers")).split(";")
    )
    below_protein_like = sum(
        1
        for row in rows
        if "receptor_coordinate_protein_like_residue_count_below_min" in _text(row.get("blockers")).split(";")
    )
    return {
        "work_order_receptor_coordinate_validation_row_count": len(rows),
        "work_order_receptor_coordinate_validation_ready_row_count": ready,
        "work_order_receptor_coordinate_validation_blocked_row_count": len(rows) - ready,
        "work_order_receptor_coordinate_validation_missing_row_count": missing,
        "work_order_receptor_coordinate_validation_read_error_row_count": read_error,
        "work_order_receptor_coordinate_validation_below_min_atom_row_count": below_min,
        "work_order_receptor_coordinate_validation_below_min_macromolecule_row_count": below_macromolecule,
        "work_order_receptor_coordinate_validation_below_min_protein_like_row_count": below_protein_like,
        "work_order_receptor_coordinate_validation_min_atom_records": MIN_RECEPTOR_COORDINATE_ATOM_RECORDS,
        "work_order_receptor_coordinate_validation_min_macromolecule_atom_records": (
            MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS
        ),
        "work_order_receptor_coordinate_validation_min_distinct_residues": (
            MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES
        ),
        "work_order_receptor_coordinate_validation_min_protein_like_residues": (
            MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES
        ),
    }


def _metric_source_present(artifact: str) -> bool:
    artifact = _text(artifact)
    if not artifact or _has_placeholder(artifact):
        return False
    return _resolve(artifact).is_file()


def _metric_source_payload_validation(
    artifact: str,
    *,
    expected_metric_name: str,
    expected_target_id: str,
    expected_pose_id: str,
    expected_value: Any,
    expected_input_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    artifact = _text(artifact)
    path = _resolve(artifact) if artifact and not _has_placeholder(artifact) else None
    blockers: list[str] = []
    present = bool(path and path.is_file())
    if not present:
        return {
            "artifact_present": False,
            "payload_valid": False,
            "payload_blockers": "source_artifact_missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "artifact_present": True,
            "payload_valid": False,
            "payload_blockers": "source_payload_json_invalid",
        }
    if not isinstance(payload, dict):
        return {
            "artifact_present": True,
            "payload_valid": False,
            "payload_blockers": "source_payload_not_object",
        }
    missing_fields = [field for field in REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS if _payload_field_missing(payload, field)]
    if missing_fields:
        blockers.append("source_payload_required_fields_missing:" + ",".join(missing_fields))
    if _text(payload.get("metric_name")) != expected_metric_name:
        blockers.append("source_payload_metric_name_mismatch")
    if _text(payload.get("target_id")) != _text(expected_target_id):
        blockers.append("source_payload_target_id_mismatch")
    if _text(payload.get("pose_id")) != _text(expected_pose_id):
        blockers.append("source_payload_pose_id_mismatch")
    expected_numeric = _float(expected_value)
    payload_numeric = _float(payload.get("value"))
    if expected_numeric is None or payload_numeric is None:
        blockers.append("source_payload_value_not_numeric")
    elif abs(expected_numeric - payload_numeric) > 1e-9:
        blockers.append("source_payload_value_mismatch")
    if not _text(payload.get("method")) or _has_placeholder(payload.get("method")):
        blockers.append("source_payload_method_missing")
    if not _nonempty_input_artifacts(payload.get("input_artifacts")):
        blockers.append("source_payload_input_artifacts_missing")
    elif not _local_input_artifacts_present(payload.get("input_artifacts")):
        blockers.append("source_payload_input_artifacts_not_found")
    elif not _payload_input_artifact_hashes_valid(
        payload.get("input_artifacts"),
        payload.get("input_artifact_sha256s"),
    ):
        blockers.append("source_payload_input_artifact_sha256_mismatch")
    elif not _payload_includes_required_input_artifacts(
        payload.get("input_artifacts"),
        list(expected_input_artifacts or []),
    ):
        blockers.append("source_payload_required_input_artifacts_missing")
    if not _text(payload.get("operator_id")) or _has_placeholder(payload.get("operator_id")):
        blockers.append("source_payload_operator_id_missing")
    if not _is_iso_timestamp(payload.get("reviewed_at_utc")):
        blockers.append("source_payload_reviewed_at_utc_invalid")
    if _bool(payload.get("license_ok")) is not True:
        blockers.append("source_payload_license_not_ok")
    if not _zero_external_engine_calls(payload.get("external_engine_calls")):
        blockers.append("source_payload_external_engine_calls_not_zero")
    return {
        "artifact_present": True,
        "payload_valid": not blockers,
        "payload_blockers": ";".join(blockers),
    }


def _build_metric_evidence_rows(
    work_order_rows: list[dict[str, Any]],
    science_input_gap_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    science_gap_by_work_order_id = {
        _text(row.get("work_order_id")): row
        for row in list(science_input_gap_rows or [])
        if _text(row.get("work_order_id"))
    }
    for row in work_order_rows:
        work_order_id = _text(row.get("work_order_id"))
        target_id = _text(row.get("target_id"))
        pose_id = _pose_id_from_work_order_row(row)
        science_gap_row = science_gap_by_work_order_id.get(work_order_id, {})
        ligand_artifact = _text(science_gap_row.get("ligand_pose_artifact"))
        receptor_artifact = _text(science_gap_row.get("receptor_coordinate_artifact"))
        required_input_artifacts = [artifact for artifact in (ligand_artifact, receptor_artifact) if artifact]
        required_input_artifact_sha256s = [
            _input_artifact_sha256(artifact)
            for artifact in required_input_artifacts
        ]
        missing_required_inputs = []
        if not ligand_artifact:
            missing_required_inputs.append("ligand_pose_artifact")
        if not receptor_artifact:
            missing_required_inputs.append("receptor_coordinate_artifact")
        dockq = _text(row.get("dockq"))
        lddt_pli = _text(row.get("lddt_pli"))
        internal_delta_g = _text(row.get("deltaG_mm_gbsa_kcal_mol"))
        dockq_source = _text(row.get("dockq_source_artifact"))
        lddt_source = _text(row.get("lddt_pli_source_artifact"))
        internal_delta_g_source = _text(row.get("internal_deltaG_source_artifact"))
        dockq_source_validation = _metric_source_payload_validation(
            dockq_source,
            expected_metric_name="dockq",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=dockq,
            expected_input_artifacts=required_input_artifacts,
        )
        lddt_source_validation = _metric_source_payload_validation(
            lddt_source,
            expected_metric_name="lddt_pli",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=lddt_pli,
            expected_input_artifacts=required_input_artifacts,
        )
        internal_delta_g_source_validation = _metric_source_payload_validation(
            internal_delta_g_source,
            expected_metric_name="internal_deltaG",
            expected_target_id=target_id,
            expected_pose_id=pose_id,
            expected_value=internal_delta_g,
            expected_input_artifacts=required_input_artifacts,
        )
        dockq_source_present = bool(dockq_source_validation["artifact_present"])
        lddt_source_present = bool(lddt_source_validation["artifact_present"])
        internal_delta_g_source_present = bool(internal_delta_g_source_validation["artifact_present"])
        dockq_source_payload_valid = bool(dockq_source_validation["payload_valid"])
        lddt_source_payload_valid = bool(lddt_source_validation["payload_valid"])
        internal_delta_g_source_payload_valid = bool(internal_delta_g_source_validation["payload_valid"])
        blockers: list[str] = []
        if _float(dockq) is None:
            blockers.append("dockq_value_missing")
        if _float(lddt_pli) is None:
            blockers.append("lddt_pli_value_missing")
        if _float(internal_delta_g) is None:
            blockers.append("internal_deltaG_value_missing")
        if missing_required_inputs:
            blockers.append("metric_required_input_artifacts_missing:" + ",".join(missing_required_inputs))
        elif not all(required_input_artifact_sha256s):
            blockers.append("metric_required_input_artifact_sha256_missing")
        if not dockq_source_present:
            blockers.append("dockq_source_artifact_missing")
        if not lddt_source_present:
            blockers.append("lddt_pli_source_artifact_missing")
        if not internal_delta_g_source_present:
            blockers.append("internal_deltaG_source_artifact_missing")
        if dockq_source_present and not dockq_source_payload_valid:
            blockers.append("dockq_source_payload_invalid")
        if lddt_source_present and not lddt_source_payload_valid:
            blockers.append("lddt_pli_source_payload_invalid")
        if internal_delta_g_source_present and not internal_delta_g_source_payload_valid:
            blockers.append("internal_deltaG_source_payload_invalid")
        status = "pass" if not blockers else "blocked"
        rows.append(
            {
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": target_id,
                "pose_id": pose_id,
                "dockq": dockq,
                "lddt_pli": lddt_pli,
                "deltaG_mm_gbsa_kcal_mol": internal_delta_g,
                "dockq_source_artifact": dockq_source,
                "lddt_pli_source_artifact": lddt_source,
                "internal_deltaG_source_artifact": internal_delta_g_source,
                "expected_dockq_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_dockq.json"
                ),
                "expected_lddt_pli_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_lddt_pli.json"
                ),
                "expected_internal_deltaG_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_internal_deltaG.json"
                ),
                "required_metric_input_artifacts": ";".join(required_input_artifacts),
                "required_metric_input_artifact_sha256s": ";".join(required_input_artifact_sha256s),
                "missing_required_metric_input_artifacts": ";".join(missing_required_inputs),
                "required_metric_source_payload_fields": (
                    ";".join(REQUIRED_METRIC_SOURCE_PAYLOAD_FIELDS)
                ),
                "dockq_source_artifact_present": dockq_source_present,
                "lddt_pli_source_artifact_present": lddt_source_present,
                "internal_deltaG_source_artifact_present": internal_delta_g_source_present,
                "dockq_source_payload_valid": dockq_source_payload_valid,
                "lddt_pli_source_payload_valid": lddt_source_payload_valid,
                "internal_deltaG_source_payload_valid": internal_delta_g_source_payload_valid,
                "dockq_source_payload_blockers": dockq_source_validation["payload_blockers"],
                "lddt_pli_source_payload_blockers": lddt_source_validation["payload_blockers"],
                "internal_deltaG_source_payload_blockers": internal_delta_g_source_validation["payload_blockers"],
                "metric_evidence_status": status,
                "blockers": ";".join(blockers),
                "next_required_science_input": "none" if status == "pass" else "reviewed_local_metric_evidence_artifacts",
                "metric_evidence_next_operator_action": (
                    "none"
                    if status == "pass"
                    else "place_reviewed_local_metric_evidence_artifacts_and_copy_paths_into_work_order"
                ),
            }
        )
    return rows


def _metric_evidence_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for row in rows if row["metric_evidence_status"] == "pass")
    missing_dockq_source = sum(1 for row in rows if not row["dockq_source_artifact_present"])
    missing_lddt_source = sum(1 for row in rows if not row["lddt_pli_source_artifact_present"])
    missing_internal_delta_g_source = sum(1 for row in rows if not row["internal_deltaG_source_artifact_present"])
    invalid_dockq_source = sum(
        1 for row in rows if row["dockq_source_artifact_present"] and not row["dockq_source_payload_valid"]
    )
    invalid_lddt_source = sum(
        1 for row in rows if row["lddt_pli_source_artifact_present"] and not row["lddt_pli_source_payload_valid"]
    )
    invalid_internal_delta_g_source = sum(
        1
        for row in rows
        if row["internal_deltaG_source_artifact_present"] and not row["internal_deltaG_source_payload_valid"]
    )
    missing_required_inputs = sum(1 for row in rows if _text(row.get("missing_required_metric_input_artifacts")))
    missing_required_hashes = sum(
        1
        for row in rows
        if (
            _text(row.get("required_metric_input_artifacts"))
            and (
                len(_input_artifact_entries(row.get("required_metric_input_artifacts"))) != len(
                    _input_artifact_entries(row.get("required_metric_input_artifact_sha256s"))
                )
                or not all(_input_artifact_entries(row.get("required_metric_input_artifact_sha256s")))
            )
        )
    )
    return {
        "work_order_metric_evidence_required": True,
        "work_order_metric_evidence_row_count": len(rows),
        "work_order_metric_evidence_ready_row_count": ready,
        "work_order_metric_evidence_blocked_row_count": len(rows) - ready,
        "work_order_metric_evidence_missing_dockq_source_row_count": missing_dockq_source,
        "work_order_metric_evidence_missing_lddt_pli_source_row_count": missing_lddt_source,
        "work_order_metric_evidence_missing_internal_deltaG_source_row_count": missing_internal_delta_g_source,
        "work_order_metric_evidence_invalid_dockq_source_payload_row_count": invalid_dockq_source,
        "work_order_metric_evidence_invalid_lddt_pli_source_payload_row_count": invalid_lddt_source,
        "work_order_metric_evidence_invalid_internal_deltaG_source_payload_row_count": invalid_internal_delta_g_source,
        "work_order_metric_evidence_missing_required_input_artifact_row_count": missing_required_inputs,
        "work_order_metric_evidence_missing_required_input_artifact_sha256_row_count": missing_required_hashes,
    }


def _read_experimental_delta_g_by_complex(path_like: str | Path) -> tuple[dict[str, float], dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, {
            "work_order_experimental_deltaG_source": str(path_like),
            "work_order_experimental_deltaG_source_present": False,
            "work_order_experimental_deltaG_source_row_count": 0,
            "work_order_experimental_deltaG_source_parsed_count": 0,
            "work_order_experimental_deltaG_source_invalid_count": 0,
            "work_order_experimental_deltaG_temperature_K": DEFAULT_DELTA_G_TEMPERATURE_K,
            "work_order_experimental_deltaG_conversion": "deltaG_kcal_mol=-RTln(10)*pAffinity",
        }

    values: dict[str, float] = {}
    source_row_count = 0
    invalid_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            source_row_count += 1
            parts = text.split()
            if len(parts) < 2:
                invalid_count += 1
                continue
            complex_id = parts[0].strip().lower()
            paffinity = _float(parts[1])
            if not complex_id or paffinity is None:
                invalid_count += 1
                continue
            values[complex_id] = PAFFINITY_TO_DG_KCAL_PER_MOL * paffinity

    return values, {
        "work_order_experimental_deltaG_source": str(path_like),
        "work_order_experimental_deltaG_source_present": True,
        "work_order_experimental_deltaG_source_row_count": source_row_count,
        "work_order_experimental_deltaG_source_parsed_count": len(values),
        "work_order_experimental_deltaG_source_invalid_count": invalid_count,
        "work_order_experimental_deltaG_temperature_K": DEFAULT_DELTA_G_TEMPERATURE_K,
        "work_order_experimental_deltaG_conversion": "deltaG_kcal_mol=-RTln(10)*pAffinity",
    }


def _seed_rows_from_pose_benchmark(
    path_like: str | Path,
    *,
    needed: int,
    max_pose_rmsd_a: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, columns, present = _read_csv(path_like)
    required_seed_columns = ["suite_id", "complex_id", "pose_id", "pose_rmsd_A", "blocker_count", "blockers"]
    missing_columns = [column for column in required_seed_columns if column not in columns] if present else list(required_seed_columns)
    best_by_complex: dict[str, dict[str, Any]] = {}
    candidate_count = 0
    for row in rows:
        complex_id = _text(row.get("complex_id"))
        pose_id = _text(row.get("pose_id"))
        pose_rmsd = _float(row.get("pose_rmsd_A"))
        if not complex_id or not pose_id or pose_rmsd is None:
            continue
        if _int(row.get("blocker_count")) != 0 or _text(row.get("blockers")):
            continue
        if pose_rmsd > float(max_pose_rmsd_a):
            continue
        candidate_count += 1
        current = best_by_complex.get(complex_id)
        current_rmsd = _float(current.get("pose_rmsd_A")) if current else None
        if current is None or current_rmsd is None or pose_rmsd < current_rmsd:
            best_by_complex[complex_id] = row

    selected = sorted(
        best_by_complex.values(),
        key=lambda row: (_float(row.get("pose_rmsd_A")) or float("inf"), _text(row.get("complex_id")), _text(row.get("pose_id"))),
    )[: max(0, int(needed))]
    summary = {
        "work_order_seed_csv": str(path_like),
        "work_order_seed_csv_present": present,
        "work_order_seed_missing_columns": missing_columns,
        "work_order_seed_column_count": len(columns),
        "work_order_seed_receptor_column_count": _column_count(columns, SEED_RECEPTOR_COLUMN_NAMES),
        "work_order_seed_interaction_metric_column_count": _column_count(
            columns,
            SEED_INTERACTION_METRIC_COLUMN_NAMES,
        ),
        "work_order_seed_internal_deltaG_column_count": _column_count(columns, SEED_INTERNAL_DG_COLUMN_NAMES),
        "work_order_seed_source_row_count": len(rows),
        "work_order_seed_candidate_row_count": candidate_count,
        "work_order_seed_distinct_target_count": len(best_by_complex),
        "work_order_seed_selected_row_count": len(selected),
    }
    return selected, summary


def _operator_field_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pending = 0
    prefilled = 0
    pending_by_field = {field_name: 0 for field_name in WORK_ORDER_OPERATOR_FIELDS}
    prefilled_by_field = {field_name: 0 for field_name in WORK_ORDER_OPERATOR_FIELDS}
    for row in rows:
        for field_name in WORK_ORDER_OPERATOR_FIELDS:
            if _has_placeholder(row.get(field_name)):
                pending += 1
                pending_by_field[field_name] += 1
            else:
                prefilled += 1
                prefilled_by_field[field_name] += 1
    return {
        "work_order_operator_field_count": len(rows) * len(WORK_ORDER_OPERATOR_FIELDS),
        "work_order_prefilled_operator_field_count": prefilled,
        "work_order_pending_operator_field_count": pending,
        "work_order_pending_operator_field_counts": pending_by_field,
        "work_order_prefilled_operator_field_counts": prefilled_by_field,
        "work_order_pending_license_ok_count": pending_by_field["license_ok"],
        "work_order_pending_dockq_count": pending_by_field["dockq"],
        "work_order_pending_lddt_pli_count": pending_by_field["lddt_pli"],
        "work_order_pending_internal_deltaG_count": pending_by_field["deltaG_mm_gbsa_kcal_mol"],
        "work_order_pending_experimental_deltaG_count": pending_by_field["deltaG_experimental_kcal_mol"],
        "work_order_remaining_operator_license_review_field_count": pending_by_field["license_ok"],
        "work_order_remaining_receptor_interaction_metric_field_count": (
            pending_by_field["dockq"] + pending_by_field["lddt_pli"]
            + pending_by_field["dockq_source_artifact"]
            + pending_by_field["lddt_pli_source_artifact"]
        ),
        "work_order_remaining_internal_refine_deltaG_field_count": pending_by_field[
            "deltaG_mm_gbsa_kcal_mol"
        ] + pending_by_field["internal_deltaG_source_artifact"],
    }


def _row_status(row: dict[str, Any], *, max_pose_rmsd_a: float, min_dockq: float, min_lddt_pli: float) -> dict[str, Any]:
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in row]
    provenance_ok = _text(row.get("provenance_kind")) in ALLOWED_PROVENANCE_KINDS and bool(_text(row.get("provenance_id")))
    split_ok = _text(row.get("split")).lower() in ALLOWED_SPLITS
    license_ok = _bool(row.get("license_ok"))
    external_engine_calls = _int(row.get("external_engine_calls"), default=999999)
    external_engine_ok = external_engine_calls == 0
    pose_rmsd = _float(row.get("pose_rmsd_A"))
    dockq = _float(row.get("dockq"))
    lddt = _float(row.get("lddt_pli"))
    dg_refine = _float(row.get("deltaG_mm_gbsa_kcal_mol"))
    dg_exp = _float(row.get("deltaG_experimental_kcal_mol"))
    target_id = _text(row.get("target_id"))
    pose_id = _pose_id_from_work_order_row(row) or _text(row.get("pose_id"))
    dockq_source_validation = _metric_source_payload_validation(
        row.get("dockq_source_artifact"),
        expected_metric_name="dockq",
        expected_target_id=target_id,
        expected_pose_id=pose_id,
        expected_value=row.get("dockq"),
    )
    lddt_source_validation = _metric_source_payload_validation(
        row.get("lddt_pli_source_artifact"),
        expected_metric_name="lddt_pli",
        expected_target_id=target_id,
        expected_pose_id=pose_id,
        expected_value=row.get("lddt_pli"),
    )
    internal_delta_g_source_validation = _metric_source_payload_validation(
        row.get("internal_deltaG_source_artifact"),
        expected_metric_name="internal_deltaG",
        expected_target_id=target_id,
        expected_pose_id=pose_id,
        expected_value=row.get("deltaG_mm_gbsa_kcal_mol"),
    )
    dockq_source_present = bool(dockq_source_validation["artifact_present"])
    lddt_source_present = bool(lddt_source_validation["artifact_present"])
    internal_delta_g_source_present = bool(internal_delta_g_source_validation["artifact_present"])
    dockq_source_payload_valid = bool(dockq_source_validation["payload_valid"])
    lddt_source_payload_valid = bool(lddt_source_validation["payload_valid"])
    internal_delta_g_source_payload_valid = bool(internal_delta_g_source_validation["payload_valid"])
    pose_metrics_present = pose_rmsd is not None and dockq is not None and lddt is not None
    pose_metrics_pass = bool(
        pose_metrics_present
        and pose_rmsd <= float(max_pose_rmsd_a)
        and dockq >= float(min_dockq)
        and lddt >= float(min_lddt_pli)
    )
    free_energy_pair_present = dg_refine is not None and dg_exp is not None
    blockers: list[str] = []
    if missing_columns:
        blockers.append("missing_columns:" + ",".join(missing_columns))
    if not provenance_ok:
        blockers.append("provenance_missing_or_unaccepted")
    if not split_ok:
        blockers.append("split_missing_or_unaccepted")
    if not license_ok:
        blockers.append("license_not_ok")
    if not external_engine_ok:
        blockers.append("external_engine_calls_present")
    if not pose_metrics_present:
        blockers.append("pose_metrics_missing")
    elif not pose_metrics_pass:
        blockers.append("pose_metrics_threshold_failed")
    if not free_energy_pair_present:
        blockers.append("free_energy_pair_missing")
    if not (dockq_source_present and lddt_source_present and internal_delta_g_source_present):
        blockers.append("metric_source_artifacts_missing")
    elif not (dockq_source_payload_valid and lddt_source_payload_valid and internal_delta_g_source_payload_valid):
        blockers.append("metric_source_payloads_invalid")
    return {
        **row,
        "row_status": "pass" if not blockers else "blocked",
        "blockers": ";".join(blockers),
        "provenance_ok": provenance_ok,
        "split_ok": split_ok,
        "license_ok_bool": license_ok,
        "external_engine_ok": external_engine_ok,
        "pose_metrics_present": pose_metrics_present,
        "pose_metrics_pass": pose_metrics_pass,
        "free_energy_pair_present": free_energy_pair_present,
        "dockq_source_artifact_present": dockq_source_present,
        "lddt_pli_source_artifact_present": lddt_source_present,
        "internal_deltaG_source_artifact_present": internal_delta_g_source_present,
        "dockq_source_payload_valid": dockq_source_payload_valid,
        "lddt_pli_source_payload_valid": lddt_source_payload_valid,
        "internal_deltaG_source_payload_valid": internal_delta_g_source_payload_valid,
        "dockq_source_payload_blockers": dockq_source_validation["payload_blockers"],
        "lddt_pli_source_payload_blockers": lddt_source_validation["payload_blockers"],
        "internal_deltaG_source_payload_blockers": internal_delta_g_source_validation["payload_blockers"],
    }


def _build_operator_work_order_rows(
    *,
    input_csv: str | Path,
    existing_row_count: int,
    valid_row_count: int,
    pose_pass_count: int,
    free_energy_pair_count: int,
    fit_split_present: bool,
    holdout_or_test_split_present: bool,
    min_total_rows: int,
    min_pose_rows: int,
    min_free_energy_pairs: int,
    seed_rows: list[dict[str, Any]] | None = None,
    experimental_delta_g_by_complex: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    needed = max(
        int(min_total_rows) - int(existing_row_count),
        int(min_total_rows) - int(valid_row_count),
        int(min_pose_rows) - int(pose_pass_count),
        int(min_free_energy_pairs) - int(free_energy_pair_count),
        0,
    )
    if needed <= 0 and fit_split_present and holdout_or_test_split_present:
        return []
    if needed <= 0:
        needed = 2

    rows: list[dict[str, Any]] = []
    seed_rows = list(seed_rows or [])[:needed]
    experimental_delta_g_by_complex = dict(experimental_delta_g_by_complex or {})
    for idx in range(needed):
        split = "fit" if idx < max(1, min(5, needed - 1)) else "holdout"
        if not fit_split_present and holdout_or_test_split_present and idx == 0:
            split = "fit"
        if fit_split_present and not holdout_or_test_split_present and idx == needed - 1:
            split = "holdout"
        seed_row = seed_rows[idx] if idx < len(seed_rows) else {}
        seed_complex_id = _text(seed_row.get("complex_id"))
        seed_pose_id = _text(seed_row.get("pose_id"))
        seed_pose_rmsd = _float(seed_row.get("pose_rmsd_A"))
        if seed_complex_id and seed_pose_id and seed_pose_rmsd is not None:
            experimental_delta_g = experimental_delta_g_by_complex.get(seed_complex_id.lower())
            benchmark_id = f"PDBBIND_CASF_{_stable_id(seed_complex_id)}_{_stable_id(seed_pose_id)}"
            target_id = seed_complex_id
            benchmark_family = "pdbbind_casf_refine_tier_public_seed"
            provenance_kind = "pdbbind"
            provenance_id = f"PDBBind/CASF:{seed_complex_id}:{seed_pose_id}"
            pose_rmsd_a = _format_float(seed_pose_rmsd)
            work_order_id = f"refine_tier_public_benchmark_seeded_{idx + 1:03d}"
            experimental_delta_g_text = (
                _format_float(experimental_delta_g)
                if experimental_delta_g is not None
                else "OPERATOR_FILL_PUBLIC_EXPERIMENTAL_DG"
            )
            acceptance_rule = (
                "PDBBind/CASF pose id and RMSD are prefilled from the local pose-affinity scorecard result; "
                "public experimental ΔG is prefilled when a matching local PDBBind pAffinity source row exists; "
                "operator must confirm source license and fill DockQ, lDDT-PLI, internal refine ΔG, and local metric source artifacts before this row can be applied."
            )
        else:
            benchmark_id = f"OPERATOR_FILL_PUBLIC_BENCHMARK_{idx + 1:03d}"
            target_id = "OPERATOR_FILL_TARGET_OR_COMPLEX_ID"
            benchmark_family = "pdbbind_or_casf_refine_tier_public"
            provenance_kind = "operator_curated_public"
            provenance_id = "OPERATOR_FILL_PUBLIC_SOURCE_ID"
            pose_rmsd_a = "OPERATOR_FILL_POSE_RMSD_A"
            work_order_id = f"refine_tier_public_benchmark_fill_{idx + 1:03d}"
            experimental_delta_g_text = "OPERATOR_FILL_PUBLIC_EXPERIMENTAL_DG"
            acceptance_rule = (
                "Fill all required columns from public provenance, set external_engine_calls=0, "
                "include local metric source artifacts, include at least one fit and one holdout/test split, and rerun this readiness gate."
            )
        row = {
            "work_order_id": work_order_id,
            "target_input_csv": str(input_csv),
            "template_row_index": idx + 1,
            "benchmark_id": benchmark_id,
            "target_id": target_id,
            "benchmark_family": benchmark_family,
            "split": split,
            "provenance_kind": provenance_kind,
            "provenance_id": provenance_id,
            "license_ok": "OPERATOR_CONFIRM_TRUE",
            "external_engine_calls": 0,
            "pose_rmsd_A": pose_rmsd_a,
            "dockq": "OPERATOR_FILL_DOCKQ",
            "lddt_pli": "OPERATOR_FILL_LDDT_PLI",
            "deltaG_mm_gbsa_kcal_mol": "OPERATOR_FILL_INTERNAL_REFINE_DG",
            "dockq_source_artifact": "OPERATOR_FILL_DOCKQ_SOURCE_ARTIFACT",
            "lddt_pli_source_artifact": "OPERATOR_FILL_LDDT_PLI_SOURCE_ARTIFACT",
            "internal_deltaG_source_artifact": "OPERATOR_FILL_INTERNAL_DELTAG_SOURCE_ARTIFACT",
            "deltaG_experimental_kcal_mol": experimental_delta_g_text,
            "operator_action": "append_validated_public_benchmark_row",
            "acceptance_rule": acceptance_rule,
            "external_state_mutated": False,
        }
        rows.append(row)
    return rows


def build_refine_tier_public_benchmark_readiness(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    min_total_rows: int = 8,
    min_pose_rows: int = 5,
    min_free_energy_pairs: int = 5,
    min_spearman: float = 0.5,
    max_pose_rmsd_a: float = 2.5,
    min_dockq: float = 0.23,
    min_lddt_pli: float = 0.5,
    work_order_seed_csv: str | Path = DEFAULT_WORK_ORDER_SEED_CSV,
    work_order_affinity_tsv: str | Path = DEFAULT_WORK_ORDER_AFFINITY_TSV,
    work_order_dataset_dir: str | Path = DEFAULT_WORK_ORDER_DATASET_DIR,
) -> dict[str, Any]:
    raw_rows, columns, input_present = _read_csv(input_csv)
    row_missing_columns = [col for col in REQUIRED_COLUMNS if col not in columns] if input_present else list(REQUIRED_COLUMNS)
    rows = [
        _row_status(row, max_pose_rmsd_a=max_pose_rmsd_a, min_dockq=min_dockq, min_lddt_pli=min_lddt_pli)
        for row in raw_rows
    ]
    valid_rows = [row for row in rows if not row["blockers"]]
    pose_rows = [row for row in rows if row["pose_metrics_present"]]
    pose_pass_rows = [row for row in rows if row["pose_metrics_pass"]]
    free_energy_rows = [row for row in rows if row["free_energy_pair_present"]]
    splits = sorted({_text(row.get("split")).lower() for row in rows if _text(row.get("split")).lower() in ALLOWED_SPLITS})
    fit_ready = "fit" in splits
    holdout_ready = bool({"holdout", "test"} & set(splits))
    spearman: float | None = None
    calibration_ready = False
    if free_energy_rows:
        fit = fit_linear_calibration(
            [_float(row.get("deltaG_mm_gbsa_kcal_mol")) for row in free_energy_rows],
            [_float(row.get("deltaG_experimental_kcal_mol")) for row in free_energy_rows],
        )
        gate = calibration_quality_gate(fit, min_pairs=min_free_energy_pairs, min_spearman=min_spearman)
        spearman = gate.get("spearman")
        calibration_ready = bool(gate.get("calibration_promotion_ready"))
    else:
        gate = {
            "calibration_promotion_ready": False,
            "pair_count": 0,
            "spearman": None,
            "min_pairs_required": min_free_energy_pairs,
            "min_spearman_required": min_spearman,
        }

    blockers: list[str] = []
    if not input_present:
        blockers.append("input_csv_missing")
    if row_missing_columns:
        blockers.append("required_columns_missing:" + ",".join(row_missing_columns))
    if len(rows) < int(min_total_rows):
        blockers.append("insufficient_total_rows")
    if len(valid_rows) < int(min_total_rows):
        blockers.append("insufficient_valid_rows")
    if len(pose_pass_rows) < int(min_pose_rows):
        blockers.append("insufficient_pose_metric_pass_rows")
    if len(free_energy_rows) < int(min_free_energy_pairs):
        blockers.append("insufficient_free_energy_pairs")
    if not calibration_ready:
        blockers.append("free_energy_spearman_or_pair_gate_not_ready")
    if not fit_ready or not holdout_ready:
        blockers.append("fit_and_holdout_splits_required")

    work_order_needed = max(
        int(min_total_rows) - int(len(rows)),
        int(min_total_rows) - int(len(valid_rows)),
        int(min_pose_rows) - int(len(pose_pass_rows)),
        int(min_free_energy_pairs) - int(len(free_energy_rows)),
        0,
    )
    if work_order_needed <= 0 and not (fit_ready and holdout_ready):
        work_order_needed = 2
    seed_rows, seed_summary = _seed_rows_from_pose_benchmark(
        work_order_seed_csv,
        needed=work_order_needed,
        max_pose_rmsd_a=max_pose_rmsd_a,
    )
    experimental_delta_g_by_complex, experimental_delta_g_summary = _read_experimental_delta_g_by_complex(
        work_order_affinity_tsv
    )
    metric_input_summary = _local_metric_input_availability(work_order_dataset_dir)

    ready = not blockers
    summary = {
        "packet_type": "refine_tier_public_benchmark_readiness",
        "status": "refine_tier_public_benchmark_ready" if ready else "blocked_refine_tier_public_benchmark_readiness",
        "claim_grade_public_benchmark_ready": ready,
        "benchmark_metric_surface_ready": len(pose_rows) > 0 and len(free_energy_rows) > 0,
        "input_csv": str(input_csv),
        "input_csv_present": input_present,
        "row_count": len(rows),
        "valid_row_count": len(valid_rows),
        "pose_metric_row_count": len(pose_rows),
        "pose_metric_pass_count": len(pose_pass_rows),
        "free_energy_pair_count": len(free_energy_rows),
        "fit_split_present": fit_ready,
        "holdout_or_test_split_present": holdout_ready,
        "free_energy_spearman": spearman,
        "min_total_rows_required": int(min_total_rows),
        "min_pose_rows_required": int(min_pose_rows),
        "min_free_energy_pairs_required": int(min_free_energy_pairs),
        "min_spearman_required": float(min_spearman),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        **seed_summary,
        **experimental_delta_g_summary,
        **metric_input_summary,
    }
    work_order_rows = _build_operator_work_order_rows(
        input_csv=input_csv,
        existing_row_count=len(rows),
        valid_row_count=len(valid_rows),
        pose_pass_count=len(pose_pass_rows),
        free_energy_pair_count=len(free_energy_rows),
        fit_split_present=fit_ready,
        holdout_or_test_split_present=holdout_ready,
        min_total_rows=min_total_rows,
        min_pose_rows=min_pose_rows,
        min_free_energy_pairs=min_free_energy_pairs,
        seed_rows=seed_rows,
        experimental_delta_g_by_complex=experimental_delta_g_by_complex,
    )
    science_input_gap_rows = _build_science_input_gap_rows(
        work_order_rows,
        dataset_dir=work_order_dataset_dir,
    )
    receptor_coordinate_intake_rows = _build_receptor_coordinate_intake_rows(
        science_input_gap_rows,
        dataset_dir=work_order_dataset_dir,
    )
    receptor_coordinate_validation_rows = _build_receptor_coordinate_validation_rows(science_input_gap_rows)
    metric_evidence_rows = _build_metric_evidence_rows(work_order_rows, science_input_gap_rows)
    summary.update(_operator_field_counts(work_order_rows))
    summary.update(_science_input_gap_summary(science_input_gap_rows))
    summary.update(_receptor_coordinate_intake_summary(receptor_coordinate_intake_rows))
    summary.update(_receptor_coordinate_validation_summary(receptor_coordinate_validation_rows))
    summary.update(_metric_evidence_summary(metric_evidence_rows))
    summary["work_order_current_local_source_prefill_ready_field_count"] = (
        (summary["work_order_pending_dockq_count"] if summary["work_order_seed_interaction_metric_column_count"] else 0)
        + (summary["work_order_pending_lddt_pli_count"] if summary["work_order_seed_interaction_metric_column_count"] else 0)
        + (
            summary["work_order_pending_internal_deltaG_count"]
            if summary["work_order_seed_internal_deltaG_column_count"]
            else 0
        )
    )
    summary["work_order_remaining_nonlicense_science_field_count"] = (
        summary["work_order_remaining_receptor_interaction_metric_field_count"]
        + summary["work_order_remaining_internal_refine_deltaG_field_count"]
    )
    summary["work_order_row_count"] = len(work_order_rows)
    summary["work_order_seeded_row_count"] = len(
        [row for row in work_order_rows if _text(row.get("work_order_id")).startswith("refine_tier_public_benchmark_seeded_")]
    )
    summary["work_order_experimental_deltaG_prefilled_count"] = len(
        [
            row
            for row in work_order_rows
            if not _has_placeholder(row.get("deltaG_experimental_kcal_mol"))
        ]
    )
    summary["operator_work_order_ready"] = bool(work_order_rows and not ready)
    summary["work_order_columns"] = WORK_ORDER_COLUMNS
    summary["work_order_csv"] = DEFAULT_OUT_WORK_ORDER_CSV
    summary["work_order_science_input_gap_csv"] = DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV
    summary["work_order_receptor_coordinate_intake_csv"] = DEFAULT_OUT_RECEPTOR_COORDINATE_INTAKE_CSV
    summary["work_order_receptor_coordinate_validation_csv"] = DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV
    summary["work_order_metric_evidence_csv"] = DEFAULT_OUT_METRIC_EVIDENCE_CSV
    summary["work_order_apply_command"] = DEFAULT_WORK_ORDER_APPLY_COMMAND
    summary["work_order_apply_write_intake_command"] = DEFAULT_WORK_ORDER_APPLY_WRITE_INTAKE_COMMAND
    summary["write_intake_approval_token_required"] = REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN
    summary["next_required_step"] = (
        "Fill the work-order CSV from reviewed public provenance, run the apply command to validate row and aggregate readiness, "
        "then rerun with --write-intake only after the apply gate is ready."
        if work_order_rows and not ready
        else "Public benchmark readiness is ready; no work-order apply step is required."
    )
    return {
        "summary": summary,
        "rows": rows,
        "work_order_rows": work_order_rows,
        "science_input_gap_rows": science_input_gap_rows,
        "receptor_coordinate_intake_rows": receptor_coordinate_intake_rows,
        "receptor_coordinate_validation_rows": receptor_coordinate_validation_rows,
        "metric_evidence_rows": metric_evidence_rows,
        "required_columns": REQUIRED_COLUMNS,
        "work_order_columns": WORK_ORDER_COLUMNS,
        "science_input_gap_columns": SCIENCE_INPUT_GAP_COLUMNS,
        "receptor_coordinate_intake_columns": RECEPTOR_COORDINATE_INTAKE_COLUMNS,
        "receptor_coordinate_validation_columns": RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
        "metric_evidence_columns": METRIC_EVIDENCE_COLUMNS,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Readiness",
        "",
        f"- status: `{summary['status']}`",
        f"- claim_grade_public_benchmark_ready: `{summary['claim_grade_public_benchmark_ready']}`",
        f"- rows valid/total: `{summary['valid_row_count']}/{summary['row_count']}`",
        f"- pose pass rows: `{summary['pose_metric_pass_count']}`",
        f"- free-energy pairs: `{summary['free_energy_pair_count']}`",
        f"- free-energy Spearman: `{summary['free_energy_spearman']}`",
        f"- blockers: `{summary['blocker_count']}`",
        f"- work-order rows: `{summary.get('work_order_row_count', 0)}`",
        f"- work-order seeded rows: `{summary.get('work_order_seeded_row_count', 0)}`",
        f"- work-order experimental ΔG prefilled rows: `{summary.get('work_order_experimental_deltaG_prefilled_count', 0)}`",
        f"- work-order pending operator fields: `{summary.get('work_order_pending_operator_field_count', 0)}`",
        f"- work-order pending license/DockQ/lDDT/internal ΔG: `{summary.get('work_order_pending_license_ok_count', 0)}/{summary.get('work_order_pending_dockq_count', 0)}/{summary.get('work_order_pending_lddt_pli_count', 0)}/{summary.get('work_order_pending_internal_deltaG_count', 0)}`",
        f"- work-order ligand pose artifacts present: `{summary.get('work_order_local_ligand_pose_artifact_count', 0)}`",
        f"- work-order missing receptor coordinate rows: `{summary.get('work_order_missing_receptor_coordinate_row_count', 0)}`",
        f"- work-order receptor coordinate intake matched/missing: `{summary.get('work_order_receptor_coordinate_intake_matched_row_count', 0)}/{summary.get('work_order_receptor_coordinate_intake_missing_row_count', 0)}`",
        "- work-order receptor coordinate intake suggested URL/local-path/review rows: "
        f"`{summary.get('work_order_receptor_coordinate_intake_suggested_public_url_row_count', 0)}/"
        f"{summary.get('work_order_receptor_coordinate_intake_suggested_local_path_row_count', 0)}/"
        f"{summary.get('work_order_receptor_coordinate_intake_operator_review_required_row_count', 0)}`",
        f"- work-order receptor coordinate validation ready/blocked: `{summary.get('work_order_receptor_coordinate_validation_ready_row_count', 0)}/{summary.get('work_order_receptor_coordinate_validation_blocked_row_count', 0)}`",
        f"- work-order receptor coordinate validation min atom records: `{summary.get('work_order_receptor_coordinate_validation_min_atom_records', 0)}`",
        f"- work-order receptor coordinate validation min macromolecule atom records: `{summary.get('work_order_receptor_coordinate_validation_min_macromolecule_atom_records', 0)}`",
        f"- work-order receptor coordinate validation min distinct residues: `{summary.get('work_order_receptor_coordinate_validation_min_distinct_residues', 0)}`",
        f"- work-order receptor coordinate validation min protein-like residues: `{summary.get('work_order_receptor_coordinate_validation_min_protein_like_residues', 0)}`",
        f"- work-order receptor coordinate validation below-min macromolecule rows: `{summary.get('work_order_receptor_coordinate_validation_below_min_macromolecule_row_count', 0)}`",
        f"- work-order receptor coordinate validation below-min protein-like rows: `{summary.get('work_order_receptor_coordinate_validation_below_min_protein_like_row_count', 0)}`",
        f"- work-order missing interaction/internal ΔG rows: `{summary.get('work_order_missing_interaction_metric_source_row_count', 0)}/{summary.get('work_order_missing_internal_deltaG_source_row_count', 0)}`",
        f"- work-order metric evidence ready/blocked rows: `{summary.get('work_order_metric_evidence_ready_row_count', 0)}/{summary.get('work_order_metric_evidence_blocked_row_count', 0)}`",
        f"- work-order metric evidence missing DockQ/lDDT/internal ΔG sources: `{summary.get('work_order_metric_evidence_missing_dockq_source_row_count', 0)}/{summary.get('work_order_metric_evidence_missing_lddt_pli_source_row_count', 0)}/{summary.get('work_order_metric_evidence_missing_internal_deltaG_source_row_count', 0)}`",
        f"- work-order tar ligand/receptor coordinate members: `{summary.get('work_order_tar_ligand_pose_member_count', 0)}/{summary.get('work_order_tar_receptor_coordinate_member_count', 0)}`",
        f"- work-order ligand-only tar archives: `{summary.get('work_order_tar_ligand_only_archive_count', 0)}`",
        f"- work-order seed CSV: `{summary.get('work_order_seed_csv')}`",
        f"- work-order experimental ΔG source: `{summary.get('work_order_experimental_deltaG_source')}`",
        f"- work-order receptor coordinate inputs: `{summary.get('work_order_local_receptor_coordinate_file_count', 0) + summary.get('work_order_tar_receptor_coordinate_member_count', 0)}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Operator Work Order",
            "",
            f"- operator_work_order_ready: `{summary.get('operator_work_order_ready', False)}`",
            f"- target input CSV: `{summary['input_csv']}`",
            f"- work-order CSV: `{summary.get('work_order_csv')}`",
            f"- science-input gap CSV: `{summary.get('work_order_science_input_gap_csv')}`",
            f"- receptor-coordinate intake CSV: `{summary.get('work_order_receptor_coordinate_intake_csv')}`",
            f"- receptor-coordinate validation CSV: `{summary.get('work_order_receptor_coordinate_validation_csv')}`",
            f"- metric-evidence CSV: `{summary.get('work_order_metric_evidence_csv')}`",
            f"- validate command: `{summary.get('work_order_apply_command')}`",
            f"- write-intake command: `{summary.get('work_order_apply_write_intake_command')}`",
            f"- write-intake approval token: `{summary.get('write_intake_approval_token_required')}`",
            "- fill the work-order CSV after operator/public-source review, validate it with the apply command, then use the write-intake command only after the apply gate is ready.",
            "- rerun this builder after intake rows are applied; this builder does not download data or run docking/MD.",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build refine-tier public benchmark readiness gate.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-work-order-csv", default=DEFAULT_OUT_WORK_ORDER_CSV)
    parser.add_argument("--out-science-input-gap-csv", default=DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV)
    parser.add_argument("--out-receptor-coordinate-intake-csv", default=DEFAULT_OUT_RECEPTOR_COORDINATE_INTAKE_CSV)
    parser.add_argument("--out-receptor-coordinate-validation-csv", default=DEFAULT_OUT_RECEPTOR_COORDINATE_VALIDATION_CSV)
    parser.add_argument("--out-metric-evidence-csv", default=DEFAULT_OUT_METRIC_EVIDENCE_CSV)
    parser.add_argument("--work-order-seed-csv", default=DEFAULT_WORK_ORDER_SEED_CSV)
    parser.add_argument("--work-order-affinity-tsv", default=DEFAULT_WORK_ORDER_AFFINITY_TSV)
    parser.add_argument("--work-order-dataset-dir", default=DEFAULT_WORK_ORDER_DATASET_DIR)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_readiness(
        input_csv=args.input_csv,
        work_order_seed_csv=args.work_order_seed_csv,
        work_order_affinity_tsv=args.work_order_affinity_tsv,
        work_order_dataset_dir=args.work_order_dataset_dir,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    write_csv_rows(_resolve(args.out_work_order_csv), payload["work_order_rows"])
    write_csv_rows(_resolve(args.out_science_input_gap_csv), payload["science_input_gap_rows"])
    write_csv_rows(_resolve(args.out_receptor_coordinate_intake_csv), payload["receptor_coordinate_intake_rows"])
    write_csv_rows(_resolve(args.out_receptor_coordinate_validation_csv), payload["receptor_coordinate_validation_rows"])
    write_csv_rows(_resolve(args.out_metric_evidence_csv), payload["metric_evidence_rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
