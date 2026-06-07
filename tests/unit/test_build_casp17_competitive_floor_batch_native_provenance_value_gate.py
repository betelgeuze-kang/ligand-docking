import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_value_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target_id", *mod.REQUIRED_VALUE_COLUMNS], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(x: float) -> str:
    return (
        f"ATOM      1  N   GLY A   1      {x:6.3f}  13.207   9.333  1.00 20.00           N\n"
        "ATOM      2  CA  GLY A   1      12.204  13.807   9.933  1.00 20.00           C\n"
        "END\n"
    )


def _batch_payload(tmp_path: Path, target_ids: list[str], intake_csv: Path, batch_folder: Path) -> Path:
    rows = [
        {
            "target_id": target_id,
            "target_name": f"{target_id} immune complex",
            "kit_folder": str(batch_folder / f"{target_id}_kit"),
            "prediction_pdb": str(tmp_path / "predictions" / f"{target_id}_model_1.pdb"),
            "ts_prediction_pdb": str(tmp_path / "predictions" / f"{target_id}TS.pdb"),
            "competitive_proof_eligible": "false",
            "author_serialized": "false",
        }
        for target_id in target_ids
    ]
    for row in rows:
        Path(row["kit_folder"]).mkdir(parents=True, exist_ok=True)
    batch_folder.mkdir(parents=True, exist_ok=True)
    batch_json = tmp_path / "batch_kit.json"
    _write_json(
        batch_json,
        {
            "summary": {
                "batch_unlock_kit_status": (
                    "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
                ),
                "batch_operator_fill_intake_csv": str(intake_csv),
                "batch_folder": str(batch_folder),
                "target_count": len(target_ids),
                "target_ids": ",".join(target_ids),
            },
            "rows": rows,
        },
    )
    return batch_json


def _completion_audit(tmp_path: Path) -> Path:
    path = tmp_path / "completion_audit.json"
    _write_json(
        path,
        {
            "summary": {
                "batch_unlock_kit_completion_audit_status": (
                    "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
                )
            }
        },
    )
    return path


def test_batch_native_provenance_value_gate_blocks_current_placeholders(tmp_path: Path) -> None:
    target_ids = ["H1319", "H1321", "H2324"]
    intake_csv = tmp_path / "operator_fill_intake_batch.csv"
    _write_csv(
        intake_csv,
        [
            {
                "target_id": target_id,
                "native_source_pdb": "REQUIRED_OPERATOR_NATIVE_PDB_SOURCE_PATH",
                "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_FILE",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
                "notes": "Do not mark cleared until native and no-leak provenance are operator-reviewed.",
            }
            for target_id in target_ids
        ],
    )
    batch_json = _batch_payload(tmp_path, target_ids, intake_csv, tmp_path / "batch")
    args = mod.parse_args(
        [
            "--batch-kit-json",
            str(batch_json),
            "--batch-completion-audit-json",
            str(_completion_audit(tmp_path)),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "GATE.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["batch_native_provenance_value_gate_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
    )
    assert summary["target_count"] == 3
    assert summary["target_ready_count"] == 0
    assert summary["target_blocked_count"] == 3
    assert summary["required_field_per_target_count"] == 13
    assert summary["required_field_total_count"] == 39
    assert summary["ready_value_count"] == 3
    assert summary["blocked_value_count"] == 36
    assert summary["native_source_ready_count"] == 0
    assert summary["evidence_ref_ready_count"] == 0
    assert summary["clearance_ready_count"] == 0
    assert summary["date_ready_count"] == 0
    assert summary["boolean_ready_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["first_blocked_target_id"] == "H1319"
    assert summary["first_blocker"] == "native_source_pdb_required"
    assert payload["rows"][0]["blocker_count"] == 12
    assert "current_casp17_target_must_be_false" in payload["rows"][0]["blockers"]
    assert ("AUTHOR" + " ") not in (tmp_path / "gate.json").read_text(encoding="utf-8")
    assert not list((tmp_path / "batch").rglob("*.pdb"))
    assert not list((tmp_path / "batch").rglob("*.cif"))


def test_batch_native_provenance_value_gate_passes_ready_values(tmp_path: Path) -> None:
    target_id = "H1319"
    prediction_pdb = tmp_path / "predictions" / f"{target_id}_model_1.pdb"
    native_pdb = tmp_path / "native" / f"{target_id}_native.pdb"
    evidence = tmp_path / "evidence" / f"{target_id}_no_leak.md"
    prediction_pdb.parent.mkdir(parents=True, exist_ok=True)
    native_pdb.parent.mkdir(parents=True, exist_ok=True)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    prediction_pdb.write_text(_pdb(10.0), encoding="utf-8")
    native_pdb.write_text(_pdb(20.0), encoding="utf-8")
    evidence.write_text(f"{target_id} reviewed as no-leak historical benchmark evidence.\n", encoding="utf-8")
    intake_csv = tmp_path / "operator_fill_intake_batch.csv"
    _write_csv(
        intake_csv,
        [
            {
                "target_id": target_id,
                "native_source_pdb": str(native_pdb),
                "no_leak_evidence_ref": str(evidence),
                "leakage_clearance": "cleared",
                "operator_clearance": "cleared",
                "operator": "operator-1",
                "prediction_created_at": "2026-04-01",
                "native_release_date": "2026-05-01",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "notes": "reviewed",
            }
        ],
    )
    batch_json = _batch_payload(tmp_path, [target_id], intake_csv, tmp_path / "batch")
    args = mod.parse_args(
        [
            "--batch-kit-json",
            str(batch_json),
            "--batch-completion-audit-json",
            str(_completion_audit(tmp_path)),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "GATE.md"),
        ]
    )
    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["batch_native_provenance_value_gate_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_gate_ready_for_operator_intake_apply"
    )
    assert summary["target_count"] == 1
    assert summary["target_ready_count"] == 1
    assert summary["target_blocked_count"] == 0
    assert summary["required_field_total_count"] == 13
    assert summary["ready_value_count"] == 13
    assert summary["blocked_value_count"] == 0
    assert summary["native_source_ready_count"] == 1
    assert summary["evidence_ref_ready_count"] == 1
    assert summary["clearance_ready_count"] == 1
    assert summary["date_ready_count"] == 1
    assert summary["boolean_ready_count"] == 1
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert payload["rows"][0]["gate_status"] == "ready_for_operator_intake_apply"
    assert payload["rows"][0]["blockers"] == ""
