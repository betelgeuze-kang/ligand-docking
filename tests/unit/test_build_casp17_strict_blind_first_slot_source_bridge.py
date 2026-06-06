import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_first_slot_source_bridge as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_first_slot_source_bridge_separates_native_authority_from_prediction(tmp_path):
    first_slot = tmp_path / "first_slot.json"
    sources = tmp_path / "sources.json"
    baseline = tmp_path / "baseline.json"
    bridge_dir = tmp_path / "bridge"

    _write_json(
        first_slot,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
            },
            "rows": [
                {"field_name": "prediction_pdb", "source_path": "dropzone/prediction/replacement_prediction.pdb"},
                {"field_name": "native_pdb", "source_path": "dropzone/native/replacement_native.pdb"},
                {"field_name": "native_authority_ref", "source_path": "dropzone/authority/native_authority.md"},
                {"field_name": "no_leak_evidence_ref", "source_path": "dropzone/no_leak/no_leak_evidence.md"},
                {"field_name": "ablation_manifest_ref", "source_path": "dropzone/ablation/ablation_manifest.csv"},
                {"field_name": "calibration_values_ref", "source_path": "dropzone/calibration/calibration_values.csv"},
            ],
        },
    )
    _write_json(
        sources,
        {
            "summary": {
                "candidate_count": 24,
                "ready_candidate_count": 24,
                "native_authority_ready_count": 24,
            },
            "rows": [
                {
                    "candidate_id": "official_archive_source_001",
                    "candidate_status": "pre_native_archive_candidate_native_authority_ready_for_download",
                    "competition": "CASP16",
                    "target_id": "T1212",
                    "native_pdb_code": "9b0l",
                    "native_structure_file_url": "https://files.rcsb.org/download/9B0L.pdb",
                    "native_pdb_url": "https://www.rcsb.org/structure/9b0l",
                    "native_public_anchor_date": "2025-02-01",
                    "native_public_anchor_url": "https://predictioncenter.org/download_area/CASP16/targets/",
                    "prediction_tarball_url": "https://predictioncenter.org/download_area/CASP16/predictions/regular/T1212.tar.gz",
                    "prediction_archive_modified_at": "2024-06-03 09:22",
                    "prediction_index_url": "https://predictioncenter.org/download_area/CASP16/predictions/regular/",
                    "source_folder": "casp17/official/001_casp16_t1212",
                }
            ],
        },
    )
    _write_json(
        baseline,
        {
            "summary": {
                "other_team_model_baseline_only_count": 24,
                "strict_blind_import_blocked_count": 24,
            }
        },
    )

    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(first_slot),
            "--official-archive-source-candidates-json",
            str(sources),
            "--official-archive-baseline-lane-json",
            str(baseline),
            "--bridge-dir",
            str(bridge_dir),
            "--out-md",
            str(tmp_path / "bridge.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_bridge_folder(args, payload)

    assert payload["summary"]["source_bridge_status"] == "first_slot_source_bridge_internal_prediction_required"
    assert payload["summary"]["official_candidate_count"] == 24
    assert payload["summary"]["native_authority_bridge_ready_count"] == 2
    assert payload["summary"]["official_prediction_baseline_only_count"] == 24
    assert payload["summary"]["internal_prediction_blocked_count"] == 1
    assert payload["summary"]["auto_apply_allowed_count"] == 0
    prediction_row = next(row for row in payload["rows"] if row["field_name"] == "prediction_pdb")
    assert prediction_row["bridge_status"] == "blocked_internal_prediction_required"
    assert prediction_row["allowed_use"] == "official_archive_prediction_tarball_baseline_only_not_internal_proof"
    native_row = next(row for row in payload["rows"] if row["field_name"] == "native_pdb")
    assert native_row["bridge_status"] == "native_authority_candidate_ready_for_operator_download"
    preview = bridge_dir / "hist_REQUIRED_MONOMER_001" / "operator_value_preview.csv"
    assert preview.exists()
    assert "CASP16_T1212" in preview.read_text(encoding="utf-8")


def test_first_slot_source_bridge_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(tmp_path / "missing_first_slot.json"),
            "--official-archive-source-candidates-json",
            str(tmp_path / "missing_sources.json"),
            "--official-archive-baseline-lane-json",
            str(tmp_path / "missing_baseline.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_bridge_status"] == "blocked_missing_inputs"
    assert "first_slot_kit_json_missing" in payload["summary"]["input_blockers"]
