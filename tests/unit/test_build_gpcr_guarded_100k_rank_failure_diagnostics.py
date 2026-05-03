from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_guarded_100k_rank_failure_diagnostics as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_rank_failure_packet_flags_non_adrb2_tail_positive_and_decoy_intrusion(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    _write_csv(
        rows_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.0",
                "binding_score_composite_v7": "-15.0",
                "mean_min_distance_A": "4.1",
            },
            *[
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": f"decoy_drd2_{idx}",
                    "is_binder": "0",
                    "reference_binding_kcal_mol": "-2.95",
                    "binding_score_composite_v7": str(-12.0 + idx * 0.1),
                    "mean_min_distance_A": "4.2",
                }
                for idx in range(21)
            ],
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-14.7",
                "binding_score_composite_v7": "-3.0",
                "mean_min_distance_A": "4.9",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_affinity_hint": "0.33",
                "ligand_h_donors": "2",
                "ligand_h_acceptors": "4",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.04",
                "mean_min_distance_A": "4.9",
                "contact_fraction": "0.002",
            }
        ],
    )
    _write_json(
        ci_json,
        {
            "summary": {
                "ranking_pr_auc": 0.2,
                "ranking_pr_auc_ci_low": 0.01,
                "ranking_topk_hit_rate": 0.1,
                "ranking_positive_count": 2,
                "threshold": 0.45,
            }
        },
    )
    _write_json(readiness_json, {"summary": {"blockers": ["ci_low_below_threshold"]}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["status"] == "blocked_ranking_quality"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["non_adrb2_tail_positive_count"] == 1
    assert "non_adrb2_positive_tail_rank" in payload["summary"]["blockers"]
    assert "target_internal_decoy_intrusion" in payload["summary"]["blockers"]
    drd2 = [row for row in payload["positive_rank_diagnostics"] if row["ligand_id"] == "CHEMBL301265"][0]
    assert drd2["global_rank"] == 23
    assert drd2["within_target_rank"] == 22
    assert drd2["features"]["ligand_affinity_hint"] == 0.33


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "diag.json"
    out_md = tmp_path / "diag.md"
    _write_csv(
        rows_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.0",
                "binding_score_composite_v7": "-15.0",
                "mean_min_distance_A": "4.1",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_decoy",
                "is_binder": "0",
                "reference_binding_kcal_mol": "-2.95",
                "binding_score_composite_v7": "-2.0",
                "mean_min_distance_A": "5.1",
            },
        ],
    )
    _write_csv(stage3_csv, [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "adrb2_pos"}])
    _write_json(ci_json, {"summary": {"ranking_pr_auc_ci_low": 0.5, "ranking_topk_hit_rate": 0.25}})
    _write_json(readiness_json, {"summary": {"blockers": []}})

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_guarded_100k_rank_failure_diagnostics.py"),
            "--rows-csv",
            str(rows_csv),
            "--stage3-csv",
            str(stage3_csv),
            "--ci-json",
            str(ci_json),
            "--readiness-json",
            str(readiness_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert payload["packet_type"] == "gpcr_guarded_100k_rank_failure_diagnostics"
    assert "GPCR Guarded 100k Rank Failure Diagnostics" in markdown
