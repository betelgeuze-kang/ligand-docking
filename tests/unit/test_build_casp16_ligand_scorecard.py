from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_casp16_ligand_scorecard as mod


def _write_json(path: Path, summary: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")
    return path


def test_casp16_ligand_scorecard_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_casp16_ligand_scorecard(
        materialization_json=tmp_path / "missing_materialization.json",
        scorecard_rows_csv=tmp_path / "missing_scorecard_rows.csv",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_casp16_ligand_scorecard"
    assert summary["scorecard_ready"] is False
    assert "materialization_json_missing_or_invalid" in summary["blockers"]
    assert "scorecard_rows_csv_missing" in summary["blockers"]
    assert summary["commercial_ligand_claim_allowed"] is False
    assert summary["download_executed"] is False
    assert summary["docking_executed"] is False
    assert summary["external_state_mutated"] is False


def test_casp16_ligand_scorecard_ready_with_operator_metric_rows(tmp_path: Path) -> None:
    materialization = _write_json(
        tmp_path / "data/competition_benchmarks/casp16_ligand/materialization_manifest.json",
        {"status": "casp16_ligand_materialization_ready"},
    )
    score_rows = tmp_path / "data/competition_benchmarks/casp16_ligand/scorecard_rows.csv"
    score_rows.write_text(
        "target_id,task_type,metric_name,metric_value,result_source\n"
        "L1001,pose,LDDT-PLI,0.71,operator://reviewed/L1001\n"
        "L1002,affinity,Kendall_tau,0.42,operator://reviewed/L1002\n",
        encoding="utf-8",
    )

    payload = mod.build_casp16_ligand_scorecard(
        materialization_json=materialization,
        scorecard_rows_csv=score_rows,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "casp16_ligand_scorecard_ready"
    assert summary["scorecard_ready"] is True
    assert summary["blockers"] == []
    assert summary["scorecard_row_count"] == 2
    assert summary["pose_row_count"] == 1
    assert summary["affinity_row_count"] == 1
    assert summary["competition_evidence_role"] == "competition_credibility_evidence_only"
    assert summary["commercial_ligand_claim_allowed"] is False


def test_casp16_ligand_scorecard_blocks_unsupported_rows(tmp_path: Path) -> None:
    materialization = _write_json(
        tmp_path / "data/competition_benchmarks/casp16_ligand/materialization_manifest.json",
        {"status": "casp16_ligand_materialization_ready"},
    )
    score_rows = tmp_path / "data/competition_benchmarks/casp16_ligand/scorecard_rows.csv"
    score_rows.write_text(
        "target_id,task_type,metric_name,metric_value,result_source\n"
        "L1001,commercial_docking,ROC-AUC,not-a-number,operator://reviewed/L1001\n",
        encoding="utf-8",
    )

    payload = mod.build_casp16_ligand_scorecard(
        materialization_json=materialization,
        scorecard_rows_csv=score_rows,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_casp16_ligand_scorecard"
    assert "scorecard_metric_values_not_numeric" in summary["blockers"]
    assert "scorecard_task_type_unsupported" in summary["blockers"]
    assert "scorecard_metric_name_unsupported" in summary["blockers"]


def test_casp16_ligand_scorecard_cli_writes_outputs(tmp_path: Path) -> None:
    materialization = _write_json(
        tmp_path / "materialization_manifest.json",
        {"status": "casp16_ligand_materialization_ready"},
    )
    score_rows = tmp_path / "scorecard_rows.csv"
    out_json = tmp_path / "scorecard.json"
    out_csv = tmp_path / "scorecard.csv"
    out_md = tmp_path / "scorecard.md"
    score_rows.write_text(
        "target_id,task_type,metric_name,metric_value,result_source\n"
        "L1001,pose,LDDT-PLI,0.71,operator://reviewed/L1001\n",
        encoding="utf-8",
    )

    assert mod.main(
        [
            "--materialization-json",
            str(materialization),
            "--scorecard-rows-csv",
            str(score_rows),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "casp16_ligand_scorecard"
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,task_type,")
    assert "CASP16 Ligand Scorecard" in out_md.read_text(encoding="utf-8")


def test_casp16_ligand_scorecard_defaults_to_current_materialization_receipt() -> None:
    assert (
        mod.DEFAULT_MATERIALIZATION_JSON
        == "runs/casp16_ligand_materialization_manifest_current.json"
    )
