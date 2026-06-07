from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_trajectory_sla_contract as mod


def _write_sla(path: Path, family: str, *, prod: bool = True, rows: int = 10000) -> None:
    path.write_text(
        json.dumps(
            {
                "family": family,
                "queue_rows": rows,
                "total_latency_sec": 10.0,
                "gate_failure_rate_proxy": 0.0,
                "traj_prod": {"enabled": prod},
                "traj_stage2_engine_prod_mode": prod,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _rocm_baseline(*, prod_profile: bool = False) -> dict[str, object]:
    return {
        "summary": {
            "status": "product_end_to_end_rocm_benchmark_ready",
            "benchmark_ready": True,
            "family": "gpcr",
            "target_id": "ADRB2_GPCR_BLIND",
            "production_trajectory_profile_enabled": prod_profile,
        }
    }


def test_product_trajectory_sla_contract_ready_across_required_families(tmp_path: Path) -> None:
    _write_sla(tmp_path / "gpcr_sla_summary.json", "gpcr")
    _write_sla(tmp_path / "ion_trpv1_sla_summary.json", "ion_channel")
    _write_sla(tmp_path / "kinase_sla_summary.json", "kinase")

    payload = mod.build_product_trajectory_sla_contract(
        runs_dir=str(tmp_path),
        rocm_benchmark_packet=_rocm_baseline(),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_trajectory_sla_contract_ready"
    assert summary["production_trajectory_sla_ready"] is True
    assert summary["ready_run_count"] == 3
    assert summary["qualified_ready_run_count"] == 3
    assert summary["ready_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["qualified_ready_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["minimum_ready_rows_per_family"] == 10000
    assert summary["sla_claim_tier"] == "restricted_family_sla"
    assert summary["restricted_family_sla_allowed"] is True
    assert summary["broad_platform_sla_allowed"] is False
    assert summary["current_rocm_baseline_ready"] is True
    assert summary["current_rocm_baseline_family"] == "gpcr"
    assert summary["current_rocm_baseline_target_id"] == "ADRB2_GPCR_BLIND"
    assert summary["current_rocm_baseline_production_trajectory_profile_enabled"] is False
    assert summary["current_rocm_baseline_claim_scope"] == "single_target_gpcr_baseline"
    assert summary["current_rocm_baseline_supports_restricted_family_sla"] is False
    assert summary["current_rocm_baseline_supports_broad_platform_sla"] is False
    assert summary["customer_sla_disclosure_ready"] is True
    assert summary["allowed_sla_claims"] == [
        "restricted_family_trajectory_profile_sla",
        "single_target_gpcr_rocm_baseline",
    ]
    assert "broad_platform_sla" in summary["blocked_sla_claims"]
    assert "current_rocm_baseline_production_trajectory_profile_claim" in summary["blocked_sla_claims"]
    assert summary["general_platform_sla_allowed"] is False
    assert summary["customer_sla_disclosure_card"]["broad_platform_sla_allowed"] is False
    assert summary["customer_sla_disclosure_card"]["current_rocm_baseline_scope"] == (
        "single_target_gpcr_baseline"
    )
    assert "must not be described as a broad platform SLA" in summary[
        "customer_sla_disclosure_card"
    ]["customer_safe_summary"]
    assert summary["restricted_sla_backed_by_historical_profile_artifacts"] is True
    assert summary["rocm_baseline_profile_gap_acknowledged"] is True
    assert all(row["qualified_for_restricted_family_sla"] for row in summary["family_sla_matrix"])


def test_product_trajectory_sla_contract_blocks_missing_family(tmp_path: Path) -> None:
    _write_sla(tmp_path / "gpcr_sla_summary.json", "gpcr")
    _write_sla(tmp_path / "ion_trpv1_sla_summary.json", "ion_channel")

    payload = mod.build_product_trajectory_sla_contract(
        runs_dir=str(tmp_path),
        rocm_benchmark_packet=_rocm_baseline(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_trajectory_sla_contract"
    assert summary["production_trajectory_sla_ready"] is False
    assert summary["missing_families"] == ["kinase"]
    assert summary["missing_qualified_families"] == ["kinase"]


def test_product_trajectory_sla_contract_blocks_smoke_only_family(tmp_path: Path) -> None:
    _write_sla(tmp_path / "gpcr_sla_summary.json", "gpcr")
    _write_sla(tmp_path / "ion_trpv1_sla_summary.json", "ion_channel")
    _write_sla(tmp_path / "kinase_smoke_sla_summary.json", "kinase", rows=128)

    payload = mod.build_product_trajectory_sla_contract(
        runs_dir=str(tmp_path),
        rocm_benchmark_packet=_rocm_baseline(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_trajectory_sla_contract"
    assert summary["ready_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["qualified_ready_families"] == ["gpcr", "ion_channel"]
    assert summary["missing_qualified_families"] == ["kinase"]
    kinase = next(row for row in payload["rows"] if row["family"] == "kinase")
    assert kinase["ready_for_sla"] is True
    assert kinase["family_sla_qualified"] is False
    assert "below_minimum_rows_for_family_sla" in kinase["blockers"]


def test_product_trajectory_sla_contract_cli_writes_outputs(tmp_path: Path) -> None:
    _write_sla(tmp_path / "gpcr_sla_summary.json", "gpcr")
    out_json = tmp_path / "sla.json"
    out_csv = tmp_path / "sla.csv"
    out_md = tmp_path / "sla.md"

    mod.main(
        [
            "--runs-dir",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["candidate_artifact_count"] == 1
    assert "source_artifact" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Product Trajectory SLA Contract" in md
    assert "minimum_ready_rows_per_family" in md
    assert "current_rocm_baseline_production_trajectory_profile_enabled" in md
    assert "customer_sla_disclosure_ready" in md
