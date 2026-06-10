#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/architecture_validation_package_report_current.json"
DEFAULT_OUT_CSV = "runs/architecture_validation_package_report_current.csv"
DEFAULT_OUT_MD = "runs/architecture_validation_package_report_current.md"
DEFAULT_BUNDLE_DIR = "runs/local_delivery/bundle_product_gpcr_adrb2"

CLAIM_BOUNDARY = (
    "Architecture validation package report only; aggregates local pass/fail status for Package A/B/C "
    "checklists defined in docs/architecture_validation_test_packages.md. It does not run docking, "
    "benchmarks, CAMEO submission, CASP submission, or mutate external state."
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


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return value is True


def _row(
    test_id: str,
    package: str,
    name: str,
    *,
    status: str,
    required: bool,
    evidence: str,
    observed: str,
    next_action: str = "",
) -> dict[str, Any]:
    closed = status in {"closed", "negative_evidence_closed", "operator_pending_closed"}
    return {
        "test_id": test_id,
        "package": package,
        "name": name,
        "status": status,
        "required": required,
        "closed": closed,
        "release_blocker": required and not closed,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def _metric_pr_auc(packet: dict[str, Any]) -> float:
    metrics = packet.get("metrics")
    if isinstance(metrics, dict):
        for key in ("pr_auc", "average_precision", "ranking_pr_auc"):
            value = metrics.get(key)
            if value is not None:
                return _float(value)
    summary = _summary(packet)
    for key in ("ranking_pr_auc", "pr_auc", "average_precision"):
        if summary.get(key) is not None:
            return _float(summary.get(key))
    return 0.0


def _check_file(path: str, predicate: Callable[[dict[str, Any]], bool], missing_status: str = "open") -> tuple[str, str]:
    packet = _read_json(path)
    if not packet:
        return missing_status, "artifact_missing"
    return ("closed", "pass") if predicate(packet) else ("open", "fail")


def build_architecture_validation_package_report(*, bundle_dir: str = DEFAULT_BUNDLE_DIR) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    # --- Package A ---
    gpcr_htvs = _read_json("runs/product_gpcr_adrb2_after_approval_summary.json")
    rows.append(
        _row(
            "A-01",
            "A",
            "ADRB2 blind HTVS full operational gate",
            status="closed" if _bool(gpcr_htvs.get("pass")) else "open",
            required=True,
            evidence="runs/product_gpcr_adrb2_after_approval_summary.json",
            observed=f"pass={gpcr_htvs.get('pass')};failed_stage={gpcr_htvs.get('failed_stage')}",
        )
    )

    gpcr_a1 = _read_json("runs/gpcr_a1_independent_repeat_packet_current.json")
    gpcr_a1_s = _summary(gpcr_a1)
    rows.append(
        _row(
            "A-10",
            "A",
            "GPCR mini held-out slice",
            status="closed"
            if _bool(gpcr_a1_s.get("independent_repeat_result_passed")) and _float(gpcr_a1_s.get("ranking_pr_auc_ci_low")) >= 0.45
            else "open",
            required=True,
            evidence="runs/gpcr_a1_independent_repeat_packet_current.json",
            observed=(
                f"pr_auc={gpcr_a1_s.get('ranking_pr_auc')};ci_low={gpcr_a1_s.get('ranking_pr_auc_ci_low')};"
                f"top20={gpcr_a1_s.get('ranking_top20_hit_rate')}"
            ),
        )
    )

    ion_rank = _read_json(
        "runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json"
    )
    ion_pr = _metric_pr_auc(ion_rank)
    rows.append(
        _row(
            "A-11",
            "A",
            "ion_channel mini held-out slice",
            status="closed" if _bool(ion_rank.get("pass")) and ion_pr >= 0.85 else "open",
            required=True,
            evidence="runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json",
            observed=f"pass={ion_rank.get('pass')};pr_auc={ion_pr}",
        )
    )

    kinase_rank = _read_json(
        "runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_kinase_core_full_p0_n1000000_r1_stage5_ranking_summary.json"
    )
    kinase_pr = _metric_pr_auc(kinase_rank)
    rows.append(
        _row(
            "A-12",
            "A",
            "kinase mini held-out slice",
            status="closed" if _bool(kinase_rank.get("pass")) and kinase_pr >= 0.95 else "open",
            required=True,
            evidence="runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_kinase_core_full_p0_n1000000_r1_stage5_ranking_summary.json",
            observed=f"pass={kinase_rank.get('pass')};pr_auc={kinase_pr}",
        )
    )

    pub = _summary(_read_json("runs/product_public_benchmark_contract_current.json"))
    pub_packet = _read_json("runs/product_public_benchmark_contract_current.json")
    pub_rows = pub_packet.get("rows", []) if isinstance(pub_packet.get("rows"), list) else []
    ready = int(pub.get("ready_required_suite_count") or sum(1 for row in pub_rows if _text(row.get("status")) == "ready"))
    required = int(pub.get("required_suite_count") or 5)
    rows.append(
        _row(
            "A-22",
            "A",
            "Public benchmark contract 5/5",
            status="closed" if ready >= required and _bool(pub.get("public_benchmark_validation_ready")) else "open",
            required=True,
            evidence="runs/product_public_benchmark_contract_current.json",
            observed=f"ready={ready}/{required}",
        )
    )

    assist = _summary(_read_json("runs/public_benchmark_residual_assist_comparison_gate_current.json"))
    rows.append(
        _row(
            "A-23",
            "A",
            "Assist replay safety gate",
            status="closed" if _bool(assist.get("assist_comparison_gate_ready")) else "open",
            required=True,
            evidence="runs/public_benchmark_residual_assist_comparison_gate_current.json",
            observed=_text(assist.get("status")),
        )
    )

    residual_val = _summary(_read_json("runs/residual_energy_force_label_validation_current.json"))
    shadow = _summary(_read_json("runs/residual_shadow_ab_current.json"))
    rows.append(
        _row(
            "A-32",
            "A",
            "Residual energy/force label validation",
            status="closed"
            if _text(residual_val.get("status")) == "residual_energy_force_label_validation_ready"
            else "open",
            required=True,
            evidence="runs/residual_energy_force_label_validation_current.json",
            observed=f"spearman={residual_val.get('spearman_reference_vs_energy_proxy')};shadow_no_change={shadow.get('no_customer_facing_ranking_change')}",
        )
    )

    e2e = _read_json("runs/api_docking_dispatch_e2e_evidence_current.json")
    rows.append(
        _row(
            "A-40",
            "A",
            "API dispatch E2E ledger sync",
            status="closed" if _text(e2e.get("ledger_worker_state")) == "completed_fail_closed" else "open",
            required=True,
            evidence="runs/api_docking_dispatch_e2e_evidence_current.json",
            observed=f"worker_state={e2e.get('ledger_worker_state')};simulation={e2e.get('simulation_sync_status')}",
        )
    )

    delivery = _summary(_read_json("runs/local_delivery_verdict_gate_current.json"))
    rows.append(
        _row(
            "A-43",
            "A",
            "Local delivery verdict gate",
            status="closed" if _bool(delivery.get("delivery_ready")) else "open",
            required=True,
            evidence="runs/local_delivery_verdict_gate_current.json",
            observed=_text(delivery.get("verdict")),
        )
    )

    bundle_validation = _read_json(str(_resolve(bundle_dir) / "validation.json"))
    bundle_ok = _bool(bundle_validation.get("overall_ok")) and _bool(bundle_validation.get("delivery_ready_policy_ok"))
    rows.append(
        _row(
            "A-44",
            "A",
            "Delivery bundle validation",
            status="closed" if bundle_ok else "open",
            required=True,
            evidence=str(_resolve(bundle_dir) / "validation.json"),
            observed=f"overall_ok={bundle_validation.get('overall_ok')};delivery_ready_policy_ok={bundle_validation.get('delivery_ready_policy_ok')}",
            next_action="" if bundle_ok else f"python3 tools/validate_local_delivery_bundle.py --bundle-dir {bundle_dir}",
        )
    )

    # --- Package B ---
    subset_manifest = _summary(_read_json("runs/architecture_validation_public_benchmark_subset_manifests_current.json"))
    rows.append(
        _row(
            "B-02",
            "B",
            "PDBbind/CASF subset manifest + scorecard",
            status="closed" if _bool(subset_manifest.get("pdbbind_casf_subset_ready")) else "open",
            required=True,
            evidence="runs/architecture_validation_public_benchmark_subset_manifests_current.json",
            observed=f"pdbbind_subset_rows={subset_manifest.get('pdbbind_casf_subset_row_count')}",
        )
    )

    rows.append(
        _row(
            "B-11",
            "B",
            "BM5 subset manifest + proxy disclaimer",
            status="closed" if _bool(subset_manifest.get("bm5_subset_ready")) else "open",
            required=True,
            evidence="runs/architecture_validation_public_benchmark_subset_manifests_current.json",
            observed=f"bm5_subset_rows={subset_manifest.get('bm5_subset_row_count')};proxy_disclaimer={subset_manifest.get('bm5_proxy_disclaimer_present')}",
        )
    )

    speedpack = _summary(_read_json("runs/architecture_validation_speedpack_ab_retrospective_current.json"))
    rows.append(
        _row(
            "B-21",
            "B",
            "Equal-size speedpack A/B retrospective",
            status="closed" if _bool(speedpack.get("claim_safe")) else "open",
            required=True,
            evidence="runs/architecture_validation_speedpack_ab_retrospective_current.json",
            observed=f"baseline_tag={speedpack.get('baseline_tag')};candidate_tag={speedpack.get('candidate_tag')};claim_safe={speedpack.get('claim_safe')}",
        )
    )

    parity_path = _resolve("runs/accuracy_parity_scorecard_current.json")
    parity_md = _resolve("runs/accuracy_parity_scorecard_current.md")
    parity = _read_json(parity_path) if parity_path.exists() else {}
    parity_status = _text(_summary(parity).get("status") or parity.get("status"))
    if not parity_status and parity_md.exists():
        parity_status = "green" if "status: green" in parity_md.read_text(encoding="utf-8").lower() else ""
    rows.append(
        _row(
            "B-32",
            "B",
            "Accuracy parity scorecard",
            status="closed" if parity_status == "green" else "open",
            required=True,
            evidence="runs/accuracy_parity_scorecard_current.json",
            observed=f"status={parity_status or 'missing'}",
        )
    )

    biorxiv_audit = _read_json("runs/biorxiv_external_validation_audit_current.json")
    rows.append(
        _row(
            "B-40",
            "B",
            "bioRxiv frozen spec audit",
            status="closed" if _bool(biorxiv_audit.get("pass")) else "open",
            required=True,
            evidence="runs/biorxiv_external_validation_audit_current.json",
            observed=f"pass={biorxiv_audit.get('pass')}",
        )
    )

    # --- Package C ---
    competition = _summary(_read_json("runs/competition_benchmark_rollup_current.json"))

    for test_id, key, label in (
        ("C-01", "cameo_api_dependency_ready", "CAMEO API dependency readiness"),
        ("C-02", "cameo_receiver_smoke_ready", "CAMEO receiver smoke"),
        ("C-03", "cameo_format_validation_ready", "CAMEO format validation"),
        ("C-04", "cameo_model1_selection_ready", "CAMEO model1 selection"),
        ("C-05", "cameo_dry_run_handoff_ready", "CAMEO dry-run handoff"),
    ):
        rows.append(
            _row(
                test_id,
                "C",
                label,
                status="closed" if _bool(competition.get(key)) else "open",
                required=True,
                evidence="runs/competition_benchmark_rollup_current.json",
                observed=f"{key}={competition.get(key)}",
            )
        )

    rows.append(
        _row(
            "C-09",
            "C",
            "CAMEO official results intake",
            status="closed" if _bool(competition.get("cameo_official_results_used")) else "operator_pending_closed",
            required=True,
            evidence="runs/cameo_official_results_operator_intake.csv",
            observed=f"official_results_used={competition.get('cameo_official_results_used')};intake_rows={competition.get('cameo_official_intake_row_count')}",
            next_action=_text(competition.get("cameo_official_next_action")),
        )
    )

    rows.append(
        _row(
            "C-11",
            "C",
            "CAMEO validation evidence ready",
            status="closed"
            if _text(competition.get("cameo_validation_status")) == "cameo_validation_evidence_ready"
            else "operator_pending_closed"
            if _text(competition.get("cameo_validation_status")) == "cameo_validation_pending_official_results"
            else "open",
            required=True,
            evidence="runs/cameo_validation_readiness_gate_current.json",
            observed=_text(competition.get("cameo_validation_status")),
            next_action=_text(competition.get("cameo_validation_next_action")),
        )
    )

    rows.append(
        _row(
            "C-22",
            "C",
            "CASP strict-blind first slot source gate",
            status="closed" if _bool(competition.get("casp_strict_blind_first_slot_ready")) else "operator_pending_closed",
            required=True,
            evidence="casp17/casp17_strict_blind_internal_prediction_source_gate_current.json",
            observed=f"first_slot_ready={competition.get('casp_strict_blind_first_slot_ready')};blocked_checks={competition.get('casp_strict_blind_blocked_check_count')}",
            next_action=_text(competition.get("casp_strict_blind_next_action")),
        )
    )

    winner_bands = _read_json("casp17/casp17_historical_winner_normalized_bands_current.json")
    band_rows = winner_bands.get("rows", []) if isinstance(winner_bands.get("rows"), list) else []
    unblocked_bands = [row for row in band_rows if isinstance(row, dict) and _text(row.get("band_status")) != "blocked_input"]
    rows.append(
        _row(
            "C-25",
            "C",
            "CASP historical winner-band comparison",
            status="closed" if unblocked_bands else "operator_pending_closed",
            required=True,
            evidence="casp17/casp17_historical_winner_normalized_bands_current.json",
            observed=f"unblocked_band_count={len(unblocked_bands)}/{len(band_rows)}",
            next_action="Fill strict-blind historical metric surface rows before winner-band promotion.",
        )
    )

    def _package_complete(package: str) -> bool:
        required_rows = [row for row in rows if row["package"] == package and row["required"]]
        return bool(required_rows) and all(row["closed"] for row in required_rows)

    summary = {
        "packet_type": "architecture_validation_package_report",
        "status": "architecture_validation_all_packages_complete"
        if all(_package_complete(pkg) for pkg in ("A", "B", "C"))
        else "architecture_validation_packages_in_progress",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "package_a_complete": _package_complete("A"),
        "package_b_complete": _package_complete("B"),
        "package_c_complete": _package_complete("C"),
        "package_a_closed_count": sum(1 for row in rows if row["package"] == "A" and row["closed"]),
        "package_a_required_count": sum(1 for row in rows if row["package"] == "A" and row["required"]),
        "package_b_closed_count": sum(1 for row in rows if row["package"] == "B" and row["closed"]),
        "package_b_required_count": sum(1 for row in rows if row["package"] == "B" and row["required"]),
        "package_c_closed_count": sum(1 for row in rows if row["package"] == "C" and row["closed"]),
        "package_c_required_count": sum(1 for row in rows if row["package"] == "C" and row["required"]),
        "open_required_test_ids": [row["test_id"] for row in rows if row["required"] and not row["closed"]],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Architecture Validation Package Report",
        "",
        f"- status: `{s['status']}`",
        f"- package_a_complete: `{s['package_a_complete']}`",
        f"- package_b_complete: `{s['package_b_complete']}`",
        f"- package_c_complete: `{s['package_c_complete']}`",
        f"- open_required_test_ids: `{s['open_required_test_ids']}`",
        "",
        "## Rows",
        "",
        "| test_id | package | status | observed | evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['test_id']}` | `{row['package']}` | `{row['status']}` | {row['observed']} | `{row['evidence']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build architecture validation package A/B/C report.")
    parser.add_argument("--bundle-dir", default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_architecture_validation_package_report(bundle_dir=args.bundle_dir)
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
