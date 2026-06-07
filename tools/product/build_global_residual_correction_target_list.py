#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GPCR_FAILURE_JSON = "runs/gpcr_100k_failure_analysis_current.json"
DEFAULT_KPI_JSON = "runs/ligand_scaleup_kpi_current.json"
DEFAULT_SCALEUP_AUDIT_JSON = "runs/ligand_scaleup_100k_test_audit_current.json"
DEFAULT_GPCR_RANKING_CSV = (
    "runs/"
    "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_"
    "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_GPCR_STAGE3_CSV = (
    "runs/"
    "external_validation_2026-03-23_scaleup_100k_pilot_v2r2_"
    "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_OUT_JSON = "runs/global_residual_correction_target_list_current.json"
DEFAULT_OUT_CSV = "runs/global_residual_correction_target_list_current.csv"
DEFAULT_OUT_MD = "runs/global_residual_correction_target_list_current.md"

TARGET_FAMILY_NOTES = {
    "gpcr": "Measured 100k failure: top-rank hard-decoy intrusion under larger background.",
    "ion_channel": "Measured 100k pass: keep ranking stable while reducing expensive stage2 volume.",
    "kinase": "Measured 100k pass with large speed gap: prefer conservative correction and aggressive routing.",
    "idp": "Design-prior only: smooth branch/state features, not raw coordinates.",
    "non_kinase_enzyme": "Future-family expansion: keep the same residual shell with strict abstention until blind evidence exists.",
    "nuclear_receptor": "Future-family expansion: state/selectivity-aware correction with strong provenance guards.",
    "transporter": "Future-family expansion: membrane/state-aware routing with the strongest abstention defaults.",
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _task_row(kpi_payload: dict[str, Any], task_id: str) -> dict[str, Any]:
    for row in kpi_payload.get("rows", []):
        if str(row.get("task_id", "")).strip() == task_id:
            return row
    return {}


def _gpcr_false_positive_metrics(
    ranking_rows: list[dict[str, str]],
    stage3_rows: list[dict[str, str]],
) -> dict[str, Any]:
    stage3_by_ligand = {
        str(row.get("ligand_id", "")).strip(): row for row in stage3_rows
    }
    top20 = ranking_rows[:20]
    binders: list[dict[str, str]] = []
    decoys: list[dict[str, str]] = []
    for row in top20:
        ligand_id = str(row.get("ligand_id", "")).strip()
        merged = dict(row)
        merged.update(stage3_by_ligand.get(ligand_id, {}))
        if str(row.get("is_binder", "")).strip() == "1":
            binders.append(merged)
        else:
            decoys.append(merged)
    def avg(items: list[dict[str, str]], key: str) -> float:
        values = [_safe_float(item.get(key)) for item in items]
        return mean(values) if values else 0.0
    return {
        "top20_binder_count": len(binders),
        "top20_decoy_count": len(decoys),
        "binder_mean_binding_energy_proxy": avg(binders, "binding_energy_proxy"),
        "decoy_mean_binding_energy_proxy": avg(decoys, "binding_energy_proxy"),
        "binder_mean_contact_fraction": avg(binders, "contact_fraction"),
        "decoy_mean_contact_fraction": avg(decoys, "contact_fraction"),
        "binder_mean_min_distance_A": avg(binders, "mean_min_distance_A"),
        "decoy_mean_min_distance_A": avg(decoys, "mean_min_distance_A"),
        "binder_mean_affinity_hint": avg(binders, "ligand_affinity_hint"),
        "decoy_mean_affinity_hint": avg(decoys, "ligand_affinity_hint"),
    }


def _row(
    *,
    scope: str,
    evidence_tier: str,
    current_signal: str,
    correction_goal: str,
    candidate_signals: str,
    lagrangian_constraints: str,
    abstention_policy: str,
    commercialization_rationale: str,
    supporting_metrics: str,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "evidence_tier": evidence_tier,
        "current_signal": current_signal,
        "correction_goal": correction_goal,
        "candidate_signals": candidate_signals,
        "lagrangian_constraints": lagrangian_constraints,
        "abstention_policy": abstention_policy,
        "commercialization_rationale": commercialization_rationale,
        "supporting_metrics": supporting_metrics,
    }


def build_payload(
    gpcr_failure_payload: dict[str, Any],
    kpi_payload: dict[str, Any],
    scaleup_audit_payload: dict[str, Any],
    ranking_rows: list[dict[str, str]],
    stage3_rows: list[dict[str, str]],
) -> dict[str, Any]:
    gpcr_kpi = _task_row(kpi_payload, "gpcr_core_full")
    ion_kpi = _task_row(kpi_payload, "ion_trpv1_chembl20_full")
    kinase_kpi = _task_row(kpi_payload, "kinase_core_full")
    gpcr_metrics = _gpcr_false_positive_metrics(ranking_rows, stage3_rows)
    gpcr_summary = gpcr_failure_payload.get("summary", {})

    rows = [
        _row(
            scope="global",
            evidence_tier="cross-domain_measured_and_design_prior",
            current_signal=(
                "100k regression is execution-valid with 1 contract failure; "
                "stage2 remains the dominant cost surface across measured ligand domains."
            ),
            correction_goal=(
                "Add a domain-conditioned residual layer that improves top-k precision and "
                "reduces expensive stage2 calls without replacing the accepted base scorer."
            ),
            candidate_signals=(
                "base_score, domain_token, uncertainty, prefix_trajectory_features, "
                "energy/contact mismatch indicators, affinity-vs-contact disagreement"
            ),
            lagrangian_constraints=(
                "top-k retention, correction_norm_bound, OOD abstention penalty, "
                "high-confidence monotonicity, budget_constrained_stage2_usage"
            ),
            abstention_policy=(
                "If uncertainty is high or family support is weak, fall back to the frozen "
                "expensive path instead of forcing a correction."
            ),
            commercialization_rationale=(
                "This keeps one correction shell across GPCR/ion/kinase and future families "
                "while preserving auditability and avoiding family-specific ad hoc rules."
            ),
            supporting_metrics=(
                f"valid_completed_test_run={scaleup_audit_payload.get('summary', {}).get('valid_completed_test_run')}; "
                f"mean_stage2_share_pct={kpi_payload.get('summary', {}).get('mean_stage2_share_pct')}"
            ),
        ),
        _row(
            scope="gpcr",
            evidence_tier="measured_failure_100k",
            current_signal=TARGET_FAMILY_NOTES["gpcr"],
            correction_goal=(
                "Penalize decoys that reach favorable composite scores despite weak energy/contact "
                "support and long-distance trajectories; keep the first two true binders stable."
            ),
            candidate_signals=(
                "binding_energy_proxy, contact_fraction, mean_min_distance_A, stability_score, "
                "ligand_affinity_hint, energy_contact_mismatch, distance_affinity_mismatch"
            ),
            lagrangian_constraints=(
                "retain ranks 1-2 binders, cap correction magnitude in the top-5, "
                "penalize false-positive promotion, preserve accepted 10k gates"
            ),
            abstention_policy=(
                "Escalate to full stage2 when GPCR residual confidence is low or when energy/contact "
                "evidence is internally inconsistent."
            ),
            commercialization_rationale=(
                "GPCR is the measured failure mode at 100k, so it is the first domain where the "
                "global residual layer must prove commercial value."
            ),
            supporting_metrics=(
                f"positive_ranks={gpcr_summary.get('scaleup_positive_ranks')}; "
                f"top20_binders={gpcr_metrics['top20_binder_count']}; "
                f"decoy_mean_energy={gpcr_metrics['decoy_mean_binding_energy_proxy']:.4f}; "
                f"decoy_mean_contact={gpcr_metrics['decoy_mean_contact_fraction']:.4f}; "
                f"decoy_mean_distance_A={gpcr_metrics['decoy_mean_min_distance_A']:.4f}"
            ),
        ),
        _row(
            scope="ion_channel",
            evidence_tier="measured_pass_100k",
            current_signal=TARGET_FAMILY_NOTES["ion_channel"],
            correction_goal=(
                "Use the residual layer mainly as a cheap router and calibration guard while keeping "
                "ranking behavior close to the accepted path."
            ),
            candidate_signals=(
                "base_score, uncertainty, short-prefix trajectory statistics, "
                "contact trend stability, domain token"
            ),
            lagrangian_constraints=(
                "no pass-to-fail transition, no more than 0.02 absolute PR-AUC drift, "
                "preserve OOD gate behavior"
            ),
            abstention_policy=(
                "If top-k uncertainty is high, route candidates back to the expensive path instead "
                "of forcing a cheap acceptance."
            ),
            commercialization_rationale=(
                "Ion channel tasks are the slowest pacing items, so even conservative routing has "
                "high throughput leverage."
            ),
            supporting_metrics=(
                f"stage2_share_pct={_safe_float(ion_kpi.get('stage2_share_pct')):.2f}; "
                f"max_required_speedup={_safe_float(ion_kpi.get('max_required_speedup_to_target')):.2f}x"
            ),
        ),
        _row(
            scope="kinase",
            evidence_tier="measured_pass_100k",
            current_signal=TARGET_FAMILY_NOTES["kinase"],
            correction_goal=(
                "Prefer conservative residual correction and more aggressive cheap routing because "
                "kinase quality is already stable under 100k stress."
            ),
            candidate_signals=(
                "base_score, uncertainty, compact prefix features, domain token, "
                "trajectory budget hints"
            ),
            lagrangian_constraints=(
                "no pass-to-fail transition, preserve PR-AUC near 1.0, "
                "favor budget reduction over ranking changes"
            ),
            abstention_policy=(
                "If the residual proposes a large rank change on kinase, abstain and use the frozen "
                "expensive path."
            ),
            commercialization_rationale=(
                "Kinase has the largest measured speed gap to the current target band, so it is the "
                "best domain for proving throughput gains safely."
            ),
            supporting_metrics=(
                f"stage2_share_pct={_safe_float(kinase_kpi.get('stage2_share_pct')):.2f}; "
                f"max_required_speedup={_safe_float(kinase_kpi.get('max_required_speedup_to_target')):.2f}x"
            ),
        ),
        _row(
            scope="idp",
            evidence_tier="design_prior",
            current_signal=TARGET_FAMILY_NOTES["idp"],
            correction_goal=(
                "Stabilize branch/state posteriors and contact-derived features without hallucinating "
                "new structure or over-smoothing true disorder."
            ),
            candidate_signals=(
                "branch posterior, contact fraction time series, min-distance posterior, "
                "state confidence, trajectory volatility"
            ),
            lagrangian_constraints=(
                "feature-space smoothing only, no coordinate hallucination, "
                "penalize overconfident structural collapse"
            ),
            abstention_policy=(
                "If disorder evidence is high or state uncertainty remains broad, keep the raw branch "
                "ensemble and skip aggressive correction."
            ),
            commercialization_rationale=(
                "IDP needs cleaner operational posteriors, but the correction layer must stay honest "
                "about disorder to remain scientifically credible."
            ),
            supporting_metrics="design_prior_only",
        ),
        _row(
            scope="non_kinase_enzyme",
            evidence_tier="future_family_design_prior",
            current_signal=TARGET_FAMILY_NOTES["non_kinase_enzyme"],
            correction_goal=(
                "Carry the same global residual shell into enzyme expansion with strict uncertainty "
                "gating and no family-specific exceptions."
            ),
            candidate_signals=(
                "base_score, uncertainty, domain token, metal/pocket context flags, "
                "energy-contact consistency"
            ),
            lagrangian_constraints=(
                "family-aware abstention, conservative correction magnitude, preserve blind governance"
            ),
            abstention_policy=(
                "If enzyme support is incomplete or evidence is out-of-family, use the frozen path."
            ),
            commercialization_rationale=(
                "Passing a non-kinase enzyme family reduces the perception that the platform is "
                "kinase-friendly by construction."
            ),
            supporting_metrics="future_family_scaffold_only",
        ),
        _row(
            scope="nuclear_receptor",
            evidence_tier="future_family_design_prior",
            current_signal=TARGET_FAMILY_NOTES["nuclear_receptor"],
            correction_goal=(
                "Use the same residual shell to improve ranking and routing while keeping state/selectivity "
                "evidence explicit and provenance-safe."
            ),
            candidate_signals=(
                "base_score, uncertainty, domain token, pocket state hints, affinity-contact consistency"
            ),
            lagrangian_constraints=(
                "family-aware abstention, top-k retention, conservative correction norm"
            ),
            abstention_policy=(
                "If receptor state evidence is weak, route back to the expensive path."
            ),
            commercialization_rationale=(
                "Nuclear receptor expansion is a high-value proof that the correction shell generalizes "
                "beyond GPCR/ion without becoming family-specific."
            ),
            supporting_metrics="future_family_scaffold_only",
        ),
        _row(
            scope="transporter",
            evidence_tier="future_family_design_prior",
            current_signal=TARGET_FAMILY_NOTES["transporter"],
            correction_goal=(
                "Use the residual shell for cautious routing only until transporter-specific state "
                "evidence exists; prioritize abstention over aggressive score reshaping."
            ),
            candidate_signals=(
                "base_score, uncertainty, membrane-state hints, trajectory prefix stability, domain token"
            ),
            lagrangian_constraints=(
                "strongest abstention penalty, correction norm bound, preserve membrane-state safety"
            ),
            abstention_policy=(
                "Default to the expensive path whenever transporter state confidence is not strong."
            ),
            commercialization_rationale=(
                "Transporter success would materially widen the platform claim, but it should be added "
                "with the strongest safety defaults."
            ),
            supporting_metrics="future_family_scaffold_only",
        ),
    ]

    summary = {
        "row_count": len(rows),
        "valid_completed_100k_test_run": bool(
            scaleup_audit_payload.get("summary", {}).get("valid_completed_test_run")
        ),
        "measured_failure_scopes": ["gpcr"],
        "measured_pass_scopes": ["ion_channel", "kinase"],
        "design_prior_scopes": [
            "idp",
            "non_kinase_enzyme",
            "nuclear_receptor",
            "transporter",
        ],
        "next_required_step": (
            "Prototype the global residual layer as a constrained router first, then validate it "
            "against the GPCR 100k failure slice before promoting it into cross-domain throughput work."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Global Residual Correction Target List",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- valid_completed_100k_test_run: `{summary['valid_completed_100k_test_run']}`",
        f"- measured_failure_scopes: `{summary['measured_failure_scopes']}`",
        f"- measured_pass_scopes: `{summary['measured_pass_scopes']}`",
        f"- design_prior_scopes: `{summary['design_prior_scopes']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Correction Targets",
        "",
        "| scope | evidence_tier | correction_goal | candidate_signals | lagrangian_constraints |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['scope']} | {row['evidence_tier']} | {row['correction_goal']} | {row['candidate_signals']} | {row['lagrangian_constraints']} |"
        )
    lines.extend(
        [
            "",
            "## Scope Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['scope']}`: {row['supporting_metrics']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a commercialization-facing target list for a global residual "
            "correction layer using the current 100k GPCR failure and scale-up KPI artifacts."
        )
    )
    parser.add_argument("--gpcr-failure-json", default=DEFAULT_GPCR_FAILURE_JSON)
    parser.add_argument("--kpi-json", default=DEFAULT_KPI_JSON)
    parser.add_argument("--scaleup-audit-json", default=DEFAULT_SCALEUP_AUDIT_JSON)
    parser.add_argument("--gpcr-ranking-csv", default=DEFAULT_GPCR_RANKING_CSV)
    parser.add_argument("--gpcr-stage3-csv", default=DEFAULT_GPCR_STAGE3_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        gpcr_failure_payload=_load_json(_resolve(args.gpcr_failure_json)),
        kpi_payload=_load_json(_resolve(args.kpi_json)),
        scaleup_audit_payload=_load_json(_resolve(args.scaleup_audit_json)),
        ranking_rows=_read_csv(_resolve(args.gpcr_ranking_csv)),
        stage3_rows=_read_csv(_resolve(args.gpcr_stage3_csv)),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
