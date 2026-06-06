import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_internal_prediction_source_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_internal_prediction_source_audit_blocks_external_baseline(tmp_path):
    first_slot = tmp_path / "first_slot.json"
    local = tmp_path / "local.json"
    route = tmp_path / "route.json"
    baseline = tmp_path / "baseline.json"
    bridge = tmp_path / "bridge.json"
    audit_dir = tmp_path / "audit"

    _write_json(
        first_slot,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "first_open_field": "prediction_pdb",
                "first_open_status": "open_missing_file",
                "first_next_action": "place prediction_pdb evidence at dropzone/replacement_prediction.pdb",
                "evidence_open_count": 6,
            }
        },
    )
    _write_json(
        local,
        {
            "summary": {
                "candidate_count": 17,
                "strict_blind_eligible_count": 0,
                "prediction_present_count": 15,
            }
        },
    )
    _write_json(
        route,
        {
            "summary": {
                "strict_blind_replacement_first_slot_source_route_board_status": (
                    "first_slot_requires_pre_native_monomer_source_or_replacement"
                ),
                "route_count": 17,
                "allowed_for_first_slot_count": 0,
                "first_external_next_action": "source a pre-native prediction archive",
            }
        },
    )
    _write_json(
        baseline,
        {
            "summary": {
                "baseline_candidate_count": 24,
                "ready_count": 24,
                "strict_blind_import_blocked_count": 24,
            }
        },
    )
    _write_json(
        bridge,
        {
            "summary": {
                "source_bridge_status": "first_slot_source_bridge_internal_prediction_required",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "bridge_row_count": 9,
                "native_authority_bridge_ready_count": 2,
                "operator_only_field_count": 6,
                "internal_prediction_blocked_count": 1,
                "first_next_action": "provide a pre-native internal prediction PDB",
            }
        },
    )

    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(first_slot),
            "--local-candidate-board-json",
            str(local),
            "--source-route-board-json",
            str(route),
            "--official-archive-baseline-lane-json",
            str(baseline),
            "--source-bridge-json",
            str(bridge),
            "--audit-dir",
            str(audit_dir),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["internal_prediction_source_audit_status"] == "internal_prediction_source_missing_for_first_slot"
    assert summary["allowed_internal_source_count"] == 0
    assert summary["official_strict_blind_blocked_count"] == 24
    assert summary["internal_prediction_blocked_count"] == 1
    official_row = next(row for row in payload["rows"] if row["source_id"] == "official_archive_prediction_tarballs")
    assert official_row["source_status"] == "blocked_external_other_team_baseline_only"
    assert official_row["allowed_for_strict_blind"] == "false"
    template = audit_dir / "hist_REQUIRED_MONOMER_001" / "internal_prediction_source_manifest_template.csv"
    assert template.exists()
    assert "prediction_pdb" in template.read_text(encoding="utf-8")


def test_internal_prediction_source_audit_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(tmp_path / "missing_first_slot.json"),
            "--local-candidate-board-json",
            str(tmp_path / "missing_local.json"),
            "--source-route-board-json",
            str(tmp_path / "missing_route.json"),
            "--official-archive-baseline-lane-json",
            str(tmp_path / "missing_baseline.json"),
            "--source-bridge-json",
            str(tmp_path / "missing_bridge.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["internal_prediction_source_audit_status"] == "blocked_missing_inputs"
    assert "first_slot_kit_json_missing" in payload["summary"]["input_blockers"]
