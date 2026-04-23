import json
from pathlib import Path

import pandas as pd

from tools import sweep_claim_input_profiles as mod


def _arg_value(cmd, name: str) -> str:
    idx = cmd.index(name)
    return str(cmd[idx + 1])


def test_parse_tail_clip_pairs():
    pairs = mod._parse_tail_clip_pairs("0.01:0.99,0.02:0.98")
    assert pairs == [(0.01, 0.99), (0.02, 0.98)]


def test_build_profiles_respects_max_profiles():
    args = mod.build_parser().parse_args(
        [
            "--manifest-csv",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--split-modes",
            "window_stratified,half",
            "--split-replicas-list",
            "3,5",
            "--max-profiles",
            "3",
            "--out-prefix",
            "runs/test_claim_sweep",
        ]
    )
    profiles = mod._build_profiles(args)
    assert len(profiles) == 3
    assert profiles[0]["profile_index"] == 1


def test_run_sweep_ranks_best_profile(monkeypatch, tmp_path: Path):
    out_prefix = str(tmp_path / "claim_sweep")

    def fake_run_cmd(cmd, env=None, dry_run=False):
        exe = " ".join(cmd)
        if "build_claim_inputs_from_openmm_manifest.py" in exe:
            for flag in (
                "--out-kinetics-csv",
                "--out-thermo-csv",
                "--out-experiment-csv",
                "--out-diagnostics-csv",
                "--out-json",
            ):
                p = Path(_arg_value(cmd, flag))
                p.parent.mkdir(parents=True, exist_ok=True)
                if p.suffix == ".csv":
                    if "diagnostics" in p.name:
                        pd.DataFrame([{"target": "Chignolin", "split_mode": "window_stratified"}]).to_csv(p, index=False)
                    elif "kinetics" in p.name:
                        pd.DataFrame([{"target": "Chignolin", "mfpt_pred": 1.0, "mfpt_ref": 1.0, "its_pred": 1.0, "its_ref": 1.0}]).to_csv(p, index=False)
                    elif "thermo" in p.name:
                        pd.DataFrame([{"target": "Chignolin", "deltaG_rmse_kcal_mol": 0.1, "state_population_jsd": 0.01, "pmf_1d_emd": 0.05}]).to_csv(p, index=False)
                    elif "experiment" in p.name:
                        pd.DataFrame([{"target": "Chignolin", "nmr_noe_violation_rate": 0.0, "cryoem_map_cc": 1.0, "saxs_chi2": 0.1}]).to_csv(p, index=False)
                    else:
                        pd.DataFrame([{"target": "Chignolin"}]).to_csv(p, index=False)
                else:
                    p.write_text(json.dumps({"summary": {"targets_with_diagnostics": 1, "targets_failed": 0}}), encoding="utf-8")
            djson = Path(_arg_value(cmd, "--out-diagnostics-json"))
            djson.write_text(json.dumps({"summary": {"targets_with_diagnostics": 1, "targets_failed": 0}}), encoding="utf-8")
            return {"cmd": list(cmd), "cmd_str": exe, "dry_run": False, "returncode": 0, "ok": True}

        if "run_allatom_claim_readiness.py" in exe:
            out_json = Path(_arg_value(cmd, "--out-json"))
            gate_csv = Path(_arg_value(cmd, "--gate-out-csv"))
            out_json.parent.mkdir(parents=True, exist_ok=True)
            pass_profile = "_p001_" in out_json.name
            out_json.write_text(
                json.dumps(
                    {
                        "summary": {
                            "claim_ready_for_allatom": bool(pass_profile),
                            "claim_failed_metrics": 0 if pass_profile else 2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            if pass_profile:
                gate_df = pd.DataFrame([{"metric": "deltaG_rmse_kcal_mol", "required_for_claim": True, "pass": True}])
            else:
                gate_df = pd.DataFrame([{"metric": "deltaG_rmse_kcal_mol", "required_for_claim": True, "pass": False}])
            gate_df.to_csv(gate_csv, index=False)
            return {"cmd": list(cmd), "cmd_str": exe, "dry_run": False, "returncode": 0, "ok": True}

        raise AssertionError(f"unexpected command: {exe}")

    monkeypatch.setattr(mod, "_run_cmd", fake_run_cmd)
    args = mod.build_parser().parse_args(
        [
            "--manifest-csv",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--split-modes",
            "window_stratified,half",
            "--split-replicas-list",
            "3",
            "--split-window-frames-list",
            "24",
            "--split-window-stride-list",
            "12",
            "--min-effective-frames-list",
            "8",
            "--thermo-agg-methods",
            "median",
            "--kinetics-agg-methods",
            "median",
            "--experiment-agg-methods",
            "median",
            "--trim-fractions",
            "0.10",
            "--tail-clip-pairs",
            "0.01:0.99",
            "--pmf-pseudocounts",
            "1e-8",
            "--max-profiles",
            "2",
            "--out-prefix",
            out_prefix,
        ]
    )
    payload = mod.run_sweep(args)

    assert payload["summary"]["overall_pass"] is True
    assert payload["summary"]["best_profile_tag"] == "p001"
    rows = payload["rows"]
    assert len(rows) == 2
    assert rows[0]["claim_ready_for_allatom"] is True
    assert rows[1]["claim_ready_for_allatom"] is False
