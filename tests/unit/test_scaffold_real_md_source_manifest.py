import json

import pandas as pd

from tools import scaffold_real_md_source_manifest as srm


def test_scaffold_real_md_source_manifest_from_source_manifest(tmp_path):
    src = tmp_path / "src.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": "/tmp/a.npy", "engine": "openmm", "label": "A"},
            {"target": "Trp_Cage", "path": "/tmp/b.npy", "engine": "amber", "label": "B"},
        ]
    ).to_csv(src, index=False)
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"

    payload = srm.scaffold_real_md_source_manifest(
        out_csv=str(out_csv),
        out_json=str(out_json),
        targets_spec="all",
        source_manifest=str(src),
        path_pattern="",
        engine_default="",
        frame_default=-1,
        include_md_config_fields=True,
        overwrite=True,
    )
    assert payload["summary"]["target_count"] == 2
    df = pd.read_csv(out_csv)
    assert "md_forcefield" in df.columns
    assert str(df.iloc[0]["engine"]) == "openmm"
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["target_count"] == 2


def test_scaffold_real_md_source_manifest_with_pattern(tmp_path):
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    payload = srm.scaffold_real_md_source_manifest(
        out_csv=str(out_csv),
        out_json=str(out_json),
        targets_spec="Chignolin,Trp_Cage",
        source_manifest=None,
        path_pattern="/data/md/{slug}.npy",
        engine_default="openmm",
        frame_default=-1,
        include_md_config_fields=False,
        overwrite=True,
    )
    assert payload["summary"]["target_count"] == 2
    df = pd.read_csv(out_csv)
    assert "md_forcefield" not in df.columns
    assert str(df[df["target"] == "Chignolin"]["path"].iloc[0]).endswith("/chignolin.npy")
    assert str(df[df["target"] == "Trp_Cage"]["engine"].iloc[0]) == "openmm"

