import json
from pathlib import Path

import pandas as pd
import pytest

from core.definitions import ResearchConstants
from tools import build_experiment_consistency_metrics as exp


def test_scaffold_template_all_targets(tmp_path):
    out_csv = tmp_path / "exp_template.csv"
    out_json = tmp_path / "exp_template.json"
    args = exp.build_parser().parse_args(
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
    payload = exp.run_build(args)

    assert payload["mode"] == "scaffold_template"
    df = pd.read_csv(out_csv)
    assert len(df) == len(ResearchConstants.CHALLENGES)
    assert {"target", "nmr_noe_violation_rate", "cryoem_map_cc", "saxs_chi2"}.issubset(df.columns)
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["target_count"] == len(ResearchConstants.CHALLENGES)


def test_build_metrics_from_input_csv(tmp_path):
    src = tmp_path / "exp_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "nmr_noe_violation_rate": 0.05, "cryoem_map_cc": 0.90, "saxs_chi2": 1.00},
            {"target": "B", "nmr_noe_violation_rate": 0.20, "cryoem_map_cc": 0.70, "saxs_chi2": 2.00},
        ]
    ).to_csv(src, index=False)

    out_csv = tmp_path / "exp_metrics.csv"
    out_json = tmp_path / "exp_metrics.json"
    args = exp.build_parser().parse_args(
        [
            "--input-csv",
            str(src),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = exp.run_build(args)

    assert payload["mode"] == "build_metrics"
    assert abs(payload["metrics"]["nmr_noe_violation_rate"] - 0.125) < 1e-9
    assert abs(payload["metrics"]["cryoem_map_cc"] - 0.8) < 1e-9
    assert abs(payload["metrics"]["saxs_chi2"] - 1.5) < 1e-9
    assert payload["summary"]["targets_pass_all"] == 1
    assert abs(payload["summary"]["pass_rate_all"] - 0.5) < 1e-9

    out_df = pd.read_csv(out_csv)
    assert len(out_df) == 2
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert "metrics" in saved
    assert "nmr_noe_violation_rate" in saved["metrics"]


def test_fail_on_threshold_exits_nonzero(tmp_path):
    src = tmp_path / "exp_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "nmr_noe_violation_rate": 0.20, "cryoem_map_cc": 0.70, "saxs_chi2": 2.00},
        ]
    ).to_csv(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        exp.main(
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
