#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_READINESS_JSON = "casp17/capri_round65/capri_round65_readiness_current.json"
DEFAULT_DROPZONE_DIR = "casp17/capri_round65/format_preflight"
DEFAULT_OUT_JSON = "casp17/capri_round65/capri_round65_format_preflight_current.json"
DEFAULT_OUT_CSV = "casp17/capri_round65/capri_round65_format_preflight_current.csv"
DEFAULT_OUT_MD = "casp17/capri_round65/CAPRI_ROUND65_FORMAT_PREFLIGHT.md"

SOURCE_ROUND = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/round/65/"
SOURCE_FORMAT = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/capri-format/"
SOURCE_CASP_CAPRI = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/casp-capri/"

NONCANONICAL_RESIDUE_REPLACEMENTS = {
    "HSD",
    "HSE",
    "HIE",
    "HID",
    "HIP",
    "CYX",
    "CYM",
    "GLH",
    "HYP",
    "MSE",
    "ASH",
}

ROW_COLUMNS = [
    "capri_target_id",
    "casp_target_id",
    "role",
    "preflight_status",
    "dropzone_dir",
    "target_template_pdb",
    "candidate_submission_pdb",
    "model_limit",
    "model_count",
    "atom_record_count",
    "header_ok",
    "author_ok",
    "compnd_ok",
    "model_order_ok",
    "endmdl_ok",
    "ter_ok",
    "end_ok",
    "parent_record_status",
    "massivefold_remark_status",
    "blockers",
    "next_action",
]

CHECKLIST_COLUMNS = ["gate", "status", "required_evidence"]

CLAIM_BOUNDARY = (
    "Local CAPRI Round 65 format preflight only. It checks submission-file presence and basic CAPRI PDB "
    "format rules before online upload. It does not download restricted CAPRI templates, submit models, "
    "replace the CAPRI validator, or certify final CASP/CAPRI acceptance."
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


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _model_limit(role: str) -> int:
    return 10 if role == "scorer" else 100


def _expected_folder(dropzone_dir: str | Path, capri_target_id: str, casp_target_id: str) -> Path:
    return _resolve(dropzone_dir) / f"{capri_target_id}_{_safe_name(casp_target_id).upper()}"


def _parse_model_numbers(lines: list[str]) -> list[int]:
    numbers: list[int] = []
    for line in lines:
        if line.startswith("MODEL"):
            try:
                numbers.append(int(line[5:].strip()))
            except ValueError:
                numbers.append(-1)
    return numbers


def _check_pdb(path: Path, capri_target_id: str, role: str) -> dict[str, Any]:
    blockers: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    nonempty = [line for line in lines if line.strip()]
    first = nonempty[0] if nonempty else ""
    header_ok = first.startswith("HEADER")
    if not header_ok:
        blockers.append("header_first_line_missing")
    elif capri_target_id not in first and capri_target_id.removeprefix("T") not in first:
        blockers.append("header_target_number_missing")
        header_ok = False
    author_ok = any(line.startswith("AUTHOR") for line in lines)
    compnd_ok = any(line.startswith("COMPND") for line in lines)
    if not author_ok:
        blockers.append("author_record_missing")
    if not compnd_ok:
        blockers.append("compnd_record_missing")
    model_numbers = _parse_model_numbers(lines)
    model_count = len(model_numbers)
    model_limit = _model_limit(role)
    if model_count <= 0:
        blockers.append("model_records_missing")
    if model_count > model_limit:
        blockers.append("model_count_exceeds_role_limit")
    expected = list(range(1, model_count + 1))
    model_order_ok = bool(model_numbers) and model_numbers == expected
    if not model_order_ok:
        blockers.append("model_records_not_sequential_1_to_n")
    endmdl_count = sum(1 for line in lines if line.startswith("ENDMDL"))
    endmdl_ok = model_count > 0 and endmdl_count == model_count
    if not endmdl_ok:
        blockers.append("endmdl_count_mismatch")
    ter_ok = any(line.startswith("TER") for line in lines)
    if not ter_ok:
        blockers.append("ter_records_missing")
    end_ok = bool(nonempty) and nonempty[-1].startswith("END")
    if not end_ok:
        blockers.append("end_record_missing")
    atom_lines = [line for line in lines if line.startswith(("ATOM", "HETATM"))]
    atom_count = len(atom_lines)
    if atom_count <= 0:
        blockers.append("atom_records_missing")
    residue_names = {line[17:20].strip().upper() for line in atom_lines if len(line) >= 20}
    if residue_names & NONCANONICAL_RESIDUE_REPLACEMENTS:
        blockers.append("noncanonical_residue_name_requires_capri_casp_fix")
    parent_count = sum(1 for line in lines if line.startswith("PARENT"))
    parent_status = "present" if parent_count else "absent_auto_parent_na_expected"
    massivefold_status = (
        "present" if any("MASSIVEFOLD" in line.upper() for line in lines if line.startswith("REMARK")) else "not_detected"
    )
    return {
        "model_count": model_count,
        "atom_record_count": atom_count,
        "header_ok": header_ok,
        "author_ok": author_ok,
        "compnd_ok": compnd_ok,
        "model_order_ok": model_order_ok,
        "endmdl_ok": endmdl_ok,
        "ter_ok": ter_ok,
        "end_ok": end_ok,
        "parent_record_status": parent_status,
        "massivefold_remark_status": massivefold_status,
        "blockers": blockers,
    }


def _role_for_target(readiness_row: dict[str, Any]) -> str:
    role = _text(readiness_row.get("recommended_role"))
    if role == "scorer":
        return "scorer"
    if "predictor" in role:
        return "predictor_server"
    return role or "unknown"


def _build_row(readiness_row: dict[str, Any], dropzone_dir: str | Path) -> dict[str, Any]:
    capri_target_id = _text(readiness_row.get("capri_target_id"))
    casp_target_id = _text(readiness_row.get("casp_target_id"))
    role = _role_for_target(readiness_row)
    folder = _expected_folder(dropzone_dir, capri_target_id, casp_target_id)
    template_pdb = folder / "target_template.pdb"
    candidate_pdb = folder / "candidate_submission.pdb"
    blockers: list[str] = []
    if role == "closed":
        status = "closed_context"
        blockers.append("closed_target")
        next_action = "no preflight action; target already closed"
        check = {}
    else:
        if not template_pdb.exists():
            blockers.append("target_template_pdb_missing")
        if not candidate_pdb.exists():
            blockers.append("candidate_submission_pdb_missing")
            check = {}
        else:
            check = _check_pdb(candidate_pdb, capri_target_id, role)
            blockers.extend(check["blockers"])
        if blockers:
            status = "blocked_format_preflight"
            next_action = "place target_template.pdb and candidate_submission.pdb, then rerun local format preflight"
        else:
            status = "format_preflight_pass_local"
            next_action = "run the CAPRI online validator before submission"
    row = {
        "capri_target_id": capri_target_id,
        "casp_target_id": casp_target_id,
        "role": role,
        "preflight_status": status,
        "dropzone_dir": _artifact(folder),
        "target_template_pdb": _artifact(template_pdb),
        "candidate_submission_pdb": _artifact(candidate_pdb),
        "model_limit": _model_limit(role),
        "model_count": _int(check.get("model_count") if check else 0),
        "atom_record_count": _int(check.get("atom_record_count") if check else 0),
        "header_ok": bool(check.get("header_ok")) if check else False,
        "author_ok": bool(check.get("author_ok")) if check else False,
        "compnd_ok": bool(check.get("compnd_ok")) if check else False,
        "model_order_ok": bool(check.get("model_order_ok")) if check else False,
        "endmdl_ok": bool(check.get("endmdl_ok")) if check else False,
        "ter_ok": bool(check.get("ter_ok")) if check else False,
        "end_ok": bool(check.get("end_ok")) if check else False,
        "parent_record_status": _text(check.get("parent_record_status")) if check else "",
        "massivefold_remark_status": _text(check.get("massivefold_remark_status")) if check else "",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "next_action": next_action,
    }
    return row


def _write_dropzones(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        folder = _resolve(row["dropzone_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(
            folder / "format_checklist.csv",
            [
                {
                    "gate": "target_template_pdb",
                    "status": "blocked" if "target_template_pdb_missing" in row["blockers"] else "ready",
                    "required_evidence": "target-specific CAPRI template downloaded from the CAPRI system",
                },
                {
                    "gate": "candidate_submission_pdb",
                    "status": "blocked" if "candidate_submission_pdb_missing" in row["blockers"] else "ready",
                    "required_evidence": "local candidate_submission.pdb assembled for this target and role",
                },
                {
                    "gate": "local_pdb_format",
                    "status": row["preflight_status"],
                    "required_evidence": "HEADER/MODEL/ENDMDL/TER/END/AUTHOR/COMPND/ATOM checks pass locally",
                },
                {
                    "gate": "capri_online_validator",
                    "status": "blocked",
                    "required_evidence": "CAPRI online validator acceptance before upload",
                },
            ],
            CHECKLIST_COLUMNS,
        )
        lines = [
            f"# CAPRI Round 65 Format Preflight: {row['capri_target_id']} / {row['casp_target_id']}",
            "",
            f"- role: `{row['role']}`",
            f"- status: `{row['preflight_status']}`",
            f"- template: `{row['target_template_pdb']}`",
            f"- candidate: `{row['candidate_submission_pdb']}`",
            f"- model count/limit: `{row['model_count']}/{row['model_limit']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            f"- next action: {row['next_action']}",
            "",
        ]
        (folder / "ACTION.md").write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    readiness_payload = _read_json(args.readiness_json)
    readiness_rows = _rows(readiness_payload)
    rows = [_build_row(row, args.dropzone_dir) for row in readiness_rows]
    _write_dropzones(rows)
    active_rows = [row for row in rows if row["preflight_status"] != "closed_context"]
    pass_rows = [row for row in active_rows if row["preflight_status"] == "format_preflight_pass_local"]
    blocked_rows = [row for row in active_rows if row["preflight_status"] != "format_preflight_pass_local"]
    template_missing_rows = [row for row in active_rows if "target_template_pdb_missing" in row["blockers"]]
    candidate_missing_rows = [row for row in active_rows if "candidate_submission_pdb_missing" in row["blockers"]]
    checked_rows = [row for row in active_rows if _resolve(row["candidate_submission_pdb"]).exists()]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    if not readiness_rows:
        status = "blocked_missing_readiness_rows"
    elif blocked_rows:
        status = "blocked_format_preflight"
    else:
        status = "format_preflight_pass_local"
    summary = {
        "packet_type": "capri_round65_format_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "format_preflight_status": status,
        "readiness_json": _artifact(args.readiness_json),
        "dropzone_dir": _artifact(args.dropzone_dir),
        "target_count": len(rows),
        "active_target_count": len(active_rows),
        "closed_target_count": len(rows) - len(active_rows),
        "local_pass_count": len(pass_rows),
        "blocked_target_count": len(blocked_rows),
        "checked_submission_count": len(checked_rows),
        "target_template_missing_count": len(template_missing_rows),
        "candidate_submission_missing_count": len(candidate_missing_rows),
        "format_error_count": sum(
            1
            for row in active_rows
            if row["blockers"]
            and "candidate_submission_pdb_missing" not in row["blockers"]
            and "target_template_pdb_missing" not in row["blockers"]
        ),
        "first_blocked_target_id": _text(first_blocked.get("capri_target_id")),
        "first_next_action": _text(first_blocked.get("next_action"))
        or "run the CAPRI online validator before submission",
        "source_round": SOURCE_ROUND,
        "source_format": SOURCE_FORMAT,
        "source_casp_capri": SOURCE_CASP_CAPRI,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CAPRI Round 65 Format Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['format_preflight_status']}`",
        f"- active/closed/total: `{summary['active_target_count']}/{summary['closed_target_count']}/{summary['target_count']}`",
        f"- local pass/blocked/checked: `{summary['local_pass_count']}/{summary['blocked_target_count']}/{summary['checked_submission_count']}`",
        f"- missing template/candidate: `{summary['target_template_missing_count']}/{summary['candidate_submission_missing_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action']}",
        f"- source format: {summary['source_format']}",
        f"- source CASP-CAPRI: {summary['source_casp_capri']}",
        "",
        "## Target Rows",
        "",
        "| CAPRI | CASP | role | status | models | atoms | template | candidate | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['capri_target_id']}` | `{row['casp_target_id']}` | `{row['role']}` | "
            f"`{row['preflight_status']}` | {row['model_count']}/{row['model_limit']} | "
            f"{row['atom_record_count']} | `{row['target_template_pdb']}` | "
            f"`{row['candidate_submission_pdb']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CAPRI Round 65 local format preflight packet.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--dropzone-dir", default=DEFAULT_DROPZONE_DIR)
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
