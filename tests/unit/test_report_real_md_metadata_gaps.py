import json

import pandas as pd
import pytest

from tools import report_real_md_metadata_gaps as rg


def test_report_real_md_metadata_gaps_init_from_template(tmp_path):
    template = tmp_path / "template.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "md_engine": "", "source_engine": "", "source_path": ""},
            {"target": "Trp_Cage", "md_engine": "", "source_engine": "", "source_path": ""},
        ]
    ).to_csv(template, index=False)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin"}, {"target": "Trp_Cage"}]).to_csv(manifest, index=False)
    metadata = tmp_path / "real_md_metadata.csv"

    out_json = tmp_path / "gap.json"
    payload = rg.report_real_md_metadata_gaps(
        metadata_csv=str(metadata),
        template_csv=str(template),
        manifest_csv=str(manifest),
        out_csv=str(tmp_path / "gap.csv"),
        out_json=str(out_json),
        out_md=str(tmp_path / "gap.md"),
        md_engine_regex=r"(openmm|amber|gromacs)",
        init_metadata_if_missing=True,
        strict=False,
    )
    assert metadata.exists()
    assert payload["summary"]["strict_ready"] is False
    assert payload["summary"]["total_targets"] == 2
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["strict_ready"] is False


def test_report_real_md_metadata_gaps_strict_ready(tmp_path):
    src = tmp_path / "source.npy"
    src.write_bytes(b"x")
    metadata = tmp_path / "real_md_metadata.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "md_engine": "openmm",
                "source_engine": "openmm",
                "source_path": str(src),
                "md_forcefield": "amber99sb",
                "md_water_model": "tip3p",
                "md_temperature_k": 300,
                "md_timestep_fs": 2,
                "md_steps": 1000000,
                "md_software_version": "openmm-8",
            }
        ]
    ).to_csv(metadata, index=False)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin"}]).to_csv(manifest, index=False)
    template = tmp_path / "template.csv"
    pd.DataFrame([{"target": "Chignolin"}]).to_csv(template, index=False)

    payload = rg.report_real_md_metadata_gaps(
        metadata_csv=str(metadata),
        template_csv=str(template),
        manifest_csv=str(manifest),
        out_csv=str(tmp_path / "gap.csv"),
        out_json=str(tmp_path / "gap.json"),
        out_md=str(tmp_path / "gap.md"),
        md_engine_regex=r"(openmm|amber|gromacs)",
        init_metadata_if_missing=False,
        strict=True,
    )
    assert payload["summary"]["strict_ready"] is True
    assert payload["summary"]["strict_ready_targets"] == 1


def test_report_real_md_metadata_gaps_strict_raise(tmp_path):
    metadata = tmp_path / "real_md_metadata.csv"
    pd.DataFrame([{"target": "Chignolin", "md_engine": "", "source_engine": "", "source_path": ""}]).to_csv(
        metadata, index=False
    )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin"}]).to_csv(manifest, index=False)
    template = tmp_path / "template.csv"
    pd.DataFrame([{"target": "Chignolin"}]).to_csv(template, index=False)

    with pytest.raises(RuntimeError):
        rg.report_real_md_metadata_gaps(
            metadata_csv=str(metadata),
            template_csv=str(template),
            manifest_csv=str(manifest),
            out_csv=str(tmp_path / "gap.csv"),
            out_json=str(tmp_path / "gap.json"),
            out_md=str(tmp_path / "gap.md"),
            md_engine_regex=r"(openmm|amber|gromacs)",
            init_metadata_if_missing=False,
            strict=True,
        )

