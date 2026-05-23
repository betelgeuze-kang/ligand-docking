from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_structure_refinement_metric_queue as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_queue_splits_protein_and_interface_metric_tasks(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    candidate = tmp_path / "candidate.pdb"
    native.write_text("ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n")
    candidate.write_text("ATOM      1  CA  GLY A   1       0.100   0.000   0.000  1.00 20.00           C\nEND\n")
    scorecard = tmp_path / "scorecard.json"
    manifest = tmp_path / "manifest.csv"
    source = tmp_path / "source.json"
    scores = tmp_path / "scores.csv"
    _write_json(
        scorecard,
        {
            "summary": {
                "status": "blocked_structure_refinement_metrics_missing",
                "target_count": 1,
                "native_reference_target_count": 1,
                "pseudo_allatom_lane_ready_count": 1,
                "rmsd_available_count": 0,
                "tm_score_available_count": 0,
                "gdt_available_count": 0,
                "lddt_or_molprobity_available_count": 0,
                "dockq_or_interface_metric_available_count": 0,
            },
            "rows": [
                {
                    "target_id": "SARS-CoV-2 Mpro",
                    "source_artifact": str(source),
                    "native_reference_available": True,
                    "native_pdb_id": "6LU7",
                    "native_pdb_path": str(native),
                    "pseudo_allatom_lane_ready": True,
                    "rmsd_available": False,
                    "tm_score_available": False,
                    "gdt_available": False,
                    "lddt_or_molprobity_available": False,
                    "dockq_or_interface_metric_available": False,
                }
            ],
        },
    )
    _write_csv(manifest, [{"target": "SARS-CoV-2 Mpro", "path": str(native), "pdb_id": "6LU7"}])
    _write_csv(scores, [{"backmapped_pdb": str(candidate)}])
    _write_json(source, {"summary": {"status": "pseudo_allatom_local_refine_ready"}, "structured": {"allatom_scores_csv": str(scores)}})

    payload = mod.build_queue(
        structure_scorecard_json=scorecard,
        native_manifest_csv=manifest,
        sarscov2_runner_json=source,
        tcruzi_review_json=tmp_path / "missing_tcruzi.json",
        cathepsin_runner_json=tmp_path / "missing_cathepsin.json",
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["status"] == "open_structure_refinement_metric_queue"
    assert summary["queue_row_count"] == 2
    assert summary["open_target_count"] == 1
    assert summary["claim_promotion_allowed"] is False
    assert rows[0]["metric_task"] == "protein_alignment_metrics"
    assert rows[0]["missing_metric_families"] == "rmsd,tm_score,gdt,lddt_or_molprobity"
    assert rows[0]["native_reference_available"] is True
    assert rows[0]["allatom_scores_available"] is True
    assert rows[0]["candidate_backmapped_pdb_count"] == 1
    assert rows[1]["metric_task"] == "interface_metrics"
    assert rows[1]["missing_metric_families"] == "dockq_or_interface"
    assert payload["claim_boundary"]["metric_availability_alone_is_not_galaxy_parity"] is True


def test_build_queue_preserves_interface_not_applicable_provenance(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    manifest = tmp_path / "manifest.csv"
    _write_json(
        scorecard,
        {
            "summary": {"status": "blocked_structure_refinement_metrics_missing", "target_count": 1},
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "native_reference_available": True,
                    "pseudo_allatom_lane_ready": True,
                    "rmsd_available": True,
                    "tm_score_available": False,
                    "gdt_available": False,
                    "lddt_or_molprobity_available": False,
                    "dockq_or_interface_metric_available": False,
                    "dockq_or_interface_not_applicable": True,
                }
            ],
        },
    )
    _write_csv(manifest, [{"target": "T. cruzi PDE", "path": "", "pdb_id": "3V94"}])

    payload = mod.build_queue(
        structure_scorecard_json=scorecard,
        native_manifest_csv=manifest,
        tcruzi_review_json=tmp_path / "missing_tcruzi.json",
        sarscov2_runner_json=tmp_path / "missing_sars.json",
        cathepsin_runner_json=tmp_path / "missing_cathepsin.json",
        generated_at_local="2026-05-14T00:00:00+09:00",
    )

    rows = payload["rows"]
    interface_rows = [row for row in rows if row["metric_task"] == "interface_metrics"]
    assert len(interface_rows) == 1
    assert interface_rows[0]["status"] == "not_applicable_provenance"


def test_cli_writes_metric_queue_outputs(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    manifest = tmp_path / "manifest.csv"
    out_json = tmp_path / "queue.json"
    out_csv = tmp_path / "queue.csv"
    out_md = tmp_path / "queue.md"
    _write_json(
        scorecard,
        {
            "summary": {"status": "blocked_structure_refinement_metrics_missing", "target_count": 1},
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "native_reference_available": False,
                    "pseudo_allatom_lane_ready": True,
                    "rmsd_available": False,
                    "tm_score_available": True,
                    "gdt_available": True,
                    "lddt_or_molprobity_available": True,
                    "dockq_or_interface_metric_available": True,
                }
            ],
        },
    )
    _write_csv(manifest, [{"target": "Cathepsin K", "path": "", "pdb_id": "5TDI"}])

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_structure_refinement_metric_queue.py"),
            "--structure-scorecard-json",
            str(scorecard),
            "--native-manifest-csv",
            str(manifest),
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
    assert payload["packet_type"] == "structure_refinement_metric_queue"
    assert payload["summary"]["queue_row_count"] == 1
    assert "Structure Refinement Metric Queue" in out_md.read_text(encoding="utf-8")
    assert "protein_alignment_metrics" in out_csv.read_text(encoding="utf-8")
