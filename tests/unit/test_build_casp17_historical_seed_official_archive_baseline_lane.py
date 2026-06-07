from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_official_archive_baseline_lane as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_official_archive_baseline_lane_separates_other_team_models_from_strict_blind(tmp_path: Path) -> None:
    source_candidates = tmp_path / "official_sources.json"
    _write_json(
        source_candidates,
        {
            "summary": {
                "strict_blind_replacement_first_slot_official_archive_source_candidates_status": (
                    "first_slot_official_archive_native_authority_candidates_available"
                )
            },
            "rows": [
                {
                    "candidate_id": "official_archive_source_001",
                    "candidate_status": "pre_native_archive_candidate_native_authority_ready_for_download",
                    "competition": "CASP16",
                    "target_id": "T1212",
                    "target_description": "Fanzor2 ternary structure protein subunit",
                    "source_category": "regular_monomer",
                    "prediction_tarball_url": "https://predictioncenter.org/download_area/CASP16/predictions/regular/T1212.tar.gz",
                    "prediction_archive_modified_at": "2024-06-03 09:22",
                    "prediction_archive_size": "24M",
                    "native_pdb_code": "9b0l",
                    "native_structure_file_url": "https://files.rcsb.org/download/9B0L.pdb",
                    "native_structure_file_format": "pdb",
                    "native_public_anchor_date": "2025-02-01",
                    "targetlist_url": "https://predictioncenter.org/casp16/targetlist.cgi?view_targets=all",
                    "targetlist_target_url": "https://predictioncenter.org/casp16/target.cgi?id=75&view=all",
                    "pre_native_by_archive_timing": "True",
                },
                {
                    "candidate_id": "official_archive_source_002",
                    "candidate_status": "pre_native_archive_candidate_native_authority_lookup_required",
                    "competition": "CASP16",
                    "target_id": "T9999",
                    "prediction_tarball_url": "https://example.invalid/T9999.tar.gz",
                    "native_structure_file_url": "",
                    "pre_native_by_archive_timing": "True",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--source-candidates-json",
            str(source_candidates),
            "--baseline-dir",
            str(tmp_path / "baseline_lane"),
            "--out-json",
            str(tmp_path / "baseline.json"),
            "--out-csv",
            str(tmp_path / "baseline.csv"),
            "--out-md",
            str(tmp_path / "BASELINE.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_baseline_lane_status"] == "official_archive_baseline_lane_ready"
    assert summary["source_candidate_count"] == 2
    assert summary["source_ready_candidate_count"] == 1
    assert summary["baseline_candidate_count"] == 1
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["strict_blind_import_blocked_count"] == 1
    assert summary["other_team_model_baseline_only_count"] == 1
    assert summary["first_target_id"] == "T1212"
    assert summary["strict_blind_intake_policy"] == "do_not_import_as_internal_prediction"

    row = payload["rows"][0]
    assert row["baseline_candidate_id"] == "official_archive_baseline_001"
    assert row["source_candidate_id"] == "official_archive_source_001"
    assert row["lane_type"] == "official_archive_baseline_replay"
    assert row["competitive_proof_eligible"] == "False"
    assert row["strict_blind_intake_policy"] == "do_not_import_as_internal_prediction"
    assert row["other_team_model_policy"] == "official_archive_models_are_baseline_only"
    assert "official_archive_baseline_001" not in row["baseline_folder"]

    written_rows = _read_csv(tmp_path / "baseline.csv")
    assert len(written_rows) == 1
    manifest = Path(row["acquisition_manifest"])
    assert manifest.is_file()
    manifest_text = manifest.read_text(encoding="utf-8")
    assert "competitive_proof_eligible: `False`" in manifest_text
    assert "curl -L" in manifest_text
    assert (tmp_path / "BASELINE.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_official_archive_baseline_lane_blocks_missing_source_candidates(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--source-candidates-json",
            str(tmp_path / "missing.json"),
            "--baseline-dir",
            str(tmp_path / "baseline_lane"),
            "--out-json",
            str(tmp_path / "baseline.json"),
            "--out-csv",
            str(tmp_path / "baseline.csv"),
            "--out-md",
            str(tmp_path / "BASELINE.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["official_archive_baseline_lane_status"] == (
        "blocked_official_archive_source_candidates_missing"
    )
    assert payload["summary"]["baseline_candidate_count"] == 0
    assert payload["summary"]["competitive_proof_eligible_count"] == 0
