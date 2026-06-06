import json
from pathlib import Path

import pandas as pd

from tools.gpcr_replay import build_gpcr_non_adrb2_candidate_leakage_audit as mod


def _write_inputs(tmp_path: Path, candidates: list[dict[str, object]]):
    splits = pd.DataFrame(
        [
            {"target": "EGFR_KINASE", "ligand_id": "erlotinib", "role": "fit"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "carazolol", "role": "far_ood_eval"},
        ]
    )
    reference = pd.DataFrame(
        [
            {
                "target": "EGFR_KINASE",
                "ligand_id": "erlotinib",
                "reference_binding_kcal_mol": -9.2,
                "is_binder": 1,
                "source": "fixture",
                "smiles": "CCO",
                "scaffold": "fit_scaffold",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carazolol",
                "reference_binding_kcal_mol": -10.2,
                "is_binder": 1,
                "source": "fixture",
                "smiles": "CCC",
                "scaffold": "adrb2_scaffold",
            },
        ]
    )
    candidate_df = pd.DataFrame(
        candidates,
        columns=[
            "target",
            "ligand_id",
            "target_family",
            "is_binder",
            "reference_binding_kcal_mol",
            "source",
            "smiles",
            "scaffold",
            "role",
            "curation_status",
        ],
    )
    candidates_csv = tmp_path / "candidates.csv"
    splits_csv = tmp_path / "splits.csv"
    reference_csv = tmp_path / "reference.csv"
    candidate_df.to_csv(candidates_csv, index=False)
    splits.to_csv(splits_csv, index=False)
    reference.to_csv(reference_csv, index=False)
    return candidates_csv, splits_csv, reference_csv


def _run(tmp_path: Path, candidates: list[dict[str, object]]):
    candidates_csv, splits_csv, reference_csv = _write_inputs(tmp_path, candidates)
    out_json = tmp_path / "audit.json"
    out_csv = tmp_path / "audit.csv"
    out_md = tmp_path / "audit.md"
    payload = mod.build_audit(
        candidates_csv=candidates_csv,
        base_splits_csv=splits_csv,
        base_reference_csv=reference_csv,
        out_json=out_json,
        out_csv=out_csv,
        out_md=out_md,
    )
    return payload, json.loads(out_json.read_text(encoding="utf-8")), out_csv, out_md


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "target": "DRD2_GPCR",
        "ligand_id": "dopamine",
        "target_family": "gpcr",
        "is_binder": 1,
        "reference_binding_kcal_mol": -8.1,
        "source": "fixture",
        "smiles": "NCCc1ccccc1",
        "scaffold": "new_scaffold",
        "role": "candidate_eval",
        "curation_status": "curated",
    }
    row.update(overrides)
    return row


def test_empty_candidates_emit_blocked_audit_artifacts(tmp_path: Path):
    payload, written, out_csv, out_md = _run(tmp_path, [])

    assert payload["pass"] is False
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert "candidate_csv_empty" in payload["summary"]["blockers"]
    assert written["pass"] is False
    assert out_csv.exists()
    assert out_md.exists()


def test_clean_non_adrb2_candidates_pass(tmp_path: Path):
    payload, written, _out_csv, _out_md = _run(tmp_path, [_candidate()])

    assert payload["pass"] is True
    assert payload["summary"]["status"] == "pass"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["target_overlap_count"] == 0
    assert payload["ligand_overlap_count"] == 0
    assert payload["scaffold_overlap_count"] == 0
    assert written["pass"] is True


def test_target_ligand_and_scaffold_leakage_block(tmp_path: Path):
    leaking = [
        _candidate(target="EGFR_KINASE", ligand_id="novel_a", scaffold="fresh_scaffold"),
        _candidate(target="DRD2_GPCR", ligand_id="erlotinib", scaffold="novel_b"),
        _candidate(target="HTR2A_GPCR", ligand_id="novel_c", scaffold="fit_scaffold"),
    ]
    payload, _written, _out_csv, _out_md = _run(tmp_path, leaking)

    assert payload["pass"] is False
    assert payload["target_overlap_count"] == 1
    assert payload["ligand_overlap_count"] == 1
    assert payload["scaffold_overlap_count"] == 1
    assert "target_overlap_count" in payload["summary"]["blockers"]
    assert "ligand_overlap_count" in payload["summary"]["blockers"]
    assert "scaffold_overlap_count" in payload["summary"]["blockers"]
