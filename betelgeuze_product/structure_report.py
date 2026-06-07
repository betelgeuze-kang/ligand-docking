from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from betelgeuze_product.structure_analysis import analyze_structure_source

CLAIM_BOUNDARY = (
    "Product structure-analysis report only; it resolves local structure evidence and summarizes parsed PDB/mmCIF "
    "features for the product target. It does not fetch PDB entries, run docking, predict structures, submit CAMEO/CASP "
    "artifacts, upload data, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return str(float(text))
    except ValueError:
        return text


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _resolve(root: Path, path_like: str) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_target_row(target_native_csv: str, target_key: str, root: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not target_native_csv:
        return {}, [_blocker("target_native_csv_missing", "A target_native_csv path is required for local product structure evidence.")]
    path = _resolve(root, target_native_csv)
    if not path.is_file():
        return {}, [_blocker("target_native_csv_not_found", f"Target native CSV is missing: {target_native_csv}")]
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        return {}, [_blocker("target_native_csv_unreadable", f"Target native CSV could not be read: {exc}")]

    if not rows:
        return {}, [_blocker("target_native_csv_empty", "Target native CSV has no rows.")]
    if target_key:
        for row in rows:
            if _text(row.get("target")) == target_key:
                return {key: _text(value) for key, value in row.items()}, []
        return {}, [_blocker("target_key_not_found", f"Target key was not found in target_native_csv: {target_key}")]
    return {key: _text(value) for key, value in rows[0].items()}, []


def _row(check: str, status: str, observed: str, required: str, artifact_path: str = "") -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def build_product_structure_analysis_report(
    *,
    target_native_csv: str,
    target_key: str,
    target_id: str = "",
    family: str = "",
    root: str | Path = ".",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    target_row, blockers = _read_target_row(target_native_csv, target_key, root_path)
    structure_path = _text(target_row.get("native_pdb_path"))
    pdb_id = _text(target_row.get("pdb_id"))
    pocket_center = {
        "x": _float_text(target_row.get("pocket_x")),
        "y": _float_text(target_row.get("pocket_y")),
        "z": _float_text(target_row.get("pocket_z")),
    }

    analysis: dict[str, Any]
    if structure_path:
        analysis = analyze_structure_source({"pdb_path": structure_path}, root=root_path)
    elif pdb_id:
        analysis = analyze_structure_source({"pdb_id": pdb_id}, root=root_path)
        blockers.append(_blocker("local_structure_path_missing", "Only a PDB id was available; no local structure file was parsed."))
    else:
        analysis = analyze_structure_source({}, root=root_path)
        blockers.append(_blocker("local_structure_source_missing", "Target row does not include native_pdb_path or pdb_id."))

    for blocker in analysis.get("blockers", []) or []:
        if isinstance(blocker, dict):
            blockers.append(dict(blocker))

    local_structure_parsed = analysis.get("status") == "structure_analysis_ready" and _int(analysis.get("atom_count")) > 0
    ligand_like_residue_count = _int(analysis.get("ligand_like_residue_count"))
    status = "product_structure_analysis_report_ready" if local_structure_parsed and not blockers else "blocked_product_structure_analysis_report"
    rows = [
        _row(
            "target_native_csv",
            "pass" if bool(target_row) else "fail",
            f"target_key={target_key or 'first_row'};row_present={bool(target_row)}",
            "target row with native_pdb_path or pdb_id",
            target_native_csv,
        ),
        _row(
            "local_structure_parse",
            "pass" if local_structure_parsed else "fail",
            f"status={analysis.get('status')};atoms={analysis.get('atom_count')};chains={analysis.get('chain_count')}",
            "structure_analysis_ready with atom_count > 0",
            structure_path,
        ),
        _row(
            "ligand_like_residue_scan",
            "pass",
            f"ligand_like_residue_count={ligand_like_residue_count};water_residue_count={analysis.get('water_residue_count')}",
            "record ligand-like HETATM residues without claiming docking results",
            structure_path,
        ),
        _row(
            "guardrails",
            "pass"
            if analysis.get("execution_enabled") is False
            and analysis.get("docking_results_emitted") is False
            and analysis.get("external_state_mutated") is False
            else "fail",
            (
                f"execution_enabled={analysis.get('execution_enabled')};"
                f"docking_results_emitted={analysis.get('docking_results_emitted')};"
                f"external_state_mutated={analysis.get('external_state_mutated')}"
            ),
            "no execution, no docking result emission, no external mutation",
        ),
    ]

    summary = {
        "packet_type": "product_structure_analysis_report",
        "status": status,
        "target_id": _text(target_id) or _text(target_row.get("target")),
        "target_key": _text(target_key),
        "family": _text(family),
        "target_native_csv": target_native_csv,
        "structure_path": structure_path,
        "pdb_id": pdb_id,
        "pocket_center": pocket_center,
        "local_structure_parsed": local_structure_parsed,
        "atom_count": _int(analysis.get("atom_count")),
        "chain_count": _int(analysis.get("chain_count")),
        "residue_count": _int(analysis.get("residue_count")),
        "polymer_residue_count": _int(analysis.get("polymer_residue_count")),
        "hetatm_residue_count": _int(analysis.get("hetatm_residue_count")),
        "water_residue_count": _int(analysis.get("water_residue_count")),
        "ligand_like_residue_count": ligand_like_residue_count,
        "element_count": _int(analysis.get("element_count")),
        "blocker_count": len(blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this parsed local structure report as product intake evidence; docking execution still requires operator approval."
            if status == "product_structure_analysis_report_ready"
            else "Repair local structure evidence before treating the product structure-analysis report as ready."
        ),
    }
    return {"summary": summary, "analysis": analysis, "target_row": target_row, "blockers": blockers, "rows": rows}
