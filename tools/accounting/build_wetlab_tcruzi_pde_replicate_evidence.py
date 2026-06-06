#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_ATTEMPTS_ROOT = (
    "runs/wetlab_tcruzi_pde_allatom_rescue/"
    "t_cruzi_pde/20_of_20/top_8_strict_then_near_fill/attempts"
)
DEFAULT_RUNNER_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_replicate_evidence_current.md"
DEFAULT_COHORT_MODE = "current_input_fingerprint"


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return float(value)
    except Exception:
        return None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _iqr(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    quartiles = statistics.quantiles(sorted(values), n=4, method="inclusive")
    return quartiles[2] - quartiles[0]


def _rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _score_rows(scores_csv: Path) -> list[dict[str, Any]]:
    with scores_csv.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row or {}) for row in csv.DictReader(fh)]


def _attempt_summary(scores_csv: Path) -> dict[str, Any]:
    state_json = scores_csv.with_name("allatom_rescue_state.json")
    if not state_json.exists():
        return {}
    payload = maybe_load_json(str(state_json))
    return dict(payload.get("summary", {}) or payload or {})


def _iter_observations(
    attempts_root: Path,
    *,
    cohort_mode: str,
    cohort_input_fingerprint_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []
    excluded_observations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for scores_csv in sorted(attempts_root.glob("*/allatom_rescue_scores.csv")):
        attempt_id = scores_csv.parent.name
        attempt_summary = _attempt_summary(scores_csv)
        attempt_input_fingerprint_sha256 = _text(attempt_summary.get("input_fingerprint_sha256"))
        cohort_match = (
            cohort_mode != "current_input_fingerprint"
            or not cohort_input_fingerprint_sha256
            or attempt_input_fingerprint_sha256 == cohort_input_fingerprint_sha256
        )
        for raw in _score_rows(scores_csv):
            ligand_id = _text(raw.get("ligand_id"))
            distance = _safe_float(raw.get("mean_min_distance_A"))
            if not ligand_id or distance is None or distance <= 0:
                continue
            observation = {
                "ligand_id": ligand_id,
                "attempt_id": attempt_id,
                "source_scores_csv": str(scores_csv),
                "attempt_input_fingerprint_sha256": attempt_input_fingerprint_sha256,
                "attempt_execution_mode": _text(attempt_summary.get("execution_mode")),
                "attempt_clash_relief_mode": _text(attempt_summary.get("clash_relief_mode")),
                "attempt_clash_relief_target_min_distance_A": _safe_float(
                    attempt_summary.get("clash_relief_target_min_distance_A")
                ),
                "mean_min_distance_A": distance,
                "contact_fraction": _safe_float(raw.get("contact_fraction")),
                "binding_energy_proxy": _safe_float(raw.get("binding_energy_proxy")),
                "binding_energy_mmpbsa_kcal_mol_proxy": _safe_float(
                    raw.get("binding_energy_mmpbsa_kcal_mol_proxy")
                ),
                "score_json": _text(raw.get("score_json")),
                "backmapped_pdb": _text(raw.get("backmapped_pdb")),
            }
            if not cohort_match:
                excluded_observations.append(observation)
                continue
            dedupe_key = (ligand_id, attempt_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            observations.append(observation)
    return observations, excluded_observations


def _build_replicate_rows(
    observations: list[dict[str, Any]],
    *,
    selected_threshold_A: float,
    cohort_mode: str,
) -> list[dict[str, Any]]:
    by_ligand: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        by_ligand.setdefault(_text(observation.get("ligand_id")), []).append(observation)

    rows: list[dict[str, Any]] = []
    for ligand_id, ligand_observations in by_ligand.items():
        distances = [
            float(observation["mean_min_distance_A"])
            for observation in ligand_observations
            if _safe_float(observation.get("mean_min_distance_A")) is not None
        ]
        contact_values = [
            float(observation["contact_fraction"])
            for observation in ligand_observations
            if _safe_float(observation.get("contact_fraction")) is not None
        ]
        energy_values = [
            float(observation["binding_energy_proxy"])
            for observation in ligand_observations
            if _safe_float(observation.get("binding_energy_proxy")) is not None
        ]
        pass_count = sum(1 for value in distances if 0 < value <= selected_threshold_A)
        replicate_count = len(distances)
        replicate_pass_fraction = pass_count / replicate_count if replicate_count else None
        attempt_ids = sorted({_text(observation.get("attempt_id")) for observation in ligand_observations})
        source_csvs = sorted(
            {_text(observation.get("source_scores_csv")) for observation in ligand_observations}
        )
        rows.append(
            {
                "row_kind": "tcruzi_pde_replicate_evidence_row",
                "target_id": TARGET_ID,
                "ligand_id": ligand_id,
                "replicate_count": replicate_count,
                "replicate_pass_count": pass_count,
                "replicate_pass_fraction": _rounded(replicate_pass_fraction),
                "selected_threshold_A": selected_threshold_A,
                "median_mean_min_distance_A": _rounded(_median(distances)),
                "mean_min_distance_iqr_A": _rounded(_iqr(distances)),
                "median_contact_fraction": _rounded(_median(contact_values)),
                "median_binding_energy_proxy": _rounded(_median(energy_values)),
                "replicate_evidence_source": "allatom_rescue_attempt_score_csvs",
                "replicate_evidence_policy": "count_current_input_fingerprint_attempt_observations_only",
                "replicate_evidence_cohort_mode": cohort_mode,
                "replicate_evidence_input_fingerprint_sha256": _text(
                    ligand_observations[0].get("attempt_input_fingerprint_sha256")
                ),
                "replicate_evidence_attempt_ids": attempt_ids,
                "replicate_evidence_score_csv_count": len(source_csvs),
                "replicate_evidence_score_csvs": source_csvs,
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            -int(row.get("replicate_count", 0) or 0),
            -float(row.get("replicate_pass_fraction", 0.0) or 0.0),
            float(row.get("median_mean_min_distance_A", 9999.0) or 9999.0),
            _text(row.get("ligand_id")),
        ),
    )


def build_payload(
    *,
    attempts_root: str = DEFAULT_ATTEMPTS_ROOT,
    runner_json: str = DEFAULT_RUNNER_JSON,
    selected_threshold_A: float = 2.5,
    cohort_mode: str = DEFAULT_COHORT_MODE,
) -> dict[str, Any]:
    attempts_root_path = resolve(attempts_root)
    runner_payload = maybe_load_json(runner_json)
    runner_summary = dict(runner_payload.get("summary", {}) or {})
    normalized_cohort_mode = _text(cohort_mode, DEFAULT_COHORT_MODE)
    if normalized_cohort_mode not in {"current_input_fingerprint", "all"}:
        raise SystemExit(f"unsupported PDE replicate evidence cohort mode: {cohort_mode}")
    cohort_input_fingerprint_sha256 = _text(runner_summary.get("input_fingerprint_sha256"))
    observations, excluded_observations = _iter_observations(
        attempts_root_path,
        cohort_mode=normalized_cohort_mode,
        cohort_input_fingerprint_sha256=cohort_input_fingerprint_sha256,
    )
    rows = _build_replicate_rows(
        observations,
        selected_threshold_A=selected_threshold_A,
        cohort_mode=normalized_cohort_mode,
    )
    robust_ligand_count = sum(1 for row in rows if int(row.get("replicate_count", 0) or 0) >= 3)
    strict_replicate_ligand_count = sum(
        1
        for row in rows
        if int(row.get("replicate_count", 0) or 0) >= 3
        and float(row.get("replicate_pass_fraction", 0.0) or 0.0) >= 0.60
    )
    best_row = rows[0] if rows else {}
    next_required_step = (
        "Attach this replicate-evidence artifact to the PDE all-atom review packet and let commercial v2 expose the next robustness blocker."
        if rows
        else "No PDE all-atom replicate score CSVs were found; run at least three attempt-family observations before commercial v2 readiness."
    )
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_replicate_evidence_ready",
            "target_id": TARGET_ID,
            "surface_label": "tcruzi_pde_replicate_evidence",
            "attempts_root": str(attempts_root_path),
            "source_runner_json": runner_json,
            "source_runner_attempt_id": _text(runner_summary.get("attempt_id")),
            "cohort_mode": normalized_cohort_mode,
            "cohort_input_fingerprint_sha256": cohort_input_fingerprint_sha256,
            "selected_threshold_A": selected_threshold_A,
            "observation_count": len(observations),
            "excluded_noncohort_observation_count": len(excluded_observations),
            "ligand_count": len(rows),
            "robust_ligand_count": robust_ligand_count,
            "strict_replicate_ligand_count": strict_replicate_ligand_count,
            "top_replicate_ligand_id": _text(best_row.get("ligand_id")),
            "top_replicate_count": int(best_row.get("replicate_count", 0) or 0),
            "top_replicate_pass_fraction": best_row.get("replicate_pass_fraction"),
            "top_mean_min_distance_iqr_A": best_row.get("mean_min_distance_iqr_A"),
            "evidence_policy": "current input-fingerprint attempt-family score aggregation; no pose-cluster or local-minimization claim is inferred",
            "next_required_step": next_required_step,
        },
        "structured": {
            "attempts_root": str(attempts_root_path),
            "runner_json": runner_json,
            "cohort_mode": normalized_cohort_mode,
            "cohort_input_fingerprint_sha256": cohort_input_fingerprint_sha256,
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build T. cruzi PDE all-atom replicate evidence.")
    parser.add_argument("--attempts-root", default=DEFAULT_ATTEMPTS_ROOT)
    parser.add_argument("--runner-json", default=DEFAULT_RUNNER_JSON)
    parser.add_argument("--selected-threshold-A", type=float, default=2.5)
    parser.add_argument("--cohort-mode", choices=["current_input_fingerprint", "all"], default=DEFAULT_COHORT_MODE)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        attempts_root=str(args.attempts_root),
        runner_json=str(args.runner_json),
        selected_threshold_A=float(args.selected_threshold_A),
        cohort_mode=str(args.cohort_mode),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE Replicate Evidence", payload)


if __name__ == "__main__":
    main()
