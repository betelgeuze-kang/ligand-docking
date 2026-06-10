#!/usr/bin/env python3
"""Evidence-depth audits for architecture validation package reports."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _pdb_atom_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.startswith(("ATOM  ", "HETATM"))
        )
    except OSError:
        return 0


def _warning(code: str, detail: str, *, test_ids: list[str], severity: str = "hard") -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "detail": detail,
        "test_ids": test_ids,
    }


def audit_evidence_depth() -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []

    metric = _read_json("casp17/casp17_win_tier_metric_surface_contract_current.json")
    metric_summary = _summary(metric)
    metric_rows = metric.get("rows", []) if isinstance(metric.get("rows"), list) else []
    summary_ready_metrics = _int(metric_summary.get("ready_metric_row_count"))
    row_ready_metrics = sum(1 for row in metric_rows if _text(row.get("metric_status")) == "metric_inputs_ready")
    row_blocked_metrics = sum(
        1 for row in metric_rows if _text(row.get("metric_status")) in {"awaiting_strict_blind_evidence_files", "blocked_input"}
    )
    if summary_ready_metrics > 0 and row_ready_metrics == 0 and metric_rows:
        warnings.append(
            _warning(
                "metric_surface_summary_row_mismatch",
                f"summary ready_metric_row_count={summary_ready_metrics} but row-level ready={row_ready_metrics}/{len(metric_rows)}",
                test_ids=["C-25"],
            )
        )
    if metric_rows and row_blocked_metrics == len(metric_rows) and summary_ready_metrics > 0:
        warnings.append(
            _warning(
                "metric_surface_all_rows_blocked",
                f"all {len(metric_rows)} metric surface rows blocked while summary claims readiness",
                test_ids=["C-25"],
            )
        )

    historical = _read_json("runs/casp17_historical_benchmark_packet_current.json")
    historical_summary = _summary(historical)
    historical_rows = historical.get("rows", []) if isinstance(historical.get("rows"), list) else []
    hist_status = _text(historical_summary.get("historical_benchmark_status"))
    hist_pass_rows = sum(1 for row in historical_rows if _text(row.get("benchmark_status")) == "pass")
    if hist_status == "pass" and not historical_rows:
        warnings.append(
            _warning(
                "historical_benchmark_summary_without_rows",
                "historical_benchmark_status=pass but manifest replay rows are empty",
                test_ids=["C-25"],
            )
        )
    if historical_rows and hist_pass_rows == 0 and hist_status == "pass":
        warnings.append(
            _warning(
                "historical_benchmark_no_pass_rows",
                f"historical_benchmark_status=pass but pass rows=0/{len(historical_rows)}",
                test_ids=["C-25"],
            )
        )

    sidechain = _read_json("runs/casp17_sidechain_native_benchmark_packet_current.json")
    sidechain_summary = _summary(sidechain)
    sidechain_rows = sidechain.get("rows", []) if isinstance(sidechain.get("rows"), list) else []
    summary_pass = _int(sidechain_summary.get("pass_count"))
    row_pass = sum(
        1 for row in sidechain_rows if _text(row.get("sidechain_native_status")) == "pass"
    )
    if summary_pass > 0 and sidechain_rows and row_pass == 0:
        warnings.append(
            _warning(
                "sidechain_native_summary_row_mismatch",
                f"summary pass_count={summary_pass} but row-level pass={row_pass}/{len(sidechain_rows)}",
                test_ids=["C-25"],
            )
        )

    strict = _summary(_read_json("casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"))
    gate_status = _text(strict.get("internal_prediction_source_gate_status"))
    prediction_pdb = _resolve(_text(strict.get("manifest_prediction_pdb")))
    atom_count = _pdb_atom_count(prediction_pdb)
    if gate_status == "internal_prediction_source_ready_for_first_slot_dropzone" and atom_count < 20:
        warnings.append(
            _warning(
                "strict_blind_prediction_pdb_placeholder",
                f"strict-blind gate ready but prediction PDB has only {atom_count} atom records (<20)",
                test_ids=["C-22"],
                severity="warning",
            )
        )

    intake_path = _resolve("runs/cameo_official_results_operator_intake.csv")
    intake_rows = 0
    if intake_path.exists():
        with intake_path.open("r", encoding="utf-8", newline="") as handle:
            intake_rows = sum(1 for _ in csv.DictReader(handle))
    cameo_used = _read_json("runs/competition_benchmark_rollup_current.json")
    if _summary(cameo_used).get("cameo_official_results_used") is True and intake_rows < 1:
        warnings.append(
            _warning(
                "cameo_official_results_without_intake_rows",
                "official_cameo_results_used=true but intake CSV has zero data rows",
                test_ids=["C-09", "C-11"],
            )
        )
    if intake_rows == 1:
        warnings.append(
            _warning(
                "cameo_single_operator_intake_row",
                "only one operator-provided CAMEO intake row; not multi-target official history",
                test_ids=["C-09", "C-11"],
                severity="warning",
            )
        )

    bands = _read_json("casp17/casp17_historical_winner_normalized_bands_current.json")
    band_rows = bands.get("rows", []) if isinstance(bands.get("rows"), list) else []
    unblocked = [row for row in band_rows if _text(row.get("band_status")) != "blocked_input"]
    if unblocked and (summary_ready_metrics == 0 or row_ready_metrics == 0) and metric_rows:
        warnings.append(
            _warning(
                "winner_band_without_metric_surface_rows",
                f"{len(unblocked)} winner bands unblocked without row-ready metric surface evidence",
                test_ids=["C-25"],
            )
        )

    hard_count = sum(1 for item in warnings if item["severity"] == "hard")
    warn_count = len(warnings) - hard_count
    if hard_count:
        tier = "accounting_only"
    elif warn_count:
        tier = "row_evidence_partial"
    elif historical_rows and hist_pass_rows == len(historical_rows) and row_ready_metrics > 0:
        tier = "row_evidence_complete"
    elif historical_rows and hist_pass_rows > 0:
        tier = "row_evidence_partial"
    else:
        tier = "accounting_only"

    return {
        "evidence_depth_tier": tier,
        "overclaim_warning_count": len(warnings),
        "overclaim_hard_warning_count": hard_count,
        "overclaim_soft_warning_count": warn_count,
        "overclaim_warnings": warnings,
        "metric_surface_summary_ready_metric_row_count": summary_ready_metrics,
        "metric_surface_row_ready_metric_row_count": row_ready_metrics,
        "historical_benchmark_row_pass_count": hist_pass_rows,
        "historical_benchmark_row_count": len(historical_rows),
        "sidechain_native_row_pass_count": row_pass,
        "strict_blind_prediction_atom_count": atom_count,
        "cameo_official_intake_row_count": intake_rows,
    }
