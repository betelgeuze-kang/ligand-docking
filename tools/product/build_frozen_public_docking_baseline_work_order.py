#!/usr/bin/env python3
"""Build the fail-closed offline baseline work order for the frozen suite.

This tool does not run or install a docking engine. It joins the frozen case
receipt with the completed internal execution and produces one operator row per
case, including the exact identities and provenance that a later Vina/GNINA/
Smina result must bind to. Missing binaries, preparation policy, licence review,
or result artifacts remain explicit blockers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXECUTION_JSON = "runs/frozen_public_docking_benchmark_execution_current.json"
DEFAULT_COLLECTION_RECEIPT = "runs/public_docking_benchmark_case_collection_current.json"
DEFAULT_OUT_JSON = "runs/frozen_public_docking_baseline_work_order_current.json"
DEFAULT_OUT_CSV = "runs/frozen_public_docking_baseline_work_order_current.csv"
DEFAULT_OUT_MD = "runs/frozen_public_docking_baseline_work_order_current.md"

ALLOWED_BASELINE_ENGINES = ("vina", "gnina", "smina")
STATUS_READY = "frozen_public_docking_baseline_work_order_filled"
STATUS_BLOCKED = "blocked_frozen_public_docking_baseline_work_order"

CLAIM_BOUNDARY = (
    "Offline baseline work order only. It binds operator-supplied Vina/GNINA/Smina preparation and result "
    "artifacts to the same frozen case identities and denominator. It does not install or run a baseline, "
    "prepare PDBQT inputs, accept an unreviewed licence, compute a paired delta, promote a claim, or mutate "
    "external state."
)

PLACEHOLDER = "OPERATOR_FILL"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"{label}_missing:{path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label}_unparseable:{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label}_not_an_object")
    return payload


def _available_binaries() -> list[str]:
    return [name for name in ALLOWED_BASELINE_ENGINES if shutil.which(name)]


def build_baseline_work_order(
    *,
    execution_json: str | Path = DEFAULT_EXECUTION_JSON,
    collection_receipt_json: str | Path = DEFAULT_COLLECTION_RECEIPT,
    preparation_policy_artifact: str | Path = "",
    available_binaries: Sequence[str] | None = None,
) -> dict[str, Any]:
    execution = _read_json(_resolve(execution_json), "subject_execution")
    collection = _read_json(_resolve(collection_receipt_json), "collection_receipt")
    execution_summary = execution.get("summary") or {}
    collection_summary = collection.get("summary") or {}
    blockers: list[str] = []
    case_set_hash = str(execution_summary.get("case_set_hash") or "")
    if case_set_hash != str(collection_summary.get("case_set_hash") or ""):
        blockers.append("baseline_work_order_case_set_hash_mismatch")
    if execution_summary.get("suite_complete") is not True:
        blockers.append("subject_execution_suite_incomplete")
    if execution_summary.get("execution_ready") is not True:
        blockers.append("subject_execution_not_ready")

    evidence_by_case = {
        str(item.get("case_id") or ""): dict(item.get("evidence") or {})
        for item in collection.get("cases") or []
        if isinstance(item, dict) and item.get("case_id")
    }
    available = (
        sorted({str(name) for name in available_binaries})
        if available_binaries is not None
        else _available_binaries()
    )
    if not available:
        blockers.append("external_oracle_binary_unavailable_offline")

    prep_policy_text = str(preparation_policy_artifact or "").strip()
    prep_policy_path = _resolve(prep_policy_text) if prep_policy_text else None
    prep_policy_sha256 = ""
    if prep_policy_path is None or not prep_policy_path.is_file():
        blockers.append("external_oracle_preparation_policy_artifact_missing")
    else:
        prep_policy_sha256 = hashlib.sha256(prep_policy_path.read_bytes()).hexdigest()

    rows: list[dict[str, Any]] = []
    internal_preparation_blocked = 0
    for result in execution.get("cases") or []:
        if not isinstance(result, dict):
            continue
        case_id = str(result.get("case_id") or "")
        evidence = evidence_by_case.get(case_id, {})
        preparation = result.get("preparation") or {}
        preparation_ready = preparation.get("ready") is True
        if not preparation_ready:
            internal_preparation_blocked += 1
        prepared_input_hash = str(preparation.get("prepared_input_hash") or "")
        receptor = preparation.get("receptor") or {}
        ligand = preparation.get("ligand") or {}
        row = {
            "case_id": case_id,
            "case_set_hash": case_set_hash,
            "frozen_at_utc": collection_summary.get("frozen_at_utc", ""),
            "target_id": result.get("target_id", ""),
            "ligand_id": result.get("ligand_id", ""),
            "receptor_entry_id": evidence.get("receptor_entry_id", ""),
            "receptor_pdb_sha256": evidence.get("receptor_pdb_sha256", ""),
            "ligand_source_entry_id": evidence.get(
                "ligand_source_entry_id", evidence.get("receptor_entry_id", "")
            ),
            "ligand_source_receptor_pdb_sha256": evidence.get(
                "ligand_source_receptor_pdb_sha256",
                evidence.get("receptor_pdb_sha256", ""),
            ),
            "ligand_comp_id": evidence.get("ligand_comp_id", ""),
            "ligand_smiles_sha256": _sha256_text(
                str(evidence.get("ligand_smiles") or "")
            ),
            "internal_preparation_ready": preparation_ready,
            "internal_preparation_blockers": ";".join(preparation.get("blockers") or []),
            "prepared_input_hash": prepared_input_hash,
            "receptor_input_hash": receptor.get("input_hash", ""),
            "ligand_input_hash": ligand.get("input_hash", ""),
            "candidate_budget": execution_summary.get("candidate_budget", ""),
            "baseline_engine": f"{PLACEHOLDER}_BASELINE_ENGINE",
            "baseline_engine_version": f"{PLACEHOLDER}_ENGINE_VERSION",
            "baseline_license_ok": f"{PLACEHOLDER}_LICENSE_OK",
            "baseline_preparation_policy_artifact": (
                str(preparation_policy_artifact)
                if prep_policy_path is not None and prep_policy_path.is_file()
                else f"{PLACEHOLDER}_PREPARATION_POLICY_ARTIFACT"
            ),
            "baseline_preparation_policy_sha256": (
                prep_policy_sha256 or f"{PLACEHOLDER}_PREPARATION_POLICY_SHA256"
            ),
            "baseline_input_artifact": f"{PLACEHOLDER}_INPUT_ARTIFACT",
            "baseline_input_artifact_sha256": f"{PLACEHOLDER}_INPUT_ARTIFACT_SHA256",
            "baseline_pose_artifact": f"{PLACEHOLDER}_POSE_ARTIFACT",
            "baseline_pose_artifact_sha256": f"{PLACEHOLDER}_POSE_ARTIFACT_SHA256",
            "baseline_runtime_seconds": f"{PLACEHOLDER}_RUNTIME_SECONDS",
            "baseline_attempt_status": f"{PLACEHOLDER}_ATTEMPT_STATUS",
            "operator_id": f"{PLACEHOLDER}_OPERATOR_ID",
            "reviewed_at_utc": f"{PLACEHOLDER}_REVIEWED_AT_UTC",
        }
        rows.append(row)

    expected_count = int(execution_summary.get("frozen_case_count") or 0)
    if len(rows) != expected_count:
        blockers.append(f"baseline_work_order_case_count_mismatch:{len(rows)}!={expected_count}")
    missing_evidence = sum(
        1
        for row in rows
        if not row["receptor_entry_id"]
        or not row["receptor_pdb_sha256"]
        or not row["ligand_comp_id"]
    )
    if missing_evidence:
        blockers.append(f"baseline_work_order_case_evidence_missing:{missing_evidence}")
    blockers.append(f"external_oracle_result_rows_missing:{len(rows)}")
    blockers.append("paired_baseline_delta_missing")
    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    summary = {
        "schema_version": "frozen_public_docking_baseline_work_order_v1",
        "status": STATUS_READY if ready else STATUS_BLOCKED,
        "ready": ready,
        "case_set_hash": case_set_hash,
        "frozen_at_utc": collection_summary.get("frozen_at_utc", ""),
        "case_count": len(rows),
        "candidate_budget": execution_summary.get("candidate_budget"),
        "internal_preparation_ready_case_count": len(rows)
        - internal_preparation_blocked,
        "internal_preparation_blocked_case_count": internal_preparation_blocked,
        "available_external_oracle_binaries": available,
        "installs_binaries": False,
        "baseline_executed": False,
        "preparation_policy_artifact": prep_policy_text,
        "preparation_policy_sha256": prep_policy_sha256,
        "required_operator_fields": [
            "baseline_engine",
            "baseline_engine_version",
            "baseline_license_ok",
            "baseline_preparation_policy_artifact",
            "baseline_preparation_policy_sha256",
            "baseline_input_artifact",
            "baseline_input_artifact_sha256",
            "baseline_pose_artifact",
            "baseline_pose_artifact_sha256",
            "baseline_runtime_seconds",
            "baseline_attempt_status",
            "operator_id",
            "reviewed_at_utc",
        ],
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Frozen Public Docking Baseline Work Order (current)",
        "",
        "Generated operator work order. Fill the CSV only after an offline licensed run.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- case_set_hash: `{summary.get('case_set_hash')}`",
        f"- case_count: `{summary.get('case_count')}`",
        f"- candidate_budget: `{summary.get('candidate_budget')}`",
        f"- internal_preparation_ready_case_count: "
        f"`{summary.get('internal_preparation_ready_case_count')}`",
        f"- internal_preparation_blocked_case_count: "
        f"`{summary.get('internal_preparation_blocked_case_count')}`",
        f"- available_external_oracle_binaries: "
        f"`{','.join(summary.get('available_external_oracle_binaries') or []) or 'none'}`",
        f"- baseline_executed: `{summary.get('baseline_executed')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers") or [])
    lines.extend(["", "## Claim Boundary", "", str(summary.get("claim_boundary") or ""), ""])
    return "\n".join(lines)


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    columns = list(rows[0]) if rows else ["case_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the offline paired-baseline work order for the frozen suite."
    )
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument("--collection-receipt-json", default=DEFAULT_COLLECTION_RECEIPT)
    parser.add_argument("--preparation-policy-artifact", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_baseline_work_order(
        execution_json=args.execution_json,
        collection_receipt_json=args.collection_receipt_json,
        preparation_policy_artifact=args.preparation_policy_artifact,
    )
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(_resolve(args.out_csv), packet["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(packet), encoding="utf-8")
    if not args.quiet:
        print(json.dumps(packet["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if packet["summary"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
