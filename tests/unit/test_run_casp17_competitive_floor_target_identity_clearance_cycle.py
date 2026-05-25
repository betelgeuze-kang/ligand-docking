import csv
import json
from pathlib import Path

from tools import run_casp17_competitive_floor_target_identity_clearance_cycle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _pdb(path: Path, *, residue: str = "ALA", x: str = "1.000", y: str = "2.000", z: str = "3.000") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"ATOM      1  CA  {residue} A   1       {x}   {y}   {z}  1.00 70.00           C\n")
    return str(path)


def _ready_provenance(target_id: str = "H1001", evidence_ref: str = "local/no_leak/H1001.md") -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "2026-01-01",
        "native_release_date": "2026-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "cleared",
        "operator": "operator-a",
        "evidence_ref": evidence_ref,
        "notes": "reviewed",
    }


def _blocked_provenance(target_id: str = "H1001") -> dict[str, str]:
    row = _ready_provenance(target_id)
    row["leakage_clearance"] = "REQUIRED_NO_LEAK_CLEARANCE"
    row["prediction_created_at"] = "YYYY-MM-DD"
    row["native_release_date"] = "YYYY-MM-DD"
    row["operator_clearance"] = "REQUIRED_OPERATOR_CLEARANCE"
    return row


def _manifest(target_id: str, prediction_pdb: str, native_pdb: str) -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "prediction_pdb": prediction_pdb,
        "native_pdb": native_pdb,
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }


def _intake_row() -> dict[str, str]:
    return {
        "dropzone_id": "priority_011_REQUIRED_COMPLEX_001",
        "operator_priority": "11",
        "row_rank": "11",
        "scope": "complex",
        "current_benchmark_id": "hist_REQUIRED_COMPLEX_001",
        "current_target_id": "REQUIRED_COMPLEX_001",
        "proposed_benchmark_id": "",
        "proposed_target_id": "",
        "evidence_ref": "",
        "operator_clearance": "",
        "identity_status": "awaiting_identity",
        "missing_field_count": "4",
        "blockers": "proposed_benchmark_id_required,proposed_target_id_required",
        "file_actions_unlocked": "0",
        "readiness_gate_status": "awaiting_identity",
        "apply_identity_command": "python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity",
        "verify_command": "python3 tools/build_casp17_competitive_floor_execution_board.py",
        "next_action": "fill proposed_benchmark_id",
    }


def _fixture(tmp_path: Path, *, ready: bool) -> dict[str, Path]:
    target_id = "H1001"
    prediction_pdb = _pdb(tmp_path / "prediction" / f"{target_id}_model_1.pdb")
    native_pdb = (
        _pdb(tmp_path / "native" / f"{target_id}_native.pdb", residue="GLY", x="4.000", y="5.000", z="6.000")
        if ready
        else str(tmp_path / "native" / f"{target_id}_native.pdb")
    )
    provenance_csv = tmp_path / "provenance_template.csv"
    manifest_csv = tmp_path / "manifest_stub.csv"
    evidence_ref = tmp_path / "no_leak" / f"{target_id}.md"
    if ready:
        evidence_ref.parent.mkdir(parents=True, exist_ok=True)
        evidence_ref.write_text(f"{target_id} operator reviewed no-leak evidence\n", encoding="utf-8")
    _write_csv(
        provenance_csv,
        [_ready_provenance(target_id, str(evidence_ref)) if ready else _blocked_provenance(target_id)],
    )
    _write_csv(manifest_csv, [_manifest(target_id, prediction_pdb, native_pdb)])
    workorder_json = tmp_path / "workorder.json"
    _write_json(
        workorder_json,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [
                {
                    "target_id": target_id,
                    "workorder_status": "native_and_provenance_required",
                    "native_dropzone_pdb": native_pdb,
                    "provenance_template_csv": str(provenance_csv),
                    "manifest_stub_csv": str(manifest_csv),
                    "prediction_pdb": prediction_pdb,
                }
            ],
        },
    )
    current_csv = tmp_path / "current_targets.csv"
    intake_csv = tmp_path / "identity_intake.csv"
    _write_csv(current_csv, [{"target_id": "T1331"}])
    _write_csv(intake_csv, [_intake_row()])
    return {
        "workorder_json": workorder_json,
        "manifest_csv": manifest_csv,
        "current_csv": current_csv,
        "intake_csv": intake_csv,
    }


def _args(tmp_path: Path, fixture: dict[str, Path], *extra: str) -> list[str]:
    return [
        "--workorder-json",
        str(fixture["workorder_json"]),
        "--manifest-sync-json",
        str(tmp_path / "manifest_sync.json"),
        "--manifest-sync-csv",
        str(tmp_path / "manifest_sync.csv"),
        "--manifest-sync-md",
        str(tmp_path / "MANIFEST_SYNC.md"),
        "--audit-json",
        str(tmp_path / "audit.json"),
        "--audit-csv",
        str(tmp_path / "audit.csv"),
        "--audit-md",
        str(tmp_path / "AUDIT.md"),
        "--action-board-json",
        str(tmp_path / "action_board.json"),
        "--action-board-csv",
        str(tmp_path / "action_board.csv"),
        "--action-board-md",
        str(tmp_path / "ACTION_BOARD.md"),
        "--action-bundle-dir",
        str(tmp_path / "action_bundle"),
        "--action-bundle-json",
        str(tmp_path / "action_bundle.json"),
        "--action-bundle-csv",
        str(tmp_path / "action_bundle.csv"),
        "--action-bundle-md",
        str(tmp_path / "ACTION_BUNDLE.md"),
        "--current-target-csv",
        str(fixture["current_csv"]),
        "--promoted-manifest-csv",
        str(tmp_path / "promoted_manifest.csv"),
        "--promotion-json",
        str(tmp_path / "promotion.json"),
        "--promotion-csv",
        str(tmp_path / "promotion.csv"),
        "--promotion-md",
        str(tmp_path / "PROMOTION.md"),
        "--identity-intake-csv",
        str(fixture["intake_csv"]),
        "--candidate-intake-csv",
        str(tmp_path / "candidate_intake.csv"),
        "--candidate-intake-sync-json",
        str(tmp_path / "candidate_intake_sync.json"),
        "--candidate-intake-sync-csv",
        str(tmp_path / "candidate_intake_sync.csv"),
        "--candidate-intake-sync-md",
        str(tmp_path / "CANDIDATE_INTAKE_SYNC.md"),
        "--intake-staging-json",
        str(tmp_path / "intake_staging.json"),
        "--intake-staging-csv",
        str(tmp_path / "intake_staging.csv"),
        "--intake-staging-md",
        str(tmp_path / "INTAKE_STAGING.md"),
        "--workbench-json",
        str(tmp_path / "workbench.json"),
        "--workbench-csv",
        str(tmp_path / "workbench.csv"),
        "--workbench-md",
        str(tmp_path / "WORKBENCH.md"),
        "--out-json",
        str(tmp_path / "cycle.json"),
        "--out-csv",
        str(tmp_path / "cycle.csv"),
        "--out-md",
        str(tmp_path / "CYCLE.md"),
        *extra,
    ]


def test_clearance_cycle_waits_for_provenance_without_mutating_manifest(tmp_path):
    fixture = _fixture(tmp_path, ready=False)
    args = mod.parse_args(_args(tmp_path, fixture))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_cycle_status"] == "awaiting_provenance"
    assert payload["summary"]["manifest_sync_awaiting_provenance_count"] == 1
    assert payload["summary"]["audit_blocked_count"] == 1
    assert payload["summary"]["action_board_status"] == "open_actions"
    assert payload["summary"]["action_board_open_action_count"] == 4
    assert payload["summary"]["action_bundle_status"] == "open_actions"
    assert payload["summary"]["action_bundle_open_action_count"] == 4
    assert payload["summary"]["action_bundle_file_count"] == 8
    assert _read_csv(fixture["manifest_csv"])[0]["operator_clearance"] == "REQUIRED_OPERATOR_CLEARANCE"
    assert _read_csv(tmp_path / "cycle.csv")[0]["stage"] == "manifest_sync"
    assert (tmp_path / "action_board.json").is_file()
    assert (tmp_path / "action_bundle.json").is_file()
    assert list((tmp_path / "action_bundle").glob("*/action_001_native_dropzone/ACTION.md"))


def test_clearance_cycle_apply_manifest_sync_reaches_intake_staging(tmp_path):
    fixture = _fixture(tmp_path, ready=True)
    args = mod.parse_args(_args(tmp_path, fixture, "--apply-manifest-sync", "--apply-candidate-intake"))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_cycle_status"] == "candidate_intake_applied"
    assert payload["summary"]["audit_pass_count"] == 1
    assert payload["summary"]["action_board_status"] == "ready"
    assert payload["summary"]["action_board_open_action_count"] == 0
    assert payload["summary"]["action_bundle_status"] == "ready"
    assert payload["summary"]["action_bundle_open_action_count"] == 0
    assert payload["summary"]["promoted_manifest_count"] == 1
    assert payload["summary"]["staged_identity_count"] == 1
    assert payload["summary"]["candidate_intake_applied_count"] == 1
    manifest = _read_csv(fixture["manifest_csv"])[0]
    assert manifest["operator_clearance"] == "cleared"
    assert manifest["leakage_clearance"] == "no_leak"
    candidate = _read_csv(tmp_path / "candidate_intake.csv")[0]
    assert candidate["proposed_target_id"] == "H1001"
    assert candidate["proposed_benchmark_id"] == "hist_H1001_clearance_candidate"
    live = _read_csv(fixture["intake_csv"])[0]
    assert live["proposed_target_id"] == "H1001"
