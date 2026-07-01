from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_broad_local_candidate_audit as mod


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target", "ligand_id", "is_binder", "score_value", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _green_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target, prefix in (
        ("CHEMBL217_DRD2_HUMAN", "DRD2"),
        ("CHEMBL224_HTR2A_HUMAN", "HTR2A"),
        ("CHEMBL233_OPRM1_HUMAN", "OPRM1"),
    ):
        rows.extend(
            [
                {
                    "target": target,
                    "ligand_id": f"{prefix}_POS_A",
                    "is_binder": 1,
                    "score_value": -10.0,
                    "mean_min_distance_A": 4.0,
                },
                {
                    "target": target,
                    "ligand_id": f"{prefix}_POS_B",
                    "is_binder": 1,
                    "score_value": -9.8,
                    "mean_min_distance_A": 4.1,
                },
                {
                    "target": target,
                    "ligand_id": f"{prefix}_DECOY_A",
                    "is_binder": 0,
                    "score_value": -1.0,
                    "mean_min_distance_A": 5.0,
                },
                {
                    "target": target,
                    "ligand_id": f"{prefix}_DECOY_B",
                    "is_binder": 0,
                    "score_value": -0.5,
                    "mean_min_distance_A": 5.2,
                },
            ]
        )
    return rows


def _write_summary(path: Path, *, ci_low: float = 0.76, top20: float = 0.6) -> None:
    path.write_text(
        json.dumps(
            {
                "lower_better": True,
                "metrics_ci_unique": {"pr_auc": {"low": ci_low}},
                "topk_unique": [{"k": 20, "hit_rate": top20}],
            }
        ),
        encoding="utf-8",
    )


def test_broad_audit_can_find_direct_metric_closure_candidate_without_summary(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_direct_eval_unique_current.csv"
    _write_rows(candidate, _green_rows())

    payload = mod.build_gpcr_hard_decoy_broad_local_candidate_audit(
        candidate_globs=[str(tmp_path / "*.csv")],
        bootstrap_n=32,
        bootstrap_seed=7,
    )

    assert payload["summary"]["status"] == "gpcr_hard_decoy_broad_local_candidate_audit_closure_candidate_ready"
    assert payload["summary"]["gpcr_actual_closure_ready"] is True
    assert payload["summary"]["closure_candidate_count"] == 1
    candidate_payload = payload["candidates"][0]
    assert candidate_payload["metric_gate_ready"] is True
    assert candidate_payload["ranking_pr_auc_ci_low_source"] == "direct_bootstrap_ready"
    assert candidate_payload["target_green_count"] == 3


def test_broad_audit_blocks_when_summary_metrics_pass_but_required_target_fails(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_summary_eval_unique_current.csv"
    summary = tmp_path / "gpcr_summary_eval_current.json"
    rows = _green_rows()
    rows[0]["score_value"] = -10.0
    rows[0]["mean_min_distance_A"] = 5.0
    rows[2]["score_value"] = -11.0
    rows[2]["mean_min_distance_A"] = 4.0
    _write_rows(candidate, rows)
    _write_summary(summary)

    payload = mod.build_gpcr_hard_decoy_broad_local_candidate_audit(
        candidate_globs=[str(tmp_path / "*eval_unique_current.csv")],
        bootstrap_n=0,
    )

    assert payload["summary"]["status"] == "blocked_gpcr_hard_decoy_broad_local_candidate_audit_no_closure_candidate"
    assert payload["summary"]["gpcr_actual_closure_ready"] is False
    candidate_payload = payload["candidates"][0]
    assert candidate_payload["metric_gate_ready"] is True
    assert candidate_payload["ranking_pr_auc_ci_low_source"] == "summary_json"
    assert candidate_payload["target_green_count"] == 2
    drd2 = next(row for row in candidate_payload["targets"] if row["target_id"] == "DRD2")
    assert "decoys_above_positive_present" in drd2["blockers"]
    assert "decoy_over_anchored_vs_positive" in drd2["blockers"]


def test_main_writes_broad_audit_artifacts(tmp_path: Path) -> None:
    candidate = tmp_path / "gpcr_summary_eval_unique_current.csv"
    summary = tmp_path / "gpcr_summary_eval_current.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    rows = _green_rows()
    rows[0]["score_value"] = -10.0
    rows[2]["score_value"] = -11.0
    _write_rows(candidate, rows)
    _write_summary(summary)

    rc = mod.main(
        [
            "--candidate-glob",
            str(tmp_path / "*eval_unique_current.csv"),
            "--bootstrap-n",
            "0",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["candidate_count"] == 1
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Broad Local Candidate Audit")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["target_id"] for row in rows] == ["DRD2", "HTR2A", "OPRM1"]
