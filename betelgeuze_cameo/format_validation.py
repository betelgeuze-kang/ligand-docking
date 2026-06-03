from __future__ import annotations

import math
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO PDB/mmCIF format validation only; no native accuracy, official CAMEO score, "
    "prediction email, or external-state mutation is performed."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _pdb_float(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _pdb_atom_key(line: str) -> tuple[str, str, str]:
    if len(line) >= 27:
        chain_id = line[21].strip() or "_"
        residue_id = line[22:26].strip() or "?"
        insertion_code = line[26].strip() or "_"
        return chain_id, residue_id, insertion_code
    fields = line.split()
    chain_id = fields[4] if len(fields) > 4 else "_"
    residue_id = fields[5] if len(fields) > 5 else "?"
    return chain_id, residue_id, "_"


def _detect_format(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".cif", ".mmcif"}:
        return "mmcif"
    if suffix in {".pdb", ".ent"}:
        return "pdb"
    stripped = text.lstrip()
    if stripped.startswith("data_") or "_atom_site." in text:
        return "mmcif"
    if any(_record(line) in {"ATOM", "HETATM", "MODEL"} for line in text.splitlines()):
        return "pdb"
    return "unknown"


def _validate_pdb(text: str) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    lines = [line.rstrip("\n\r") for line in text.splitlines() if line.strip()]
    atom_lines = [line for line in lines if _record(line) in {"ATOM", "HETATM"}]
    polymer_atom_lines = [line for line in lines if _record(line) == "ATOM"]
    model_indices: list[int] = []
    coordinate_parse_error_count = 0
    chain_ids: set[str] = set()
    residues: set[tuple[str, str, str]] = set()

    for line in lines:
        if _record(line) == "MODEL":
            parts = line.split()
            if len(parts) < 2:
                blockers.append(_blocker("model_index_missing", "MODEL records must include an integer index."))
                continue
            parsed = _int(parts[1], default=-1)
            if parsed < 1:
                blockers.append(_blocker("model_index_not_positive_integer", "MODEL records must use positive integer indices."))
            else:
                model_indices.append(parsed)

    for line in atom_lines:
        xyz = (_pdb_float(line, 30, 38, 6), _pdb_float(line, 38, 46, 7), _pdb_float(line, 46, 54, 8))
        if any(value is None for value in xyz):
            coordinate_parse_error_count += 1
            continue
        chain_id, residue_id, insertion_code = _pdb_atom_key(line)
        chain_ids.add(chain_id)
        residues.add((chain_id, residue_id, insertion_code))

    if not atom_lines:
        blockers.append(_blocker("atom_records_missing", "PDB file must contain at least one ATOM or HETATM coordinate record."))
    if atom_lines and not polymer_atom_lines:
        warnings.append(_warning("polymer_atom_records_missing", "PDB file contains HETATM records but no polymer ATOM records."))
    if coordinate_parse_error_count:
        blockers.append(_blocker("coordinate_parse_error", "One or more PDB coordinate records do not have parseable x/y/z values."))
    if len(set(model_indices)) != len(model_indices):
        blockers.append(_blocker("duplicate_model_index", "MODEL indices must be unique."))

    model_count = len(model_indices) if model_indices else (1 if atom_lines else 0)
    if model_count > 5:
        blockers.append(_blocker("cameo_top5_model_limit_exceeded", "CAMEO handoff supports at most five ranked models."))
    if atom_lines and "END" not in {_record(line) for line in lines}:
        warnings.append(_warning("end_record_missing", "PDB file has coordinates but no END record."))

    metrics = {
        "detected_format": "pdb",
        "atom_count": len(atom_lines),
        "polymer_atom_count": len(polymer_atom_lines),
        "model_count": model_count,
        "model_indices": model_indices or ([1] if atom_lines else []),
        "chain_count": len(chain_ids),
        "residue_count": len(residues),
        "coordinate_parse_error_count": coordinate_parse_error_count,
    }
    return metrics, blockers, warnings


def _read_mmcif_loops(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    loops: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "loop_":
            index += 1
            continue
        index += 1
        fields: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("_"):
            fields.append(lines[index].strip().split()[0])
            index += 1
        rows: list[list[str]] = []
        while index < len(lines):
            stripped = lines[index].strip()
            lower = stripped.lower()
            if lower == "loop_" or lower.startswith("data_") or stripped.startswith("_"):
                break
            if stripped and not stripped.startswith("#"):
                try:
                    rows.append(shlex.split(stripped, posix=True))
                except ValueError:
                    rows.append(stripped.split())
            index += 1
        if fields:
            loops.append((fields, rows))
    return loops


def _validate_mmcif(text: str) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    lines = [line.rstrip("\n\r") for line in text.splitlines() if line.strip()]
    if not any(line.strip().lower().startswith("data_") for line in lines):
        blockers.append(_blocker("data_block_missing", "mmCIF file must include a data_ block."))

    atom_site_fields_seen = False
    atom_count = 0
    coordinate_parse_error_count = 0
    chain_ids: set[str] = set()
    residues: set[tuple[str, str]] = set()
    model_indices: set[int] = set()

    for fields, rows in _read_mmcif_loops(lines):
        if not any(field.startswith("_atom_site.") for field in fields):
            continue
        atom_site_fields_seen = True
        field_index = {field: idx for idx, field in enumerate(fields)}
        group_idx = field_index.get("_atom_site.group_PDB")
        x_idx = field_index.get("_atom_site.Cartn_x")
        y_idx = field_index.get("_atom_site.Cartn_y")
        z_idx = field_index.get("_atom_site.Cartn_z")
        chain_idx = field_index.get("_atom_site.auth_asym_id", field_index.get("_atom_site.label_asym_id", -1))
        residue_idx = field_index.get("_atom_site.auth_seq_id", field_index.get("_atom_site.label_seq_id", -1))
        model_idx = field_index.get("_atom_site.pdbx_PDB_model_num", -1)
        for row in rows:
            if group_idx is not None and len(row) > group_idx and row[group_idx].upper() not in {"ATOM", "HETATM"}:
                continue
            if group_idx is None and row and row[0].upper() not in {"ATOM", "HETATM"}:
                continue
            atom_count += 1
            if x_idx is None or y_idx is None or z_idx is None or max(x_idx, y_idx, z_idx) >= len(row):
                coordinate_parse_error_count += 1
            else:
                xyz = (_float_or_none(row[x_idx]), _float_or_none(row[y_idx]), _float_or_none(row[z_idx]))
                if any(value is None for value in xyz):
                    coordinate_parse_error_count += 1
            chain_id = row[chain_idx] if chain_idx >= 0 and len(row) > chain_idx else "_"
            residue_id = row[residue_idx] if residue_idx >= 0 and len(row) > residue_idx else "?"
            chain_ids.add(chain_id)
            residues.add((chain_id, residue_id))
            if model_idx >= 0 and len(row) > model_idx:
                parsed_model = _int(row[model_idx], default=0)
                if parsed_model > 0:
                    model_indices.add(parsed_model)

    if not atom_site_fields_seen:
        blockers.append(_blocker("atom_site_loop_missing", "mmCIF file must include _atom_site fields."))
    if atom_count == 0:
        blockers.append(_blocker("atom_records_missing", "mmCIF file must include at least one ATOM or HETATM atom_site row."))
    if coordinate_parse_error_count:
        blockers.append(_blocker("coordinate_parse_error", "One or more mmCIF atom_site rows do not have parseable x/y/z values."))

    model_count = len(model_indices) if model_indices else (1 if atom_count else 0)
    if model_count > 5:
        blockers.append(_blocker("cameo_top5_model_limit_exceeded", "CAMEO handoff supports at most five ranked models."))
    if atom_site_fields_seen and not any(field in text for field in ("_atom_site.Cartn_x", "_atom_site.Cartn_y", "_atom_site.Cartn_z")):
        warnings.append(_warning("cartesian_coordinate_fields_missing", "mmCIF atom_site loop does not expose standard Cartn_x/Cartn_y/Cartn_z fields."))

    metrics = {
        "detected_format": "mmcif",
        "atom_count": atom_count,
        "polymer_atom_count": atom_count,
        "model_count": model_count,
        "model_indices": sorted(model_indices) if model_indices else ([1] if atom_count else []),
        "chain_count": len(chain_ids),
        "residue_count": len(residues),
        "coordinate_parse_error_count": coordinate_parse_error_count,
    }
    return metrics, blockers, warnings


def validate_model_file(model_path: str | Path, *, target_id: str = "", candidate_id: str = "", cameo_model_rank: int = 0) -> dict[str, Any]:
    path = Path(model_path)
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    metrics: dict[str, Any] = {
        "detected_format": "unknown",
        "atom_count": 0,
        "polymer_atom_count": 0,
        "model_count": 0,
        "model_indices": [],
        "chain_count": 0,
        "residue_count": 0,
        "coordinate_parse_error_count": 0,
    }

    if not path.exists():
        blockers.append(_blocker("model_file_missing", f"Model file `{path}` is missing."))
        return _payload(path, target_id, candidate_id, cameo_model_rank, metrics, blockers, warnings)
    if not path.is_file():
        blockers.append(_blocker("model_path_not_file", f"Model path `{path}` is not a file."))
        return _payload(path, target_id, candidate_id, cameo_model_rank, metrics, blockers, warnings)

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        blockers.append(_blocker("model_file_empty", f"Model file `{path}` is empty."))
        return _payload(path, target_id, candidate_id, cameo_model_rank, metrics, blockers, warnings)

    detected_format = _detect_format(path, text)
    if detected_format == "pdb":
        metrics, blockers, warnings = _validate_pdb(text)
    elif detected_format == "mmcif":
        metrics, blockers, warnings = _validate_mmcif(text)
    else:
        blockers.append(_blocker("unsupported_model_format", "Model file must be a PDB or mmCIF coordinate file."))
        metrics["detected_format"] = detected_format
    return _payload(path, target_id, candidate_id, cameo_model_rank, metrics, blockers, warnings)


def build_format_validation_packet(
    rows: list[dict[str, Any]],
    *,
    target_id: str = "",
    base_dir: str | Path = ".",
    selected_only: bool = True,
) -> dict[str, Any]:
    base = Path(base_dir)
    filtered = [row for row in rows if not target_id or _text(row.get("target_id")).upper() == target_id.upper()]
    selected = [row for row in filtered if _row_is_selected(row)]
    rows_to_validate = selected if selected_only and selected else filtered
    validation_rows: list[dict[str, Any]] = []
    for row in rows_to_validate:
        raw_model_path = _text(row.get("model_path"))
        resolved_model_path = Path(raw_model_path)
        if raw_model_path and not resolved_model_path.is_absolute():
            resolved_model_path = base / resolved_model_path
        validation = validate_model_file(
            resolved_model_path if raw_model_path else "",
            target_id=_text(row.get("target_id")),
            candidate_id=_text(row.get("candidate_id")),
            cameo_model_rank=_int(row.get("cameo_model_rank")),
        )
        summary = validation["summary"]
        validation_rows.append(
            {
                **row,
                "model_path": raw_model_path,
                "format_validation_status": summary["format_validation_status"],
                "detected_format": summary["detected_format"],
                "format_blocker_count": summary["blocker_count"],
                "format_warning_count": summary["warning_count"],
                "atom_count": summary["atom_count"],
                "model_count": summary["model_count"],
                "chain_count": summary["chain_count"],
                "residue_count": summary["residue_count"],
                "coordinate_parse_error_count": summary["coordinate_parse_error_count"],
                "format_blockers": ",".join(blocker["code"] for blocker in validation["blockers"]),
                "format_warnings": ",".join(warning["code"] for warning in validation["warnings"]),
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )

    pass_count = sum(1 for row in validation_rows if row["format_validation_status"] == "pass")
    fail_count = len(validation_rows) - pass_count
    model1_rows = [row for row in validation_rows if _int(row.get("cameo_model_rank")) == 1]
    model1_format_pass = len(model1_rows) == 1 and model1_rows[0]["format_validation_status"] == "pass"
    status = "cameo_format_validation_ready"
    if not validation_rows:
        status = "blocked_no_models_to_validate"
    elif fail_count:
        status = "blocked_format_validation_failures"
    elif selected_only and selected and not model1_format_pass:
        status = "blocked_model1_format_not_pass"

    summary = {
        "packet_type": "cameo_format_validation_packet",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "target_id": _text(target_id) or (_text(validation_rows[0].get("target_id")) if validation_rows else ""),
        "input_row_count": len(rows),
        "filtered_row_count": len(filtered),
        "selected_input_row_count": len(selected),
        "validated_model_count": len(validation_rows),
        "format_pass_count": pass_count,
        "format_fail_count": fail_count,
        "model1_format_pass": model1_format_pass,
        "native_or_external_accuracy_used": False,
        "outbound_email_enabled": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator-reviewed dry-run packaging can begin, but outbound CAMEO prediction email remains disabled."
            if status == "cameo_format_validation_ready"
            else "Repair or regenerate blocked model files before any CAMEO handoff."
        ),
    }
    return {"summary": summary, "rows": validation_rows}


def _row_is_selected(row: dict[str, Any]) -> bool:
    if _int(row.get("cameo_model_rank")) > 0:
        return True
    for key in ("model1_candidate", "top5_candidate"):
        value = _text(row.get(key)).lower()
        if value in {"1", "true", "yes"}:
            return True
    return _text(row.get("selection_status")) in {"model1_candidate", "top5_candidate"}


def _payload(
    path: Path,
    target_id: str,
    candidate_id: str,
    cameo_model_rank: int,
    metrics: dict[str, Any],
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    if cameo_model_rank > 5 and not any(blocker["code"] == "cameo_model_rank_out_of_range" for blocker in blockers):
        blockers.append(_blocker("cameo_model_rank_out_of_range", "CAMEO handoff ranks must be in the model1 through model5 range."))
    summary = {
        "packet_type": "cameo_model_format_validation",
        "target_id": _text(target_id),
        "candidate_id": _text(candidate_id),
        "model_path": str(path),
        "cameo_model_rank": cameo_model_rank,
        "format_validation_status": "fail" if blockers else "pass",
        "detected_format": metrics.get("detected_format", "unknown"),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "atom_count": metrics.get("atom_count", 0),
        "polymer_atom_count": metrics.get("polymer_atom_count", 0),
        "model_count": metrics.get("model_count", 0),
        "model_indices": metrics.get("model_indices", []),
        "chain_count": metrics.get("chain_count", 0),
        "residue_count": metrics.get("residue_count", 0),
        "coordinate_parse_error_count": metrics.get("coordinate_parse_error_count", 0),
        "native_or_external_accuracy_used": False,
        "outbound_email_enabled": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "metrics": metrics}
