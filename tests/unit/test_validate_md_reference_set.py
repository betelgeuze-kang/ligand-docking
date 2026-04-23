import json

import numpy as np
import pandas as pd
import pytest

from tools import validate_md_reference_set as vmr


def test_validate_md_reference_set_ready_when_all_rows_valid(tmp_path):
    a = tmp_path / "chignolin.npy"
    b = tmp_path / "trp_cage.npy"
    np.save(a, np.zeros((10, 3), dtype=np.float32))
    np.save(b, np.zeros((20, 3), dtype=np.float32))

    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": str(a), "engine": "openmm", "label": "x", "frame": -1},
            {"target": "Trp_Cage", "path": str(b), "engine": "openmm", "label": "y", "frame": -1},
        ]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    payload = vmr.validate_md_reference_set(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=2,
        strict=True,
    )
    assert payload["summary"]["ready"] is True
    assert payload["summary"]["md_ok_targets"] == 2
    assert out_csv.exists()
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["ready"] is True


def test_validate_md_reference_set_not_ready_on_n_res_mismatch(tmp_path):
    a = tmp_path / "chignolin_bad.npy"
    np.save(a, np.zeros((9, 3), dtype=np.float32))
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(a), "engine": "openmm", "label": "x", "frame": -1}]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    payload = vmr.validate_md_reference_set(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=1,
        strict=False,
    )
    assert payload["summary"]["ready"] is False
    assert "Chignolin" in payload["summary"]["failed_targets"]
    fail_reasons = payload["summary"]["failed_rows"][0]["reasons"]
    assert "n_res_mismatch" in fail_reasons


def test_validate_md_reference_set_strict_raises_on_missing_file(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(tmp_path / "missing.npy"), "engine": "openmm", "label": "x"}]
    ).to_csv(manifest, index=False)

    with pytest.raises(RuntimeError):
        vmr.validate_md_reference_set(
            manifest_csv=str(manifest),
            out_json=str(tmp_path / "out.json"),
            out_csv=str(tmp_path / "out.csv"),
            md_engine_regex=r"(openmm|amber|gromacs)",
            expected_target_count=1,
            strict=True,
        )


def test_validate_md_reference_set_accepts_2bead_when_representation_is_set(tmp_path):
    a = tmp_path / "chignolin_2bead.npy"
    np.save(a, np.zeros((20, 3), dtype=np.float32))
    manifest = tmp_path / "manifest_2bead.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(a),
                "engine": "openmm",
                "label": "x",
                "frame": -1,
                "representation": "ca_sc_2bead",
            }
        ]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out_2bead.json"
    out_csv = tmp_path / "out_2bead.csv"
    payload = vmr.validate_md_reference_set(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=1,
        strict=True,
    )
    assert payload["summary"]["ready"] is True
    df = pd.read_csv(out_csv)
    assert int(df.iloc[0]["expected_n_atoms"]) == 20
    assert bool(df.iloc[0]["row_ok"]) is True


def test_validate_md_reference_set_rejects_unlabeled_2bead_shape(tmp_path):
    a = tmp_path / "chignolin_2bead_unlabeled.npy"
    np.save(a, np.zeros((20, 3), dtype=np.float32))
    manifest = tmp_path / "manifest_2bead_unlabeled.csv"
    pd.DataFrame(
        [{"target": "Chignolin", "path": str(a), "engine": "openmm", "label": "x", "frame": -1}]
    ).to_csv(manifest, index=False)

    out_json = tmp_path / "out_2bead_unlabeled.json"
    out_csv = tmp_path / "out_2bead_unlabeled.csv"
    payload = vmr.validate_md_reference_set(
        manifest_csv=str(manifest),
        out_json=str(out_json),
        out_csv=str(out_csv),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=1,
        strict=False,
    )
    assert payload["summary"]["ready"] is False
    assert "Chignolin" in payload["summary"]["failed_targets"]
    reasons = payload["summary"]["failed_rows"][0]["reasons"]
    assert "n_res_mismatch" in reasons
