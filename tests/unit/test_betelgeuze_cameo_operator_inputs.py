from __future__ import annotations

from pathlib import Path

from betelgeuze_cameo.operator_inputs import build_operator_input_validation


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "ATOM      1  N   GLY A   1      11.104  13.207   9.111  1.00 20.00           N",
                "ATOM      2  CA  GLY A   1      12.104  13.207   9.111  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_cameo_operator_inputs_ready_pending_official_results(tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "model1.pdb"
    _write_pdb(model_path)

    payload = build_operator_input_validation(
        candidates_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "source_kind": "internal_prediction",
                "validation_status": "pass",
                "model_path": str(model_path),
                "confidence_mean": "0.82",
                "continuity_fraction": "0.97",
            }
        ],
        model_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "cameo_model_rank": "1",
                "model_path": str(model_path),
            }
        ],
        official_result_rows=[],
        base_dir=tmp_path,
    )

    assert payload["summary"]["status"] == "cameo_operator_inputs_ready_pending_official_results"
    assert payload["summary"]["blocker_count"] == 0
    assert payload["summary"]["outbound_email_enabled"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert payload["summary"]["native_local_accuracy_used"] is False


def test_cameo_operator_inputs_block_placeholders_and_missing_model(tmp_path: Path) -> None:
    payload = build_operator_input_validation(
        candidates_rows=[
            {
                "target_id": "OPERATOR_FILL_CAMEO_TARGET_ID",
                "candidate_id": "OPERATOR_FILL_INTERNAL_CANDIDATE_ID",
                "source_kind": "OPERATOR_FILL_internal_prediction_OR_local_pipeline_OR_cameo_dry_run",
                "validation_status": "OPERATOR_FILL_pass_AFTER_LOCAL_QA",
                "model_path": "OPERATOR_FILL_RELATIVE_OR_ABSOLUTE_MODEL_PATH",
                "confidence_mean": "OPERATOR_FILL_0_TO_1_OR_0_TO_100",
                "continuity_fraction": "OPERATOR_FILL_0_TO_1",
            }
        ],
        model_rows=[
            {
                "target_id": "OPERATOR_FILL_CAMEO_TARGET_ID",
                "candidate_id": "OPERATOR_FILL_SELECTED_CANDIDATE_ID",
                "cameo_model_rank": "OPERATOR_FILL_1_TO_5_MODEL1_IS_1",
                "model_path": "OPERATOR_FILL_RELATIVE_OR_ABSOLUTE_PDB_OR_MMCIF_PATH",
            }
        ],
        official_result_rows=[],
        base_dir=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_cameo_operator_input_validation"
    assert any(blocker["code"] == "candidate_row_blocked" for blocker in payload["blockers"])
    assert any(blocker["code"] == "model_row_blocked" for blocker in payload["blockers"])


def test_cameo_operator_inputs_block_non_official_results_when_required(tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "model1.pdb"
    _write_pdb(model_path)

    payload = build_operator_input_validation(
        candidates_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "source_kind": "internal_prediction",
                "validation_status": "pass",
                "model_path": str(model_path),
                "confidence_mean": "0.82",
                "continuity_fraction": "0.97",
            }
        ],
        model_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "cameo_model_rank": "1",
                "model_path": str(model_path),
            }
        ],
        official_result_rows=[
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "cameo_model_rank": "1",
                "result_source_kind": "local_native",
                "lddt": "0.7",
            }
        ],
        base_dir=tmp_path,
        require_official_results=True,
    )

    assert payload["summary"]["status"] == "blocked_cameo_operator_input_validation"
    assert any("result_source_not_official_cameo" in blocker["reason"] for blocker in payload["blockers"])
