import json
from pathlib import Path

import pandas as pd
import pytest

from core.definitions import ResearchConstants
from tools import scaffold_md_manifest as sm


def test_scaffold_md_manifest_defaults_all_targets(tmp_path):
    out_manifest = tmp_path / "md_template.csv"
    out_json = tmp_path / "md_template.json"
    md_dir = tmp_path / "md_refs"

    summary = sm.scaffold_md_manifest(
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        md_dir=str(md_dir),
    )

    df = pd.read_csv(out_manifest)
    expected = list(ResearchConstants.CHALLENGES.keys())
    assert df["target"].tolist() == expected
    assert df["engine"].tolist() == ["openmm"] * len(expected)
    assert set(df.columns) == {"target", "path", "engine", "label", "frame"}
    assert summary["target_count"] == len(expected)
    assert summary["missing_paths"] == len(expected)


def test_scaffold_md_manifest_uses_source_manifest_target_order(tmp_path):
    src = tmp_path / "source.csv"
    pd.DataFrame(
        [
            {"target": "Trp_Cage", "path": "a", "engine": "x"},
            {"target": "Chignolin", "path": "b", "engine": "y"},
            {"target": "Trp_Cage", "path": "c", "engine": "z"},
        ]
    ).to_csv(src, index=False)

    out_manifest = tmp_path / "md_template.csv"
    out_json = tmp_path / "md_template.json"
    sm.scaffold_md_manifest(
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        md_dir=str(tmp_path / "refs"),
        source_manifest=str(src),
        engine="gromacs",
        label_suffix="prod",
    )

    df = pd.read_csv(out_manifest)
    assert df["target"].tolist() == ["Trp_Cage", "Chignolin"]
    assert df["engine"].tolist() == ["gromacs", "gromacs"]
    assert df["label"].tolist() == ["Trp_Cage_prod", "Chignolin_prod"]
    payload = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert payload["target_count"] == 2


def test_scaffold_md_manifest_strict_existing_paths_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sm.scaffold_md_manifest(
            out_manifest=str(tmp_path / "md_template.csv"),
            out_json=str(tmp_path / "md_template.json"),
            md_dir=str(tmp_path / "missing_refs"),
            targets_spec="Chignolin",
            strict_existing_paths=True,
        )
