#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT.md"

AUDIT_COLUMNS = [
    "target_id",
    "audit_status",
    "workorder_status",
    "native_dropzone_pdb",
    "native_file_status",
    "native_atom_record_count",
    "native_protein_atom_record_count",
    "native_chain_id_count",
    "native_coordinate_status",
    "identity_discovery_blocker_status",
    "identity_discovery_blockers",
    "provenance_template_csv",
    "provenance_status",
    "evidence_ref_status",
    "evidence_ref_path",
    "evidence_ref_content_status",
    "evidence_ref_sha256",
    "manifest_stub_csv",
    "manifest_stub_status",
    "manifest_provenance_status",
    "manifest_provenance_mismatch_count",
    "prediction_file_status",
    "prediction_atom_record_count",
    "prediction_protein_atom_record_count",
    "prediction_chain_id_count",
    "prediction_coordinate_status",
    "native_prediction_identity_status",
    "blockers",
    "next_action",
]
PROVENANCE_TO_MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
CLEAR_VALUES = {"cleared", "no_leak", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
URL_PREFIXES = ("http://", "https://")
EVIDENCE_REF_BLOCKED_MARKERS = (
    "clearance_evidence_status: request_template",
    "evidence request template",
    "not a completed no-leak clearance",
)
PROVENANCE_REVIEW_RESOLVABLE_IDENTITY_BLOCKERS = {"no_leak_clearance_required", "target_origin_review_required"}
CLAIM_BOUNDARY = (
    "Local competitive-floor target identity clearance workorder audit only. It verifies per-target native "
    "dropzones, local no-leak evidence references, provenance templates, and manifest stubs before any manual "
    "promotion. It does not fetch native structures, verify external URLs, clear no-leak provenance, choose "
    "historical targets, score native accuracy, mutate identity intake files, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _split_blockers(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(",") if part.strip()]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv_one(path_like: str | Path) -> tuple[dict[str, str], list[str]]:
    path_text = _text(path_like)
    if not path_text:
        return {}, ["csv_path_missing"]
    path = _resolve(path_like)
    if not path.exists():
        return {}, [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    if len(rows) > 1:
        blockers.append(f"{path.name}_multiple_rows")
    return (rows[0] if rows else {}), blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _pdb_status(
    path_like: str | Path,
    *,
    role: str,
    missing_coordinate_status: str,
    path_missing_blocker: str | None = None,
) -> tuple[str, int, int, int, str, list[str]]:
    path_text = _text(path_like)
    if not path_text:
        blocker = path_missing_blocker or f"{role}_pdb_missing"
        return "missing", 0, 0, 0, missing_coordinate_status, [blocker]
    path = _resolve(path_text)
    if not path.exists():
        missing_blocker = f"{role}_pdb_missing" if role == "native" else f"{role}_pdb_not_found"
        return "missing", 0, 0, 0, missing_coordinate_status, [missing_blocker]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "unreadable", 0, 0, 0, "unreadable", [f"{role}_pdb_unreadable"]
    atom_lines = [line for line in lines if line.startswith(("ATOM", "HETATM"))]
    protein_atom_lines = [line for line in lines if line.startswith("ATOM")]
    atom_count = len(atom_lines)
    protein_atom_count = len(protein_atom_lines)
    chain_ids = {(line[21].strip() or "_blank") for line in protein_atom_lines if len(line) > 21}
    coordinate_blockers: list[str] = []
    for line in atom_lines:
        try:
            float(line[30:38])
            float(line[38:46])
            float(line[46:54])
        except ValueError:
            coordinate_blockers.append(f"{role}_pdb_coordinates_invalid")
            break
    if atom_count <= 0:
        return "invalid", atom_count, protein_atom_count, len(chain_ids), "invalid", [
            f"{role}_pdb_has_no_atom_records"
        ]
    if protein_atom_count <= 0:
        return "invalid", atom_count, protein_atom_count, len(chain_ids), "invalid", [
            f"{role}_pdb_has_no_protein_atom_records"
        ]
    if coordinate_blockers:
        return "invalid", atom_count, protein_atom_count, len(chain_ids), "invalid", coordinate_blockers
    return "present", atom_count, protein_atom_count, len(chain_ids), "valid", []


def _native_status(path_like: str | Path) -> tuple[str, int, int, int, str, list[str]]:
    return _pdb_status(
        path_like,
        role="native",
        missing_coordinate_status="waiting_on_native",
        path_missing_blocker="native_dropzone_path_missing",
    )


def _prediction_status(path_like: str | Path) -> tuple[str, int, int, int, str, list[str]]:
    return _pdb_status(path_like, role="prediction", missing_coordinate_status="waiting_on_prediction")


def _evidence_ref_status(value: Any, *, target_id: str) -> tuple[str, str, str, str, list[str]]:
    ref = _text(value)
    if _contains_placeholder(ref):
        return "missing", "", "waiting_on_evidence_ref", "", ["evidence_ref_required"]
    if ref.lower().startswith(URL_PREFIXES):
        return "external_unverified", ref, "waiting_on_local_file", "", ["evidence_ref_must_be_local_file"]
    path = _resolve(ref)
    if not path.exists():
        return "missing", ref, "waiting_on_evidence_ref", "", ["evidence_ref_file_missing"]
    if not path.is_file():
        return "invalid", ref, "waiting_on_file", "", ["evidence_ref_not_file"]
    try:
        if path.stat().st_size <= 0:
            return "empty", ref, "empty", "", ["evidence_ref_file_empty"]
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unreadable", ref, "unreadable", "", ["evidence_ref_file_unreadable"]
    blockers: list[str] = []
    lowered = content.lower()
    if target_id.lower() not in lowered:
        blockers.append("evidence_ref_target_id_missing")
    if not any(marker in lowered for marker in ["no-leak", "no_leak", "no leak"]):
        blockers.append("evidence_ref_no_leak_marker_missing")
    if any(marker in lowered for marker in EVIDENCE_REF_BLOCKED_MARKERS):
        blockers.append("evidence_ref_is_request_template")
    content_status = "verified" if not blockers else "content_blocked"
    return "present", ref, content_status, _sha256(path), blockers


def _identity_discovery_blocker_status(
    blockers: list[str],
    *,
    provenance_status: str,
    evidence_ref_content_status: str,
) -> tuple[str, list[str]]:
    if not blockers:
        return "not_applicable", []
    unresolved: list[str] = []
    provenance_review_ready = provenance_status == "ready" and evidence_ref_content_status == "verified"
    for blocker in blockers:
        if blocker in PROVENANCE_REVIEW_RESOLVABLE_IDENTITY_BLOCKERS and provenance_review_ready:
            continue
        unresolved.append(f"identity_discovery_{blocker}")
    if unresolved:
        return "blocked", unresolved
    return "cleared_by_provenance_review", []


def _sha256(path_like: str | Path) -> str:
    return hashlib.sha256(_resolve(path_like).read_bytes()).hexdigest()


def _native_prediction_identity_status(
    native_path_like: str | Path,
    prediction_path_like: str | Path,
    *,
    native_file_status: str,
    prediction_file_status: str,
    blockers: list[str],
) -> str:
    if native_file_status != "present":
        return "waiting_on_native"
    if prediction_file_status != "present":
        return "waiting_on_prediction"
    native = _resolve(native_path_like)
    prediction = _resolve(prediction_path_like)
    try:
        if native.samefile(prediction):
            blockers.append("native_pdb_same_path_as_prediction_pdb")
            return "same_file"
        if _sha256(native) == _sha256(prediction):
            blockers.append("native_pdb_identical_to_prediction_pdb")
            return "identical_content"
    except OSError:
        blockers.append("native_prediction_identity_unreadable")
        return "unreadable"
    return "distinct"


def _provenance_status(row: dict[str, str], blockers: list[str]) -> str:
    required_text = ["benchmark_id", "target_id", "scope", "prediction_method", "operator", "evidence_ref"]
    for column in required_text:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"{column}_required")
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    prediction_date = _date_or_none(row.get("prediction_created_at"))
    native_date = _date_or_none(row.get("native_release_date"))
    if prediction_date is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_date is not None and native_date is not None and prediction_date >= native_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    return "ready" if not blockers else "blocked"


def _manifest_status(
    row: dict[str, str],
    *,
    target_id: str,
    native_dropzone_pdb: str,
    provenance_ready: bool,
    blockers: list[str],
) -> str:
    if _text(row.get("target_id")).upper() != target_id:
        blockers.append("manifest_target_id_mismatch")
    prediction = _text(row.get("prediction_pdb"))
    if not prediction:
        blockers.append("manifest_prediction_pdb_missing")
    elif not _resolve(prediction).exists():
        blockers.append("manifest_prediction_pdb_not_found")
    native = _text(row.get("native_pdb"))
    if not native:
        blockers.append("manifest_native_pdb_missing")
    elif _artifact(native) != _artifact(native_dropzone_pdb):
        blockers.append("manifest_native_pdb_not_dropzone")
    elif not _resolve(native).exists():
        blockers.append("manifest_native_pdb_not_found")
    for column in [
        "leakage_clearance",
        "prediction_created_at",
        "native_release_date",
        "prediction_generated_before_native_release",
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
        "operator_clearance",
    ]:
        if _contains_placeholder(row.get(column)):
            blockers.append(f"manifest_{column}_required")
    if not provenance_ready:
        blockers.append("manifest_waiting_on_provenance_template")
    return "ready" if not blockers else "blocked"


def _manifest_provenance_status(
    provenance: dict[str, str],
    manifest: dict[str, str],
    *,
    provenance_ready: bool,
    manifest_readable: bool,
    blockers: list[str],
) -> tuple[str, int]:
    if not provenance_ready:
        return "waiting_on_provenance", 0
    if not manifest_readable:
        return "waiting_on_manifest", 0
    mismatch_count = 0
    for column in PROVENANCE_TO_MANIFEST_COLUMNS:
        if _text(provenance.get(column)) != _text(manifest.get(column)):
            blockers.append(f"manifest_provenance_{column}_mismatch")
            mismatch_count += 1
    return ("matched" if mismatch_count == 0 else "mismatch"), mismatch_count


def _next_action(blockers: list[str]) -> str:
    blocker_set = set(blockers)
    if not blockers:
        return "review and promote the manifest stub only after final operator signoff"
    if any(blocker.startswith("identity_discovery_current_casp17_target") for blocker in blockers):
        return "replace target identity with a cleared historical non-CASP17 benchmark target"
    if any(blocker.startswith("identity_discovery_synthetic_test_artifact") for blocker in blockers):
        return "exclude synthetic test artifacts from target identity clearance"
    if any(blocker.startswith("identity_discovery_") for blocker in blockers):
        return "complete target-origin and no-leak evidence review before native/provenance promotion"
    if "native_pdb_missing" in blocker_set or "manifest_native_pdb_not_found" in blocker_set:
        return "place the cleared native PDB in the per-target native dropzone"
    if any(blocker.startswith("native_pdb_") or blocker == "native_prediction_identity_unreadable" for blocker in blockers):
        return "replace the native dropzone file with an independently cleared native PDB distinct from the prediction"
    if any(blocker.startswith("prediction_pdb_") for blocker in blockers):
        return "replace the prediction PDB with an internal protein-coordinate model file"
    if any(blocker.startswith("evidence_ref") for blocker in blockers):
        return "attach a local no-leak evidence file and record its path in evidence_ref"
    if any(blocker.startswith("manifest_provenance_") for blocker in blockers):
        return "sync cleared provenance fields into the manifest stub and rerun the audit"
    if any("operator_clearance" in blocker or "leakage_clearance" in blocker for blocker in blockers):
        return "complete no-leak and operator clearance fields in the provenance template"
    if any("date" in blocker for blocker in blockers):
        return "fill prediction and native release dates, ensuring prediction predates native release"
    return "resolve the listed clearance audit blockers"


def _audit_row(workorder_row: dict[str, Any]) -> dict[str, Any]:
    target_id = _text(workorder_row.get("target_id")).upper()
    native_dropzone = _text(workorder_row.get("native_dropzone_pdb"))
    (
        native_file_status,
        atom_count,
        protein_atom_count,
        chain_id_count,
        native_coordinate_status,
        native_blockers,
    ) = _native_status(native_dropzone)
    provenance_row, provenance_file_blockers = _read_csv_one(workorder_row.get("provenance_template_csv"))
    provenance_blockers = list(provenance_file_blockers)
    provenance_status = _provenance_status(provenance_row, provenance_blockers) if not provenance_file_blockers else "blocked"
    evidence_ref_status, evidence_ref_path, evidence_ref_content_status, evidence_ref_sha256, evidence_ref_blockers = (
        _evidence_ref_status(provenance_row.get("evidence_ref"), target_id=target_id)
        if not provenance_file_blockers
        else ("waiting_on_provenance", "", "waiting_on_provenance", "", [])
    )
    source_identity_blockers = _split_blockers(workorder_row.get("identity_discovery_blockers"))
    identity_discovery_blocker_status, identity_discovery_blockers = _identity_discovery_blocker_status(
        source_identity_blockers,
        provenance_status=provenance_status,
        evidence_ref_content_status=evidence_ref_content_status,
    )
    manifest_row, manifest_file_blockers = _read_csv_one(workorder_row.get("manifest_stub_csv"))
    manifest_blockers = list(manifest_file_blockers)
    manifest_status = (
        _manifest_status(
            manifest_row,
            target_id=target_id,
            native_dropzone_pdb=native_dropzone,
            provenance_ready=provenance_status == "ready",
            blockers=manifest_blockers,
        )
        if not manifest_file_blockers
        else "blocked"
    )
    manifest_provenance_blockers: list[str] = []
    manifest_provenance_status, manifest_provenance_mismatch_count = _manifest_provenance_status(
        provenance_row,
        manifest_row,
        provenance_ready=provenance_status == "ready",
        manifest_readable=not manifest_file_blockers,
        blockers=manifest_provenance_blockers,
    )
    prediction = _text(manifest_row.get("prediction_pdb") or workorder_row.get("prediction_pdb") or workorder_row.get("ts_prediction_pdb"))
    (
        prediction_file_status,
        prediction_atom_count,
        prediction_protein_atom_count,
        prediction_chain_id_count,
        prediction_coordinate_status,
        prediction_blockers,
    ) = _prediction_status(prediction)
    native_prediction_identity_blockers: list[str] = []
    native_prediction_identity_status = _native_prediction_identity_status(
        native_dropzone,
        prediction,
        native_file_status=native_file_status,
        prediction_file_status=prediction_file_status,
        blockers=native_prediction_identity_blockers,
    )
    blockers = [
        *native_blockers,
        *prediction_blockers,
        *identity_discovery_blockers,
        *provenance_blockers,
        *evidence_ref_blockers,
        *manifest_blockers,
        *manifest_provenance_blockers,
        *native_prediction_identity_blockers,
    ]
    audit_status = "pass" if not blockers else "blocked"
    return {
        "target_id": target_id,
        "audit_status": audit_status,
        "workorder_status": _text(workorder_row.get("workorder_status")),
        "native_dropzone_pdb": native_dropzone,
        "native_file_status": native_file_status,
        "native_atom_record_count": atom_count,
        "native_protein_atom_record_count": protein_atom_count,
        "native_chain_id_count": chain_id_count,
        "native_coordinate_status": native_coordinate_status,
        "identity_discovery_blocker_status": identity_discovery_blocker_status,
        "identity_discovery_blockers": ",".join(source_identity_blockers),
        "provenance_template_csv": _text(workorder_row.get("provenance_template_csv")),
        "provenance_status": provenance_status,
        "evidence_ref_status": evidence_ref_status,
        "evidence_ref_path": evidence_ref_path,
        "evidence_ref_content_status": evidence_ref_content_status,
        "evidence_ref_sha256": evidence_ref_sha256,
        "manifest_stub_csv": _text(workorder_row.get("manifest_stub_csv")),
        "manifest_stub_status": manifest_status,
        "manifest_provenance_status": manifest_provenance_status,
        "manifest_provenance_mismatch_count": manifest_provenance_mismatch_count,
        "prediction_file_status": prediction_file_status,
        "prediction_atom_record_count": prediction_atom_count,
        "prediction_protein_atom_record_count": prediction_protein_atom_count,
        "prediction_chain_id_count": prediction_chain_id_count,
        "prediction_coordinate_status": prediction_coordinate_status,
        "native_prediction_identity_status": native_prediction_identity_status,
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": _next_action(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    rows = [_audit_row(row) for row in _rows(workorder_payload)]
    pass_count = sum(1 for row in rows if row["audit_status"] == "pass")
    first_blocked = next((row for row in rows if row["audit_status"] != "pass"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_workorder_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_workorder_audit_status": "pass"
        if rows and pass_count == len(rows)
        else ("blocked" if rows else "missing_workorders"),
        "workorder_json": _artifact(args.workorder_json),
        "clearance_workorder_status": _text(workorder_summary.get("clearance_workorder_status")),
        "audit_target_count": len(rows),
        "audit_pass_count": pass_count,
        "audit_blocked_count": len(rows) - pass_count,
        "native_present_count": sum(1 for row in rows if row["native_file_status"] == "present"),
        "native_valid_count": sum(1 for row in rows if row["native_file_status"] == "present"),
        "native_protein_atom_count": sum(int(row["native_protein_atom_record_count"]) for row in rows),
        "native_coordinate_valid_count": sum(1 for row in rows if row["native_coordinate_status"] == "valid"),
        "provenance_ready_count": sum(1 for row in rows if row["provenance_status"] == "ready"),
        "evidence_ref_present_count": sum(1 for row in rows if row["evidence_ref_status"] == "present"),
        "evidence_ref_blocked_count": sum(
            1
            for row in rows
            if row["evidence_ref_status"] not in {"present", "waiting_on_provenance"}
        ),
        "evidence_ref_waiting_count": sum(
            1 for row in rows if row["evidence_ref_status"] == "waiting_on_provenance"
        ),
        "evidence_ref_verified_count": sum(
            1 for row in rows if row["evidence_ref_content_status"] == "verified"
        ),
        "evidence_ref_content_blocked_count": sum(
            1 for row in rows if row["evidence_ref_content_status"] == "content_blocked"
        ),
        "manifest_stub_ready_count": sum(1 for row in rows if row["manifest_stub_status"] == "ready"),
        "manifest_provenance_matched_count": sum(
            1 for row in rows if row["manifest_provenance_status"] == "matched"
        ),
        "manifest_provenance_mismatch_count": sum(
            int(row["manifest_provenance_mismatch_count"]) for row in rows
        ),
        "prediction_present_count": sum(1 for row in rows if row["prediction_file_status"] == "present"),
        "prediction_protein_atom_count": sum(int(row["prediction_protein_atom_record_count"]) for row in rows),
        "prediction_coordinate_valid_count": sum(1 for row in rows if row["prediction_coordinate_status"] == "valid"),
        "identity_discovery_blocked_count": sum(
            1 for row in rows if row["identity_discovery_blocker_status"] == "blocked"
        ),
        "identity_discovery_cleared_count": sum(
            1 for row in rows if row["identity_discovery_blocker_status"] == "cleared_by_provenance_review"
        ),
        "native_prediction_distinct_count": sum(
            1 for row in rows if row["native_prediction_identity_status"] == "distinct"
        ),
        "native_prediction_same_count": sum(
            1
            for row in rows
            if row["native_prediction_identity_status"] in {"same_file", "identical_content"}
        ),
        "native_prediction_waiting_count": sum(
            1
            for row in rows
            if row["native_prediction_identity_status"] in {"waiting_on_native", "waiting_on_prediction"}
        ),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_status": _text(first_blocked.get("audit_status")),
        "first_blocked_next_action": _text(first_blocked.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Workorder Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_workorder_audit_status: `{summary['clearance_workorder_audit_status']}`",
        f"- clearance_workorder_status: `{summary['clearance_workorder_status'] or '-'}`",
        f"- audit pass/blocked/total: `{summary['audit_pass_count']}/{summary['audit_blocked_count']}/{summary['audit_target_count']}`",
        f"- prediction/native/provenance/manifest ready: `{summary['prediction_present_count']}/{summary['native_valid_count']}/{summary['provenance_ready_count']}/{summary['manifest_stub_ready_count']}`",
        f"- prediction protein atoms/coordinate-valid: `{summary['prediction_protein_atom_count']}/{summary['prediction_coordinate_valid_count']}`",
        f"- native protein atoms/coordinate-valid: `{summary['native_protein_atom_count']}/{summary['native_coordinate_valid_count']}`",
        f"- identity discovery blockers blocked/cleared: `{summary['identity_discovery_blocked_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- local evidence refs present/blocked/waiting: `{summary['evidence_ref_present_count']}/{summary['evidence_ref_blocked_count']}/{summary['evidence_ref_waiting_count']}`",
        f"- local evidence content verified/blocked: `{summary['evidence_ref_verified_count']}/{summary['evidence_ref_content_blocked_count']}`",
        f"- manifest/provenance matched/mismatches: `{summary['manifest_provenance_matched_count']}/{summary['manifest_provenance_mismatch_count']}`",
        f"- native/prediction distinct/same/waiting: `{summary['native_prediction_distinct_count']}/{summary['native_prediction_same_count']}/{summary['native_prediction_waiting_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_status'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Audit Rows",
        "",
        "| target | audit | native | atoms | protein atoms | chains | coordinates | identity blockers | prediction | pred atoms | pred protein atoms | pred chains | pred coordinates | provenance | evidence | evidence content | manifest | manifest/provenance | native/prediction | blockers | next action |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['audit_status']}` | `{row['native_file_status']}` | "
            f"{row['native_atom_record_count']} | {row['native_protein_atom_record_count']} | "
            f"{row['native_chain_id_count']} | `{row['native_coordinate_status']}` | "
            f"`{row['identity_discovery_blocker_status']}` | "
            f"`{row['prediction_file_status']}` | {row['prediction_atom_record_count']} | "
            f"{row['prediction_protein_atom_record_count']} | {row['prediction_chain_id_count']} | "
            f"`{row['prediction_coordinate_status']}` | `{row['provenance_status']}` | "
            f"`{row['evidence_ref_status']}` | `{row['evidence_ref_content_status']}` | `{row['manifest_stub_status']}` | "
            f"`{row['manifest_provenance_status']}` | "
            f"`{row['native_prediction_identity_status']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append(
            "| - | `missing_workorders` | - | 0 | 0 | 0 | - | - | - | 0 | 0 | 0 | - | - | - | - | - | - | - | `workorders_missing` | "
            "rerun clearance workorder builder |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 target identity clearance workorders.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
