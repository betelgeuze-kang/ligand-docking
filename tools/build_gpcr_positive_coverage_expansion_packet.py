#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CI_PACKET_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_RANK_DIAGNOSTICS_JSON = "runs/gpcr_core_rank_diagnostics_current.json"
DEFAULT_STAGE5_ROWS_CSV = "runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
DEFAULT_STAGE5_SUMMARY_JSON = "runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
DEFAULT_REFERENCE_CSV = "config/ligand_binding_reference_blind_gpcr_adrb2_chembl50_v1.csv"
DEFAULT_SPLITS_CSV = "config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv"
DEFAULT_OUT_JSON = "runs/gpcr_positive_coverage_expansion_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_positive_coverage_expansion_packet_current.md"

MINIMUM_FROZEN_POSITIVE_COUNT = 9
DEFAULT_REQUIRED_ADDITIONS = 3


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed", "green", "frozen"}


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _coverage_requirement(ci_packet: dict[str, Any]) -> dict[str, Any]:
    requirement = ci_packet.get("claim_coverage_requirement")
    if not isinstance(requirement, dict):
        requirement = {}
    summary = ci_packet.get("summary") if isinstance(ci_packet.get("summary"), dict) else {}
    observed = _as_int(
        requirement.get("observed_positive_count", summary.get("ranking_positive_count")),
        default=0,
    )
    minimum = _as_int(requirement.get("minimum_positive_count_for_claim"), default=MINIMUM_FROZEN_POSITIVE_COUNT)
    gap = max(_as_int(requirement.get("positive_coverage_gap"), default=minimum - observed), DEFAULT_REQUIRED_ADDITIONS)
    return {
        "observed_positive_count": int(observed),
        "minimum_positive_count_for_frozen_packet": int(max(minimum, MINIMUM_FROZEN_POSITIVE_COUNT)),
        "minimum_non_leaky_positive_additions": int(gap),
        "non_leaky_positive_requirement": (
            f"add at least {gap} GPCR positives with zero fit/eval leakage and no target-specific shortcut"
        ),
        "source_requirement": "curated target/ligand rows must pass leakage audit before freezing",
    }


def _required_positive_rows(count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        rows.append(
            {
                "slot": int(idx),
                "row_classification": "possible_target_ligand_row",
                "family": "gpcr",
                "target": "",
                "ligand_id": "",
                "required_label": "positive",
                "status": "needs_curated_non_leaky_source",
                "leakage_precheck_required": True,
                "required_checks": [
                    "target not present in fit roles",
                    "ligand/scaffold not present in fit roles",
                    "family-held-out assignment recorded",
                    "native/reference path available for positive coverage check",
                ],
            }
        )
    return rows


def _split_role_map(split_rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    roles: dict[tuple[str, str], str] = {}
    for row in split_rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key[0] and key[1]:
            roles[key] = _text(row.get("role"))
    return roles


def _reference_candidate_rows(
    *,
    reference_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    stage5_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    existing_positive_keys = {
        (_text(row.get("target")), _text(row.get("ligand_id")))
        for row in stage5_rows
        if _is_positive(row)
    }
    existing_fit_ligands = {
        _text(row.get("ligand_id"))
        for row in reference_rows
        if _text(row.get("target")) != "ADRB2_GPCR_BLIND" and _text(row.get("ligand_id"))
    }
    roles = _split_role_map(split_rows)
    candidates: list[dict[str, Any]] = []
    for row in reference_rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if not target or not ligand_id or not _is_positive(row):
            continue
        if (target, ligand_id) in existing_positive_keys:
            continue
        if "GPCR" not in target.upper():
            continue
        role = roles.get((target, ligand_id), _text(row.get("role")) or "unknown")
        risk_flags: list[str] = []
        if target == "ADRB2_GPCR_BLIND":
            risk_flags.append("target_specific_adrb2_bias_review_required")
        if ligand_id in existing_fit_ligands:
            risk_flags.append("ligand_seen_in_fit_role")
        if role != "far_ood_eval":
            risk_flags.append("not_far_ood_eval_role")
        candidates.append(
            {
                "row_classification": "possible_target_ligand_row",
                "target": target,
                "ligand_id": ligand_id,
                "role": role,
                "reference_binding_kcal_mol": row.get("reference_binding_kcal_mol"),
                "source": _text(row.get("source")),
                "is_binder": 1,
                "leakage_precheck_required": True,
                "family_held_out_required": True,
                "claim_policy": "coverage_candidate_only_not_router_or_platform_claim",
                "risk_flags": risk_flags,
                "risk_status": "review_required" if risk_flags else "candidate_after_leakage_audit",
            }
        )
    return candidates


def _selected_candidate_rows(
    *,
    candidate_rows: list[dict[str, Any]],
    required_count: int,
) -> list[dict[str, Any]]:
    sorted_rows = sorted(
        candidate_rows,
        key=lambda row: (
            1 if row.get("risk_flags") else 0,
            _as_float(row.get("reference_binding_kcal_mol"), 999999.0),
            _text(row.get("target")),
            _text(row.get("ligand_id")),
        ),
    )
    return [dict(row, slot=idx) for idx, row in enumerate(sorted_rows[:required_count], start=1)]


def _positive_targets_from_rows(stage5_rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in stage5_rows:
        if not _is_positive(row):
            continue
        target = _text(row.get("target")) or "unknown"
        counts[target] = counts.get(target, 0) + 1
    return dict(sorted(counts.items()))


def _diagnostic_target_counts(rank_diagnostics: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    candidates = rank_diagnostics.get("candidates")
    if not isinstance(candidates, list):
        return counts
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        top20 = candidate.get("top20_composition") if isinstance(candidate.get("top20_composition"), dict) else {}
        target_counts = top20.get("target_counts") if isinstance(top20.get("target_counts"), dict) else {}
        for target, count in target_counts.items():
            target_text = _text(target) or "unknown"
            counts[target_text] = counts.get(target_text, 0) + _as_int(count)
    return dict(sorted(counts.items()))


def _risk_rows(
    *,
    coverage: dict[str, Any],
    rank_diagnostics: dict[str, Any],
    stage5_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    positive_targets = _positive_targets_from_rows(stage5_rows)
    diagnostic_targets = _diagnostic_target_counts(rank_diagnostics)
    target_counts = positive_targets or diagnostic_targets
    rows: list[dict[str, Any]] = []
    if len(target_counts) <= 1:
        rows.append(
            {
                "row_classification": "leakage_or_target_specific_bias_risk_row",
                "risk_type": "single_target_positive_coverage",
                "severity": "blocking_for_router_platform_claim",
                "observed_positive_count": coverage["observed_positive_count"],
                "target_counts": target_counts,
                "mitigation": "freeze only after adding non-leaky positives spanning held-out GPCR family/target evidence",
            }
        )
    if coverage["observed_positive_count"] < coverage["minimum_positive_count_for_frozen_packet"]:
        rows.append(
            {
                "row_classification": "leakage_or_target_specific_bias_risk_row",
                "risk_type": "positive_count_below_frozen_minimum",
                "severity": "blocking_for_full_100k_guarded_rerun",
                "observed_positive_count": coverage["observed_positive_count"],
                "required_positive_count": coverage["minimum_positive_count_for_frozen_packet"],
                "mitigation": "do not mark full-100k eligibility until a frozen packet reaches positive_count >= 9",
            }
        )
    return rows


def _family_held_out_gate(family_scorecard: dict[str, Any]) -> dict[str, Any]:
    summary = family_scorecard.get("summary") if isinstance(family_scorecard.get("summary"), dict) else {}
    green = summary.get("scorecard_level_status") == "pass" and summary.get("acceptance_overall_pass") is not False
    return {
        "required_before_router_platform_claim": True,
        "status": "green" if green else "missing_or_not_green",
        "scorecard_level_status": summary.get("scorecard_level_status"),
        "acceptance_overall_pass": summary.get("acceptance_overall_pass"),
        "router_platform_claim_allowed": False,
        "policy": "router/platform claim remains forbidden until family-held-out scorecard is green; this packet never flips claim_promotion_allowed",
    }


def _frozen_summary(frozen_packet: dict[str, Any]) -> dict[str, Any]:
    summary = frozen_packet.get("summary") if isinstance(frozen_packet.get("summary"), dict) else {}
    source = summary if summary else frozen_packet
    frozen = any(
        _as_bool(source.get(key))
        for key in ("frozen", "packet_frozen", "is_frozen", "freeze_complete", "curation_frozen")
    )
    positive_count = _as_int(
        source.get("positive_count", source.get("ranking_positive_count", source.get("observed_positive_count"))),
        default=0,
    )
    return {"frozen": bool(frozen), "positive_count": int(positive_count)}


def _full_100k_eligibility(frozen_packet: dict[str, Any], frozen_packet_json: Path | None) -> dict[str, Any]:
    if frozen_packet_json is None or not frozen_packet:
        return {
            "eligible": False,
            "reason": "frozen_packet_missing",
            "requires_frozen_packet": True,
            "minimum_positive_count": MINIMUM_FROZEN_POSITIVE_COUNT,
            "frozen_packet_json": str(frozen_packet_json) if frozen_packet_json else None,
            "frozen": False,
            "positive_count": 0,
        }
    frozen = _frozen_summary(frozen_packet)
    if not frozen["frozen"]:
        reason = "packet_not_frozen"
        eligible = False
    elif frozen["positive_count"] < MINIMUM_FROZEN_POSITIVE_COUNT:
        reason = "positive_count_below_9"
        eligible = False
    else:
        reason = "frozen_positive_count_ready"
        eligible = True
    return {
        "eligible": bool(eligible),
        "reason": reason,
        "requires_frozen_packet": True,
        "minimum_positive_count": MINIMUM_FROZEN_POSITIVE_COUNT,
        "frozen_packet_json": str(frozen_packet_json),
        "frozen": bool(frozen["frozen"]),
        "positive_count": int(frozen["positive_count"]),
        "guardrails": [
            "guarded rerun only; no threshold relaxation",
            "family-held-out scorecard still required before router/platform claim",
            "claim_promotion_allowed remains false in this expansion packet",
        ],
    }


def build_packet(
    *,
    ci_packet_json: Path | str | None = DEFAULT_CI_PACKET_JSON,
    rank_diagnostics_json: Path | str | None = DEFAULT_RANK_DIAGNOSTICS_JSON,
    stage5_rows_csv: Path | str | None = DEFAULT_STAGE5_ROWS_CSV,
    stage5_summary_json: Path | str | None = DEFAULT_STAGE5_SUMMARY_JSON,
    reference_csv: Path | str | None = DEFAULT_REFERENCE_CSV,
    splits_csv: Path | str | None = DEFAULT_SPLITS_CSV,
    family_scorecard_json: Path | str | None = None,
    frozen_packet_json: Path | str | None = None,
) -> dict[str, Any]:
    ci_path = _resolve(ci_packet_json)
    rank_path = _resolve(rank_diagnostics_json)
    rows_path = _resolve(stage5_rows_csv)
    summary_path = _resolve(stage5_summary_json)
    reference_path = _resolve(reference_csv)
    splits_path = _resolve(splits_csv)
    scorecard_path = _resolve(family_scorecard_json)
    frozen_path = _resolve(frozen_packet_json)

    ci_packet = _read_json(ci_path)
    rank_diagnostics = _read_json(rank_path)
    stage5_rows = _read_csv(rows_path)
    stage5_summary = _read_json(summary_path)
    reference_rows = _read_csv(reference_path)
    split_rows = _read_csv(splits_path)
    family_scorecard = _read_json(scorecard_path)
    frozen_packet = _read_json(frozen_path)

    coverage = _coverage_requirement(ci_packet)
    family_gate = _family_held_out_gate(family_scorecard)
    eligibility = _full_100k_eligibility(frozen_packet, frozen_path)
    reference_candidates = _reference_candidate_rows(
        reference_rows=reference_rows,
        split_rows=split_rows,
        stage5_rows=stage5_rows,
    )
    selected_candidates = _selected_candidate_rows(
        candidate_rows=reference_candidates,
        required_count=coverage["minimum_non_leaky_positive_additions"],
    )
    risk_rows = _risk_rows(
        coverage=coverage,
        rank_diagnostics=rank_diagnostics,
        stage5_rows=stage5_rows,
    )

    return {
        "packet_type": "gpcr_positive_coverage_expansion",
        "generated_at_local": dt.datetime.now().replace(microsecond=0).isoformat(),
        "source_artifacts": {
            "ci_packet_json": str(ci_path) if ci_path else None,
            "rank_diagnostics_json": str(rank_path) if rank_path else None,
            "stage5_rows_csv": str(rows_path) if rows_path else None,
            "stage5_summary_json": str(summary_path) if summary_path else None,
            "reference_csv": str(reference_path) if reference_path else None,
            "splits_csv": str(splits_path) if splits_path else None,
            "family_scorecard_json": str(scorecard_path) if scorecard_path else None,
            "frozen_packet_json": str(frozen_path) if frozen_path else None,
        },
        "summary": {
            "status": "gpcr_positive_coverage_expansion_packet_ready",
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "observed_positive_count": coverage["observed_positive_count"],
            "minimum_positive_count_for_frozen_packet": coverage["minimum_positive_count_for_frozen_packet"],
            "minimum_non_leaky_positive_additions": coverage["minimum_non_leaky_positive_additions"],
            "reference_candidate_count": len(reference_candidates),
            "selected_candidate_count": len(selected_candidates),
            "risk_row_count": len(risk_rows),
            "family_held_out_status": family_gate["status"],
            "full_100k_guarded_rerun_eligible": eligibility["eligible"],
            "full_100k_guarded_rerun_reason": eligibility["reason"],
            "next_required_step": "Curate and freeze non-leaky GPCR positive coverage rows, then run family-held-out scorecard before any router/platform claim.",
        },
        "claim_boundaries": {
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "claim_boundary_note": "coverage expansion evidence is preparatory only until frozen coverage and family-held-out gates are green",
        },
        "coverage_requirement": coverage,
        "required_positive_addition_rows": _required_positive_rows(
            coverage["minimum_non_leaky_positive_additions"]
        ),
        "candidate_target_ligand_rows": reference_candidates,
        "selected_candidate_target_ligand_rows": selected_candidates,
        "risk_classification_rows": risk_rows,
        "family_held_out_gate": family_gate,
        "full_100k_guarded_rerun_eligibility": eligibility,
        "stage5_context": {
            "rows_available": bool(stage5_rows),
            "row_count": int(len(stage5_rows)),
            "positive_target_counts": _positive_targets_from_rows(stage5_rows),
            "summary_available": bool(stage5_summary),
            "summary_metric_keys": sorted((stage5_summary.get("metrics") or {}).keys())
            if isinstance(stage5_summary.get("metrics"), dict)
            else [],
            "reference_rows_available": bool(reference_rows),
            "reference_row_count": int(len(reference_rows)),
        },
        "next_required_actions": [
            "curate the required possible_target_ligand rows from non-leaky GPCR evidence",
            "run leakage audit and reject target/scaffold/family overlap risks",
            "freeze a positive coverage packet only after positive_count >= 9",
            "run family-held-out scorecard and keep router/platform claim blocked until green",
            "only then allow a guarded full-100k rerun; do not relax thresholds or fake pass",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["coverage_requirement"]
    family_gate = payload["family_held_out_gate"]
    eligibility = payload["full_100k_guarded_rerun_eligibility"]
    candidates = payload.get("selected_candidate_target_ligand_rows", [])
    lines = [
        "# GPCR Positive Coverage Expansion Packet",
        "",
        "## Claim Boundary",
        "- claim_promotion_allowed=false",
        "- router_claim_allowed=false",
        "- platform_claim_allowed=false",
        "- threshold_relaxation_allowed=false",
        "- fake_pass_allowed=false",
        "",
        "## Coverage Requirement",
        f"- observed_positive_count={coverage['observed_positive_count']}",
        f"- minimum_non_leaky_positive_additions={coverage['minimum_non_leaky_positive_additions']}",
        f"- minimum_positive_count_for_frozen_packet={coverage['minimum_positive_count_for_frozen_packet']}",
        "",
        "## Family-Held-Out Gate",
        f"- status={family_gate['status']}",
        "- router/platform claim forbidden until scorecard is green",
        "",
        "## Full 100k Guarded Rerun",
        f"- full_100k_guarded_rerun_eligible={str(eligibility['eligible']).lower()}",
        f"- reason={eligibility['reason']}",
        f"- frozen={str(eligibility['frozen']).lower()}",
        f"- positive_count={eligibility['positive_count']}",
        "",
        "## Row Classifications",
        "| row_classification | count | note |",
        "| --- | ---: | --- |",
        (
            f"| possible_target_ligand_row | {len(payload['required_positive_addition_rows'])} | "
            "curate and leakage-check before freezing |"
        ),
        (
            f"| leakage_or_target_specific_bias_risk_row | {len(payload['risk_classification_rows'])} | "
            "blocks router/platform claims |"
        ),
        "",
        "## Selected Candidate Rows",
        "",
        "| slot | target | ligand_id | role | risk_status | risk_flags |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    if candidates:
        for row in candidates:
            lines.append(
                "| {slot} | `{target}` | `{ligand}` | `{role}` | `{risk_status}` | {risk_flags} |".format(
                    slot=row.get("slot"),
                    target=row.get("target"),
                    ligand=row.get("ligand_id"),
                    role=row.get("role"),
                    risk_status=row.get("risk_status"),
                    risk_flags=", ".join(row.get("risk_flags", []) or []),
                )
            )
    else:
        lines.append("|  |  |  |  | `none_found` |  |")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ci-packet-json", default=DEFAULT_CI_PACKET_JSON)
    parser.add_argument("--rank-diagnostics-json", default=DEFAULT_RANK_DIAGNOSTICS_JSON)
    parser.add_argument("--stage5-rows-csv", default=DEFAULT_STAGE5_ROWS_CSV)
    parser.add_argument("--stage5-summary-json", default=DEFAULT_STAGE5_SUMMARY_JSON)
    parser.add_argument("--reference-csv", default=DEFAULT_REFERENCE_CSV)
    parser.add_argument("--splits-csv", default=DEFAULT_SPLITS_CSV)
    parser.add_argument("--family-scorecard-json", default="")
    parser.add_argument("--frozen-packet-json", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        ci_packet_json=args.ci_packet_json,
        rank_diagnostics_json=args.rank_diagnostics_json,
        stage5_rows_csv=args.stage5_rows_csv,
        stage5_summary_json=args.stage5_summary_json,
        reference_csv=args.reference_csv,
        splits_csv=args.splits_csv,
        family_scorecard_json=args.family_scorecard_json,
        frozen_packet_json=args.frozen_packet_json,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    assert out_json is not None
    assert out_md is not None
    _write_json(out_json, payload)
    _write_md(out_md, render_markdown(payload))
    print(json.dumps({"out_json": str(out_json), "out_md": str(out_md)}, indent=2))


if __name__ == "__main__":
    main()
