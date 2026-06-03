from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from betelgeuze_product.structure_analysis import analyze_structure_source

ALLOWED_SCOPE_FAMILIES = {"kinase", "gpcr", "ion_channel"}
MAX_P0_LIGAND_COUNT = 10000
CLAIM_BOUNDARY = (
    "Commercial docking request contract only; validates intake and records a local fail-closed ledger. "
    "It does not run docking, emit scientific results, send data externally, or widen delivery-ready scope."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_family(value: Any) -> str:
    text = _text(value).lower().replace("-", "_").replace(" ", "_")
    if text == "ionchannel":
        return "ion_channel"
    return text


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def request_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _structure_source(payload: dict[str, Any]) -> dict[str, str]:
    candidates = {
        "pdb_id": _text(payload.get("pdb_id")),
        "pdb_path": _text(payload.get("pdb_path")),
        "pdb_content": _text(payload.get("pdb_content")),
        "mmcif_path": _text(payload.get("mmcif_path")),
        "mmcif_content": _text(payload.get("mmcif_content")),
    }
    present = {key: value for key, value in candidates.items() if value}
    return present


def _ligand_id(row: Any, index: int) -> str:
    if isinstance(row, dict):
        return _text(row.get("ligand_id") or row.get("id") or row.get("name") or f"ligand_{index}")
    return f"ligand_{index}"


def _ligand_has_source(row: Any) -> bool:
    if not isinstance(row, dict):
        return bool(_text(row))
    for key in ("smiles", "sdf_path", "mol2_path", "pdbqt_path", "inchi", "compound_id"):
        if _text(row.get(key)):
            return True
    return False


def validate_docking_request(payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    family = _canonical_family(payload.get("family") or payload.get("scope_family"))
    ligands = _as_list(payload.get("ligands"))
    structure_source = _structure_source(payload)
    request_type = _text(payload.get("request_type") or "structure_analysis_ligand_docking")

    if request_type not in {"structure_analysis_ligand_docking", "ligand_docking", "docking_screen"}:
        blockers.append(_blocker("unsupported_request_type", "Request type must be a structure-analysis or ligand-docking product request."))
    if family not in ALLOWED_SCOPE_FAMILIES:
        blockers.append(
            _blocker(
                "scope_family_not_delivery_ready",
                "Initial commercial delivery scope is restricted to kinase, gpcr, and ion_channel.",
            )
        )
    if not _text(payload.get("target_id") or payload.get("target_name")):
        blockers.append(_blocker("target_id_missing", "A stable target_id or target_name is required."))
    if not structure_source:
        blockers.append(_blocker("structure_source_missing", "Provide one structure source: pdb_id, pdb_path, pdb_content, mmcif_path, or mmcif_content."))
    if len(structure_source) > 1:
        blockers.append(_blocker("multiple_structure_sources", "Provide exactly one structure source for reproducible product intake."))
    if not ligands:
        blockers.append(_blocker("ligands_missing", "At least one ligand row is required for a docking request."))
    if len(ligands) > MAX_P0_LIGAND_COUNT:
        blockers.append(_blocker("ligand_count_exceeds_p0_limit", f"P0 intake is capped at {MAX_P0_LIGAND_COUNT} ligands."))

    ligand_ids: list[str] = []
    ligand_source_missing = 0
    for index, ligand in enumerate(ligands, start=1):
        ligand_id = _ligand_id(ligand, index)
        ligand_ids.append(ligand_id)
        if not _ligand_has_source(ligand):
            ligand_source_missing += 1
    duplicate_ligand_ids = sorted({ligand_id for ligand_id in ligand_ids if ligand_ids.count(ligand_id) > 1})
    if duplicate_ligand_ids:
        blockers.append(_blocker("duplicate_ligand_ids", "Ligand ids must be unique within a product request."))
    if ligand_source_missing:
        blockers.append(_blocker("ligand_source_missing", "Every ligand row must provide smiles, sdf_path, mol2_path, pdbqt_path, inchi, or compound_id."))

    if len(ligands) > 1000:
        warnings.append({"code": "large_ligand_request", "severity": "warning", "reason": "Large ligand requests should use an externalized heavy-artifact manifest."})

    return {
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "warnings": warnings,
        "normalized": {
            "request_type": request_type,
            "family": family,
            "target_id": _text(payload.get("target_id") or payload.get("target_name")),
            "structure_source_kind": next(iter(structure_source.keys()), ""),
            "ligand_count": len(ligands),
            "ligand_ids": ligand_ids,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_docking_job_record(
    payload: dict[str, Any],
    *,
    job_id: str | None = None,
    source_host: str = "",
) -> dict[str, Any]:
    validation = validate_docking_request(payload)
    normalized = validation["normalized"]
    structure_analysis = analyze_structure_source(payload)
    return {
        "job_id": job_id or str(uuid.uuid4()),
        "status": "accepted_fail_closed" if validation["status"] == "pass" else "blocked_contract_validation",
        "created_at_utc": utc_now_iso(),
        "source_host": source_host,
        "request_sha256": request_sha256(payload),
        "request_type": normalized["request_type"],
        "target_id": normalized["target_id"],
        "family": normalized["family"],
        "structure_source_kind": normalized["structure_source_kind"],
        "ligand_count": normalized["ligand_count"],
        "structure_analysis_status": structure_analysis["status"],
        "structure_source_available": structure_analysis["source_available"],
        "structure_atom_count": structure_analysis["atom_count"],
        "structure_chain_count": structure_analysis["chain_count"],
        "structure_residue_count": structure_analysis["residue_count"],
        "structure_ligand_like_residue_count": structure_analysis["ligand_like_residue_count"],
        "structure_analysis": structure_analysis,
        "validation_status": validation["status"],
        "blockers": validation["blockers"],
        "warnings": validation["warnings"],
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "allowed_scope_families": sorted(ALLOWED_SCOPE_FAMILIES),
        "heavy_artifact_policy": "manifest_first_externalize_before_delete",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def persist_docking_job_record(record: dict[str, Any], jobs_dir: Path) -> Path:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    out_path = jobs_dir / f"{record['job_id']}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
