import json

import pandas as pd

from tools.build_cath_noise_augmentation import build_cath_noise_augmentation


def _write_toy_pdb(path):
    lines = [
        "ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C",
        "ATOM      2  CA  GLY A   2      13.800  10.000  10.000  1.00 20.00           C",
        "ATOM      3  CA  SER A   3      17.600  10.000  10.000  1.00 20.00           C",
        "ATOM      4  CA  THR A   4      21.400  10.000  10.000  1.00 20.00           C",
        "ATOM      5  CA  TYR A   5      25.200  10.000  10.000  1.00 20.00           C",
        "END",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_build_cath_noise_augmentation_outputs_rows(tmp_path):
    pdb_path = tmp_path / "toy.pdb"
    _write_toy_pdb(pdb_path)

    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "CATH_TEST",
                "path": str(pdb_path),
                "status": "downloaded",
            }
        ]
    ).to_csv(manifest_csv, index=False)

    out_csv = tmp_path / "aug.csv"
    out_json = tmp_path / "aug.json"
    summary = build_cath_noise_augmentation(
        manifest_csv=str(manifest_csv),
        out_csv=str(out_csv),
        out_json=str(out_json),
        seed=7,
        variants_per_target=6,
        noise_sigmas="0.2,0.6",
        min_ca_residues=3,
    )

    assert out_csv.exists()
    assert out_json.exists()
    assert summary["rows_total"] == 6
    assert summary["targets"] == 1

    df = pd.read_csv(out_csv)
    assert len(df) == 6
    assert int(df["stable_label"].sum() + df["unstable_label"].sum()) == 6

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "summary" in payload
    assert payload["summary"]["rows_total"] == 6
