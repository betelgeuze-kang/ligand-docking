import pandas as pd
import pytest

from tools import refresh_external_eval_submission as refresh


def test_read_manifest_targets_success(tmp_path):
    fp = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "path": "/tmp/a.npy"},
            {"target": "Trp_Cage", "path": "/tmp/b.npy"},
        ]
    ).to_csv(fp, index=False)
    targets = refresh._read_manifest_targets(str(fp))
    assert targets == ["Chignolin", "Trp_Cage"]


def test_read_manifest_targets_missing_column(tmp_path):
    fp = tmp_path / "manifest.csv"
    pd.DataFrame([{"path": "/tmp/a.npy"}]).to_csv(fp, index=False)
    with pytest.raises(ValueError):
        refresh._read_manifest_targets(str(fp))


def test_extract_worst_targets_top_k(tmp_path):
    fp = tmp_path / "report.csv"
    pd.DataFrame(
        [
            {"target": "A", "avg_rmsd": 0.1},
            {"target": "B", "avg_rmsd": 0.3},
            {"target": "C", "avg_rmsd": 0.2},
        ]
    ).to_csv(fp, index=False)
    worst = refresh._extract_worst_targets(str(fp), top_k=2)
    assert worst == ["B", "C"]


def test_extract_worst_targets_missing_columns(tmp_path):
    fp = tmp_path / "report.csv"
    pd.DataFrame([{"target": "A", "rmsd": 0.1}]).to_csv(fp, index=False)
    with pytest.raises(ValueError):
        refresh._extract_worst_targets(str(fp), top_k=2)


def test_validate_baseline_target_set_ok():
    targets = list(refresh.ResearchConstants.CHALLENGES.keys())
    refresh._validate_baseline_target_set(targets)


def test_validate_baseline_target_set_mismatch():
    targets = list(refresh.ResearchConstants.CHALLENGES.keys())[:-1]
    with pytest.raises(ValueError):
        refresh._validate_baseline_target_set(targets)
