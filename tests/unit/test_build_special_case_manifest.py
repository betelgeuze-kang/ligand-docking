import pandas as pd
import pytest

from tools import build_special_case_manifest as m


def test_build_special_case_manifest_emits_rows(tmp_path):
    src = tmp_path / "metal.csv"
    pd.DataFrame(
        [
            {"target": "T1", "pdb_id": "1AAA", "uniprot_id": "P1", "notes": "n1"},
            {"target": "T2", "pdb_id": "1AAB", "uniprot_id": "P2", "notes": "n2"},
        ]
    ).to_csv(src, index=False)
    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"

    args = m.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--targets",
            "T1",
            "--source-csv",
            str(src),
            "--out-manifest",
            str(out_manifest),
            "--out-json",
            str(out_json),
        ]
    )
    payload = m.run_build(args)
    assert payload["summary"]["rows_emitted"] == 1
    assert out_manifest.exists()
    assert out_json.exists()


def test_build_special_case_manifest_strict_fail_on_empty(tmp_path):
    src = tmp_path / "metal.csv"
    pd.DataFrame([{"target": "T1", "pdb_id": "1AAA", "uniprot_id": "P1"}]).to_csv(src, index=False)
    out_manifest = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"

    args = m.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--targets",
            "NOPE",
            "--source-csv",
            str(src),
            "--out-manifest",
            str(out_manifest),
            "--out-json",
            str(out_json),
            "--strict-fail",
        ]
    )
    with pytest.raises(RuntimeError):
        m.run_build(args)
