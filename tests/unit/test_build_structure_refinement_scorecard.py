from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_structure_refinement_scorecard as mod

ROOT = Path(__file__).resolve().parents[2]


TARGETS = ("T. cruzi PDE", "SARS-CoV-2 Mpro", "Cathepsin K")


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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _native_manifest(tmp_path: Path) -> Path:
    rows: list[dict[str, object]] = []
    for index, target in enumerate(TARGETS, start=1):
        pdb_path = tmp_path / f"native_{index}.pdb"
        pdb_path.write_text("HEADER TEST\n", encoding="utf-8")
        rows.append(
            {
                "target": target,
                "path": str(pdb_path),
                "source_kind": "pdb_or_other",
                "source_id": f"T{index}",
                "status": "downloaded",
                "pdb_id": f"T{index}",
            }
        )
    manifest = tmp_path / "native_manifest.csv"
    _write_csv(manifest, rows)
    return manifest


def _ready_source(path: Path, target: str, extra_summary: dict[str, object] | None = None) -> Path:
    summary: dict[str, object] = {
        "status": "pseudo_allatom_local_refine_ready",
        "target_id": target,
        "selected_command_kind": "pseudo_allatom_local_refine",
        "slice_candidate_count": 8,
    }
    if extra_summary:
        summary.update(extra_summary)
    _write_json(path, {"summary": summary})
    return path


def test_build_scorecard_blocks_native_backed_lanes_without_structure_metrics(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE")
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=tmp_path / "missing_materialization.json",
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_structure_refinement_metrics_missing"
    assert summary["target_count"] == 3
    assert summary["native_reference_target_count"] == 3
    assert summary["pseudo_allatom_lane_ready_count"] == 3
    assert summary["rmsd_available_count"] == 0
    assert summary["tm_score_available_count"] == 0
    assert summary["gdt_available_count"] == 0
    assert summary["gdt_ts_proxy_available_count"] == 0
    assert summary["tm_score_ca_proxy_available_count"] == 0
    assert summary["lddt_ca_proxy_available_count"] == 0
    assert summary["lddt_or_molprobity_available_count"] == 0
    assert summary["dockq_or_interface_metric_available_count"] == 0
    assert summary["dockq_or_interface_not_applicable_count"] == 0
    assert summary["dockq_or_interface_resolved_count"] == 0
    assert summary["galaxy_class_claim_allowed"] is False
    assert summary["blocker_counts"]["rmsd_missing"] == 3
    assert summary["blocker_counts"]["tm_score_missing"] == 3
    assert summary["blocker_counts"]["gdt_missing"] == 3
    assert summary["blocker_counts"]["lddt_or_molprobity_missing"] == 3
    assert summary["blocker_counts"]["dockq_or_interface_metric_missing"] == 3


def test_build_scorecard_passes_only_when_all_required_metrics_exist(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    metric_summary = {
        "rmsd": 1.2,
        "tm_score": 0.82,
        "gdt_ts": 0.71,
        "lddt": 0.78,
        "dockq": 0.64,
    }
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE", metric_summary)
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro", metric_summary)
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K", metric_summary)

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=tmp_path / "missing_materialization.json",
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    assert payload["summary"]["status"] == "structure_refinement_scorecard_pass"
    assert payload["summary"]["claim_promotion_allowed"] is True
    assert payload["summary"]["galaxy_class_claim_allowed"] is True
    assert all(not row["blockers"] for row in payload["rows"])


def test_build_scorecard_reads_materialized_rmsd_but_keeps_proxy_claim_locked(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE")
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")
    materialization = tmp_path / "materialization.json"
    _write_json(
        materialization,
        {
            "rows": [
                {
                    "target": "SARS-CoV-2 Mpro",
                    "metric_status": "metrics_computed",
                    "ca_aligned_rmsd_A": 1.5,
                    "gdt_ts_proxy": 0.9,
                    "tm_score_ca_proxy": 0.8,
                    "lddt_ca_proxy": 0.7,
                },
                {
                    "target": "Cathepsin K",
                    "metric_status": "metrics_computed",
                    "ca_aligned_rmsd_A": 2.0,
                    "gdt_ts_proxy": 0.75,
                    "tm_score_ca_proxy": 0.65,
                    "lddt_ca_proxy": 0.55,
                },
            ]
        },
    )

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=materialization,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["rmsd_available_count"] == 2
    assert payload["summary"]["gdt_available_count"] == 0
    assert payload["summary"]["tm_score_true_metric_available_count"] == 0
    assert payload["summary"]["gdt_ts_true_metric_available_count"] == 0
    assert payload["summary"]["lddt_ca_true_metric_available_count"] == 0
    assert payload["summary"]["gdt_ts_proxy_available_count"] == 2
    assert payload["summary"]["tm_score_ca_proxy_available_count"] == 2
    assert payload["summary"]["lddt_ca_proxy_available_count"] == 2
    assert payload["summary"]["galaxy_class_claim_allowed"] is False
    assert rows["SARS-CoV-2 Mpro"]["rmsd_available"] is True
    assert rows["SARS-CoV-2 Mpro"]["gdt_available"] is False
    assert rows["SARS-CoV-2 Mpro"]["gdt_ts_proxy_available"] is True
    assert rows["SARS-CoV-2 Mpro"]["tm_score_ca_proxy_available"] is True
    assert rows["SARS-CoV-2 Mpro"]["lddt_ca_proxy_available"] is True
    assert rows["SARS-CoV-2 Mpro"]["best_ca_aligned_rmsd_A"] == 1.5
    assert rows["SARS-CoV-2 Mpro"]["best_tm_score_ca_proxy"] == 0.8
    assert rows["SARS-CoV-2 Mpro"]["best_lddt_ca_proxy"] == 0.7


def test_build_scorecard_treats_interface_not_applicable_as_resolved_not_metric_pass(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE")
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")
    materialization = tmp_path / "materialization.json"
    _write_json(
        materialization,
        {
            "rows": [
                {
                    "target": target,
                    "metric_status": "not_applicable_without_complex_interface_claim",
                    "dockq_available": False,
                }
                for target in TARGETS
            ]
        },
    )

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=materialization,
        generated_at_local="2026-05-14T00:00:00+09:00",
    )

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["dockq_or_interface_metric_available_count"] == 0
    assert payload["summary"]["dockq_or_interface_not_applicable_count"] == 3
    assert payload["summary"]["dockq_or_interface_resolved_count"] == 3
    assert payload["summary"]["dockq_pass"] is True
    assert "dockq_or_interface_metric_missing" not in payload["summary"]["blocker_counts"]
    assert rows["T. cruzi PDE"]["dockq_or_interface_metric_available"] is False
    assert rows["T. cruzi PDE"]["dockq_or_interface_not_applicable"] is True
    assert rows["T. cruzi PDE"]["dockq_or_interface_resolved"] is True


def test_build_scorecard_accepts_internal_ca_true_metrics_with_interface_na(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE")
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")
    materialization = tmp_path / "materialization.json"
    rows = []
    for target in TARGETS:
        rows.append(
            {
                "target": target,
                "metric_status": "metrics_computed",
                "ca_aligned_rmsd_A": 1.0,
                "tm_score": 0.8,
                "gdt_ts": 0.75,
                "lddt_ca": 0.7,
            }
        )
        rows.append(
            {
                "target": target,
                "metric_status": "not_applicable_without_complex_interface_claim",
                "dockq_available": False,
            }
        )
    _write_json(
        materialization,
        {
            "summary": {
                "metric_backend": "internal_deterministic_ca_true_metrics",
                "chain_aware_canonical_ca_matching": True,
            },
            "rows": rows,
        },
    )

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=materialization,
        generated_at_local="2026-05-17T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "structure_refinement_scorecard_pass"
    assert summary["tm_score_available_count"] == 3
    assert summary["gdt_available_count"] == 3
    assert summary["lddt_or_molprobity_available_count"] == 3
    assert summary["metric_backend"] == "internal_deterministic_ca_true_metrics"
    assert summary["chain_aware_canonical_ca_matching"] is True
    assert summary["tm_score_true_metric_available_count"] == 3
    assert summary["gdt_ts_true_metric_available_count"] == 3
    assert summary["lddt_ca_true_metric_available_count"] == 3
    assert summary["best_tm_score"] == 0.8
    assert summary["best_gdt_ts"] == 0.75
    assert summary["best_lddt_ca"] == 0.7
    assert summary["molprobity_full_atom_quality_caveat"] is True
    assert summary["dockq_or_interface_resolved_count"] == 3
    assert summary["galaxy_class_claim_allowed"] is True


def test_build_scorecard_uses_structured_candidate_paths_but_summary_gate_authority(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    scores = tmp_path / "scores.csv"
    _write_csv(scores, [{"backmapped_pdb": str(tmp_path / "candidate.pdb")}])
    tcruzi = tmp_path / "tcruzi.json"
    _write_json(
        tcruzi,
        {
            "summary": {
                "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
                "target_id": "T. cruzi PDE",
                "packet_ready_for_operator_review": True,
                "selected_command_kind": "pseudo_allatom_backmapping_rescore",
                "commercial_hard_gate_pass_v2": False,
            },
            "structured": {"allatom_scores_csv": str(scores)},
        },
    )
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")

    payload = mod.build_scorecard(
        native_manifest_csv=manifest,
        tcruzi_review_json=tcruzi,
        sarscov2_runner_json=sars,
        cathepsin_runner_json=cathepsin,
        metric_materialization_json=tmp_path / "missing_materialization.json",
        generated_at_local="2026-05-14T00:00:00+09:00",
    )

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T. cruzi PDE"]["allatom_scores_available"] is True
    assert rows["T. cruzi PDE"]["commercial_hard_gate_pass"] is False


def test_cli_writes_structure_refinement_artifacts(tmp_path: Path) -> None:
    manifest = _native_manifest(tmp_path)
    tcruzi = _ready_source(tmp_path / "tcruzi.json", "T. cruzi PDE")
    sars = _ready_source(tmp_path / "sars.json", "SARS-CoV-2 Mpro")
    cathepsin = _ready_source(tmp_path / "cathepsin.json", "Cathepsin K")
    out_json = tmp_path / "scorecard.json"
    out_csv = tmp_path / "scorecard.csv"
    out_md = tmp_path / "scorecard.md"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_structure_refinement_scorecard.py"),
            "--native-manifest-csv",
            str(manifest),
            "--tcruzi-review-json",
            str(tcruzi),
            "--sarscov2-runner-json",
            str(sars),
            "--cathepsin-runner-json",
            str(cathepsin),
            "--metric-materialization-json",
            str(tmp_path / "missing_materialization.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "structure_refinement_scorecard"
    assert out_csv.exists()
    assert "Structure Refinement Scorecard" in out_md.read_text(encoding="utf-8")
