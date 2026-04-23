from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_gpcr_residual_prototype_spec(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype.json"
    out_csv = tmp_path / "prototype.csv"
    out_md = tmp_path / "prototype.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_mode"] == "shadow_only"
    assert payload["summary"]["prototype_status"] == "shadow_runtime_ready"
    assert payload["prototype"]["constraints"]["preserve_top2_binders"] is True
    assert any(row["feature_name"] == "mean_min_distance_A" for row in payload["feature_rows"])


def test_build_gpcr_residual_prototype_spec_narrow_v2(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v2.json"
    out_csv = tmp_path / "prototype_v2.csv"
    out_md = tmp_path / "prototype_v2.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "narrow_v2",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "narrow_v2"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.75
    assert payload["prototype"]["tuning"]["require_distance_above_z"] == 0.35


def test_build_gpcr_residual_prototype_spec_chembl50_v3(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v3.json"
    out_csv = tmp_path / "prototype_v3.csv"
    out_md = tmp_path / "prototype_v3.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "chembl50_v3",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "chembl50_v3"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.5
    assert payload["prototype"]["tuning"]["chembl50_abstain_on_borderline_support"] is True


def test_build_gpcr_residual_prototype_spec_chembl50_v4(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v4.json"
    out_csv = tmp_path / "prototype_v4.csv"
    out_md = tmp_path / "prototype_v4.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "chembl50_v4",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "chembl50_v4"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.35
    assert payload["prototype"]["tuning"]["core_guard_abstain_on_small_margin"] is True
