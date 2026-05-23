from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_external_evidence_crosscheck as mod


ROOT = Path(__file__).resolve().parents[2]


def _activity(value: str = "100.0") -> dict[str, object]:
    return {
        "molecule_chembl_id": "CHEMBL411729",
        "target_chembl_id": "CHEMBL2535",
        "target_organism": "Homo sapiens",
        "standard_type": "IC50",
        "standard_value": value,
        "standard_units": "nM",
        "standard_relation": "=",
        "pchembl_value": "7.00",
    }


def _pubmed(count: int) -> dict[str, object]:
    return {"esearchresult": {"count": str(count), "idlist": [str(idx) for idx in range(count)]}}


def _bindingdb(count: int) -> dict[str, object]:
    return {"getLindsByUniprotsResponse": {"affinities": [{} for _ in range(count)]}}


def test_build_transporter_external_evidence_crosscheck_blocks_negative_promotion() -> None:
    payload = mod.build_payload(
        {"activities": []},
        {
            "activities": [
                _activity("20000.0"),
                {
                    "target_organism": "Homo sapiens",
                    "standard_type": "EC50",
                    "standard_value": "3300.0",
                    "standard_units": "nM",
                },
                {"activity_comment": "Not Active"},
            ]
        },
        {"activities": [_activity("100.0"), _activity("4100.0")]},
        {"activities": [_activity("10900.0")]},
        {"activities": []},
        _bindingdb(0),
        _bindingdb(12),
        _pubmed(8),
        _pubmed(3),
        _pubmed(2),
        _pubmed(10),
        {
            "result": {
                "23123479": {"title": "AQP1 negative source context"},
                "27078104": {"title": "GLUT1 cytochalasin B structure context"},
            }
        },
        {"citation": [{"title": "GLUT1 4PYP structure"}]},
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["crosscheck_ready"] is True
    assert summary["aqp1_uniprot_accession"] == "P29972"
    assert summary["glut1_uniprot_accession"] == "P11166"
    assert summary["aqp1_bindingdb_affinity_count"] == 0
    assert summary["aqp1_target_chembl_exact_activity_count"] == 3
    assert summary["aqp1_target_chembl_quantitative_activity_count"] == 2
    assert summary["aqp1_target_chembl_functional_quantitative_count"] == 2
    assert summary["aqp1_target_chembl_direct_binding_count"] == 0
    assert summary["aqp1_target_chembl_unquantified_not_active_count"] == 1
    assert summary["glut1_bindingdb_affinity_count"] == 12
    assert summary["glut1_positive_exact_activity_count"] == 3
    assert summary["direct_negative_quantitative_row_found_count"] == 0
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is False
    assert rows[0]["target_id"] == "AQP1"
    assert rows[0]["evidence_role"] == "target_wide_functional_activity_inventory"
    assert rows[0]["chembl_direct_binding_activity_count"] == 0
    assert rows[0]["interpretation"] == "exact_human_functional_activity_present_no_direct_binding_kcal"
    assert rows[1]["chembl_exact_activity_count"] == 0
    assert rows[1]["interpretation"] == "review_only_literature_context_no_exact_quantitative_target_pair"
    assert rows[3]["target_id"] == "GLUT1"
    assert rows[3]["candidate"] == "cytochalasin B"
    assert rows[3]["best_ic50_nm"] == "100"


def test_build_transporter_external_evidence_crosscheck_cli(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    fixtures = {
        "aqp1.json": {"activities": []},
        "aqp1_target.json": {"activities": [_activity("20000.0")]},
        "cyto.json": {"activities": [_activity("100.0")]},
        "wzb117.json": {"activities": [_activity("10900.0")]},
        "stf31.json": {"activities": []},
        "bdb_aqp1.json": _bindingdb(0),
        "bdb_glut1.json": _bindingdb(5),
        "pmid_snp.json": _pubmed(8),
        "pmid_tea.json": _pubmed(2),
        "pmid_dmso.json": _pubmed(1),
        "pmid_glut1.json": _pubmed(4),
        "summaries.json": {"result": {"23123479": {"title": "AQP1"}, "27078104": {"title": "GLUT1"}}},
        "rcsb.json": {"citation": [{"title": "4PYP"}]},
    }
    for name, payload in fixtures.items():
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path

    out_json = tmp_path / "crosscheck.json"
    out_csv = tmp_path / "crosscheck.csv"
    out_md = tmp_path / "crosscheck.md"
    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_external_evidence_crosscheck.py",
            "--aqp1-chembl-activity-json",
            str(paths["aqp1.json"]),
            "--aqp1-chembl-target-activity-json",
            str(paths["aqp1_target.json"]),
            "--glut1-cyto-activity-json",
            str(paths["cyto.json"]),
            "--glut1-wzb117-activity-json",
            str(paths["wzb117.json"]),
            "--glut1-stf31-activity-json",
            str(paths["stf31.json"]),
            "--bindingdb-aqp1-json",
            str(paths["bdb_aqp1.json"]),
            "--bindingdb-glut1-json",
            str(paths["bdb_glut1.json"]),
            "--pubmed-aqp1-snp-json",
            str(paths["pmid_snp.json"]),
            "--pubmed-aqp1-tea-json",
            str(paths["pmid_tea.json"]),
            "--pubmed-aqp1-dmso-json",
            str(paths["pmid_dmso.json"]),
            "--pubmed-glut1-json",
            str(paths["pmid_glut1.json"]),
            "--pubmed-key-summaries-json",
            str(paths["summaries.json"]),
            "--rcsb-4pyp-json",
            str(paths["rcsb.json"]),
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
    assert payload["summary"]["current_decision"] == "keep_transporter_negative_slots_review_only"
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter External Evidence Crosscheck")
