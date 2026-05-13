from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_negative_candidate_harvest as mod


ROOT = Path(__file__).resolve().parents[2]


def _activity(
    target: str,
    molecule: str,
    *,
    comment: str = "",
    standard_type: str = "Kd",
    relation: str = "",
    value: str = "",
    units: str = "nM",
    validity: str = "",
) -> dict[str, object]:
    return {
        "target_chembl_id": target,
        "target_organism": "Homo sapiens",
        "molecule_chembl_id": molecule,
        "molecule_pref_name": None,
        "canonical_smiles": "CCO",
        "document_chembl_id": "CHEMBL_DOC",
        "document_year": 2020,
        "assay_chembl_id": "CHEMBL_ASSAY",
        "assay_description": "Inhibition against target",
        "activity_comment": comment or None,
        "standard_type": standard_type,
        "standard_relation": relation or None,
        "standard_value": value or None,
        "standard_units": units,
        "data_validity_comment": validity or None,
    }


def test_build_transporter_negative_candidate_harvest_prioritizes_glut1_lower_bounds() -> None:
    payload = mod.build_payload(
        {
            "activities": [
                _activity("CHEMBL4523210", "CHEMBL_AQP1_NOT_ACTIVE", comment="Not Active", standard_type="Inhibition"),
                _activity(
                    "CHEMBL4523210",
                    "CHEMBL_AQP1_WEAK_OUTLIER",
                    standard_type="IC50",
                    relation="=",
                    value="17000000",
                    validity="Outside typical range",
                ),
            ]
        },
        {
            "activities": [
                _activity("CHEMBL2535", "CHEMBL_GLUT1_WEAK_1", relation=">", value="100000"),
                _activity("CHEMBL2535", "CHEMBL_GLUT1_WEAK_2", relation=">", value="100000"),
                _activity("CHEMBL2535", "CHEMBL_GLUT1_INACTIVE", comment="Not Active", standard_type="Inhibition"),
            ]
        },
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["candidate_harvest_ready"] is True
    assert summary["aqp1_candidate_review_row_count"] == 2
    assert summary["glut1_candidate_review_row_count"] == 3
    assert summary["aqp1_quantitative_lower_bound_candidate_count"] == 0
    assert summary["glut1_quantitative_lower_bound_candidate_count"] == 2
    assert summary["potential_aqp1_negative_slot_cover_count"] == 0
    assert summary["potential_glut1_negative_slot_cover_count"] == 2
    assert summary["unreviewed_direct_negative_quantitative_candidate_count"] == 2
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is False
    assert summary["candidate_harvest_status"] == "glut1_quantitative_candidate_review_available_aqp1_still_blocked"
    assert rows[0]["target_id"] == "AQP1"
    assert rows[0]["evidence_class"] == "chembl_not_active_nonquantitative"
    assert any(row["evidence_class"] == "chembl_quantitative_weak_or_no_binding_lower_bound" for row in rows)
    assert all(row["authoritative_negative_apply_allowed"] is False for row in rows)


def test_build_transporter_negative_candidate_harvest_cli(tmp_path: Path) -> None:
    aqp1_json = tmp_path / "aqp1.json"
    glut1_json = tmp_path / "glut1.json"
    out_json = tmp_path / "harvest.json"
    out_csv = tmp_path / "harvest.csv"
    out_md = tmp_path / "harvest.md"
    aqp1_json.write_text(
        json.dumps({"activities": [_activity("CHEMBL4523210", "CHEMBL_AQP1_NOT_ACTIVE", comment="Not Active")]}),
        encoding="utf-8",
    )
    glut1_json.write_text(
        json.dumps({"activities": [_activity("CHEMBL2535", "CHEMBL_GLUT1_WEAK", relation=">", value="100000")]}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_negative_candidate_harvest.py",
            "--aqp1-target-activity-json",
            str(aqp1_json),
            "--glut1-target-activity-json",
            str(glut1_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["candidate_harvest_ready"] is True
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter Negative Candidate Harvest")
