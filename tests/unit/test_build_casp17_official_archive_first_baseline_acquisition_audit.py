import json
import tarfile
from pathlib import Path

from tools import build_casp17_official_archive_first_baseline_acquisition_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_tar(path: Path, members: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.parent / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    for name, content in members.items():
        member_path = staging / name
        member_path.parent.mkdir(parents=True, exist_ok=True)
        member_path.write_text(content, encoding="utf-8")
    with tarfile.open(path, "w:gz") as archive:
        for member_path in sorted(staging.rglob("*")):
            if member_path.is_file():
                archive.add(member_path, arcname=str(member_path.relative_to(staging)))


def test_builds_first_baseline_acquisition_audit(tmp_path):
    baseline_folder = tmp_path / "baseline" / "001_casp16_t1212"
    _write_tar(
        baseline_folder / "downloads" / "T1212.tar.gz",
        {
            "T1212/T1212TS001_1": "MODEL        1\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n",
            "T1212/T1212TS001_2": "MODEL        2\nATOM      1  CA  ALA A   1       1.0   1.0   1.0\nEND\n",
        },
    )
    native = baseline_folder / "native" / "9B0L.pdb"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text(
        "HEADER    TEST\n"
        "ATOM      1  CA  ALA A   1       0.0   0.0   0.0\n"
        "HETATM    2  C1  LIG A   2       1.0   1.0   1.0\n"
        "END\n",
        encoding="utf-8",
    )
    baseline_json = tmp_path / "baseline.json"
    _write_json(
        baseline_json,
        {
            "summary": {"official_archive_baseline_lane_status": "official_archive_baseline_lane_ready"},
            "rows": [
                {
                    "baseline_candidate_id": "official_archive_baseline_001",
                    "source_candidate_id": "official_archive_source_001",
                    "competition": "CASP16",
                    "target_id": "T1212",
                    "native_pdb_code": "9b0l",
                    "baseline_folder": str(baseline_folder),
                    "prediction_tarball_url": "https://predictioncenter.example/T1212.tar.gz",
                    "native_structure_file_url": "https://files.example/9B0L.pdb",
                    "competitive_proof_eligible": False,
                    "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                    "other_team_model_policy": "official_archive_models_are_baseline_only",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--baseline-json",
            str(baseline_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
            "--out-dir",
            str(tmp_path / "audit_dir"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_first_baseline_acquisition_audit_status"] == (
        "official_archive_first_baseline_acquired"
    )
    assert summary["first_target_id"] == "T1212"
    assert summary["first_native_pdb_code"] == "9B0L"
    assert summary["ready_artifact_count"] == 2
    assert summary["blocked_artifact_count"] == 0
    assert summary["tarball_model_count"] == 2
    assert summary["native_pdb_atom_count"] == 2
    assert summary["competitive_proof_eligible"] is False
    assert summary["strict_blind_intake_policy"] == "do_not_import_as_internal_prediction"
    assert payload["rows"][0]["artifact_kind"] == "prediction_tarball"
    assert payload["rows"][1]["artifact_kind"] == "native_pdb"
    assert (tmp_path / "audit_dir" / "first_baseline_acquisition_audit.json").exists()
    assert "Claim Boundary" in (tmp_path / "AUDIT.md").read_text(encoding="utf-8")
