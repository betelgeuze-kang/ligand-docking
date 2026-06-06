import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_batch_closure_runway as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_batch_closure_runway_prioritizes_first_slot_source_gate(tmp_path):
    queue = tmp_path / "queue.json"
    dropzones = tmp_path / "dropzones.json"
    operator = tmp_path / "operator.json"
    intake = tmp_path / "intake.json"
    first = tmp_path / "first.json"

    _write_json(
        queue,
        {
            "rows": [
                {"queue_rank": 1, "required_benchmark_id": "hist_REQUIRED_MONOMER_001", "required_target_id": "T1", "scope": "monomer"},
                {"queue_rank": 2, "required_benchmark_id": "hist_REQUIRED_MONOMER_002", "required_target_id": "T2", "scope": "monomer"},
            ]
        },
    )
    _write_json(
        dropzones,
        {
            "rows": [
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_001", "file_present_count": 0, "file_missing_count": 6},
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_002", "file_present_count": 0, "file_missing_count": 6},
            ]
        },
    )
    _write_json(
        operator,
        {
            "rows": [
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_001", "gate_status": "awaiting_operator_value"},
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_002", "gate_status": "awaiting_operator_value"},
            ]
        },
    )
    _write_json(
        intake,
        {
            "rows": [
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_001", "filled_field_count": 0, "missing_field_count": 16},
                {"required_benchmark_id": "hist_REQUIRED_MONOMER_002", "filled_field_count": 0, "missing_field_count": 16},
            ]
        },
    )
    _write_json(
        first,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_slot_closure_kit_status": "blocked_on_internal_prediction_source_gate",
                "first_blocked_step": "internal_prediction_source_gate",
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
                "kit_folder": "kit/hist_REQUIRED_MONOMER_001",
            }
        },
    )

    args = mod.parse_args(
        [
            "--queue-json",
            str(queue),
            "--dropzones-json",
            str(dropzones),
            "--operator-gate-json",
            str(operator),
            "--intake-json",
            str(intake),
            "--first-slot-closure-kit-json",
            str(first),
            "--runway-dir",
            str(tmp_path / "runway"),
            "--out-json",
            str(tmp_path / "runway.json"),
            "--out-csv",
            str(tmp_path / "runway.csv"),
            "--out-md",
            str(tmp_path / "runway.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["batch_closure_runway_status"] == "blocked_on_first_slot_internal_prediction_source"
    assert payload["summary"]["slot_count"] == 2
    assert payload["summary"]["source_gate_blocked_count"] == 1
    assert payload["summary"]["evidence_file_blocked_count"] == 1
    assert payload["summary"]["first_blocked_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert payload["rows"][0]["first_blocking_stage"] == "internal_prediction_source_gate"
    assert payload["rows"][1]["first_blocking_stage"] == "evidence_files"
    assert (tmp_path / "runway" / "batch_closure_runway.csv").exists()


def test_batch_closure_runway_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--queue-json",
            str(tmp_path / "missing_queue.json"),
            "--dropzones-json",
            str(tmp_path / "missing_dropzones.json"),
            "--operator-gate-json",
            str(tmp_path / "missing_operator.json"),
            "--intake-json",
            str(tmp_path / "missing_intake.json"),
            "--first-slot-closure-kit-json",
            str(tmp_path / "missing_first.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_closure_runway_status"] == "blocked_missing_inputs"
    assert "queue_json_missing" in payload["summary"]["input_blockers"]
