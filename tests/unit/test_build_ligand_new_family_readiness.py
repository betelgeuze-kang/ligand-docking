from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_ligand_new_family_readiness(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    template_ca2 = {
        "status": "template_not_runnable",
        "required_artifacts": {
            "core_profile_json": "config/ca2_core.json",
            "ood_profile_json": "config/ca2_ood.json",
            "target_csv": "config/ca2_target.csv",
        },
        "sets": [{"tasks": [{"task_id": "ca2_core"}]}, {"tasks": [{"task_id": "ca2_ood"}]}],
        "scaffold_status": {"ready_for_validate_only": False, "claim_ready": False},
    }
    template_pxr = {
        "status": "template_not_runnable",
        "required_artifacts": {
            "core_profile_json": "config/pxr_core.json",
            "ood_profile_json": "config/pxr_ood.json",
        },
        "sets": [{"tasks": [{"task_id": "pxr_core"}]}],
        "scaffold_status": {"ready_for_validate_only": False, "claim_ready": False},
    }
    template_transport = {
        "status": "template_not_runnable",
        "required_artifacts": {
            "aqp1_profile_json": "config/aqp1.json",
            "glut1_profile_json": "config/glut1.json",
        },
        "sets": [{"tasks": [{"task_id": "aqp1_core"}]}, {"tasks": [{"task_id": "glut1_ood"}]}],
        "scaffold_status": {"ready_for_validate_only": False, "claim_ready": False},
    }

    _write_json(config_dir / "external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json", template_ca2)
    _write_json(config_dir / "external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json", template_pxr)
    _write_json(config_dir / "external_validation_transporter_membrane_sets_v1_template.json", template_transport)

    _write_json(config_dir / "ca2_core.json", {"dry_run": True, "targets": "CA2", "run_scope": "full", "description": "ca2 core"})
    _write_json(config_dir / "ca2_ood.json", {"dry_run": True, "targets": "CA2", "run_scope": "full", "description": "ca2 ood"})
    (config_dir / "ca2_target.csv").write_text("target_id\nCA2\n", encoding="utf-8")
    _write_json(config_dir / "pxr_core.json", {"dry_run": True, "targets": "PXR", "run_scope": "full", "description": "pxr core"})
    _write_json(config_dir / "pxr_ood.json", {"dry_run": True, "targets": "PXR", "run_scope": "full", "description": "pxr ood"})
    _write_json(config_dir / "aqp1.json", {"dry_run": True, "targets": "AQP1", "run_scope": "full", "description": "aqp1"})
    _write_json(config_dir / "glut1.json", {"dry_run": True, "targets": "GLUT1", "run_scope": "full", "description": "glut1"})

    out_json = runs_dir / "ligand_new_family_readiness_current.json"
    out_csv = runs_dir / "ligand_new_family_readiness_current.csv"
    out_md = runs_dir / "ligand_new_family_readiness_current.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_ligand_new_family_readiness.py"),
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json.relative_to(tmp_path)),
            "--out-csv",
            str(out_csv.relative_to(tmp_path)),
            "--out-md",
            str(out_md.relative_to(tmp_path)),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["family_count"] == 3
    assert payload["summary"]["template_exists_count"] == 3
    assert payload["summary"]["all_profiles_dry_run_count"] == 3
    assert payload["summary"]["claim_ready_count"] == 0

    families = {row["family_id"]: row for row in payload["summary"]["families"]}
    assert families["non_kinase_enzyme_ca2"]["required_artifact_exists_count"] == 3
    assert families["non_kinase_enzyme_ca2"]["profile_count"] == 2
    assert families["transporter_membrane"]["dry_run_profile_count"] == 2

    df = pd.read_csv(out_csv)
    assert set(df["family_id"]) == {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr", "transporter_membrane"}
    assert set(df["profile_role"]) == {"core", "ood", "aqp1", "glut1"}
    assert df["profile_dry_run"].all()

    md_text = out_md.read_text(encoding="utf-8")
    assert "Ligand New-Family Readiness" in md_text
    assert "## Family Summary" in md_text
    assert "## Profile Details" in md_text
