import json
from pathlib import Path

from tools import build_casp17_3d_molecular_object_metric_handoff as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _metric_contract(path: Path) -> None:
    _write_json(
        path,
        {
            "summary": {
                "metric_surface_contract_status": (
                    "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
                ),
                "required_metric_count": 11,
            },
            "rows": [{"metric_name": metric} for metric in mod.FALLBACK_REQUIRED_METRICS],
        },
    )


def _atlas_object(
    tmp_path: Path,
    protein_key: str,
    object_key: str,
    target_group: str,
    lane: str = "current_object_library",
) -> dict:
    atlas_protein = tmp_path / "atlas" / protein_key
    atlas_object = atlas_protein / object_key
    _touch(atlas_protein / "README.md")
    _write_json(atlas_protein / "protein_manifest.json", {"summary": {"protein_key": protein_key}})
    _touch(atlas_object / "README.md")
    _write_json(atlas_object / "object_manifest.json", {"summary": {"object_key": object_key}})
    row = {
        "atlas_protein_key": protein_key,
        "atlas_object_key": object_key,
        "source_lane": lane,
        "target_id": protein_key.split("_", 1)[0],
        "target_group": target_group,
        "protein_name": protein_key.split("_", 1)[1],
        "object_id": object_key,
        "object_role": object_key,
        "atlas_status": "pass",
        "atlas_protein_folder": str(atlas_protein),
        "atlas_object_folder": str(atlas_object),
        "atlas_protein_manifest": str(atlas_protein / "protein_manifest.json"),
        "atlas_object_manifest": str(atlas_object / "object_manifest.json"),
        "model_path": _touch(tmp_path / "models" / f"{object_key}.pdb", "ATOM\n"),
        "viewer_html": _touch(tmp_path / "viewers" / f"{object_key}.html"),
        "projection_svg": _touch(tmp_path / "renders" / f"{object_key}.svg"),
        "native_status": "native_accuracy_not_scored",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "source_policy": "review_only",
    }
    if lane == "massivefold_freeze_candidate":
        row.update(
            {
                "model_sha256": "model-sha",
                "top5_manifest_csv": _touch(tmp_path / "top5" / f"{object_key}.csv"),
                "top5_manifest_sha256": "top5-sha",
                "escrow_md": _touch(tmp_path / "escrow" / f"{object_key}.md"),
            }
        )
    return row


def _audit_row(row: dict, status: str = "pass") -> dict:
    return {
        "atlas_protein_key": row["atlas_protein_key"],
        "atlas_object_key": row["atlas_object_key"],
        "audit_status": status,
    }


def test_3d_molecular_object_metric_handoff_maps_object_families_and_ligand_gap(
    tmp_path: Path,
) -> None:
    atlas_json = tmp_path / "atlas.json"
    audit_json = tmp_path / "audit.json"
    metric_contract_json = tmp_path / "metric_contract.json"
    out_dir = tmp_path / "handoff"
    monomer = _atlas_object(tmp_path, "T9001_Monomer", "current_chain_A", "protein_or_monomer")
    complex_row = _atlas_object(tmp_path, "H9002_Complex", "current_chain_A", "protein_complex")
    rna = _atlas_object(
        tmp_path,
        "R9003_RNA_hybrid",
        "massivefold_model1_candidate",
        "rna_hybrid",
        lane="massivefold_freeze_candidate",
    )
    _write_json(
        atlas_json,
        {
            "summary": {
                "casp17_3d_molecular_object_atlas_status": (
                    "casp17_3d_molecular_object_atlas_ready_review_only"
                )
            },
            "rows": [monomer, complex_row, rna],
        },
    )
    _write_json(
        audit_json,
        {
            "summary": {
                "atlas_completion_audit_status": (
                    "casp17_3d_molecular_object_atlas_completion_audit_pass"
                )
            },
            "rows": [_audit_row(monomer), _audit_row(complex_row), _audit_row(rna)],
        },
    )
    _metric_contract(metric_contract_json)

    args = mod.parse_args(
        [
            "--atlas-json",
            str(atlas_json),
            "--atlas-completion-audit-json",
            str(audit_json),
            "--metric-surface-contract-json",
            str(metric_contract_json),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "handoff.json"),
            "--out-csv",
            str(tmp_path / "handoff.csv"),
            "--out-md",
            str(tmp_path / "HANDOFF.md"),
            "--out-html",
            str(tmp_path / "handoff.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["atlas_object_key"]: row for row in payload["rows"]}
    assert summary["metric_handoff_status"] == (
        "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
    )
    assert summary["object_ready_count"] == 3
    assert summary["object_blocked_count"] == 0
    assert summary["metric_requirement_count"] == 19
    assert summary["covered_required_metric_count"] == 9
    assert summary["required_metric_count"] == 11
    assert summary["missing_required_metric_count"] == 2
    assert summary["missing_required_metric_names"] == "LDDT-PLI,BiSyRMSD"
    assert summary["ligand_metric_gap_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert rows["current_chain_A"]["handoff_status"] == "ready_review_only"
    assert rows["massivefold_model1_candidate"]["metric_extension_notes"] == (
        "rna_hybrid_metric_extension_required"
    )
    assert (out_dir / "H9002_Complex" / "current_chain_A" / "METRIC_HANDOFF.md").is_file()
    assert (out_dir / "H9002_Complex" / "current_chain_A" / "metric_requirements.csv").is_file()
    assert (out_dir / "R9003_RNA_hybrid" / "massivefold_model1_candidate" / "metric_handoff_manifest.json").is_file()
    assert not list(out_dir.rglob("*.pdb"))
    assert not list(out_dir.rglob("*.cif"))
    assert "AUTHOR " not in (tmp_path / "handoff.json").read_text(encoding="utf-8")


def test_3d_molecular_object_metric_handoff_blocks_failed_atlas_audit_links(
    tmp_path: Path,
) -> None:
    atlas_json = tmp_path / "atlas.json"
    audit_json = tmp_path / "audit.json"
    metric_contract_json = tmp_path / "metric_contract.json"
    row = _atlas_object(tmp_path, "T9999_Blocked", "current_chain_A", "protein_or_monomer")
    Path(row["viewer_html"]).unlink()
    _write_json(
        atlas_json,
        {
            "summary": {
                "casp17_3d_molecular_object_atlas_status": (
                    "casp17_3d_molecular_object_atlas_ready_review_only"
                )
            },
            "rows": [row],
        },
    )
    _write_json(
        audit_json,
        {
            "summary": {"atlas_completion_audit_status": "casp17_3d_molecular_object_atlas_completion_audit_blocked"},
            "rows": [_audit_row(row, status="blocked")],
        },
    )
    _metric_contract(metric_contract_json)
    args = mod.parse_args(
        [
            "--atlas-json",
            str(atlas_json),
            "--atlas-completion-audit-json",
            str(audit_json),
            "--metric-surface-contract-json",
            str(metric_contract_json),
            "--out-dir",
            str(tmp_path / "handoff"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["metric_handoff_status"] == (
        "casp17_3d_molecular_object_metric_handoff_blocked"
    )
    assert payload["summary"]["object_blocked_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "atlas_completion_audit_not_pass" in blockers
    assert "atlas_completion_audit_row_not_pass" in blockers
    assert "viewer_html_missing" in blockers
