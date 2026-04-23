import json
from pathlib import Path

import pandas as pd
import pytest

from core.definitions import ResearchConstants
from tools import build_kinetics_equivalence_metrics as kinetics


def test_scaffold_template_all_targets(tmp_path):
    out_csv = tmp_path / "kinetics_template.csv"
    out_json = tmp_path / "kinetics_template.json"
    args = kinetics.build_parser().parse_args(
        [
            "--scaffold-template",
            "--scaffold-targets",
            "all",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = kinetics.run_build(args)

    assert payload["mode"] == "scaffold_template"
    df = pd.read_csv(out_csv)
    assert len(df) == len(ResearchConstants.CHALLENGES)
    assert {"target", "mfpt_pred", "mfpt_ref", "its_pred", "its_ref"}.issubset(df.columns)
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["target_count"] == len(ResearchConstants.CHALLENGES)


def test_build_metrics_from_input_csv(tmp_path):
    src = tmp_path / "kinetics_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "mfpt_pred": 100.0, "mfpt_ref": 100.0, "its_pred": 10.0, "its_ref": 10.0},
            {"target": "B", "mfpt_pred": 100.0, "mfpt_ref": 10.0, "its_pred": 20.0, "its_ref": 10.0},
        ]
    ).to_csv(src, index=False)

    out_csv = tmp_path / "kinetics_metrics.csv"
    out_json = tmp_path / "kinetics_metrics.json"
    args = kinetics.build_parser().parse_args(
        [
            "--input-csv",
            str(src),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = kinetics.run_build(args)

    assert payload["mode"] == "build_metrics"
    # A: 0, B: 1 => mean 0.5
    assert abs(payload["metrics"]["log10_mfpt_error"] - 0.5) < 1e-9
    # A: 0, B: 1 => mean 0.5
    assert abs(payload["metrics"]["implied_timescale_rel_error"] - 0.5) < 1e-9
    # default thresholds are strict enough that only A passes
    assert payload["summary"]["targets_pass_both"] == 1
    assert abs(payload["summary"]["pass_rate_both"] - 0.5) < 1e-9

    out_df = pd.read_csv(out_csv)
    assert len(out_df) == 2
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert "metrics" in saved
    assert "log10_mfpt_error" in saved["metrics"]


def test_fail_on_threshold_exits_nonzero(tmp_path):
    src = tmp_path / "kinetics_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "mfpt_pred": 100.0, "mfpt_ref": 10.0, "its_pred": 20.0, "its_ref": 10.0},
        ]
    ).to_csv(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        kinetics.main(
            [
                "--input-csv",
                str(src),
                "--fail-on-threshold",
                "--out-csv",
                str(tmp_path / "o.csv"),
                "--out-json",
                str(tmp_path / "o.json"),
            ]
        )
    assert exc_info.value.code == 2

