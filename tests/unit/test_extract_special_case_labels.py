import pandas as pd

from tools import extract_special_case_labels as x


def test_extract_special_case_labels_uses_explicit_values(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "domain": "dna",
                "target": "DNA_T1",
                "protein_dna_contact_f1": 0.91,
                "base_stacking_order_error": 0.09,
                "phosphate_contact_recall": 0.9,
                "backbone_break_rate": 0.002,
                "overflow_flag": 0,
                "neighbor_saturated": 0,
            }
        ]
    ).to_csv(manifest, index=False)
    out_csv = tmp_path / "labels.csv"
    out_json = tmp_path / "labels.json"

    args = x.build_parser().parse_args(
        [
            "--domain",
            "dna",
            "--manifest-csv",
            str(manifest),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = x.run_extract(args)
    assert payload["summary"]["targets_total"] == 1
    assert payload["summary"]["overflow_events_count"] == 0
    df = pd.read_csv(out_csv)
    assert float(df.iloc[0]["protein_dna_contact_f1"]) == 0.91


def test_extract_special_case_labels_overflow_count(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"domain": "metal", "target": "M1", "overflow_flag": 1, "neighbor_saturated": 0},
            {"domain": "metal", "target": "M2", "overflow_flag": 0, "neighbor_saturated": 1},
        ]
    ).to_csv(manifest, index=False)
    out_csv = tmp_path / "labels.csv"
    out_json = tmp_path / "labels.json"
    args = x.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--manifest-csv",
            str(manifest),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ]
    )
    payload = x.run_extract(args)
    assert payload["summary"]["overflow_events_count"] == 2
