import json

import pandas as pd

from tools import build_cath_diversity_split as m


def test_build_cath_diversity_split_writes_outputs(tmp_path, monkeypatch):
    domain_list_text = "\n".join(
        [
            "# comment",
            "1aaaA00 1 10 8 10 1 1 1 1 1 80 1.2",
            "1bbbA00 1 20 8 10 1 1 1 1 1 76 1.4",
            "2cccA00 2 30 8 10 1 1 1 1 1 90 2.0",
            "2dddA00 2 40 8 10 1 1 1 1 1 95 2.5",
            "3eeeA00 3 50 8 10 1 1 1 1 1 105 2.8",
            "3fffA00 3 60 8 10 1 1 1 1 1 112 3.0",
            "4gggA00 4 70 8 10 1 1 1 1 1 120 2.2",
            "4hhhA00 4 80 8 10 1 1 1 1 1 128 2.1",
        ]
    )
    s40_text = "\n".join(
        [
            "1aaaA00",
            "1bbbA00",
            "2cccA00",
            "2dddA00",
            "3eeeA00",
            "3fffA00",
            "4gggA00",
            "4hhhA00",
        ]
    )

    def _fake_download(url: str, timeout_sec: float) -> str:
        if "domain-list" in url:
            return domain_list_text
        if "S40" in url or "non-redundant" in url:
            return s40_text
        raise RuntimeError(url)

    monkeypatch.setattr(m, "_download_text", _fake_download)

    out_sources = tmp_path / "cath_sources.csv"
    out_split = tmp_path / "cath_split.csv"
    out_summary = tmp_path / "cath_summary.json"
    summary = m.build_cath_diversity_split(
        out_sources_csv=str(out_sources),
        out_split_csv=str(out_split),
        out_summary_json=str(out_summary),
        target_count=8,
        train_ratio=0.6,
        val_ratio=0.2,
        seed=42,
        cath_domain_list_url="https://example/domain-list.txt",
        cath_s40_url="https://example/S40.list",
        timeout_sec=3.0,
        use_s40_filter=True,
        allow_duplicate_pdb=False,
    )

    assert out_sources.exists()
    assert out_split.exists()
    assert out_summary.exists()
    assert summary["counts"]["selected_rows"] == 8
    assert summary["counts"]["unique_pdb_ids"] == 8

    src_df = pd.read_csv(out_sources)
    split_df = pd.read_csv(out_split)
    assert src_df["target"].nunique() == 8
    assert split_df["target"].nunique() == 8
    assert set(split_df["split"].unique()).issubset({"train", "val", "holdout"})
    assert src_df["pdb_id"].nunique() == 8

    payload = json.loads(out_summary.read_text(encoding="utf-8"))
    assert "counts" in payload
    assert "outputs" in payload
