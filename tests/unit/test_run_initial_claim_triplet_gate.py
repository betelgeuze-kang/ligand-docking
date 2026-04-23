import json
from pathlib import Path

from tools import run_initial_claim_triplet_gate as mod


def _arg_value(cmd, name: str) -> str:
    idx = cmd.index(name)
    return str(cmd[idx + 1])


def test_triplet_gate_passes_three_replicates(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_cmd(cmd, env=None, dry_run=False):
        if not dry_run:
            rep_tag = _arg_value(cmd, "--date-tag")
            rep_json = runs_dir / f"nightly_screening_batch_{rep_tag}.json"
            rep_json.write_text(
                json.dumps(
                    {
                        "pass": True,
                        "claim_status": {
                            "initial_claim_ready_for_allatom": True,
                            "initial_claim_failed_metrics": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
        return {"cmd": list(cmd), "cmd_str": " ".join(cmd), "dry_run": bool(dry_run), "returncode": 0, "ok": True}

    monkeypatch.setattr(mod, "_run_cmd", fake_run_cmd)
    args = mod.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-19-triplet",
            "--repeats",
            "3",
            "--mode",
            "smoke",
            "--runs-dir",
            str(runs_dir),
            "--run-ood-measured20",
            "--run-special-cases",
        ]
    )
    payload = mod.run_triplet(args)

    assert payload["summary"]["pass"] is True
    assert payload["summary"]["repeats_executed"] == 3
    assert len(payload["rows"]) == 3
    assert all(bool(r["rep_pass"]) for r in payload["rows"])


def test_triplet_gate_fail_fast_on_second_replicate(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_cmd(cmd, env=None, dry_run=False):
        if not dry_run:
            rep_tag = _arg_value(cmd, "--date-tag")
            rep_index = int(rep_tag.rsplit("_rep", 1)[-1])
            ready = rep_index != 2
            failed = 0 if rep_index != 2 else 3
            rep_json = runs_dir / f"nightly_screening_batch_{rep_tag}.json"
            rep_json.write_text(
                json.dumps(
                    {
                        "pass": True,
                        "claim_status": {
                            "initial_claim_ready_for_allatom": ready,
                            "initial_claim_failed_metrics": failed,
                        },
                    }
                ),
                encoding="utf-8",
            )
        return {"cmd": list(cmd), "cmd_str": " ".join(cmd), "dry_run": bool(dry_run), "returncode": 0, "ok": True}

    monkeypatch.setattr(mod, "_run_cmd", fake_run_cmd)
    args = mod.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-19-triplet",
            "--repeats",
            "3",
            "--mode",
            "smoke",
            "--runs-dir",
            str(runs_dir),
            "--fail-fast",
        ]
    )
    payload = mod.run_triplet(args)

    assert payload["summary"]["pass"] is False
    assert payload["summary"]["first_failed_replicate"] == 2
    assert payload["summary"]["repeats_executed"] == 2
    assert len(payload["rows"]) == 2
    assert payload["rows"][1]["rep_pass"] is False


def test_triplet_gate_claim_profile_json_applies_overrides(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    claim_profile = tmp_path / "claim_profile.json"
    claim_profile.write_text(
        json.dumps(
            {
                "profile": {
                    "claim_kinetics_agg_method": "mean",
                    "claim_pmf_pseudocount": 2.0,
                    "claim_split_replicas": 9,
                }
            }
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_run_cmd(cmd, env=None, dry_run=False):
        captured["cmd"] = list(cmd)
        return {"cmd": list(cmd), "cmd_str": " ".join(cmd), "dry_run": bool(dry_run), "returncode": 0, "ok": True}

    monkeypatch.setattr(mod, "_run_cmd", fake_run_cmd)
    args = mod.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-19-triplet",
            "--repeats",
            "1",
            "--mode",
            "smoke",
            "--runs-dir",
            str(runs_dir),
            "--claim-profile-json",
            str(claim_profile),
            "--dry-run",
        ]
    )
    payload = mod.run_triplet(args)
    assert payload["summary"]["claim_profile"]["loaded"] is True
    cmd_str = " ".join(captured["cmd"])
    assert "--claim-kinetics-agg-method mean" in cmd_str
    assert "--claim-pmf-pseudocount 2.0" in cmd_str
    assert "--claim-split-replicas 9" in cmd_str


def test_triplet_gate_uses_speed_defaults_json(monkeypatch, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    defaults = tmp_path / "speed_defaults.json"
    defaults.write_text(
        json.dumps(
            {
                "sections": {
                    "initial_claim_triplet": {
                        "speed_mode": "turbo",
                        "speed_mode_replicas": 64,
                        "speed_profile_max_replicas": 256,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    captured = {}

    def fake_run_cmd(cmd, env=None, dry_run=False):
        captured["cmd"] = list(cmd)
        return {"cmd": list(cmd), "cmd_str": " ".join(cmd), "dry_run": bool(dry_run), "returncode": 0, "ok": True}

    monkeypatch.setattr(mod, "_run_cmd", fake_run_cmd)
    args = mod.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-19-triplet",
            "--repeats",
            "1",
            "--mode",
            "smoke",
            "--runs-dir",
            str(runs_dir),
            "--speed-profile-defaults-json",
            str(defaults),
            "--speed-profile-defaults-section",
            "initial_claim_triplet",
            "--dry-run",
        ]
    )
    payload = mod.run_triplet(args)
    cmd_str = " ".join(captured["cmd"])
    assert "--speed-mode turbo" in cmd_str
    assert "--speed-mode-replicas 64" in cmd_str
    assert "--speed-profile-max-replicas 256" in cmd_str
    assert payload["summary"]["speed_profile_defaults"]["resolved"]["speed_mode"] == "turbo"
