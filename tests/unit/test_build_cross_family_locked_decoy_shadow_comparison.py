from __future__ import annotations

import json
from pathlib import Path

from tools import build_cross_family_locked_decoy_shadow_comparison as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _task_payload(
    summary_json: Path,
    pipeline_summary_json: Path,
    *,
    task_id: str,
    set_id: str,
    passed: bool,
    pr_auc: float,
    ef1: float,
    unique_auc: float,
) -> dict:
    return {
        "task_id": task_id,
        "set_id": set_id,
        "pass": passed,
        "run_ok": passed,
        "summary_json": str(summary_json),
        "pipeline_summary_json": str(pipeline_summary_json),
        "metrics": {
            "ranking_pr_auc": pr_auc,
            "ranking_ef1": ef1,
            "ranking_unique_auc": unique_auc,
            "operational_gate_pass": passed,
            "strict_gate_pass": True,
        },
    }


def _pipeline_with_stage3_fallback(path: Path, stage3_summary_json: Path) -> None:
    _write_json(
        path,
        {
            "summary": {},
            "stages": {
                "stage3_backmapping_scoring": {
                    "cmd": [
                        "python3",
                        "tools/run_ligand_backmapping_scoring.py",
                        "--out-summary-json",
                        str(stage3_summary_json),
                    ]
                }
            },
        },
    )


def _stage3_summary(path: Path, *, family: str, positive_delta_count: int, mean_delta: float) -> None:
    _write_json(
        path,
        {
            "summary": {
                "residual_prototype": {
                    "enabled": True,
                    "mode": "shadow_only",
                    "family": family,
                    "status": "shadow_ready_noop_family",
                    "tuning_variant": "family_noop_shadow",
                    "positive_delta_count": positive_delta_count,
                    "yellow_band_count": 0,
                    "mean_delta": mean_delta,
                    "max_delta": mean_delta,
                }
            }
        },
    )


def test_build_cross_family_locked_decoy_shadow_comparison_partial(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_proc_lines", lambda tag: ["333 python3 tools/run_external_validation_blind_sets.py --tag " + tag])

    baseline_root = tmp_path / "baseline"
    candidate_root = tmp_path / "candidate"
    scaffold_json = tmp_path / "scaffold.json"
    baseline_root.mkdir()
    candidate_root.mkdir()

    expected_rows = [
        {"set_id": "set1_core_blind", "task_id": "ion_trpv1_chembl20_full", "family": "ion_channel", "domain": "ion_channel", "ligand_sizes": "10000"},
        {"set_id": "set1_core_blind", "task_id": "kinase_core_full", "family": "kinase", "domain": "kinase", "ligand_sizes": "10000"},
        {"set_id": "set2_expanded_ood", "task_id": "ion_trpv1_chembl50_full", "family": "ion_channel", "domain": "ion_channel", "ligand_sizes": "10000"},
        {"set_id": "set2_expanded_ood", "task_id": "kinase_strict_full", "family": "kinase", "domain": "kinase", "ligand_sizes": "10000"},
    ]
    _write_json(
        scaffold_json,
        {
            "comparison_kind": "cross_family_locked_decoy_shadow",
            "baseline_run_root": str(baseline_root),
            "family_scope": ["ion_channel", "kinase"],
            "profile_rows": expected_rows,
        },
    )

    baseline_tasks = []
    for idx, row in enumerate(expected_rows):
        summary_json = tmp_path / f"baseline_{idx}_summary.json"
        pipeline_json = tmp_path / f"baseline_{idx}_pipeline.json"
        _write_json(summary_json, {"pass": True})
        _write_json(pipeline_json, {"summary": {}})
        baseline_tasks.append(
            _task_payload(
                summary_json,
                pipeline_json,
                task_id=row["task_id"],
                set_id=row["set_id"],
                passed=True,
                pr_auc=1.0 if "kinase" in row["task_id"] else 0.98,
                ef1=98.0,
                unique_auc=1.0,
            )
        )
    _write_json(
        baseline_root / "state.json",
        {
            "status": "completed",
            "sets": [
                {"set_id": "set1_core_blind", "tasks": baseline_tasks[:2]},
                {"set_id": "set2_expanded_ood", "tasks": baseline_tasks[2:]},
            ],
        },
    )

    ion_stage3 = tmp_path / "ion_stage3_summary.json"
    kin_stage3 = tmp_path / "kin_stage3_summary.json"
    ion_pipeline = tmp_path / "ion_candidate_pipeline.json"
    kin_pipeline = tmp_path / "kin_candidate_pipeline.json"
    ion_summary = tmp_path / "ion_candidate_summary.json"
    kin_summary = tmp_path / "kin_candidate_summary.json"
    _stage3_summary(ion_stage3, family="ion_channel", positive_delta_count=0, mean_delta=0.0)
    _stage3_summary(kin_stage3, family="kinase", positive_delta_count=0, mean_delta=0.0)
    _pipeline_with_stage3_fallback(ion_pipeline, ion_stage3)
    _pipeline_with_stage3_fallback(kin_pipeline, kin_stage3)
    _write_json(ion_summary, {"pass": True})
    _write_json(kin_summary, {"pass": True})
    _write_json(
        candidate_root / "state.json",
        {
            "status": "running",
            "protocol_id": "cross_family_locked_decoy_shadow_v1",
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "tasks": [
                        _task_payload(ion_summary, ion_pipeline, task_id="ion_trpv1_chembl20_full", set_id="set1_core_blind", passed=True, pr_auc=0.98, ef1=98.0, unique_auc=1.0),
                        _task_payload(kin_summary, kin_pipeline, task_id="kinase_core_full", set_id="set1_core_blind", passed=True, pr_auc=1.0, ef1=98.0, unique_auc=1.0),
                    ],
                }
            ],
        },
    )

    payload = mod.build_payload(
        scaffold_json=scaffold_json,
        baseline_run_root=baseline_root,
        candidate_run_root=candidate_root,
    )

    assert payload["summary"]["candidate_run_status"] == "running"
    assert payload["summary"]["completed_candidate_tasks"] == 2
    assert payload["summary"]["comparison_ready"] is False
    rows = {row["task_id"]: row for row in payload["task_rows"]}
    assert rows["ion_trpv1_chembl20_full"]["candidate_complete"] is True
    assert rows["ion_trpv1_chembl20_full"]["residual_status"] == "shadow_ready_noop_family"
    assert rows["ion_trpv1_chembl50_full"]["candidate_complete"] is False
    family_rows = {row["family"]: row for row in payload["family_rows"]}
    assert family_rows["ion_channel"]["completed_candidate_tasks"] == 1
    assert family_rows["kinase"]["completed_candidate_tasks"] == 1


def test_build_cross_family_locked_decoy_shadow_comparison_complete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_proc_lines", lambda tag: [])

    baseline_root = tmp_path / "baseline"
    candidate_root = tmp_path / "candidate"
    scaffold_json = tmp_path / "scaffold.json"
    baseline_root.mkdir()
    candidate_root.mkdir()

    expected_rows = [
        {"set_id": "set1_core_blind", "task_id": "ion_trpv1_chembl20_full", "family": "ion_channel", "domain": "ion_channel", "ligand_sizes": "10000"},
        {"set_id": "set1_core_blind", "task_id": "kinase_core_full", "family": "kinase", "domain": "kinase", "ligand_sizes": "10000"},
    ]
    _write_json(
        scaffold_json,
        {
            "comparison_kind": "cross_family_locked_decoy_shadow",
            "baseline_run_root": str(baseline_root),
            "family_scope": ["ion_channel", "kinase"],
            "profile_rows": expected_rows,
        },
    )

    baseline_tasks = []
    candidate_tasks = []
    for idx, row in enumerate(expected_rows):
        baseline_summary = tmp_path / f"baseline_{idx}_summary.json"
        candidate_summary = tmp_path / f"candidate_{idx}_summary.json"
        baseline_pipeline = tmp_path / f"baseline_{idx}_pipeline.json"
        candidate_pipeline = tmp_path / f"candidate_{idx}_pipeline.json"
        stage3_summary = tmp_path / f"stage3_{idx}.json"
        _write_json(baseline_summary, {"pass": True})
        _write_json(candidate_summary, {"pass": True})
        _write_json(baseline_pipeline, {"summary": {}})
        _stage3_summary(stage3_summary, family=row["family"], positive_delta_count=0, mean_delta=0.0)
        _pipeline_with_stage3_fallback(candidate_pipeline, stage3_summary)
        baseline_tasks.append(
            _task_payload(baseline_summary, baseline_pipeline, task_id=row["task_id"], set_id=row["set_id"], passed=True, pr_auc=0.98, ef1=98.0, unique_auc=1.0)
        )
        candidate_tasks.append(
            _task_payload(candidate_summary, candidate_pipeline, task_id=row["task_id"], set_id=row["set_id"], passed=True, pr_auc=0.98, ef1=98.0, unique_auc=1.0)
        )

    _write_json(baseline_root / "state.json", {"status": "completed", "sets": [{"set_id": "set1_core_blind", "tasks": baseline_tasks}]})
    _write_json(
        candidate_root / "state.json",
        {"status": "completed", "protocol_id": "cross_family_locked_decoy_shadow_v1", "sets": [{"set_id": "set1_core_blind", "tasks": candidate_tasks}]},
    )

    payload = mod.build_payload(
        scaffold_json=scaffold_json,
        baseline_run_root=baseline_root,
        candidate_run_root=candidate_root,
    )

    assert payload["summary"]["completed_candidate_tasks"] == 2
    assert payload["summary"]["comparison_ready"] is True
    assert payload["summary"]["candidate_fail_count"] == 0


def test_proc_lines_ignores_monitor_processes(monkeypatch) -> None:
    def _fake_check_output(args, text, stderr):
        return "\n".join(
            [
                "111 python3 tools/monitor_cross_family_locked_decoy_shadow.py --run-root runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_r1 --loop",
                "222 python3 tools/monitor_biorxiv_external_validation.py --run-root runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_r1 --loop",
                "333 python3 tools/run_external_validation_blind_sets.py --tag 2026-03-25_r1",
            ]
        )

    monkeypatch.setattr(mod.subprocess, "check_output", _fake_check_output)
    rows = mod._proc_lines("2026-03-25_r1")
    assert rows == ["333 python3 tools/run_external_validation_blind_sets.py --tag 2026-03-25_r1"]
