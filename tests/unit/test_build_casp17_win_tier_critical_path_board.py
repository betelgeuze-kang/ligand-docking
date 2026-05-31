import json
from pathlib import Path

from tools import build_casp17_win_tier_critical_path_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_tier_critical_path_board_marks_strict_blind_blocker(tmp_path):
    protein_library = tmp_path / "protein_library.json"
    rna_coverage = tmp_path / "rna_coverage.json"
    protein_coverage = tmp_path / "protein_coverage.json"
    metric_contract = tmp_path / "metric_contract.json"
    strict_cycle = tmp_path / "strict_cycle.json"
    first_slot = tmp_path / "first_slot.json"
    readiness = tmp_path / "readiness.json"
    clearance = tmp_path / "clearance.json"

    _write_json(
        protein_library,
        {
            "summary": {
                "completion_audit_status": "pass",
                "object_pass_count": 58,
                "object_blocked_count": 0,
                "object_folder_count": 58,
                "protein_folder_count": 19,
                "next_action": "keep protein-name folders green",
            }
        },
    )
    _write_json(
        rna_coverage,
        {
            "summary": {
                "massivefold_rna_model_selection_coverage_status": (
                    "massivefold_rna_model_selection_coverage_ready_review_only"
                ),
                "target_count": 6,
                "ready_target_count": 6,
                "partial_target_count": 0,
                "model1_candidate_count": 6,
                "top5_candidate_count": 30,
                "next_action": "use RNA picks for review-only model selection",
            }
        },
    )
    _write_json(
        protein_coverage,
        {
            "summary": {
                "protein_complex_massivefold_model_selection_coverage_status": (
                    "protein_complex_massivefold_model_selection_coverage_ready_review_only"
                ),
                "target_count": 9,
                "ready_target_count": 9,
                "partial_target_count": 0,
                "model1_candidate_count": 9,
                "top5_candidate_count": 45,
                "next_action": "use protein/complex picks for review-only model selection",
            }
        },
    )
    _write_json(
        metric_contract,
        {
            "summary": {
                "metric_surface_contract_status": "awaiting_strict_blind_evidence_files",
                "metric_surface_row_count": 440,
                "ready_metric_row_count": 0,
                "blocked_metric_row_count": 440,
                "first_blocked_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_blocked_metric": "GDT_TS",
                "next_action": "fill strict-blind prediction/native/no-leak evidence",
            }
        },
    )
    _write_json(
        strict_cycle,
        {
            "summary": {
                "strict_blind_replacement_cycle_status": "awaiting_evidence_files",
                "slot_count": 40,
                "promotion_ready_count": 0,
                "evidence_file_present_count": 0,
                "evidence_file_missing_count": 240,
                "operator_action_board_action_count": 400,
                "operator_action_board_open_value_count": 400,
                "first_blocking_stage": "evidence_dropzones",
                "first_next_action": "place strict-blind evidence files",
            }
        },
    )
    _write_json(
        first_slot,
        {
            "summary": {
                "strict_blind_replacement_first_slot_kit_status": "awaiting_first_slot_evidence_files",
                "evidence_action_count": 6,
                "evidence_ready_count": 0,
                "operator_action_count": 10,
                "operator_ready_count": 0,
                "first_open_field": "prediction_pdb",
                "first_next_action": "place prediction_pdb evidence",
                "kit_folder": "casp17/historical_seed_strict_blind_replacement_first_slot_kit/hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        readiness,
        {
            "summary": {
                "readiness_gate_status": "awaiting_identity",
                "gate_count": 6,
                "pass_count": 1,
                "blocked_gate_count": 5,
                "first_blocked_gate_id": "identity_gate",
                "first_blocked_next_action": "fill proposed_benchmark_id and proposed_target_id",
            }
        },
    )
    _write_json(
        clearance,
        {
            "summary": {
                "clearance_cycle_status": "awaiting_operator_intake",
                "stage_count": 9,
                "ready_stage_count": 1,
                "blocked_stage_count": 8,
                "operator_intake_status": "awaiting_input",
                "first_next_action": "fill native_source_pdb and no-leak provenance",
            }
        },
    )

    args = mod.parse_args(
        [
            "--protein-object-library-completion-audit-json",
            str(protein_library),
            "--massivefold-rna-model-selection-coverage-json",
            str(rna_coverage),
            "--protein-complex-massivefold-model-selection-coverage-json",
            str(protein_coverage),
            "--win-tier-metric-surface-contract-json",
            str(metric_contract),
            "--strict-blind-replacement-cycle-json",
            str(strict_cycle),
            "--strict-blind-first-slot-kit-json",
            str(first_slot),
            "--competitive-readiness-gate-json",
            str(readiness),
            "--competitive-target-identity-clearance-cycle-json",
            str(clearance),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod._write_md(args.out_md, payload)
    board_md = Path(args.out_md).read_text(encoding="utf-8")

    assert payload["summary"]["critical_path_status"] == "competitive_proof_blocked_on_strict_blind_evidence"
    assert payload["summary"]["three_d_object_ready_count"] == 58
    assert payload["summary"]["external_model_selection_ready_target_count"] == 15
    assert payload["summary"]["external_model_selection_model1_count"] == 15
    assert payload["summary"]["external_model_selection_top5_count"] == 75
    assert payload["summary"]["strict_blind_evidence_file_missing_count"] == 240
    assert payload["summary"]["strict_blind_operator_open_value_count"] == 400
    assert payload["summary"]["first_blocked_stage_id"] == "win_tier_metric_surface"
    assert "strict-blind slots ready/total: `0/40`" in board_md
    assert "external review-only model1/top5 picks: `15/75`" in board_md


def test_build_casp17_win_tier_critical_path_board_reports_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--protein-object-library-completion-audit-json",
            str(tmp_path / "missing.json"),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["critical_path_status"] == "blocked_missing_inputs"
    assert "protein_object_library_completion_audit_json_missing" in payload["summary"]["input_blockers"]
