from __future__ import annotations

from pathlib import Path

from betelgeuze_product.lit_pcba_scorecard import build_lit_pcba_scorecard


def test_lit_pcba_scorecard_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = build_lit_pcba_scorecard(
        scores_csv=tmp_path / "scores.csv",
        labels_csv=tmp_path / "labels.csv",
        score_col="binding_score",
        out_json=tmp_path / "scorecard.json",
        out_md=tmp_path / "scorecard.md",
        out_detail_csv=tmp_path / "detail.csv",
        out_topk_csv=tmp_path / "topk.csv",
        out_unique_csv=tmp_path / "unique.csv",
        run_command="python3 tools/build_lit_pcba_scorecard.py",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_lit_pcba_scorecard"
    assert summary["pass"] is False
    assert {"scores_csv_missing", "labels_csv_missing"} <= set(summary["blockers"])
    assert payload["scorecard_row"]["suite_id"] == "lit_pcba_virtual_screening"
    assert payload["scorecard_row"]["status"] == "fail"
    assert summary["external_state_mutated"] is False


def test_lit_pcba_scorecard_passes_synthetic_ranked_panel(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    labels = tmp_path / "labels.csv"
    lines_scores = ["target,ligand_id,binding_score"]
    lines_labels = ["target,ligand_id,is_binder"]
    for i in range(1, 101):
        ligand = f"L{i:03d}"
        is_binder = 1 if i <= 10 else 0
        score = float(i) if is_binder else float(i + 100)
        lines_scores.append(f"T1,{ligand},{score}")
        lines_labels.append(f"T1,{ligand},{is_binder}")
    scores.write_text("\n".join(lines_scores) + "\n", encoding="utf-8")
    labels.write_text("\n".join(lines_labels) + "\n", encoding="utf-8")

    payload = build_lit_pcba_scorecard(
        scores_csv=scores,
        labels_csv=labels,
        score_col="binding_score",
        out_json=tmp_path / "scorecard.json",
        out_md=tmp_path / "scorecard.md",
        out_detail_csv=tmp_path / "detail.csv",
        out_topk_csv=tmp_path / "topk.csv",
        out_unique_csv=tmp_path / "unique.csv",
        min_eval_unique_keys=100,
        primary_metric_threshold=1.2,
        bootstrap_n=0,
        run_command="python3 tools/build_lit_pcba_scorecard.py",
    )

    summary = payload["summary"]
    assert summary["status"] == "lit_pcba_scorecard_pass"
    assert summary["pass"] is True
    assert summary["primary_metric_value"] >= 1.2
    assert summary["eval_unique_keys"] == 100
    assert payload["scorecard_row"]["status"] == "pass"
    assert payload["scorecard_row"]["scorecard_json"].endswith("scorecard.json")
