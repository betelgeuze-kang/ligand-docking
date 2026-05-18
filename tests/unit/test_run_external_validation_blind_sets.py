from pathlib import Path

from tools import run_external_validation_blind_sets as mod


def test_validate_set_defs_accepts_comparison_candidate_claim_role(tmp_path: Path) -> None:
    profile_json = tmp_path / "profile.json"
    profile_json.write_text("{}", encoding="utf-8")

    mod._validate_set_defs(
        [
            {
                "set_id": "set1_core_blind",
                "title": "Core Blind Set",
                "purpose": "Comparison-only guarded candidate.",
                "claim_role": "comparison_candidate",
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "profile_json": str(profile_json),
                        "ligand_sizes": "100000",
                        "date_tag_suffix": "gpcr-core-full-comparison",
                    }
                ],
            }
        ],
        "unit_spec",
    )


def test_run_set_reruns_failed_ligand_task_when_resuming(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    (tmp_path / "runs").mkdir()
    profile_json = tmp_path / "profile.json"
    profile_json.write_text("{}", encoding="utf-8")
    summary_json = tmp_path / "runs/external_validation_unit_set1_gpcr_core_full_summary.json"
    summary_json.write_text("{}", encoding="utf-8")
    base_root = tmp_path / "bundle"
    state_json = base_root / "set1" / "state.json"
    state_json.parent.mkdir(parents=True)
    mod._write_json(
        state_json,
        {
            "set_id": "set1",
            "title": "Set 1",
            "tasks": {
                "gpcr_core_full": {
                    "done": True,
                    "result": {"pass": False},
                }
            },
        },
    )
    calls = []

    def _fake_run(cmd, log):
        calls.append(cmd)
        return {"ok": True, "returncode": 0, "cmd": cmd, "log": str(log)}

    monkeypatch.setattr(mod, "_run", _fake_run)
    monkeypatch.setattr(mod, "_extract_ligand_result", lambda path: {"pass": True, "raw_pass": True})
    monkeypatch.setattr(mod, "_copy_ligand_result_bundle", lambda result, domain_dir: [])

    result = mod._run_set(
        base_root,
        "unit",
        {
            "set_id": "set1",
            "title": "Set 1",
            "purpose": "Unit rerun check.",
            "tasks": [
                {
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "kind": "ligand_stress",
                    "profile_json": "profile.json",
                    "ligand_sizes": "10000",
                    "date_tag_suffix": "gpcr-core-full",
                }
            ],
        },
        resume=True,
    )

    assert result["pass"] is True
    assert len(calls) == 1
    assert calls[0][1].endswith("tools/run_ligand_stress_validation.py")


def test_extract_ligand_result_finds_ranking_summary_from_stage5_cmd(tmp_path: Path) -> None:
    ranking_summary = tmp_path / "run_p0_n100000_r1_stage5_ranking_summary.json"
    integrity_summary = tmp_path / "run_p0_n100000_r1_stage45_integrity_summary.json"
    pipeline_summary = tmp_path / "run_p0_n100000_r1_summary.json"
    stress_summary = tmp_path / "run_summary.json"
    ranking_summary.write_text('{"pass": true}', encoding="utf-8")
    integrity_summary.write_text('{"pass": true}', encoding="utf-8")
    pipeline_summary.write_text(
        """
{
  "stages": {
    "stage5_ranking_eval": {
      "ok": true,
      "cmd": ["python3", "tools/evaluate_ligand_ranking_metrics.py", "--out-json", "__RANKING__"]
    },
    "stage45_integrity": {
      "ok": true,
      "cmd": ["python3", "tools/validate_ligand_eval_integrity.py", "--out-json", "__INTEGRITY__"]
    },
    "stage6_operational_gate": {
      "ranking_score_col_used": "score",
      "ranking_probability_score_col_used": "score"
    }
  }
}
""".replace("__RANKING__", str(ranking_summary)).replace("__INTEGRITY__", str(integrity_summary)),
        encoding="utf-8",
    )
    stress_summary.write_text(
        """
{
  "pass": false,
  "runs": [
    {
      "summary_json": "__PIPELINE__",
      "ranking_unique_auc": 0.9,
      "ranking_pr_auc": 0.1,
      "ranking_ef1": 30.0,
      "ranking_bedroc": 1.0,
      "operational_gate_pass": false,
      "strict_gate_pass": true
    }
  ],
  "artifacts": {}
}
""".replace("__PIPELINE__", str(pipeline_summary)),
        encoding="utf-8",
    )

    result = mod._extract_ligand_result(stress_summary)

    assert result["ranking_summary_json"] == str(ranking_summary.resolve())
    assert result["integrity_summary_json"] == str(integrity_summary.resolve())
    assert result["metrics"]["ranking_pass"] is True
    assert result["metrics"]["integrity_pass"] is True
