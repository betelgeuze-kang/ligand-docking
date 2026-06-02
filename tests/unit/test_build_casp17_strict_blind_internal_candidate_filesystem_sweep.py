import json
from pathlib import Path

from tools import build_casp17_strict_blind_internal_candidate_filesystem_sweep as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "HEADER    FIXTURE",
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_internal_candidate_filesystem_sweep_classifies_proof_boundaries(tmp_path: Path) -> None:
    _write_pdb(tmp_path / "runs" / "casp17_predictions_current" / "T9001TS.pdb")
    _write_pdb(tmp_path / "casp17" / "massivefold_external_pool_intake" / "r1" / "model.cif")
    _write_pdb(tmp_path / "casp17" / "official_archive_first_baseline_model_pool" / "T1TS001_1.pdb")
    _write_pdb(tmp_path / "data" / "native" / "native_candidate.pdb")
    _write_pdb(
        tmp_path
        / "casp17"
        / "historical_seed_top5_candidate_pools"
        / "01_hist"
        / "model_1_selected_prediction_copy.pdb"
    )
    _write_pdb(
        tmp_path
        / "casp17"
        / "historical_seed_strict_blind_replacement_evidence_dropzones"
        / "01_slot"
        / "prediction"
        / "replacement_prediction.pdb"
    )
    _write_pdb(tmp_path / "archives" / "old_internal" / "candidate.pdb")
    _write_json(
        tmp_path / "current_targets.json",
        {"rows": [{"target_id": "T9001"}]},
    )
    _write_json(
        tmp_path / "source_gate.json",
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "first_blocker": "internal_source_id_missing_or_external",
            }
        },
    )

    args = mod.parse_args(
        [
            "--scan-root",
            str(tmp_path),
            "--current-targets-json",
            str(tmp_path / "current_targets.json"),
            "--source-gate-json",
            str(tmp_path / "source_gate.json"),
            "--sample-limit",
            "2",
            "--out-json",
            str(tmp_path / "sweep.json"),
            "--out-csv",
            str(tmp_path / "sweep.csv"),
            "--out-md",
            str(tmp_path / "sweep.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    rows = {row["category_id"]: row for row in payload["rows"]}

    assert payload["summary"]["filesystem_sweep_status"] == (
        "strict_blind_filesystem_sweep_operator_review_required"
    )
    assert payload["summary"]["scanned_structure_file_count"] == 7
    assert payload["summary"]["verified_pre_native_internal_count"] == 0
    assert payload["summary"]["unknown_possible_internal_review_count"] == 1
    assert rows["current_casp17_or_review_only"]["file_count"] == 1
    assert rows["massivefold_external_baseline_only"]["file_count"] == 1
    assert rows["official_archive_baseline_only"]["file_count"] == 1
    assert rows["native_or_reference_not_prediction"]["file_count"] == 1
    assert rows["historical_seed_top5_post_native_review_only"]["file_count"] == 1
    assert rows["strict_blind_dropzone_unverified"]["file_count"] == 1
    assert rows["unknown_possible_internal_review"]["file_count"] == 1
    assert rows["unknown_possible_internal_review"]["allowed_for_strict_blind"] == "false"
    assert "source_class_chronology_no_leak_operator_clearance_unverified" in rows[
        "unknown_possible_internal_review"
    ]["blockers"]
    assert "verified pre-native internal candidates: `0`" in Path(args.out_md).read_text(
        encoding="utf-8"
    )
