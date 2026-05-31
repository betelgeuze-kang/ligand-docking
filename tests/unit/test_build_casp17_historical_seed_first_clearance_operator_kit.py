from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_first_clearance_operator_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _no_leak_field(name: str, current: str = "") -> dict[str, str]:
    return {
        "target_id": "HIST_CHIGNOLIN",
        "benchmark_id": "hist_seed_chignolin",
        "scope": "monomer",
        "lane": "no_leak_provenance",
        "field_name": name,
        "current_value": current,
        "proposed_value": "",
        "evidence_source": "casp17/historical_seed_no_leak_provenance_dossiers/02_hist_chignolin_no_leak_provenance.md",
        "candidate_status": "operator_required",
        "blockers": "operator_no_leak_evidence_required",
        "notes": "manual provenance field",
    }


def _proposed_field(lane: str, name: str, current: str, proposed: str) -> dict[str, str]:
    return {
        "target_id": "HIST_CHIGNOLIN",
        "benchmark_id": "hist_seed_chignolin",
        "scope": "monomer",
        "lane": lane,
        "field_name": name,
        "current_value": current,
        "proposed_value": proposed,
        "evidence_source": f"casp17/evidence/{name}.csv",
        "candidate_status": "proposed",
        "blockers": "",
        "notes": "operator review candidate",
    }


def test_first_clearance_operator_kit_splits_no_leak_intake_from_preview(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    fill_json = tmp_path / "fill.json"
    no_leak_json = tmp_path / "no_leak.json"
    operator_csv = tmp_path / "operator.csv"
    kit_dir = tmp_path / "kit"
    out_json = tmp_path / "kit.json"
    out_csv = tmp_path / "kit.csv"
    out_md = tmp_path / "kit.md"

    _write_json(
        board_json,
        {
            "rows": [
                {
                    "target_id": "HIST_CHIGNOLIN",
                    "benchmark_id": "hist_seed_chignolin",
                    "scope": "monomer",
                    "execution_status": "operator_no_leak_only",
                    "no_leak_repair_csv": str(tmp_path / "repair.csv"),
                }
            ]
        },
    )
    no_leak_fields = [
        _no_leak_field("no_leak_evidence_ref"),
        _no_leak_field("leakage_clearance", "REQUIRED_NO_LEAK_CLEARANCE"),
        _no_leak_field("operator_clearance", "REQUIRED_OPERATOR_CLEARANCE"),
        _no_leak_field("operator", "REQUIRED_OPERATOR_ID"),
        _no_leak_field("prediction_created_at", "YYYY-MM-DD"),
        _no_leak_field("native_release_date", "YYYY-MM-DD"),
        _no_leak_field("prediction_generated_before_native_release", "REQUIRED_TRUE_CONFIRMATION"),
        _no_leak_field("public_template_or_native_used_for_prediction", "REQUIRED_FALSE_CONFIRMATION"),
        _no_leak_field("other_team_model_used", "REQUIRED_FALSE_CONFIRMATION"),
        _no_leak_field("post_release_information_used", "REQUIRED_FALSE_CONFIRMATION"),
    ]
    ready_fields = [
        _proposed_field("calibration", "selected_model_rank", "REQUIRED_1_TO_5", "1"),
        _proposed_field("calibration", "best_model_rank", "REQUIRED_1_TO_5", "1"),
        _proposed_field("calibration", "selected_native_metric", "REQUIRED_NATIVE_METRIC", "100.000"),
        _proposed_field("calibration", "best_native_metric", "REQUIRED_ORACLE_METRIC", "100.000"),
        _proposed_field("calibration", "selected_score", "REQUIRED_INTERNAL_SCORE", "0.363"),
        _proposed_field("calibration", "best_score", "REQUIRED_ORACLE_SCORE", "0.363"),
        _proposed_field(
            "ablation",
            "ablation_manifest_ref",
            "REQUIRED_ABLATION_MANIFEST_REF",
            "casp17/historical_seed_ablation_candidate_manifests/02_hist_chignolin_ablation_candidates.csv",
        ),
    ]
    _write_json(fill_json, {"field_rows_by_target": {"HIST_CHIGNOLIN": no_leak_fields + ready_fields}})
    _write_csv(
        tmp_path / "repair.csv",
        [
            {
                "field_name": "prediction_created_at",
                "weak_local_candidate_value": "2026-02-19",
                "weak_local_candidate_source": "prediction_path_date",
                "notes": "weak path date only",
            },
            {
                "field_name": "native_release_date",
                "weak_local_candidate_value": "2026-02-12",
                "weak_local_candidate_source": "native_file_mtime_not_release_authority",
                "notes": "weak mtime only",
            },
        ],
        [
            "field_name",
            "weak_local_candidate_value",
            "weak_local_candidate_source",
            "notes",
        ],
    )
    operator_fieldnames = [
        "seed_rank",
        "benchmark_id",
        "target_id",
        "scope",
        "no_leak_evidence_ref",
        "leakage_clearance",
        "operator_clearance",
        "operator",
        "prediction_created_at",
        "native_release_date",
        "prediction_generated_before_native_release",
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "selected_model_rank",
        "best_model_rank",
        "selected_native_metric",
        "best_native_metric",
        "selected_score",
        "best_score",
        "ablation_manifest_ref",
    ]
    _write_csv(
        operator_csv,
        [
            {
                "seed_rank": "2",
                "benchmark_id": "hist_seed_chignolin",
                "target_id": "HIST_CHIGNOLIN",
                "scope": "monomer",
                "no_leak_evidence_ref": "",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                "selected_model_rank": "REQUIRED_1_TO_5",
                "best_model_rank": "REQUIRED_1_TO_5",
                "selected_native_metric": "REQUIRED_NATIVE_METRIC",
                "best_native_metric": "REQUIRED_ORACLE_METRIC",
                "selected_score": "REQUIRED_INTERNAL_SCORE",
                "best_score": "REQUIRED_ORACLE_SCORE",
                "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
            }
        ],
        operator_fieldnames,
    )
    args = mod.parse_args(
        [
            "--execution-board-json",
            str(board_json),
            "--fill-candidates-json",
            str(fill_json),
            "--no-leak-gap-repair-json",
            str(no_leak_json),
            "--operator-clearance-csv",
            str(operator_csv),
            "--kit-dir",
            str(kit_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["first_clearance_kit_status"] == "operator_no_leak_intake_ready"
    assert payload["summary"]["target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["no_leak_field_count"] == 10
    assert payload["summary"]["ready_candidate_field_count"] == 7
    assert payload["summary"]["calibration_candidate_count"] == 6
    assert payload["summary"]["ablation_candidate_count"] == 1
    assert payload["summary"]["weak_hint_count"] == 2
    assert payload["summary"]["promotion_preview_status"] == "waiting_on_operator_no_leak_fields"

    no_leak_rows = _read_csv(kit_dir / "HIST_CHIGNOLIN" / "no_leak_operator_intake.csv")
    assert len(no_leak_rows) == 10
    assert no_leak_rows[4]["field_name"] == "prediction_created_at"
    assert no_leak_rows[4]["weak_local_hint"] == "2026-02-19"
    assert no_leak_rows[5]["weak_local_hint_source"] == "native_file_mtime_not_release_authority"

    ready_rows = _read_csv(kit_dir / "HIST_CHIGNOLIN" / "ready_field_candidates.csv")
    assert len(ready_rows) == 7
    assert ready_rows[-1]["lane"] == "ablation"

    preview = _read_csv(kit_dir / "HIST_CHIGNOLIN" / "promotion_preview.csv")[0]
    assert preview["leakage_clearance"] == "REQUIRED_NO_LEAK_CLEARANCE"
    assert preview["prediction_created_at"] == "YYYY-MM-DD"
    assert preview["selected_model_rank"] == "1"
    assert preview["selected_score"] == "0.363"
    assert preview["ablation_manifest_ref"].endswith("02_hist_chignolin_ablation_candidates.csv")
    assert preview["promotion_preview_status"] == "waiting_on_operator_no_leak_fields"
    assert "Claim Boundary" in out_md.read_text(encoding="utf-8")
