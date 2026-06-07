from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools.gpcr_replay import build_gpcr_drd2_hard_decoy_penalty_envelope as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_penalty_envelope_blocks_when_valid_anchor_decoy_remains_above_positive(tmp_path: Path) -> None:
    rows_csv = tmp_path / "slice_rows.csv"
    _write_csv(
        rows_csv,
        [
            {
                "ligand_id": "invalid_decoy",
                "is_positive": "False",
                "base_score": "-10.0",
                "label_free_penalty_pressure": "2.0",
                "label_free_support_pressure": "0.0",
                "slice_label_text": "invalid_close_overanchor_no_basic",
            },
            {
                "ligand_id": "valid_anchor_decoy",
                "is_positive": "False",
                "base_score": "-9.0",
                "label_free_penalty_pressure": "0.0",
                "label_free_support_pressure": "0.8",
                "slice_label_text": "valid_anchor_challenge",
            },
            {
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "base_score": "-1.0",
                "label_free_penalty_pressure": "0.0",
                "label_free_support_pressure": "0.8",
                "slice_label_text": "positive_repaired_anchor_window",
            },
        ],
    )

    payload, grid_rows = mod.build_envelope(
        rows_csv=rows_csv,
        grid="0,5,10",
        topk_threshold=3,
        bounded_weight_ceiling=10,
        generated_at_local="2026-05-05T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_valid_anchor_challenge_remaining"
    assert summary["claim_promotion_allowed"] is False
    assert summary["bounded_best_positive_rank"] == 2
    assert summary["bounded_best_valid_anchor_challenge_above_positive_count"] == 1
    assert payload["bounded_best_grid_row"]["top1_ligand_id"] == "valid_anchor_decoy"
    assert len(grid_rows) == 9


def test_penalty_envelope_cli_writes_outputs(tmp_path: Path) -> None:
    rows_csv = tmp_path / "slice_rows.csv"
    _write_csv(
        rows_csv,
        [
            {
                "ligand_id": "decoy",
                "is_positive": "False",
                "base_score": "-2.0",
                "label_free_penalty_pressure": "2.0",
                "label_free_support_pressure": "0.0",
                "slice_label_text": "invalid_close_overanchor_no_basic",
            },
            {
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "base_score": "-1.0",
                "label_free_penalty_pressure": "0.0",
                "label_free_support_pressure": "0.8",
                "slice_label_text": "positive_repaired_anchor_window",
            },
        ],
    )
    out_json = tmp_path / "envelope.json"
    out_csv = tmp_path / "envelope.csv"
    out_md = tmp_path / "envelope.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_drd2_hard_decoy_penalty_envelope.py"),
            "--rows-csv",
            str(rows_csv),
            "--grid",
            "0,1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["status"] == "slice_pairwise_green_diagnostic_only"
    assert "GPCR DRD2 Hard-Decoy Penalty Envelope" in out_md.read_text(encoding="utf-8")
    assert "penalty_weight" in out_csv.read_text(encoding="utf-8")
