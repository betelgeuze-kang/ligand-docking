import json
from pathlib import Path

import pandas as pd
import pytest

from tools import run_post_gate_pipeline as p


def _arg_list(tmp_path):
    defaults_json = tmp_path / "defaults.json"
    defaults_json.write_text(
        json.dumps(
            {
                "defaults": {
                    "active_learning_ood_pair_csv": str(tmp_path / "ood_pair.csv"),
                    "active_learning_accuracy_external_csv": str(tmp_path / "acc.csv"),
                    "active_learning_curriculum_base_manifest_csv": str(tmp_path / "base_manifest.csv"),
                    "active_learning_curriculum_checkpoint_dir": str(tmp_path / "ckpts"),
                    "active_learning_stage2_csv": str(tmp_path / "fallback_stage2.csv"),
                    "sentinel_sources_csv": str(tmp_path / "sentinel_sources.csv"),
                    "sentinel_targets": "Hemoglobin_4HHB",
                    "cath_sources_csv": str(tmp_path / "cath_sources.csv"),
                    "cath_split_csv": str(tmp_path / "cath_split.csv"),
                    "cath_manifest_csv": str(tmp_path / "cath_manifest_full.csv"),
                    "special_case_policy_json": str(tmp_path / "special_case_policy.json"),
                    "special_case_metal_sources_csv": str(tmp_path / "special_metal.csv"),
                    "special_case_dna_sources_csv": str(tmp_path / "special_dna.csv"),
                    "special_case_membrane_sources_csv": str(tmp_path / "special_membrane.csv"),
                }
            }
        ),
        encoding="utf-8",
    )

    # Minimal files used by defaults.
    pd.DataFrame([{"target": "Chignolin", "paired": 1}]).to_csv(tmp_path / "ood_pair.csv", index=False)
    pd.DataFrame([{"target": "Chignolin", "avg_rmsd_aligned": 0.1}]).to_csv(tmp_path / "acc.csv", index=False)
    pd.DataFrame([{"target": "Chignolin", "multiplier": 1.0}]).to_csv(tmp_path / "base_manifest.csv", index=False)
    pd.DataFrame([{"target": "Chignolin", "throughput_on": 100.0}]).to_csv(tmp_path / "fallback_stage2.csv", index=False)
    pd.DataFrame([{"target": "Hemoglobin_4HHB", "pdb_id": "4HHB", "uniprot_id": ""}]).to_csv(
        tmp_path / "sentinel_sources.csv",
        index=False,
    )
    pd.DataFrame([{"target": f"CATH_T{i}", "pdb_id": "1CRN", "uniprot_id": ""} for i in range(1, 13)]).to_csv(
        tmp_path / "cath_sources.csv",
        index=False,
    )
    pd.DataFrame([{"target": f"CATH_T{i}", "split": "train"} for i in range(1, 13)]).to_csv(
        tmp_path / "cath_split.csv",
        index=False,
    )
    policy_payload = {
        "common": {"require_core_gate_pass": True, "fail_on_overflow_or_saturation": True},
        "domains": {
            "metal": {"metrics": [{"name": "coordination_number_mae", "operator": "<=", "threshold": 0.3}]},
            "dna": {"metrics": [{"name": "protein_dna_contact_f1", "operator": ">=", "threshold": 0.85}]},
            "membrane": {"metrics": [{"name": "tilt_angle_mae_deg", "operator": "<=", "threshold": 12.0}]},
        },
    }
    (tmp_path / "special_case_policy.json").write_text(json.dumps(policy_payload), encoding="utf-8")
    pd.DataFrame([{"target": "Carbonic_Anhydrase_2_Zn", "pdb_id": "1CA2", "uniprot_id": "P00918"}]).to_csv(
        tmp_path / "special_metal.csv",
        index=False,
    )
    pd.DataFrame([{"target": "TBP_DNA_Complex", "pdb_id": "1CDW", "uniprot_id": "P20226"}]).to_csv(
        tmp_path / "special_dna.csv",
        index=False,
    )
    pd.DataFrame([{"target": "Beta2AR_GPCR", "pdb_id": "2RH1", "uniprot_id": "P07550"}]).to_csv(
        tmp_path / "special_membrane.csv",
        index=False,
    )

    out_prefix = tmp_path / "runs" / "post_gate_pipeline_2026-02-19"
    return [
        "--defaults-json",
        str(defaults_json),
        "--date-tag",
        "2026-02-19",
        "--run-scope",
        "smoke_then_full",
        "--out-prefix",
        str(out_prefix),
    ]


def _fake_run_cmd_factory(tmp_path, *, gate_pass_attempt=1, fail_stage=None):
    state = {"gate_calls": 0, "cmds": []}

    def _value(cmd, key, default=""):
        if key in cmd:
            i = cmd.index(key)
            if i + 1 < len(cmd):
                return cmd[i + 1]
        return default

    def _write_text(path, text):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")

    def _write_json(path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    def _fake(cmd, env=None):
        state["cmds"].append(list(cmd))
        script = Path(cmd[1]).name if len(cmd) > 1 else "unknown"
        rc = 0
        ok = True
        stdout = ""
        stderr = ""

        if script == "validate_accuracy_gate.py":
            state["gate_calls"] += 1
            out_json = _value(cmd, "--out-json")
            out_csv = _value(cmd, "--out-csv")
            stage2_prefix = _value(cmd, "--stage2-prefix")
            pass_gate = state["gate_calls"] >= int(gate_pass_attempt)
            _write_json(out_json, {"summary": {"pass": pass_gate, "failed_metrics": []}})
            _write_text(out_csv, "target,pass\nChignolin,1\n")
            _write_text(f"{stage2_prefix}.csv", "target,throughput_on\nChignolin,100.0\n")
            if not pass_gate:
                rc = 2
                ok = False
                stderr = "gate fail"

        elif script == "run_active_learning_cycle.py":
            out_prefix = _value(cmd, "--out-prefix")
            should_fail = fail_stage == "stage4_smoke" and ("stage4_smoke" in out_prefix)
            should_fail = should_fail or (fail_stage == "stage4_full" and ("stage4_full" in out_prefix))
            _write_json(f"{out_prefix}_summary.json", {"pass": (not should_fail), "summary": {}})
            if should_fail:
                rc = 3
                ok = False
                stderr = "stage4 fail"

        elif script == "run_ood_first_validation_batch.py":
            out_prefix = _value(cmd, "--out-prefix")
            should_fail = fail_stage == "stage5_smoke" and ("stage5_smoke" in out_prefix)
            should_fail = should_fail or (fail_stage == "stage5_full" and ("stage5_full" in out_prefix))
            _write_json(f"{out_prefix}_summary.json", {"pass": (not should_fail)})
            _write_text(f"{out_prefix}_pair_metrics.csv", "target,paired,rmsd_aligned_A\nHemoglobin_4HHB,1,0.1\n")
            if should_fail:
                rc = 3
                ok = False
                stderr = "stage5 fail"

        elif script == "fetch_public_structure_set.py":
            out_manifest = _value(cmd, "--out-manifest-csv")
            out_summary = _value(cmd, "--out-summary-json")
            _write_text(out_manifest, "target,path,source_kind,status\nCATH_T1,/tmp/a.pdb,pdb_or_other,downloaded\n")
            _write_json(out_summary, {"summary": {"downloaded_count": 1}})

        elif script == "curate_structure_quality.py":
            out_csv = _value(cmd, "--out-csv")
            out_json = _value(cmd, "--out-json")
            _write_text(out_csv, "target,include\nCATH_T1,1\n")
            _write_json(out_json, {"summary": {"included": 1}})

        elif script == "build_cath_noise_augmentation.py":
            out_csv = _value(cmd, "--out-csv")
            out_json = _value(cmd, "--out-json")
            should_fail = fail_stage == "stage6_smoke" and ("stage6_smoke" in out_json)
            should_fail = should_fail or (fail_stage == "stage6_full" and ("stage6_full" in out_json))
            _write_text(out_csv, "target,stable_label,unstable_label\nCATH_T1,1,0\n")
            rows_total = 0 if should_fail else 10
            _write_json(out_json, {"summary": {"rows_total": rows_total}})
            if should_fail:
                rc = 3
                ok = False
                stderr = "stage6 fail"

        elif script == "run_special_case_pipeline.py":
            out_prefix = _value(cmd, "--out-prefix")
            should_fail = fail_stage == "stage7_metal_smoke" and ("stage7_metal_smoke" in out_prefix)
            should_fail = should_fail or (fail_stage == "stage7_metal_full" and ("stage7_metal_full" in out_prefix))
            should_fail = should_fail or (fail_stage == "stage8_dna_smoke" and ("stage8_dna_smoke" in out_prefix))
            should_fail = should_fail or (fail_stage == "stage8_dna_full" and ("stage8_dna_full" in out_prefix))
            should_fail = should_fail or (
                fail_stage == "stage9_membrane_smoke" and ("stage9_membrane_smoke" in out_prefix)
            )
            should_fail = should_fail or (
                fail_stage == "stage9_membrane_full" and ("stage9_membrane_full" in out_prefix)
            )
            _write_json(
                f"{out_prefix}_summary.json",
                {
                    "pass": (not should_fail),
                    "stages": {
                        "stage_metal": {"pass": not should_fail},
                        "stage_dna": {"pass": not should_fail},
                        "stage_membrane": {"pass": not should_fail},
                    },
                },
            )
            if should_fail:
                rc = 3
                ok = False
                stderr = "special stage fail"

        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "returncode": int(rc),
            "ok": bool(ok),
            "duration_sec": 0.01,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }

    return _fake, state


def test_pipeline_gate_first_pass_then_all_stages(monkeypatch, tmp_path):
    fake_run, state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=1, fail_stage=None)
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    assert out["pass"] is True
    assert out["exit_code"] == 0
    assert out["stage1_gate"]["passed_attempt_index"] == 1
    assert out["stages"]["stage4"]["pass"] is True
    assert out["stages"]["stage5"]["pass"] is True
    assert out["stages"]["stage6"]["pass"] is True
    assert out["stages"]["stage7_metal"]["pass"] is True
    assert out["stages"]["stage8_dna"]["pass"] is True
    assert out["stages"]["stage9_membrane"]["pass"] is True
    assert Path(out["artifacts"]["summary_json"]).exists()
    assert Path(out["artifacts"]["summary_md"]).exists()
    assert Path(out["artifacts"]["steps_csv"]).exists()
    assert Path(out["artifacts"]["gate_attempts_csv"]).exists()
    assert out["stage1_gate"]["attempts_csv"] == out["artifacts"]["gate_attempts_csv"]
    assert len(state["cmds"]) == 17


def test_pipeline_gate_retries_until_attempt4(monkeypatch, tmp_path):
    fake_run, _state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=4, fail_stage=None)
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    assert out["pass"] is True
    assert out["stage1_gate"]["passed_attempt_index"] == 4
    assert len(out["stage1_gate"]["attempts"]) == 4


def test_pipeline_gate_fails_after_max_retries(monkeypatch, tmp_path):
    fake_run, _state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=999, fail_stage=None)
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path) + ["--gate-retry-max", "5"])
    out = p.run_pipeline(args)
    assert out["pass"] is False
    assert out["exit_code"] == 2
    assert out["failed_stage"] == "stage1_gate"
    assert len(out["stage1_gate"]["attempts"]) == 5


def test_pipeline_stage4_smoke_fail_stops_before_full(monkeypatch, tmp_path):
    fake_run, state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=1, fail_stage="stage4_smoke")
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    assert out["pass"] is False
    assert out["exit_code"] == 3
    assert out["failed_stage"] == "stage4_smoke"
    cmd_strs = [" ".join(cmd) for cmd in state["cmds"]]
    assert all("stage4_full" not in s for s in cmd_strs)


def test_pipeline_stage5_fail_stops_before_stage6(monkeypatch, tmp_path):
    fake_run, state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=1, fail_stage="stage5_smoke")
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    assert out["pass"] is False
    assert out["exit_code"] == 3
    assert out["failed_stage"] == "stage5_smoke"
    cmd_strs = [" ".join(cmd) for cmd in state["cmds"]]
    assert all("stage6_smoke" not in s for s in cmd_strs)


def test_pipeline_summary_schema_contains_required_fields(monkeypatch, tmp_path):
    fake_run, _state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=1, fail_stage=None)
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    required = [
        "generated_at_local",
        "date_tag",
        "run_scope",
        "pass",
        "exit_code",
        "failed_stage",
        "stage1_gate",
        "stages",
        "steps",
        "artifacts",
    ]
    for k in required:
        assert k in out
    assert "stage7_metal" in out["stages"]
    assert "stage8_dna" in out["stages"]
    assert "stage9_membrane" in out["stages"]


def test_pipeline_stage7_fail_stops_before_stage8(monkeypatch, tmp_path):
    fake_run, state = _fake_run_cmd_factory(tmp_path, gate_pass_attempt=1, fail_stage="stage7_metal_smoke")
    monkeypatch.setattr(p, "_run_cmd", fake_run)

    args = p.build_parser().parse_args(_arg_list(tmp_path))
    out = p.run_pipeline(args)
    assert out["pass"] is False
    assert out["exit_code"] == 3
    assert out["failed_stage"] == "stage7_metal_smoke"
    cmd_strs = [" ".join(cmd) for cmd in state["cmds"]]
    assert all("stage8_dna" not in s for s in cmd_strs)
