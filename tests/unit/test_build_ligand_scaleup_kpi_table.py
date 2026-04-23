from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_ligand_scaleup_kpi_table(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run_root = runs / "external_validation_blind_runs" / "external_validation_blind_runs_2026-03-22_biorxiv_v7r1"
    run_root.mkdir(parents=True)

    raw_gpcr = runs / "external_validation_2026-03-22_biorxiv_v7r1_set1_core_blind_gpcr_core_full_p0_n10000_r1_summary.json"
    raw_ion = runs / "external_validation_2026-03-22_biorxiv_v7r1_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n10000_r1_summary.json"

    _write_json(
        raw_gpcr,
        {
            "stages": {
                "stage2_trajectory_generation": {"duration_sec": 140.0},
                "stage3_backmapping_scoring": {"duration_sec": 14.0},
                "stage45_eval_integrity": {"duration_sec": 0.4},
                "stage5_ranking_eval": {"duration_sec": 8.8},
            }
        },
    )
    _write_json(
        raw_ion,
        {
            "stages": {
                "stage2_trajectory_generation": {"duration_sec": 525.0},
                "stage3_backmapping_scoring": {"duration_sec": 44.0},
                "stage45_eval_integrity": {"duration_sec": 0.4},
                "stage5_ranking_eval": {"duration_sec": 9.6},
            }
        },
    )

    gpcr_wrapper = runs / "external_validation_2026-03-22_biorxiv_v7r1_set1_core_blind_gpcr_core_full_summary.json"
    ion_wrapper = runs / "external_validation_2026-03-22_biorxiv_v7r1_set2_expanded_ood_ion_trpv1_chembl50_full_summary.json"
    _write_json(
        gpcr_wrapper,
        {
            "runs": [
                {
                    "summary_json": str(raw_gpcr),
                    "sla_total_latency_sec": 167.7,
                    "sla_queue_rate_stage2_rows_per_sec": 71.4,
                    "sla_queue_rate_stage3_rows_per_sec": 717.1,
                }
            ]
        },
    )
    _write_json(
        ion_wrapper,
        {
            "runs": [
                {
                    "summary_json": str(raw_ion),
                    "sla_queue_rate_stage2_rows_per_sec": 19.0,
                }
            ]
        },
    )

    top_summary = {
        "sets": [
            {
                "set_id": "set1_core_blind",
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "pass": True,
                        "raw_pass": True,
                        "profile_json": "config/gpcr.json",
                        "summary_json": str(gpcr_wrapper),
                    }
                ],
            },
            {
                "set_id": "set2_expanded_ood",
                "tasks": [
                    {
                        "task_id": "ion_trpv1_chembl50_full",
                        "domain": "ion_channel",
                        "kind": "ligand_stress",
                        "pass": True,
                        "raw_pass": True,
                        "profile_json": "config/ion.json",
                        "summary_json": str(ion_wrapper),
                    }
                ],
            },
            {
                "set_id": "set3_operational_smoke",
                "tasks": [
                    {
                        "task_id": "gpcr_smoke",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "pass": True,
                        "raw_pass": False,
                        "profile_json": "config/gpcr_smoke.json",
                        "summary_json": str(gpcr_wrapper),
                    }
                ],
            },
        ]
    }
    _write_json(run_root / "summary.json", top_summary)

    freeze_json = runs / "biorxiv_submission_freeze_current.json"
    _write_json(
        freeze_json,
        {
            "bundle_tag": "2026-03-22_biorxiv_v7r1",
            "run_root": str(run_root),
        },
    )

    out_json = runs / "ligand_scaleup_kpi_current.json"
    out_csv = runs / "ligand_scaleup_kpi_current.csv"
    out_md = runs / "ligand_scaleup_kpi_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_ligand_scaleup_kpi_table.py"),
            "--freeze-json",
            str(freeze_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["priority_counts"]["P0"] == 1
    assert payload["summary"]["slowest_task_at_1m"]["task_id"] == "ion_trpv1_chembl50_full"
    assert payload["summary"]["slowest_task_at_1m"]["timing_coverage_tier"] == "derived_partial"
    assert round(float(payload["summary"]["mean_max_required_speedup_to_target"]), 2) == 1.74
    assert payload["summary"]["coverage_summary"]["measured_total_latency_count"] == 1
    assert payload["summary"]["coverage_summary"]["stage2_queue_rate_count"] == 2
    assert payload["summary"]["coverage_summary"]["stage3_queue_rate_count"] == 1
    assert payload["summary"]["coverage_summary"]["planning_ready_count"] == 1

    domain_rollups = payload["summary"]["domain_rollups"]
    assert [row["domain"] for row in domain_rollups] == ["ion_channel", "gpcr"]
    ion_rollup = next(row for row in domain_rollups if row["domain"] == "ion_channel")
    assert ion_rollup["pacing_task_id"] == "ion_trpv1_chembl50_full"
    assert round(float(ion_rollup["max_projected_1m_wall_hr"]), 2) == 16.08
    assert round(float(ion_rollup["pacing_gap_to_target_100k_min"]), 2) == 46.50
    assert round(float(ion_rollup["pacing_required_speedup_to_target_1m"]), 2) == 1.61
    assert ion_rollup["coverage_tier_counts"]["derived_partial"] == 1

    pacing_items = payload["summary"]["pacing_items"]
    assert pacing_items[0]["task_id"] == "ion_trpv1_chembl50_full"
    assert pacing_items[0]["timing_coverage_tier"] == "derived_partial"
    assert round(float(pacing_items[0]["max_required_speedup_to_target"]), 2) == 1.93
    target_gap_items = payload["summary"]["target_gap_items"]
    assert target_gap_items[0]["task_id"] == "ion_trpv1_chembl50_full"
    assert round(float(target_gap_items[0]["required_speedup_to_target_100k"]), 2) == 1.93

    df = pd.read_csv(out_csv)
    assert set(df["task_id"]) == {"gpcr_core_full", "ion_trpv1_chembl50_full"}
    gpcr_row = df.loc[df["task_id"] == "gpcr_core_full"].iloc[0]
    assert round(float(gpcr_row["projected_1m_wall_hr"]), 2) == 4.66
    assert gpcr_row["speedpack_priority"] == "P1"
    assert str(gpcr_row["timing_coverage_tier"]) == "measured_full"
    assert round(float(gpcr_row["required_speedup_to_target_1m"]), 2) == 1.55
    ion_row = df.loc[df["task_id"] == "ion_trpv1_chembl50_full"].iloc[0]
    assert round(float(ion_row["projected_1m_wall_hr"]), 2) == 16.08
    assert str(ion_row["total_latency_source"]) == "recomputed_stage_sum"
    assert str(ion_row["timing_coverage_tier"]) == "derived_partial"
    assert int(ion_row["pacing_rank_1m"]) == 1
    assert bool(ion_row["is_domain_pacing_item"]) is True
    assert round(float(ion_row["max_required_speedup_to_target"]), 2) == 1.93

    md_text = out_md.read_text(encoding="utf-8")
    assert "Ligand Scale-Up KPI Table" in md_text
    assert "## Coverage" in md_text
    assert "## Domain Rollups" in md_text
    assert "## Pacing Items" in md_text
    assert "## Target Gap Items" in md_text
    assert "req x @100k" in md_text
    assert "gpcr_core_full" in md_text
