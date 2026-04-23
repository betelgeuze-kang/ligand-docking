import json
from pathlib import Path

import pandas as pd
import pytest

from tools import build_md_only_manifest as mdonly


def test_build_md_only_manifest_filters_engine_and_existing(tmp_path):
    p_exist_a = tmp_path / "a.npy"
    p_exist_b = tmp_path / "b.npy"
    p_exist_a.write_bytes(b"x")
    p_exist_b.write_bytes(b"y")
    p_missing = tmp_path / "missing.npy"

    input_manifest = tmp_path / "in.csv"
    pd.DataFrame(
        [
            {"target": "A", "path": str(p_exist_a), "engine": "openmm"},
            {"target": "B", "path": str(p_missing), "engine": "amber"},
            {"target": "C", "path": str(p_exist_b), "engine": "rcsb_experimental"},
        ]
    ).to_csv(input_manifest, index=False)

    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    summary = mdonly.build_md_only_manifest(
        input_manifest=str(input_manifest),
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        md_engine_regex=r"(openmm|amber|gromacs)",
        require_existing_paths=True,
        strict_target_count=None,
    )
    assert summary["total_rows_output"] == 1
    out_df = pd.read_csv(out_manifest)
    assert out_df["target"].tolist() == ["A"]
    payload = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert payload["total_rows_output"] == 1


def test_build_md_only_manifest_strict_target_count_raises(tmp_path):
    p_exist = tmp_path / "a.npy"
    p_exist.write_bytes(b"x")
    input_manifest = tmp_path / "in.csv"
    pd.DataFrame([{"target": "A", "path": str(p_exist), "engine": "openmm"}]).to_csv(
        input_manifest, index=False
    )

    with pytest.raises(ValueError):
        mdonly.build_md_only_manifest(
            input_manifest=str(input_manifest),
            out_manifest=str(tmp_path / "out.csv"),
            out_json=str(tmp_path / "out.json"),
            md_engine_regex=r"(openmm|amber|gromacs)",
            require_existing_paths=True,
            strict_target_count=2,
        )


def test_build_md_only_manifest_writes_readable_empty_csv(tmp_path):
    p_exist = tmp_path / "a.npy"
    p_exist.write_bytes(b"x")
    input_manifest = tmp_path / "in.csv"
    pd.DataFrame([{"target": "A", "path": str(p_exist), "engine": "rcsb_experimental"}]).to_csv(
        input_manifest, index=False
    )
    out_manifest = tmp_path / "out.csv"
    mdonly.build_md_only_manifest(
        input_manifest=str(input_manifest),
        out_manifest=str(out_manifest),
        out_json=str(tmp_path / "out.json"),
        md_engine_regex=r"(openmm|amber|gromacs)",
        require_existing_paths=True,
        strict_target_count=None,
    )
    out_df = pd.read_csv(out_manifest)
    assert out_df.empty
    assert set(out_df.columns) == {"target", "path", "engine"}
