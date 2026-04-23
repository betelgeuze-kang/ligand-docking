import json

import numpy as np
import pandas as pd
import pytest

from tools import validate_md_provenance as vmp


def test_validate_md_provenance_ready_with_md_source(tmp_path):
    p = tmp_path / "ref.npy"
    s = tmp_path / "src.npy"
    np.save(p, np.zeros((10, 3), dtype=np.float32))
    np.save(s, np.zeros((10, 3), dtype=np.float32))

    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(p),
                "engine": "openmm",
                "source_engine": "openmm",
                "source_path": str(s),
            }
        ]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    payload = vmp.validate_md_provenance(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        engine_regex=r"(openmm|amber|gromacs)",
        source_engine_regex=r"(openmm|amber|gromacs)",
        require_source_engine=True,
        require_source_path=True,
        expected_target_count=1,
        strict=True,
    )
    assert payload["summary"]["ready"] is True
    assert out_csv.exists()
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["ready"] is True


def test_validate_md_provenance_fail_on_non_md_source_engine(tmp_path):
    p = tmp_path / "ref.npy"
    np.save(p, np.zeros((10, 3), dtype=np.float32))

    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(p),
                "engine": "openmm_proxy_external",
                "source_engine": "rcsb_experimental",
            }
        ]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    payload = vmp.validate_md_provenance(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        engine_regex=r"(openmm|amber|gromacs)",
        source_engine_regex=r"(openmm|amber|gromacs)",
        require_source_engine=True,
        require_source_path=False,
        expected_target_count=1,
        strict=False,
    )
    assert payload["summary"]["ready"] is False
    assert "Chignolin" in payload["summary"]["failed_targets"]


def test_validate_md_provenance_strict_raises(tmp_path):
    p = tmp_path / "ref.npy"
    np.save(p, np.zeros((10, 3), dtype=np.float32))

    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(p), "engine": "openmm_proxy_external", "source_engine": ""}]
    ).to_csv(manifest, index=False)

    with pytest.raises(RuntimeError):
        vmp.validate_md_provenance(
            manifest_csv=str(manifest),
            out_json=str(tmp_path / "out.json"),
            out_csv=str(tmp_path / "out.csv"),
            engine_regex=r"(openmm|amber|gromacs)",
            source_engine_regex=r"(openmm|amber|gromacs)",
            require_source_engine=True,
            require_source_path=False,
            expected_target_count=1,
            strict=True,
        )

