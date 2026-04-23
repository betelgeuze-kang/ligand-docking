import json

import pandas as pd
import pytest

from tools import prepare_real_md_manifest as prm


def test_prepare_real_md_manifest_generates_template_and_fails_readiness(tmp_path):
    in_manifest = tmp_path / "input.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": str(tmp_path / "a.npy"), "engine": "rcsb_experimental", "label": "A"},
            {"target": "Trp_Cage", "path": str(tmp_path / "b.npy"), "engine": "rcsb_experimental", "label": "B"},
        ]
    ).to_csv(in_manifest, index=False)
    (tmp_path / "a.npy").write_bytes(b"x")
    (tmp_path / "b.npy").write_bytes(b"y")

    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    template_csv = tmp_path / "template.csv"
    payload = prm.prepare_real_md_manifest(
        input_manifest=str(in_manifest),
        metadata_csv=str(tmp_path / "missing_meta.csv"),
        template_csv=str(template_csv),
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        engine_regex=r"(openmm|amber|gromacs)",
        write_template=True,
        require_existing_source_path=True,
        expected_target_count=2,
        strict=False,
    )
    assert payload["summary"]["ready"] is False
    assert len(payload["summary"]["missing_metadata_targets"]) == 2
    assert template_csv.exists()
    assert out_manifest.exists()
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["ready"] is False


def test_prepare_real_md_manifest_ready_with_metadata(tmp_path):
    src = tmp_path / "source.npy"
    src.write_bytes(b"z")
    ref = tmp_path / "ref.npy"
    ref.write_bytes(b"r")

    in_manifest = tmp_path / "input.csv"
    pd.DataFrame([{"target": "Chignolin", "path": str(ref), "engine": "legacy"}]).to_csv(in_manifest, index=False)

    meta = tmp_path / "meta.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "md_engine": "openmm",
                "source_engine": "openmm",
                "source_path": str(src),
                "md_forcefield": "amber99sb",
            }
        ]
    ).to_csv(meta, index=False)

    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    payload = prm.prepare_real_md_manifest(
        input_manifest=str(in_manifest),
        metadata_csv=str(meta),
        template_csv=str(tmp_path / "template.csv"),
        out_manifest=str(out_manifest),
        out_json=str(out_json),
        engine_regex=r"(openmm|amber|gromacs)",
        write_template=True,
        require_existing_source_path=True,
        expected_target_count=1,
        strict=True,
    )
    assert payload["summary"]["ready"] is True
    df = pd.read_csv(out_manifest)
    assert df.iloc[0]["engine"] == "openmm"
    assert df.iloc[0]["source_engine"] == "openmm"


def test_prepare_real_md_manifest_strict_raises_when_not_ready(tmp_path):
    in_manifest = tmp_path / "input.csv"
    pd.DataFrame([{"target": "Chignolin", "path": str(tmp_path / "a.npy"), "engine": "legacy"}]).to_csv(
        in_manifest, index=False
    )
    (tmp_path / "a.npy").write_bytes(b"x")

    with pytest.raises(RuntimeError):
        prm.prepare_real_md_manifest(
            input_manifest=str(in_manifest),
            metadata_csv=str(tmp_path / "missing.csv"),
            template_csv=str(tmp_path / "template.csv"),
            out_manifest=str(tmp_path / "out.csv"),
            out_json=str(tmp_path / "out.json"),
            engine_regex=r"(openmm|amber|gromacs)",
            write_template=True,
            require_existing_source_path=True,
            expected_target_count=1,
            strict=True,
        )

