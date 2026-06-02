import json
from pathlib import Path

from tools import (
    build_casp17_competitive_floor_batch_native_provenance_operator_fill_preflight as preflight,
)
from tools import (
    build_casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit as mod,
)
from tests.unit.test_build_casp17_competitive_floor_batch_native_provenance_operator_fill_preflight import (
    _materialize_inputs,
)


def _build_preflight(tmp_path: Path) -> Path:
    gate_json, board_json, audit_json = _materialize_inputs(tmp_path, ["H1319", "H1321", "H2324"])
    out_json = tmp_path / "preflight.json"
    args = preflight.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(board_json),
            "--action-board-completion-audit-json",
            str(audit_json),
            "--out-dir",
            str(tmp_path / "preflight"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "PREFLIGHT.md"),
        ]
    )
    payload = preflight.build_payload(args)
    preflight.write_outputs(args, payload)
    return out_json


def test_operator_fill_preflight_completion_audit_passes_ready_packet(tmp_path: Path) -> None:
    preflight_json = _build_preflight(tmp_path)
    args = mod.parse_args(
        [
            "--preflight-json",
            str(preflight_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["batch_native_provenance_operator_fill_preflight_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_pass"
    )
    assert summary["target_count"] == 3
    assert summary["target_pass_count"] == 3
    assert summary["target_blocked_count"] == 0
    assert summary["root_manifest_present"] == 1
    assert summary["target_folder_count"] == 3
    assert summary["target_readme_count"] == 3
    assert summary["target_operator_template_file_count"] == 3
    assert summary["target_field_policy_file_count"] == 3
    assert summary["operator_template_expected_rows"] == 3
    assert summary["operator_template_csv_rows"] == 3
    assert summary["operator_template_row_mismatch_count"] == 0
    assert summary["field_policy_expected_rows"] == 36
    assert summary["field_policy_csv_rows"] == 36
    assert summary["field_policy_row_mismatch_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert not summary["first_blocked_target_id"]
    assert not summary["first_blocker"]
    assert all(row["audit_status"] == "pass" for row in payload["rows"])
    assert ("AUTHOR" + " ") not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_operator_fill_preflight_completion_audit_blocks_coordinate_copy(tmp_path: Path) -> None:
    preflight_json = _build_preflight(tmp_path)
    payload = json.loads(preflight_json.read_text(encoding="utf-8"))
    first_folder = Path(payload["rows"][0]["target_preflight_folder"])
    (first_folder / "unexpected_native_copy.pdb").write_text("HEADER SHOULD NOT BE HERE\n", encoding="utf-8")
    args = mod.parse_args(
        [
            "--preflight-json",
            str(preflight_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    audit_payload = mod.build_payload(args)

    assert audit_payload["summary"]["batch_native_provenance_operator_fill_preflight_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_blocked"
    )
    assert audit_payload["summary"]["target_pass_count"] == 2
    assert audit_payload["summary"]["target_blocked_count"] == 1
    assert audit_payload["summary"]["coordinate_copy_count"] == 1
    assert audit_payload["summary"]["target_coordinate_copy_count"] == 1
    assert audit_payload["summary"]["first_blocked_target_id"] == "H1319"
    assert audit_payload["summary"]["first_blocker"] == "target_preflight_coordinate_copy_present"
