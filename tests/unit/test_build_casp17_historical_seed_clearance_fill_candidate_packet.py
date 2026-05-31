from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_clearance_fill_candidate_packet as mod


OPERATOR_FIELDS = [
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

CALIBRATION_FIELDS = [
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPERATOR_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _operator_row(rank: int, target_id: str) -> dict[str, str]:
    return {
        "seed_rank": str(rank),
        "benchmark_id": f"hist_seed_{target_id.lower()}",
        "target_id": target_id,
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


def _no_leak_row(target_id: str) -> dict[str, str]:
    return {
        "target_id": target_id,
        "dossier_md": f"casp17/no_leak/{target_id}.md",
        "operator_required_open_fields": ",".join(mod.NO_LEAK_FIELDS),
    }


def _ablation_row(target_id: str, baseline_count: int) -> dict[str, object]:
    return {
        "target_id": target_id,
        "candidate_manifest_csv": f"casp17/ablation/{target_id}.csv",
        "baseline_candidate_count": baseline_count,
        "selected_prediction_present": True,
        "native_reference_present": True,
    }


def _calibration_rows(target_id: str, status: str = "proposed") -> list[dict[str, str]]:
    rows = []
    for index, field in enumerate(CALIBRATION_FIELDS, start=1):
        rows.append(
            {
                "target_id": target_id,
                "benchmark_id": f"hist_seed_{target_id.lower()}",
                "scope": "monomer",
                "field_name": field,
                "current_value": "REQUIRED",
                "proposed_value": str(index),
                "evidence_source": f"casp17/calibration/{target_id}.csv",
                "candidate_status": status,
                "blockers": "" if status != "conflict" else "existing_value_differs_from_candidate",
            }
        )
    return rows


def _args(
    tmp_path: Path,
    operator_csv: Path,
    no_leak_json: Path,
    ablation_json: Path,
    calibration_json: Path,
) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--no-leak-dossiers-json",
        str(no_leak_json),
        "--ablation-candidates-json",
        str(ablation_json),
        "--calibration-field-candidates-json",
        str(calibration_json),
        "--field-dir",
        str(tmp_path / "field_candidates"),
        "--out-json",
        str(tmp_path / "fill.json"),
        "--out-csv",
        str(tmp_path / "fill.csv"),
        "--out-md",
        str(tmp_path / "FILL.md"),
    ]


def test_clearance_fill_packet_consolidates_calibration_and_ablation_candidates(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    no_leak_json = tmp_path / "no_leak.json"
    ablation_json = tmp_path / "ablation.json"
    calibration_json = tmp_path / "calibration.json"
    _write_csv(operator_csv, [_operator_row(1, "HIST_A"), _operator_row(2, "HIST_B")])
    _write_json(no_leak_json, {"rows": [_no_leak_row("HIST_A"), _no_leak_row("HIST_B")]})
    _write_json(ablation_json, {"rows": [_ablation_row("HIST_A", 1), _ablation_row("HIST_B", 0)]})
    _write_json(
        calibration_json,
        {"field_rows_by_target": {"HIST_A": _calibration_rows("HIST_A"), "HIST_B": _calibration_rows("HIST_B")}},
    )

    args = mod.parse_args(_args(tmp_path, operator_csv, no_leak_json, ablation_json, calibration_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_fill_candidate_status"] == "operator_provenance_required_with_field_candidates"
    assert payload["summary"]["seed_row_count"] == 2
    assert payload["summary"]["field_count"] == 34
    assert payload["summary"]["proposed_field_count"] == 13
    assert payload["summary"]["operator_required_field_count"] == 20
    assert payload["summary"]["blocked_field_count"] == 1
    assert payload["summary"]["calibration_candidate_count"] == 12
    assert payload["summary"]["ablation_candidate_count"] == 1
    assert payload["summary"]["no_leak_manual_field_count"] == 20
    assert payload["summary"]["partial_candidate_row_count"] == 2
    assert payload["summary"]["full_clearance_ready_row_count"] == 0
    assert payload["rows"][0]["clearance_fill_candidate_status"] == "partial_candidates_operator_provenance_required"
    assert payload["rows"][0]["proposed_field_count"] == 7
    assert payload["rows"][1]["clearance_fill_candidate_status"] == (
        "partial_candidates_operator_provenance_and_ablation_required"
    )
    assert payload["rows"][1]["blocked_field_count"] == 1

    field_csv = Path(payload["rows"][0]["field_candidate_csv"])
    if not field_csv.is_absolute():
        field_csv = mod.ROOT / field_csv
    with field_csv.open("r", encoding="utf-8", newline="") as handle:
        field_rows = list(csv.DictReader(handle))
    assert len(field_rows) == 17
    assert {row["lane"] for row in field_rows} == {"no_leak_provenance", "calibration", "ablation"}

    written = json.loads((tmp_path / "fill.json").read_text(encoding="utf-8"))
    assert written["summary"]["claim_boundary"].startswith("Local CASP17 historical seed clearance")


def test_clearance_fill_packet_blocks_conflicting_candidate_values(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    no_leak_json = tmp_path / "no_leak.json"
    ablation_json = tmp_path / "ablation.json"
    calibration_json = tmp_path / "calibration.json"
    _write_csv(operator_csv, [_operator_row(1, "HIST_A")])
    _write_json(no_leak_json, {"rows": [_no_leak_row("HIST_A")]})
    _write_json(ablation_json, {"rows": [_ablation_row("HIST_A", 1)]})
    _write_json(calibration_json, {"field_rows_by_target": {"HIST_A": _calibration_rows("HIST_A", "conflict")}})

    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, operator_csv, no_leak_json, ablation_json, calibration_json))
    )

    assert payload["summary"]["clearance_fill_candidate_status"] == "blocked_field_candidate_conflict"
    assert payload["summary"]["conflict_field_count"] == 6
    assert payload["rows"][0]["clearance_fill_candidate_status"] == "blocked_field_candidate_conflict"
    assert "field_candidate_conflict" in payload["rows"][0]["blockers"]


def test_clearance_fill_packet_reports_missing_inputs(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    _write_csv(operator_csv, [_operator_row(1, "HIST_A")])

    payload = mod.build_payload(
        mod.parse_args(
            _args(
                tmp_path,
                operator_csv,
                tmp_path / "missing_no_leak.json",
                tmp_path / "missing_ablation.json",
                tmp_path / "missing_calibration.json",
            )
        )
    )

    assert payload["summary"]["clearance_fill_candidate_status"] == "blocked_missing_input"
    assert "no_leak_dossiers_missing" in payload["summary"]["input_blockers"]
    assert "calibration_field_candidates_missing" in payload["summary"]["input_blockers"]
