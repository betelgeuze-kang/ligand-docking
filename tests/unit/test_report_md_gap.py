import json
from pathlib import Path

import pandas as pd

from tools import report_md_gap as gap


def test_report_md_gap_not_ready_when_md_only_incomplete(tmp_path):
    p1 = tmp_path / "a.npy"
    p1.write_bytes(b"x")

    accuracy_csv = tmp_path / "accuracy.csv"
    pd.DataFrame(
        [
            {
                "target": "A",
                "avg_rmsd": 1.0,
                "avg_rmsd_aligned": 0.5,
                "avg_rmsd_vs_native": 0.8,
                "avg_rmsd_vs_native_aligned": 0.4,
                "reference_engine": "openmm",
            }
        ]
    ).to_csv(accuracy_csv, index=False)

    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "A", "path": str(p1), "engine": "openmm"},
            {"target": "B", "path": str(tmp_path / "missing.npy"), "engine": "openmm"},
        ]
    ).to_csv(manifest_csv, index=False)

    md_only_csv = tmp_path / "md_only.csv"
    pd.DataFrame([{"target": "A", "path": str(p1), "engine": "openmm"}]).to_csv(md_only_csv, index=False)

    out_json = tmp_path / "gap.json"
    payload = gap.build_gap_report(
        accuracy_csv=str(accuracy_csv),
        manifest_csv=str(manifest_csv),
        md_only_manifest_csv=str(md_only_csv),
        baseline_status_json=None,
        out_json=str(out_json),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=2,
    )
    assert payload["status"]["real_md_comparison_ready"] is False
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["status"]["real_md_comparison_ready"] is False


def test_report_md_gap_ready_when_md_only_complete(tmp_path):
    p1 = tmp_path / "a.npy"
    p2 = tmp_path / "b.npy"
    p1.write_bytes(b"x")
    p2.write_bytes(b"y")

    accuracy_csv = tmp_path / "accuracy.csv"
    pd.DataFrame(
        [
            {"target": "A", "avg_rmsd": 1.0, "reference_engine": "openmm"},
            {"target": "B", "avg_rmsd": 2.0, "reference_engine": "amber"},
        ]
    ).to_csv(accuracy_csv, index=False)

    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "A", "path": str(p1), "engine": "openmm"},
            {"target": "B", "path": str(p2), "engine": "amber"},
        ]
    ).to_csv(manifest_csv, index=False)

    md_only_csv = tmp_path / "md_only.csv"
    pd.DataFrame(
        [
            {"target": "A", "path": str(p1), "engine": "openmm"},
            {"target": "B", "path": str(p2), "engine": "amber"},
        ]
    ).to_csv(md_only_csv, index=False)

    payload = gap.build_gap_report(
        accuracy_csv=str(accuracy_csv),
        manifest_csv=str(manifest_csv),
        md_only_manifest_csv=str(md_only_csv),
        baseline_status_json=None,
        out_json=str(tmp_path / "gap.json"),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=2,
    )
    assert payload["status"]["real_md_comparison_ready"] is True


def test_report_md_gap_handles_empty_md_only_csv(tmp_path):
    accuracy_csv = tmp_path / "accuracy.csv"
    pd.DataFrame([{"target": "A", "avg_rmsd": 1.0, "reference_engine": "openmm"}]).to_csv(
        accuracy_csv, index=False
    )
    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "A", "path": str(tmp_path / "a.npy"), "engine": "openmm"}]).to_csv(
        manifest_csv, index=False
    )
    # Intentionally write empty file.
    md_only_csv = tmp_path / "md_only.csv"
    md_only_csv.write_text("", encoding="utf-8")

    payload = gap.build_gap_report(
        accuracy_csv=str(accuracy_csv),
        manifest_csv=str(manifest_csv),
        md_only_manifest_csv=str(md_only_csv),
        baseline_status_json=None,
        out_json=str(tmp_path / "gap.json"),
        md_engine_regex=r"(openmm|amber|gromacs)",
        expected_target_count=1,
    )
    assert payload["status"]["real_md_comparison_ready"] is False
