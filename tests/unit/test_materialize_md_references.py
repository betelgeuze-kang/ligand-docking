import json

import numpy as np
import pandas as pd
import pytest

from tools import materialize_md_references as mmr


def test_materialize_md_references_writes_canonical_files(tmp_path):
    src_a = tmp_path / "src_a.npy"
    src_b = tmp_path / "src_b.npy"
    np.save(src_a, np.zeros((10, 3), dtype=np.float32))
    np.save(src_b, np.zeros((20, 3), dtype=np.float32))

    template = tmp_path / "template.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": str(tmp_path / "dst/chig.npy"), "engine": "openmm", "label": "t1"},
            {"target": "Trp_Cage", "path": str(tmp_path / "dst/trp.npy"), "engine": "openmm", "label": "t2"},
        ]
    ).to_csv(template, index=False)

    source = tmp_path / "source.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": str(src_a), "engine": "rcsb", "label": "s1"},
            {"target": "Trp_Cage", "path": str(src_b), "engine": "ldi", "label": "s2"},
        ]
    ).to_csv(source, index=False)

    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    summary = mmr.materialize_md_references(
        template_manifest=str(template),
        source_manifest=str(source),
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        engine_policy="template",
        label_policy="source",
        strict_target_count=2,
    )

    assert summary["rows_written"] == 2
    out_df = pd.read_csv(out_manifest)
    assert out_df["engine"].tolist() == ["openmm", "openmm"]
    assert out_df["label"].tolist() == ["s1", "s2"]
    for p in out_df["path"].tolist():
        arr = np.load(p)
        assert arr.shape[1] == 3
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["targets_written"] == 2


def test_materialize_md_references_source_policy(tmp_path):
    src_a = tmp_path / "src_a.npy"
    np.save(src_a, np.zeros((10, 3), dtype=np.float32))
    template = tmp_path / "template.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(tmp_path / "dst/chig.npy"), "engine": "openmm", "label": "t1"}]
    ).to_csv(template, index=False)
    source = tmp_path / "source.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(src_a), "engine": "amber", "label": "s1"}]
    ).to_csv(source, index=False)

    out_manifest = tmp_path / "out.csv"
    mmr.materialize_md_references(
        template_manifest=str(template),
        source_manifest=str(source),
        out_manifest=str(out_manifest),
        out_json=str(tmp_path / "out.json"),
        engine_policy="source",
        label_policy="template",
        strict_target_count=1,
    )
    out_df = pd.read_csv(out_manifest)
    assert out_df["engine"].tolist() == ["amber"]
    assert out_df["label"].tolist() == ["t1"]


def test_materialize_md_references_strict_target_count_raises(tmp_path):
    src_a = tmp_path / "src_a.npy"
    np.save(src_a, np.zeros((10, 3), dtype=np.float32))
    template = tmp_path / "template.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": str(tmp_path / "dst/chig.npy"), "engine": "openmm", "label": "t1"},
            {"target": "Trp_Cage", "path": str(tmp_path / "dst/trp.npy"), "engine": "openmm", "label": "t2"},
        ]
    ).to_csv(template, index=False)
    source = tmp_path / "source.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(src_a), "engine": "amber", "label": "s1"}]
    ).to_csv(source, index=False)

    with pytest.raises(ValueError):
        mmr.materialize_md_references(
            template_manifest=str(template),
            source_manifest=str(source),
            out_manifest=str(tmp_path / "out.csv"),
            out_json=str(tmp_path / "out.json"),
            strict_target_count=2,
        )
