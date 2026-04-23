import json
from pathlib import Path

import pandas as pd

from tools import build_live_unseen_hardcase_manifest as mod


def test_build_manifest_picks_failed_targets(tmp_path):
    live_manifest = tmp_path / "live_manifest.csv"
    npz_a = tmp_path / "a.npz"
    npz_b = tmp_path / "b.npz"
    npz_a.write_bytes(b"x")
    npz_b.write_bytes(b"x")
    pd.DataFrame(
        [
            {"target": "Live_kinase_alpha", "split": "train", "output_npz": str(npz_a)},
            {"target": "Live_ligase_beta", "split": "train", "output_npz": str(npz_b)},
        ]
    ).to_csv(live_manifest, index=False)

    fail_csv = tmp_path / "fail.csv"
    pd.DataFrame(
        [
            {"target": "Live_auto_kinase_alpha", "source_target": "Auto_kinase_alpha", "fail_count": 5},
            {"target": "Live_auto_other", "source_target": "Auto_other", "fail_count": 2},
        ]
    ).to_csv(fail_csv, index=False)

    out_manifest = tmp_path / "hardcase.csv"
    out_summary = tmp_path / "hardcase.json"
    summary = mod.build_manifest(
        live_manifest_csv=str(live_manifest),
        failure_breakdown_csv=str(fail_csv),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        min_fail_count=1.0,
        max_targets=1,
    )
    assert summary["pass"] is True
    assert summary["selected_targets_count"] == 1
    assert summary["selected_targets"][0] == "Live_kinase_alpha"
    out_df = pd.read_csv(out_manifest)
    assert sorted(out_df["target"].unique().tolist()) == ["Live_kinase_alpha"]


def test_build_manifest_fallback_all_targets_when_no_match(tmp_path):
    live_manifest = tmp_path / "live_manifest.csv"
    npz_a = tmp_path / "a.npz"
    npz_a.write_bytes(b"x")
    pd.DataFrame(
        [
            {"target": "Live_kinase_alpha", "split": "train", "output_npz": str(npz_a)},
        ]
    ).to_csv(live_manifest, index=False)

    fail_csv = tmp_path / "fail.csv"
    pd.DataFrame(
        [
            {"target": "Live_auto_unmatched", "source_target": "Auto_unmatched", "fail_count": 3},
        ]
    ).to_csv(fail_csv, index=False)

    out_manifest = tmp_path / "hardcase.csv"
    out_summary = tmp_path / "hardcase.json"
    summary = mod.build_manifest(
        live_manifest_csv=str(live_manifest),
        failure_breakdown_csv=str(fail_csv),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        fallback_all_targets=True,
    )
    assert summary["pass"] is True
    assert summary["used_fallback_all_targets"] is True
    out_df = pd.read_csv(out_manifest)
    assert out_df.shape[0] == 1

    saved = json.loads(Path(out_summary).read_text(encoding="utf-8"))
    assert saved["used_fallback_all_targets"] is True
