import pandas as pd

from tools import build_active_learning_priority_targets as mod


def test_build_priority_targets_merges_ood_and_oversize(tmp_path):
    ood_csv = tmp_path / "ood.csv"
    oversize_csv = tmp_path / "oversize.csv"
    out_csv = tmp_path / "priority.csv"
    out_json = tmp_path / "priority.json"

    pd.DataFrame(
        [
            {"target": "A", "paired": 1, "rmsd_aligned_A": 10.0},
            {"target": "B", "paired": 1, "rmsd_aligned_A": 9.0},
            {"target": "C", "paired": 1, "rmsd_aligned_A": 2.0},
        ]
    ).to_csv(ood_csv, index=False)
    pd.DataFrame(
        [
            {"source_target": "D", "ca_count": 900},
            {"source_target": "E", "ca_count": 700},
        ]
    ).to_csv(oversize_csv, index=False)

    payload = mod.build_priority_targets(
        targets="A,B,D,E",
        ood_pair_csv=str(ood_csv),
        ood_min_rmsd=8.0,
        ood_topk=2,
        oversize_breakdown_csv=str(oversize_csv),
        oversize_topk=2,
        oversize_target_col="source_target",
        out_csv=str(out_csv),
        out_json=str(out_json),
    )

    assert out_csv.exists()
    assert out_json.exists()
    assert payload["summary"]["priority_targets_count"] == 4
    assert payload["summary"]["ood_selected"] == 2
    assert payload["summary"]["oversize_selected"] == 2
