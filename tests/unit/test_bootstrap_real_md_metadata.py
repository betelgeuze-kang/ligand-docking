import json

import pandas as pd

from tools import bootstrap_real_md_metadata as brm


def test_bootstrap_real_md_metadata_fills_missing_fields(tmp_path):
    base = tmp_path / "base.csv"
    src = tmp_path / "src.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "md_engine": "", "source_engine": "", "source_path": "", "notes": ""},
            {"target": "Trp_Cage", "md_engine": "", "source_engine": "", "source_path": "", "notes": ""},
        ]
    ).to_csv(base, index=False)
    pd.DataFrame(
        [
            {"target": "Chignolin", "engine": "openmm_proxy_external", "path": "/tmp/ch.npy", "label": "ch"},
            {"target": "Trp_Cage", "engine": "openmm_proxy_external", "path": "/tmp/tc.npy", "label": "tc"},
        ]
    ).to_csv(src, index=False)

    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    payload = brm.bootstrap_real_md_metadata(
        base_metadata_csv=str(base),
        source_manifest_csv=str(src),
        out_csv=str(out_csv),
        out_json=str(out_json),
        md_engine_from="engine",
        source_engine_from="engine",
        source_path_from="path",
        source_label_from="label",
        note_tag="NOT_REAL_MD",
        overwrite_existing_nonempty=False,
    )
    assert payload["summary"]["updated_target_count"] == 2
    df = pd.read_csv(out_csv)
    assert str(df.iloc[0]["md_engine"]) == "openmm_proxy_external"
    assert str(df.iloc[0]["source_engine"]) == "openmm_proxy_external"
    assert str(df.iloc[0]["source_path"]) == "/tmp/ch.npy"
    assert "NOT_REAL_MD" in str(df.iloc[0]["notes"])
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["updated_target_count"] == 2


def test_bootstrap_real_md_metadata_does_not_overwrite_by_default(tmp_path):
    base = tmp_path / "base.csv"
    src = tmp_path / "src.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "md_engine": "amber", "source_engine": "amber", "source_path": "/a", "notes": ""}]
    ).to_csv(base, index=False)
    pd.DataFrame([{"target": "Chignolin", "engine": "openmm", "path": "/b", "label": "x"}]).to_csv(src, index=False)

    out_csv = tmp_path / "out.csv"
    brm.bootstrap_real_md_metadata(
        base_metadata_csv=str(base),
        source_manifest_csv=str(src),
        out_csv=str(out_csv),
        out_json=str(tmp_path / "out.json"),
        md_engine_from="engine",
        source_engine_from="engine",
        source_path_from="path",
        source_label_from="label",
        note_tag="TAG",
        overwrite_existing_nonempty=False,
    )
    df = pd.read_csv(out_csv)
    assert str(df.iloc[0]["md_engine"]) == "amber"
    assert str(df.iloc[0]["source_engine"]) == "amber"
    assert str(df.iloc[0]["source_path"]) == "/a"

