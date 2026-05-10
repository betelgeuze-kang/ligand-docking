from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_structure_refinement_metric_materialization as mod

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


def _pdb(path: Path, coords: list[tuple[float, float, float]]) -> None:
    lines = []
    serial = 1
    for idx, (x, y, z) in enumerate(coords, start=1):
        lines.append(
            f"ATOM  {serial:5d} CA  ALA A{idx:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C"
        )
        serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_kabsch_rmsd_handles_rigid_translation(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    candidate = tmp_path / "candidate.pdb"
    _pdb(native, [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    _pdb(candidate, [(5, -2, 3), (6, -2, 3), (5, -1, 3)])

    native_ca = mod._ca_coords(native)
    candidate_ca = mod._ca_coords(candidate)
    rmsd, distances = mod._kabsch_rmsd(native_ca, candidate_ca)

    assert rmsd is not None
    assert rmsd < 1e-9
    assert mod._gdt_ts_proxy(distances) == 1.0
    assert mod._tm_score_ca_proxy(distances) == 1.0
    ref, aligned, _ = mod._aligned_ca_pair(native_ca, candidate_ca)
    assert mod._lddt_ca_proxy(ref, aligned) == 1.0


def test_build_materialization_computes_rmsd_and_gdt_proxy(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    candidate = tmp_path / "candidate.pdb"
    scores = tmp_path / "scores.csv"
    queue = tmp_path / "queue.json"
    _pdb(native, [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    _pdb(candidate, [(0.1, 0, 0), (1.1, 0, 0), (0.1, 1, 0)])
    _write_csv(scores, [{"backmapped_pdb": str(candidate)}])
    _write_json(
        queue,
        {
            "rows": [
                {
                    "target": "SARS-CoV-2 Mpro",
                    "queue_id": "SARS-CoV-2 Mpro::protein_alignment_metrics",
                    "metric_task": "protein_alignment_metrics",
                    "native_pdb_path": str(native),
                    "allatom_scores_csv": str(scores),
                },
                {
                    "target": "SARS-CoV-2 Mpro",
                    "queue_id": "SARS-CoV-2 Mpro::interface_metrics",
                    "metric_task": "interface_metrics",
                },
            ]
        },
    )

    payload = mod.build_materialization(
        queue_json=queue,
        max_candidates_per_target=8,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    computed = [row for row in payload["rows"] if row.get("metric_status") == "metrics_computed"]
    interface = [row for row in payload["rows"] if row.get("metric_status") == "not_applicable_without_complex_interface_claim"]
    assert summary["status"] == "structure_refinement_metric_materialization_partial"
    assert summary["rmsd_available_target_count"] == 1
    assert summary["gdt_ts_proxy_available_target_count"] == 1
    assert summary["tm_score_ca_proxy_available_target_count"] == 1
    assert summary["lddt_ca_proxy_available_target_count"] == 1
    assert summary["galaxy_class_claim_allowed"] is False
    assert len(computed) == 1
    assert computed[0]["ca_aligned_rmsd_A"] is not None
    assert computed[0]["gdt_ts_proxy"] == 1.0
    assert computed[0]["tm_score_ca_proxy"] == 1.0
    assert computed[0]["lddt_ca_proxy"] == 1.0
    assert interface and interface[0]["dockq_available"] is False
    assert payload["claim_boundary"]["gdt_ts_proxy_is_not_true_galaxy_metric"] is True
    assert payload["claim_boundary"]["tm_score_ca_proxy_is_not_true_tm_score"] is True
    assert payload["claim_boundary"]["lddt_ca_proxy_is_not_true_lddt_or_molprobity"] is True


def test_cli_writes_outputs(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_json(
        queue,
        {
            "rows": [
                {
                    "target": "T. cruzi PDE",
                    "queue_id": "T. cruzi PDE::protein_alignment_metrics",
                    "metric_task": "protein_alignment_metrics",
                    "native_pdb_path": "",
                    "allatom_scores_csv": "",
                }
            ]
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_structure_refinement_metric_materialization.py"),
            "--queue-json",
            str(queue),
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
    assert payload["packet_type"] == "structure_refinement_metric_materialization"
    assert "Structure Refinement Metric Materialization" in out_md.read_text(encoding="utf-8")
    assert "blocked_native_missing" in out_csv.read_text(encoding="utf-8")
