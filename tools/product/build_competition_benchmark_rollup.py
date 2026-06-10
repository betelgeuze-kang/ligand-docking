#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/competition_benchmark_rollup_current.json"
DEFAULT_INTAKE_CSV = "runs/cameo_official_results_operator_intake.csv"

CLAIM_BOUNDARY = (
    "Competition benchmark rollup only; aggregates local CAMEO and CASP competition-lane readiness. "
    "It does not submit predictions, fetch official pages, or mutate external state."
)

INTAKE_COLUMNS = (
    "target_id",
    "candidate_id",
    "cameo_model_rank",
    "result_source_kind",
    "result_source_url",
    "result_record_id",
    "retrieved_at_utc",
    "assessment_date",
    "lddt",
    "tm_score",
    "qs_score",
    "rmsd_A",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ensure_intake_template(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(INTAKE_COLUMNS))
            writer.writeheader()
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows)


def build_competition_benchmark_rollup(*, intake_csv: str = DEFAULT_INTAKE_CSV) -> dict[str, Any]:
    intake_path = _resolve(intake_csv)
    intake_rows = _ensure_intake_template(intake_path)

    cameo_api = _summary(_read_json("runs/cameo_api_dependency_readiness_current.json"))
    cameo_receiver = _summary(_read_json("runs/cameo_receiver_smoke_contract_current.json"))
    cameo_format = _summary(_read_json("runs/cameo_format_validation_packet_current.json"))
    cameo_selection = _summary(_read_json("runs/cameo_model1_selection_packet_current.json"))
    cameo_handoff = _summary(_read_json("runs/cameo_dry_run_handoff_packet_current.json"))
    cameo_validation = _summary(_read_json("runs/cameo_validation_readiness_gate_current.json"))
    cameo_intake_gate = _summary(_read_json("runs/cameo_official_results_intake_gate_current.json"))

    strict_blind = _read_json("casp17/casp17_strict_blind_internal_prediction_source_gate_current.json")
    strict_rows = strict_blind.get("rows", []) if isinstance(strict_blind.get("rows"), list) else []
    blocked_checks = sum(1 for row in strict_rows if isinstance(row, dict) and _text(row.get("check_status")) == "blocked")
    first_slot_ready = blocked_checks == 0 and bool(strict_rows)

    winner_bands = _read_json("casp17/casp17_historical_winner_normalized_bands_current.json")
    band_rows = winner_bands.get("rows", []) if isinstance(winner_bands.get("rows"), list) else []
    unblocked_bands = [row for row in band_rows if isinstance(row, dict) and _text(row.get("band_status")) != "blocked_input"]

    official_used = bool(cameo_validation.get("official_cameo_results_used") is True) or bool(
        cameo_intake_gate.get("official_cameo_results_used") is True
    )

    summary = {
        "packet_type": "competition_benchmark_rollup",
        "status": "competition_benchmark_rollup_ready",
        "cameo_api_dependency_ready": _text(cameo_api.get("status")) == "cameo_api_dependency_ready",
        "cameo_receiver_smoke_ready": _text(cameo_receiver.get("status")) == "cameo_receiver_smoke_ready",
        "cameo_format_validation_ready": _text(cameo_format.get("status")) == "cameo_format_validation_ready",
        "cameo_model1_selection_ready": _text(cameo_selection.get("selection_status")) == "cameo_model1_selection_ready",
        "cameo_dry_run_handoff_ready": _text(cameo_handoff.get("status")) == "cameo_handoff_dry_run_ready",
        "cameo_validation_status": _text(cameo_validation.get("status")),
        "cameo_validation_next_action": _text(cameo_validation.get("next_required_step")),
        "cameo_official_results_used": official_used,
        "cameo_official_intake_row_count": intake_rows,
        "cameo_official_next_action": "Fill official CAMEO assessment rows in cameo_official_results_operator_intake.csv"
        if not official_used
        else "",
        "casp_strict_blind_first_slot_ready": first_slot_ready,
        "casp_strict_blind_blocked_check_count": blocked_checks,
        "casp_strict_blind_next_action": "Provide verified pre-native internal prediction source for first strict-blind slot."
        if not first_slot_ready
        else "",
        "casp_winner_band_unblocked_count": len(unblocked_bands),
        "casp_winner_band_total_count": len(band_rows),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build competition benchmark rollup for Package C.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_competition_benchmark_rollup(intake_csv=args.intake_csv)
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
