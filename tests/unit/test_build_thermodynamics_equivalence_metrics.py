import json
from pathlib import Path

import pandas as pd
import pytest

from core.definitions import ResearchConstants
from tools import build_thermodynamics_equivalence_metrics as thermo


def test_scaffold_template_all_targets(tmp_path):
    out_csv = tmp_path / "thermo_template.csv"
    out_json = tmp_path / "thermo_template.json"
    args = thermo.build_parser().parse_args(
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
    payload = thermo.run_build(args)

    assert payload["mode"] == "scaffold_template"
    df = pd.read_csv(out_csv)
    assert len(df) == len(ResearchConstants.CHALLENGES)
    assert {"target", "deltaG_rmse_kcal_mol", "state_population_jsd", "pmf_1d_emd"}.issubset(
        df.columns
    )
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["target_count"] == len(ResearchConstants.CHALLENGES)


def test_build_metrics_from_input_csv(tmp_path):
    src = tmp_path / "thermo_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "deltaG_rmse_kcal_mol": 0.2, "state_population_jsd": 0.01, "pmf_1d_emd": 0.10},
            {"target": "B", "deltaG_rmse_kcal_mol": 0.8, "state_population_jsd": 0.08, "pmf_1d_emd": 0.30},
        ]
    ).to_csv(src, index=False)

    out_csv = tmp_path / "thermo_metrics.csv"
    out_json = tmp_path / "thermo_metrics.json"
    args = thermo.build_parser().parse_args(
        [
            "--input-csv",
            str(src),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = thermo.run_build(args)

    assert payload["mode"] == "build_metrics"
    assert abs(payload["metrics"]["deltaG_rmse_kcal_mol"] - 0.5) < 1e-9
    assert abs(payload["metrics"]["state_population_jsd"] - 0.045) < 1e-9
    assert abs(payload["metrics"]["pmf_1d_emd"] - 0.2) < 1e-9
    assert payload["summary"]["targets_pass_all"] == 1
    assert abs(payload["summary"]["pass_rate_all"] - 0.5) < 1e-9

    out_df = pd.read_csv(out_csv)
    assert len(out_df) == 2
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert "metrics" in saved
    assert "deltaG_rmse_kcal_mol" in saved["metrics"]


def test_fail_on_threshold_exits_nonzero(tmp_path):
    src = tmp_path / "thermo_input.csv"
    pd.DataFrame(
        [
            {"target": "A", "deltaG_rmse_kcal_mol": 0.8, "state_population_jsd": 0.08, "pmf_1d_emd": 0.30},
        ]
    ).to_csv(src, index=False)

    with pytest.raises(SystemExit) as exc_info:
        thermo.main(
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
